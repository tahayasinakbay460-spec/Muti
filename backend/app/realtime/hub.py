"""
Yayın merkezleri (hub):
  - RoomHub → bir odadaki herkese anlık mesaj gönderir (sohbet, hediye, koltuklar).
  - UserHub → tek bir kişiye, hangi ekranda olursa olsun anlık mesaj gönderir (özel mesaj bildirimi).

Her kullanıcı odaya girince sunucuyla arasında açık bir hat (WebSocket) kurulur.
Hub, "hangi odada hangi hatlar açık" listesini tutar. Bir olay olduğunda
(sohbet mesajı, hediye, koltuk değişimi) `publish` çağrılır ve o odadaki
herkese aynı mesaj gider.

Gönderilen her mesajın biçimi:
    { "event": "chat:message", "payload": { ... } }

DEMO KISAYOLU: Bağlantılar bu sürecin belleğinde durur. Birden fazla sunucu
çalışınca A sunucusundaki kullanıcı B sunucusundakine mesaj ulaştıramaz.
Canlıda `publish` mesajı Redis pub/sub kanalına bırakacak, her sunucu o kanalı
dinleyip kendi bağlantılarına `_deliver_local` ile dağıtacak. Bu yüzden iki
fonksiyon şimdiden ayrı yazıldı.
"""
import asyncio
import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Yavaş/kopmuş bir istemci diğerlerini bekletmesin: bu sürede gönderemezsek bağlantıyı düşeriz.
SEND_TIMEOUT_SECONDS = 5


class RoomHub:
    def __init__(self) -> None:
        # oda id → { o odaya bu sunucudan bağlı WebSocket → bağlantının sahibi (kullanıcı id) }
        # Sahibini de tutuyoruz ki odadan atılan birinin bağlantılarını bulup kapatabilelim.
        self._connections: dict[int, dict[WebSocket, int]] = {}

    def add(self, room_id: int, websocket: WebSocket, user_id: int) -> None:
        self._connections.setdefault(room_id, {})[websocket] = user_id

    def remove(self, room_id: int, websocket: WebSocket) -> None:
        sockets = self._connections.get(room_id)
        if not sockets:
            return
        sockets.pop(websocket, None)
        if not sockets:
            # Boş odaların kaydını tutmayalım, bellek şişmesin.
            del self._connections[room_id]

    async def disconnect_user(self, room_id: int, user_id: int, code: int) -> None:
        """
        Bir kullanıcının bu odadaki bütün bağlantılarını kapatır (odadan atma).
        Redis'e geçişte bu da bir pub/sub mesajı olacak; her sunucu kendi bağlantılarını kapatacak.
        """
        sockets = [ws for ws, owner in self._connections.get(room_id, {}).items() if owner == user_id]
        for websocket in sockets:
            self.remove(room_id, websocket)
            try:
                await websocket.close(code=code)
            except Exception:
                logger.debug("WebSocket already closed")

    async def disconnect_room(self, room_id: int, code: int) -> None:
        """Odadaki herkesin bağlantısını kapatır (oda kapatıldı)."""
        for websocket in list(self._connections.get(room_id, {})):
            self.remove(room_id, websocket)
            try:
                await websocket.close(code=code)
            except Exception:
                logger.debug("WebSocket already closed")

    async def send_to_user(self, room_id: int, user_id: int, event: str, payload: dict) -> None:
        """
        Olayı yalnızca odadaki TEK bir kişiye gönderir (koltuk daveti, sesli görüşme sinyali).
        Redis'e geçişte bu da pub/sub üzerinden "şu odadaki şu kişiye" diye dağıtılacak.
        """
        sockets = [ws for ws, owner in self._connections.get(room_id, {}).items() if owner == user_id]
        if not sockets:
            return
        message = json.dumps({"event": event, "payload": payload}, ensure_ascii=False, default=str)
        results = await asyncio.gather(*(_send(ws, message) for ws in sockets))
        for websocket, delivered in zip(sockets, results):
            if not delivered:
                self.remove(room_id, websocket)

    async def publish(self, room_id: int, event: str, payload: dict) -> None:
        """Bir olayı odadaki herkese duyurur. Servisler ve router'lar bunu çağırır."""
        # JSON'a bir kez çeviriyoruz, herkese aynı yazıyı gönderiyoruz.
        message = json.dumps({"event": event, "payload": payload}, ensure_ascii=False, default=str)
        # Redis'e geçişte burası: `await redis.publish(f"room:{room_id}", message)` olacak.
        await self._deliver_local(room_id, message)

    async def _deliver_local(self, room_id: int, message: str) -> None:
        """Mesajı BU sunucuya bağlı olanlara dağıtır."""
        sockets = list(self._connections.get(room_id, {}))
        if not sockets:
            return
        # Hepsine aynı anda gönder (sırayla beklemek yerine).
        results = await asyncio.gather(*(_send(ws, message) for ws in sockets))
        for websocket, delivered in zip(sockets, results):
            if not delivered:
                self.remove(room_id, websocket)


class UserHub:
    """
    Kişiye özel kanal. Kullanıcı giriş yapmış olduğu sürece (hangi ekranda olursa olsun)
    sunucuyla arasında bir hat açık durur: /ws/me. Özel mesaj gelince buradan haber verilir.

    Aynı kişi birden fazla cihaz/sekmeden bağlı olabilir; mesaj hepsine gider.
    DEMO KISAYOLU: RoomHub gibi bellek içi; canlıda Redis pub/sub ile sunucular arası dağıtılacak.
    """

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}

    def add(self, user_id: int, websocket: WebSocket) -> None:
        self._connections.setdefault(user_id, set()).add(websocket)

    def remove(self, user_id: int, websocket: WebSocket) -> None:
        sockets = self._connections.get(user_id)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            del self._connections[user_id]

    async def publish(self, user_id: int, event: str, payload: dict) -> None:
        """Olayı kişinin açık olan bütün bağlantılarına gönderir. Bağlı değilse hiçbir şey olmaz."""
        sockets = list(self._connections.get(user_id, ()))
        if not sockets:
            return
        message = json.dumps({"event": event, "payload": payload}, ensure_ascii=False, default=str)
        results = await asyncio.gather(*(_send(ws, message) for ws in sockets))
        for websocket, delivered in zip(sockets, results):
            if not delivered:
                self.remove(user_id, websocket)


async def _send(websocket: WebSocket, message: str) -> bool:
    try:
        await asyncio.wait_for(websocket.send_text(message), SEND_TIMEOUT_SECONDS)
        return True
    except Exception:
        # Bağlantı kopmuş ya da çok yavaş. Sessizce listeden çıkarılacak.
        logger.debug("WebSocket send failed, dropping connection")
        return False


# Uygulamanın kullandığı tek hub'lar.
room_hub = RoomHub()
user_hub = UserHub()
