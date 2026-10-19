# DERS 3 — Olaylar (event): aynı hattan farklı türde mesajlar.
#
# Ders 2'de hattan sadece düz yazı gidiyordu. Ama odada sohbet de var, zar da,
# hediye de... Sunucu gelen şeyin ne olduğunu nereden bilecek?
# Cevap: her mesaj JSON ve iki parçalı:
#     {"event": "chat:message",    "payload": {"text": "selam"}}
#     {"event": "game:dice_rolled", "payload": {}}
# "event" = ne tür bir mesaj (HTTP'deki /adres gibi), "payload" = içeriği.
#
# İkinci ders: SUNUCU OTORİTEDİR. İstemcinin söylediği isme ve zar sonucuna
# güvenmiyoruz; isim bağlantıdan, zar sunucunun kendi attığı sayıdan geliyor.
#
# Projedeki karşılığı: backend/app/realtime/room_socket.py (while True döngüsü)
#
# Çalıştır:  ..\..\..\backend\venv\Scripts\python.exe server.py

import json
import secrets

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()
connections: dict[WebSocket, str] = {}


async def publish(event: str, payload: dict):
    """Bir olayı odadaki herkese yollar. Projede: room_hub.publish(...)"""
    message = json.dumps({"event": event, "payload": payload}, ensure_ascii=False)
    print(f"[sunucu] Herkese: {message}")
    for websocket in list(connections):
        await websocket.send_text(message)


async def send_error(websocket: WebSocket, detail: str):
    """Hata sadece hatayı yapana gider, odaya değil."""
    await websocket.send_text(json.dumps({"event": "error", "payload": {"detail": detail}}, ensure_ascii=False))


@app.websocket("/ws")
async def room(websocket: WebSocket, name: str = "anonim"):
    await websocket.accept()
    connections[websocket] = name
    await publish("room:user_joined", {"user": name, "count": len(connections)})

    try:
        while True:
            raw = await websocket.receive_text()
            print(f"[sunucu] {name} gönderdi: {raw}")

            # 1) Düzgün JSON mu?
            try:
                message = json.loads(raw)
                event = message["event"]
                payload = message.get("payload") or {}
            except (ValueError, KeyError, TypeError):
                await send_error(websocket, "Mesaj biçimi hatalı.")
                continue

            # 2) Olay adına göre ne yapılacağına karar ver.
            if event == "chat:message":
                text = str(payload.get("text", "")).strip()
                if not text or len(text) > 200:
                    await send_error(websocket, "Mesaj boş veya çok uzun.")
                    continue
                # "user" alanını payload'dan DEĞİL, bağlantıdan alıyoruz.
                await publish("chat:message", {"user": name, "text": text})

            elif event == "game:dice_rolled":
                # İstemci payload'a {"values": [6, 6]} koysa bile bakmıyoruz.
                values = [secrets.randbelow(6) + 1, secrets.randbelow(6) + 1]
                await publish("game:dice_rolled", {"user": name, "values": values})

            else:
                await send_error(websocket, f"Bilinmeyen olay: {event}")

    except WebSocketDisconnect:
        connections.pop(websocket, None)
        await publish("room:user_left", {"user": name, "count": len(connections)})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9000)
