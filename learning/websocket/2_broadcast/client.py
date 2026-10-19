# DERS 2 — Sohbet istemcisi. 2-3 ayrı terminalde aç, farklı isimlerle gir.
#
# Ders 1'den farkı: İki iş AYNI ANDA yapılıyor:
#   - dinle: sunucudan ne gelirse ekrana yaz (sen bir şey yazmasan bile)
#   - yaz:   klavyeden okuyup sunucuya gönder
# Ders 1'de cevap sadece sen yazınca geliyordu. Burada başkası yazınca da
# sana anında düşüyor; tarayıcıdaki sohbet de tam böyle çalışıyor.
#
# Çalıştır:  ..\..\..\backend\venv\Scripts\python.exe client.py
# Çıkmak için: /q

import asyncio

from websockets.asyncio.client import connect


async def listen(websocket):
    """Hattan gelen her mesajı ekrana yazar. Hat kapanana kadar bitmez."""
    async for message in websocket:
        print(message)


async def main():
    name = input("Adın: ")
    async with connect(f"ws://127.0.0.1:9000/ws?name={name}") as websocket:
        # Dinlemeyi arka planda başlat; biz bu sırada klavyeyi bekleyeceğiz.
        listener = asyncio.create_task(listen(websocket))

        while True:
            text = await asyncio.to_thread(input)
            if text == "/q":
                break
            await websocket.send(text)

        listener.cancel()


asyncio.run(main())
