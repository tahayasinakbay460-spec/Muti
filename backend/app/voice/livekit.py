"""
LiveKit ses sağlayıcısı (SFU).

LiveKit açık kaynaklı (Apache 2.0) bir medya sunucusudur: kendi sunucumuza kurulabilir
ya da LiveKit Cloud'dan hazır alınabilir; ikisinde de bu kod aynıdır. Konuşmacı sesini
bir kez gönderir, sunucu herkese dağıtır. Kalabalık odalar için mesh yerine bu kullanılır.

NASIL ÇALIŞIR?
  1. join_info: kişiye bizim imzaladığımız kısa ömürlü bir token veririz. Token'ın
     içinde "hangi odaya girebilir, konuşabilir mi" yazar; LiveKit buna uyar.
  2. Koltuklar değişince (sync_publishers) LiveKit'in yönetim API'sini çağırıp kişinin
     konuşma iznini açar/kapatırız. Mikrofonu engellenen ya da koltuktan inen birinin
     sesi böylece SUNUCU tarafında kesilir; istemci hile yapsa da duyulmaz.
  3. Atılan kişi ses odasından çıkarılır, kapanan odanın ses odası silinir.

Yönetim API'si çağrıları başarısız olursa (LiveKit geçici olarak ulaşılamaz) oda işlemleri
bozulmasın diye hata yalnızca loglanır.

DURUM: LiveKit sunucusuyla henüz denenmedi (bkz. GECMIS.md). Token biçimi testle doğrulanıyor.
"""
import logging
import time

import httpx
import jwt

from app.voice.base import VoiceJoinInfo, VoiceProvider

logger = logging.getLogger(__name__)

TOKEN_TTL_SECONDS = 6 * 60 * 60
API_TIMEOUT_SECONDS = 5


def livekit_room_name(room_id: int) -> str:
    return f"room-{room_id}"


class LiveKitVoiceProvider(VoiceProvider):
    name = "livekit"

    def __init__(self, url: str, api_key: str, api_secret: str) -> None:
        if not (url and api_key and api_secret):
            raise RuntimeError("VOICE_PROVIDER=livekit için LIVEKIT_URL, LIVEKIT_API_KEY ve LIVEKIT_API_SECRET gerekli.")
        self.url = url                      # istemcinin bağlanacağı adres: wss://ses.ornek.com
        # Yönetim API'si aynı adreste HTTP üzerinden çalışır.
        self.api_url = url.replace("wss://", "https://").replace("ws://", "http://").rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        # oda → en son izin verdiğimiz konuşmacılar. Yalnızca değişenler için API çağırırız.
        # DEMO KISAYOLU: bellek içi; çok sunuculu kurulumda Redis'e taşınmalı.
        self._publishers: dict[int, set[int]] = {}

    def _token(self, identity: str, grant: dict, name: str | None = None, ttl: int = TOKEN_TTL_SECONDS) -> str:
        now = int(time.time())
        claims = {"iss": self.api_key, "sub": identity, "nbf": now, "exp": now + ttl, "video": grant}
        if name:
            claims["name"] = name
        return jwt.encode(claims, self.api_secret, algorithm="HS256")

    async def join_info(self, room_id: int, user_id: int, display_name: str, can_publish: bool) -> VoiceJoinInfo:
        token = self._token(
            identity=str(user_id),
            name=display_name,
            grant={
                "room": livekit_room_name(room_id), "roomJoin": True,
                "canPublish": can_publish, "canSubscribe": True, "canPublishData": False,
            },
        )
        return VoiceJoinInfo(provider=self.name, can_publish=can_publish, url=self.url, token=token)

    async def _call(self, method: str, room_id: int, body: dict) -> None:
        """LiveKit yönetim API'si (Twirp: JSON gövdeli POST)."""
        room = livekit_room_name(room_id)
        admin_token = self._token("muti-server", {"room": room, "roomAdmin": True, "roomCreate": True}, ttl=60)
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{self.api_url}/twirp/livekit.RoomService/{method}",
                    json={"room": room, **body},
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
            # 404: kişi henüz ses odasına bağlanmamış; bağlandığında token'ındaki izin geçerli olur.
            if response.status_code not in (200, 404):
                logger.warning("LiveKit %s failed: %s %s", method, response.status_code, response.text[:200])
        except httpx.HTTPError as error:
            logger.warning("LiveKit %s unreachable: %s", method, error)

    async def sync_publishers(self, room_id: int, publisher_ids: set[int]) -> None:
        previous = self._publishers.get(room_id, set())
        self._publishers[room_id] = set(publisher_ids)
        for user_id in publisher_ids ^ previous:   # yalnızca durumu değişenler
            await self._call("UpdateParticipant", room_id, {
                "identity": str(user_id),
                "permission": {"canPublish": user_id in publisher_ids, "canSubscribe": True},
            })

    async def remove_participant(self, room_id: int, user_id: int) -> None:
        await self._call("RemoveParticipant", room_id, {"identity": str(user_id)})

    async def close_room(self, room_id: int) -> None:
        self._publishers.pop(room_id, None)
        await self._call("DeleteRoom", room_id, {})
