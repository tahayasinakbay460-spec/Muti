# WebSocket'i öğrenme dersleri

Projeden bağımsız, en basit örnekler. Sırayla yap: her ders bir öncekinin üstüne bir şey ekler.

| Ders | Ne öğreniyorsun | Projedeki karşılığı |
|---|---|---|
| `1_echo` | Hat bir kere açılır, kapanmaz; aynı hattan çok mesaj gider gelir | `room_socket.py` → `accept()` ve `while True` |
| `2_broadcast` | Sunucu odadakilerin listesini tutar, mesajı herkese yollar; kimse sormadan da konuşur | `hub.py` → `RoomHub` |
| `3_events` | `{"event", "payload"}` biçimi; sunucu otoritedir (isim ve zar sunucudan) | `room_socket.py` döngüsü, `frontend/js/realtime.js` |

## Nasıl çalıştırılır

Her ders için **en az iki terminal** aç (Ders 2 ve 3'te üç terminal daha eğlenceli).

**Terminal 1 — sunucu:**
```bat
cd learning\websocket\1_echo
..\..\..\backend\venv\Scripts\python.exe server.py
```

**Terminal 2, 3 — istemciler:**
```bat
cd learning\websocket\1_echo
..\..\..\backend\venv\Scripts\python.exe client.py
```

Diğer derslerde `1_echo` yerine `2_broadcast` veya `3_events` yaz. Sunucuyu `Ctrl+C` ile kapat, sonra sıradaki dersin sunucusunu aç (hepsi 9000 portunu kullanır). İstemciden `/q` ile çık.

## Her derste dene

**Ders 1:** Sunucu terminalinde "bağlandı" yazısını gör. Birkaç mesaj gönder: hepsi aynı bağlantıdan gidiyor. İstemciyi kapat: sunucuda "kapandı" yazısını gör.

**Ders 2:** İki istemciyle (Ali, Ayşe) gir. Ali yazınca Ayşe'nin ekranına, Ayşe hiçbir şey yapmadan düşüyor. 20 saniye bekle: sunucu kimse sormadan saati duyuruyor. HTTP'de bu ikisi de mümkün değil.

**Ders 3:** `/zar` dene. Sonra `/hile` dene: kendine 6-6 ve başkasının adını yazıyorsun ama sunucu ikisini de yok sayıyor. `/bozuk` ile hata olayının sadece sana geldiğini gör.

## Kendin değiştirmeyi dene

- Ders 2: mesajı gönderen hariç herkese yollasın (`broadcast`'e bir `except_websocket` parametresi ekle).
- Ders 3: yeni bir olay ekle, örneğin `gift:sent` → payload `{"to": "Ayşe", "gift": "gül"}`; herkese "Ali, Ayşe'ye gül gönderdi" yazsın.
- Ders 3: aynı kişi saniyede 3'ten fazla mesaj atarsa hata versin (projede `RateLimiter`, `room_socket.py:53`).
