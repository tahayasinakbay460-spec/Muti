"""
Kişiye özel WebSocket: kullanıcı giriş yaptığı sürece açık kalan hat.

Adres:  ws://sunucu/ws/me?token=<access_token>

Oda WebSocket'inden farkı: oda hattı yalnızca o odadayken açıktır; bu hat ise
uygulama açık olduğu sürece açıktır. Özel mesaj gibi "nerede olursan ol sana
ulaşması gereken" olaylar buradan gelir.

İstemci bu hatta yalnızca `ping` gönderir (birkaç dakikada bir). Sunucu bununla
kişiyi "çevrimiçi" sayar. Asıl işlemler (mesaj gönderme) REST ile yapılır.
"""
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.database import SessionLocal
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.models import User
from app.realtime import events
from app.realtime.hub import user_hub
from app.realtime.state import room_state

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
    try:
        while True:
            raw = await websocket.receive_text()
            # Gelen her mesaj "buradayım" demektir; içeriği yalnızca ping olabilir, başka bir şey işlenmez.
            await room_state.touch_presence(user_id)
            try:
                is_ping = json.loads(raw).get("event") == events.PING
            except (ValueError, AttributeError):
                is_ping = False
            if not is_ping:
                await websocket.send_text(json.dumps({
                    "event": events.ERROR, "payload": {"code": "unknown_event", "detail": "Bilinmeyen olay."},
                }))
    except WebSocketDisconnect:
        pass
    finally:
        user_hub.remove(user_id, websocket)
