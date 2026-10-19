# DERS 1 — En basit WebSocket sunucusu: "yankı" (echo)
#
# Ne yapar: Biri bağlanınca hat açılır. Ne yazarsa sunucu ona geri yollar.
# Görmen gereken: Hat bir kere açılıyor ve kapanmıyor. Aynı hattan istediğin
# kadar mesaj gidip geliyor. HTTP'de her mesaj için yeni bağlantı açılırdı.
#
# Çalıştır:  ..\..\..\backend\venv\Scripts\python.exe server.py

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()


# @app.get("/...") HTTP içindir. @app.websocket("/...") ise açık kalan hat içindir.
@app.websocket("/ws")
async def echo(websocket: WebSocket):
    # Birisi aradı, telefonu açıyoruz. Bunu yapmazsak bağlantı kurulmaz.
    await websocket.accept()
    print("[sunucu] Biri bağlandı, hat açık.")

    try:
        # Sonsuz döngü: hat açık olduğu sürece karşı tarafı dinle.
        while True:
            # Karşı taraf bir şey yazana kadar BURADA bekler (program donmaz,
            # "await" sayesinde sunucu bu arada başka işler yapabilir).
            text = await websocket.receive_text()
            print(f"[sunucu] Gelen: {text!r}")

            # Aynı hattan geri gönder.
            await websocket.send_text(f"Yankı: {text}")
    except WebSocketDisconnect:
        # Karşı taraf kapattı (çıktı, sekmeyi kapattı, interneti gitti).
        print("[sunucu] Bağlantı kapandı.")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9000)
