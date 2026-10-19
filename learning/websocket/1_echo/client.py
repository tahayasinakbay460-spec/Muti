# DERS 1 — İstemci. Tarayıcının yaptığı işi burada Python yapıyor.
#
# Çalıştır (sunucu açıkken, AYRI bir terminalde):
#   ..\..\..\backend\venv\Scripts\python.exe client.py
# Çıkmak için: /q

import asyncio

from websockets.asyncio.client import connect


async def main():
    # Adres http:// değil ws:// ile başlıyor. Bağlantı burada BİR KERE kuruluyor.
    async with connect("ws://127.0.0.1:9000/ws") as websocket:
        print("Bağlandın. Bir şey yaz, Enter'a bas.")

        while True:
            # input() klavyeyi beklerken programı kilitlemesin diye ayrı iş parçacığında.
            text = await asyncio.to_thread(input, "Sen: ")
            if text == "/q":
                break

            await websocket.send(text)       # hatta yaz
            reply = await websocket.recv()   # hattan cevabı oku
            print(reply)

    print("Bağlantı kapatıldı.")


asyncio.run(main())
