"""
Agora ses sağlayıcısı (ücretli bulut hizmeti, SFU).

Agora, sesi dünya genelindeki kendi sunucuları üzerinden dağıtır: konuşmacı sesini bir kez
gönderir, Agora odadaki herkese ulaştırır. Mesh'in iki sorununu birden çözer:
  - Kalabalık oda: konuşmacının interneti dinleyici sayısından etkilenmez.
  - Sıkı ağlar (şirket, bazı mobil operatörler): Agora'nın kendi aktarıcıları vardır,
    ayrıca TURN sunucusu kurmamız gerekmez.
Ücreti dakika başınadır (ayda 10.000 dakika ücretsiz); fiyat için Agora'nın sitesine bakılır.

NASIL ÇALIŞIR?
  1. join_info: kişiye bizim imzaladığımız bir token veririz (AccessToken2, "007" ile başlar).
     Token'da "hangi kanal (oda), hangi kullanıcı, konuşabilir mi" yazar; Agora buna uyar.
     İmza App Certificate ile atılır. Certificate yalnızca sunucuda durur, tarayıcıya gitmez.
  2. Koltuğa oturan kişi konuşma izinli yeni bir token ister (bkz. js/voice/agora.js).
     Koltuktan inen kişinin elindeki token süresi dolana kadar geçerli kalır. Bu yüzden
     mesh'teki gibi dinleyiciler de koltukta olmayanın sesini kendi taraflarında çalmaz.
  3. Atılan kişi ve kapatılan oda Agora'nın REST API'siyle sesten de çıkarılır. Bunun için
     Agora konsolundaki "Customer ID / Customer Secret" gerekir; girilmemişse bu adım atlanır
     (kişi odadan yine atılır, yalnızca ses bağlantısı token süresi dolana kadar açık kalabilir).

Token biçimi Agora'nın resmî kodundan (github.com/AgoraIO/Tools, DynamicKey/python3)
sadeleştirilerek yazıldı: yalnızca ses (RTC) için gereken kısım.
"""
import base64
import hmac
import logging
import secrets
import struct
import time
import zlib
from hashlib import sha256

import httpx

from app.voice.base import VoiceJoinInfo, VoiceProvider

logger = logging.getLogger(__name__)

TOKEN_TTL_SECONDS = 60 * 60          # bitmeden önce istemci kendisi yeniler
API_URL = "https://api.agora.io/dev/v1/kicking-rule"
API_TIMEOUT_SECONDS = 5
KICK_MINUTES = 60                    # atılan kişi elindeki token ile bu süre sese giremez

# Token içindeki sabit numaralar (Agora'nın belirlediği değerler)
_SERVICE_RTC = 1
_PRIVILEGE_JOIN = 1
_PRIVILEGE_PUBLISH_AUDIO = 2


def agora_channel_name(room_id: int) -> str:
    return f"room-{room_id}"


# Agora token'ı ikili (binary) bir paket: sayılar küçük uçlu (little-endian), metinler
# önce 2 baytlık uzunluk sonra içerik olarak yazılır.
def _uint16(value: int) -> bytes:
    return struct.pack("<H", value)


def _uint32(value: int) -> bytes:
    return struct.pack("<I", value)


def _string(value: bytes) -> bytes:
    return _uint16(len(value)) + value


def build_rtc_token(
    app_id: str, app_certificate: str, channel: str, uid: int, can_publish: bool,
    ttl: int = TOKEN_TTL_SECONDS, issued_at: int | None = None, salt: int | None = None,
) -> str:
    """
    Agora AccessToken2 üretir. `issued_at` ve `salt` yalnızca testte sabitlenir.
    Süreler "üretildiği andan itibaren kaç saniye" olarak yazılır.
    """
    issued_at = issued_at or int(time.time())
    salt = salt or secrets.randbelow(99_999_999) + 1    # her token'da farklı rastgele sayı

    privileges = {_PRIVILEGE_JOIN: ttl}
    if can_publish:
        privileges[_PRIVILEGE_PUBLISH_AUDIO] = ttl
    service = _uint16(_SERVICE_RTC) + _uint16(len(privileges))
    for key in sorted(privileges):
        service += _uint16(key) + _uint32(privileges[key])
    service += _string(channel.encode()) + _string(str(uid).encode())

    signing_info = (
        _string(app_id.encode()) + _uint32(issued_at) + _uint32(ttl) + _uint32(salt)
        + _uint16(1) + service       # 1 = içinde tek hizmet (RTC) var
    )
    # İmza anahtarı: certificate, üretim zamanı ve tuz ile iki kez HMAC'lenir
    key = hmac.new(_uint32(issued_at), app_certificate.encode(), sha256).digest()
    key = hmac.new(_uint32(salt), key, sha256).digest()
    signature = hmac.new(key, signing_info, sha256).digest()
    return "007" + base64.b64encode(zlib.compress(_string(signature) + signing_info)).decode()


class AgoraVoiceProvider(VoiceProvider):
    name = "agora"

    def __init__(
        self, app_id: str, app_certificate: str, customer_id: str = "", customer_secret: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not (app_id and app_certificate):
            raise RuntimeError("VOICE_PROVIDER=agora için AGORA_APP_ID ve AGORA_APP_CERTIFICATE gerekli.")
        self.app_id = app_id
        self.app_certificate = app_certificate
        self.customer_id = customer_id
        self.customer_secret = customer_secret
        self._transport = transport      # testte sahte HTTP; normalde None (gerçek internet)

    async def join_info(self, room_id: int, user_id: int, display_name: str, can_publish: bool) -> VoiceJoinInfo:
        channel = agora_channel_name(room_id)
        token = build_rtc_token(self.app_id, self.app_certificate, channel, user_id, can_publish)
        return VoiceJoinInfo(
            provider=self.name, can_publish=can_publish, app_id=self.app_id, channel=channel, token=token,
        )

    async def _kick(self, room_id: int, user_id: int | None) -> None:
        """
        Agora'nın "kanaldan çıkarma kuralı" API'si. user_id yoksa kanaldaki herkes çıkarılır.
        Agora'ya ulaşılamazsa oda işlemi bozulmasın diye hata yalnızca loglanır.
        """
        if not (self.customer_id and self.customer_secret):
            return
        body = {
            "appid": self.app_id, "cname": agora_channel_name(room_id),
            "time": KICK_MINUTES, "privileges": ["join_channel"],
        }
        if user_id is not None:
            body["uid"] = user_id
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT_SECONDS, transport=self._transport) as client:
                response = await client.post(API_URL, json=body, auth=(self.customer_id, self.customer_secret))
            if response.status_code != 200:
                logger.warning("Agora kick failed: %s %s", response.status_code, response.text[:200])
        except httpx.HTTPError as error:
            logger.warning("Agora unreachable: %s", error)

    async def remove_participant(self, room_id: int, user_id: int) -> None:
        await self._kick(room_id, user_id)

    async def close_room(self, room_id: int) -> None:
        await self._kick(room_id, None)
