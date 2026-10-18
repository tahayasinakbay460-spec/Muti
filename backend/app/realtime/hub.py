"""
Oda yayın merkezi (hub): bir odadaki herkese anlık mesaj gönderir.

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
        # oda id → o odaya bu sunucudan bağlı WebSocket'ler
        self._connections: dict[int, set[WebSocket]] = {}

    def add(self, room_id: int, websocket: WebSocket) -> None:
        self._connections.setdefault(room_id, set()).add(websocket)

    def remove(self, room_id: int, websocket: WebSocket) -> None:
        sockets = self._connections.get(room_id)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            # Boş odaların kaydını tutmayalım, bellek şişmesin.
            del self._connections[room_id]

    async def publish(self, room_id: int, event: str, payload: dict) -> None:
        """Bir olayı odadaki herkese duyurur. Servisler ve router'lar bunu çağırır."""
        # JSON'a bir kez çeviriyoruz, herkese aynı yazıyı gönderiyoruz.
        message = json.dumps({"event": event, "payload": payload}, ensure_ascii=False, default=str)
        # Redis'e geçişte burası: `await redis.publish(f"room:{room_id}", message)` olacak.
        await self._deliver_local(room_id, message)

    async def _deliver_local(self, room_id: int, message: str) -> None:
        """Mesajı BU sunucuya bağlı olanlara dağıtır."""
        sockets = list(self._connections.get(room_id, ()))
        if not sockets:
            return
        # Hepsine aynı anda gönder (sırayla beklemek yerine).
        results = await asyncio.gather(*(self._send(ws, message) for ws in sockets))
        for websocket, delivered in zip(sockets, results):
            if not delivered:
                self.remove(room_id, websocket)

    @staticmethod
    async def _send(websocket: WebSocket, message: str) -> bool:
        try:
            await asyncio.wait_for(websocket.send_text(message), SEND_TIMEOUT_SECONDS)
            return True
        except Exception:
            # Bağlantı kopmuş ya da çok yavaş. Sessizce listeden çıkarılacak.
            logger.debug("WebSocket send failed, dropping connection")
            return False


# Uygulamanın kullandığı tek hub.
room_hub = RoomHub()
