"""
Kişiye özel WebSocket: kullanıcı giriş yaptığı sürece açık kalan hat.

Adres:  ws://sunucu/ws/me?token=<access_token>

Oda WebSocket'inden farkı: oda hattı yalnızca o odadayken açıktır; bu hat ise
uygulama açık olduğu sürece açıktır. Özel mesaj gibi "nerede olursan ol sana
ulaşması gereken" olaylar buradan gelir.

İstemci bu hatta `ping` gönderir (birkaç dakikada bir); sunucu bununla kişiyi "çevrimiçi" sayar.
Bir de birebir aramada (mesh) tarayıcılar arası bağlantı mesajı `call:signal` gönderilir.
Asıl işlemler (mesaj gönderme, aramayı açma) REST ile yapılır.
"""
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.database import SessionLocal
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.models import User
from app.realtime import events
from app.realtime.hub import user_hub
from app.realtime.state import room_state
from app.services import call_service
from app.realtime.room_socket import RateLimiter

router = APIRouter()


@router.websocket("/ws/me")
async def user_socket(websocket: WebSocket, token: str = "") -> None:
    await websocket.accept()
    try:
        user_id = decode_access_token(token)
    except AppError:
        await websocket.close(code=events.CLOSE_UNAUTHORIZED)
        return

    async with SessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None or not user.is_active:
            await websocket.close(code=events.CLOSE_UNAUTHORIZED)
            return

    user_hub.add(user_id, websocket)
    await room_state.touch_presence(user_id)
    # Bağlantı kurulurken onlarca küçük mesaj gider; sınır yalnızca kötüye kullanımı keser.
    signal_limiter = RateLimiter(limit=300, period=10)
    try:
        while True:
            raw = await websocket.receive_text()
            # Gelen her mesaj "buradayım" demektir.
            await room_state.touch_presence(user_id)
            try:
                message = json.loads(raw)
                event = message.get("event")
            except (ValueError, AttributeError):
                message, event = {}, None
            if event == events.PING:
                continue
            if event == events.CALL_SIGNAL and signal_limiter.allow():
                try:
                    await call_service.relay_signal(user_id, events.CallSignalIn.model_validate(message.get("payload")))
                except ValidationError:
                    pass
                continue
            await websocket.send_text(json.dumps({
                "event": events.ERROR, "payload": {"code": "unknown_event", "detail": "Bilinmeyen olay."},
            }))
    except WebSocketDisconnect:
        pass
    finally:
        user_hub.remove(user_id, websocket)
