# DERS 2 — Sohbet odası: bir kişinin mesajı HERKESE gider.
#
# Ders 1'den farkı:
#   1) Sunucu açık hatların listesini tutuyor (kim odada?).
#   2) Gelen mesajı sadece gönderene değil, listedeki herkese yolluyor.
#   3) Sunucu kimse bir şey sormadan da konuşabiliyor (saat duyurusu).
#      HTTP'de bu imkânsız: sunucu sadece sorulana cevap verebilir.
#
# Projedeki karşılığı: backend/app/realtime/hub.py (RoomHub)
#
# Çalıştır:  ..\..\..\backend\venv\Scripts\python.exe server.py

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# Odadakilerin defteri: { açık hat → kullanıcının adı }
# Projede bunun adı RoomHub._connections.
connections: dict[WebSocket, str] = {}


async def broadcast(text: str):
    """Mesajı odadaki herkesin hattına yazar."""
    print(f"[sunucu] Herkese ({len(connections)} kişi): {text}")
    # list(...) ile kopyasını alıyoruz; gönderirken biri çıkarsa liste değişmesin.
    for websocket in list(connections):
        await websocket.send_text(text)


async def announce_time():
    """Arka planda çalışır: her 20 saniyede bir, KİMSE SORMADAN herkese saati söyler."""
    while True:
        await asyncio.sleep(20)
        if connections:
            await broadcast(f"[duyuru] Saat {datetime.now():%H:%M:%S}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sunucu açılınca saat duyurusunu başlat, kapanınca durdur.
    task = asyncio.create_task(announce_time())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


# ?name=Ali → adres sonundaki isim. Projede bunun yerine ?token=... var ve
# isim token'dan çıkarılıyor (kimse başkasının adıyla giremesin diye).
@app.websocket("/ws")
async def chat(websocket: WebSocket, name: str = "anonim"):
    await websocket.accept()
    connections[websocket] = name
    await broadcast(f"--> {name} odaya girdi. Odada {len(connections)} kişi var.")

    try:
        while True:
            text = await websocket.receive_text()
            # Ders 1'de: websocket.send_text(...)  → sadece gönderene
            # Burada:    broadcast(...)            → herkese
            await broadcast(f"{name}: {text}")
    except WebSocketDisconnect:
        # Defterden sil, yoksa kapanmış bir hatta yazmaya çalışırız.
        connections.pop(websocket, None)
        await broadcast(f"<-- {name} odadan çıktı. Odada {len(connections)} kişi var.")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9000)
