# DERS 3 — Olaylı istemci. 2-3 terminalde aç.
#
# Komutlar:
#   düz yazı → sohbet mesajı
#   /zar     → zar at (sonucu sunucu belirler)
#   /hile    → kendine 6-6 yazıp başkasının adıyla zar atmayı dene; ne olacak?
#   /bozuk   → JSON olmayan bir şey gönder
#   /q       → çık
#
# Gelen mesajı "event" adına göre farklı gösteriyoruz.
# Projedeki karşılığı: frontend/js/realtime.js (olay adına göre ekrana dağıtma)
#
# Çalıştır:  ..\..\..\backend\venv\Scripts\python.exe client.py

import asyncio
import json

from websockets.asyncio.client import connect


def show(raw: str):
    """Gelen olayı türüne göre ekrana yazar. Tarayıcıda bu, ekranı güncellemek olurdu."""
    message = json.loads(raw)
    event, payload = message["event"], message["payload"]

    if event == "chat:message":
        print(f"{payload['user']}: {payload['text']}")
    elif event == "game:dice_rolled":
        print(f"[zar] {payload['user']} attı: {payload['values']}")
    elif event == "room:user_joined":
        print(f"--> {payload['user']} girdi ({payload['count']} kişi)")
    elif event == "room:user_left":
        print(f"<-- {payload['user']} çıktı ({payload['count']} kişi)")
    elif event == "error":
        print(f"[HATA] {payload['detail']}")


async def listen(websocket):
    async for raw in websocket:
        show(raw)


def build(text: str) -> str:
    """Klavyeden yazılanı hatta gidecek mesaja çevirir."""
    if text == "/zar":
        return json.dumps({"event": "game:dice_rolled", "payload": {}})
    if text == "/hile":
        # Sunucu bunları görmezden gelecek: isim bağlantıdan, zar sunucudan.
        return json.dumps({"event": "game:dice_rolled", "payload": {"values": [6, 6], "user": "Başkası"}})
    if text == "/bozuk":
        return "bu json değil"
    return json.dumps({"event": "chat:message", "payload": {"text": text}}, ensure_ascii=False)


async def main():
    name = input("Adın: ")
    async with connect(f"ws://127.0.0.1:9000/ws?name={name}") as websocket:
        listener = asyncio.create_task(listen(websocket))
        while True:
            text = await asyncio.to_thread(input)
            if text == "/q":
                break
            await websocket.send(build(text))
        listener.cancel()


asyncio.run(main())
