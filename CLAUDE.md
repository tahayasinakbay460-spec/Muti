# Top Top - Sesli Sohbet ve Oyun Ekosistemi

App Store ve Google Play'de bulunan "TopTop" uygulamasına benzeyen bir ürün geliştiriyoruz: kullanıcılar sesli sohbet odalarında bir araya gelir, oda içinde eşzamanlı mini oyunlar oynar ve birbirlerine sanal hediye gönderir. Sistem yüksek eşzamanlı (high-concurrency) ve gerçek zamanlı çalışacak şekilde tasarlanır.

Referans her zaman gerçek TopTop uygulamasıdır: ekran düzeni, akışlar ve özellikler ona benzemelidir (oda listesi, oda içi koltuk/mikrofon düzeni, hediye paneli, oyun girişi, cüzdan, profil). Marka varlıkları (logo, görseller, metinler) kopyalanmaz; kendi tasarımımızı üretiriz.

## Yol Haritası

1. **Web demo (şu anki aşama)** — tarayıcıda çalışan, gösterilebilir bir sürüm. Mobil uygulama görünümünde (telefon genişliğinde, mobile-first) HTML/CSS/JS.
   - **Önce frontend:** ekranlar sahte (mock) veriyle çalışır halde yapılır.
   - **Sonra backend:** frontend'in ihtiyaç duyduğu API ve WebSocket uçları yazılır, mock veri gerçek çağrılarla değiştirilir.
2. **Mobil uygulama** — iOS ve Android. Aynı backend API'sini kullanır; bu yüzden API baştan mobil istemciye uygun (token tabanlı, sürümlü, stateless) tasarlanır.

## Dil Kuralı (zorunlu)

- **Kod tamamen İngilizce:** dosya/klasör adları, değişken, fonksiyon, sınıf adları, route yolları, JSON alanları, Pydantic şemaları, veritabanı tablo/kolon adları, WebSocket event adları, commit mesajları.
- **Yalnızca açıklamalar Türkçe:** kod yorumları ve docstring'ler.
- **Arayüz metinleri Türkçe:** kullanıcının ekranda gördüğü yazılar (buton, başlık, bildirim) Türkçedir; bunlar kod değil içeriktir.
- Örnek: `POST /api/v1/wallet/purchase`, `class GiftSendRequest`, kolon `coin_balance` — yorum: `# Bakiyeyi atomik olarak düşür`.
- Mevcut kodda Türkçe adlar var (`/api/jeton/satin-al`, `/kullanicilar`, `mesaj` vb.). Bunlar dokunulan her yerde İngilizceye çevrilir; yeni Türkçe ad eklenmez.

## Mevcut Durum (repodaki kod)

Yapılan her işin kaydı kök dizindeki `GECMIS.md` dosyasındadır. **Her çalışma sonunda `GECMIS.md` içindeki "Kayıtlar" bölümünün en üstüne tarihli bir kayıt eklenir** (amaç, ne yapıldı, doğrulama, açık kalanlar) **ve dosyanın başındaki "Şu an neredeyiz" özeti güncellenir.** Yeni bir oturumda bağlam için önce o dosya okunur.

- `backend/` — FastAPI + async SQLAlchemy 2.0, SQLite (`backend/app.db`, aiosqlite), PyJWT + bcrypt. Frontend'in `httpApi` sözleşmesini (`/api/v1/...`) ve oda WebSocket'ini karşılar. Katmanlı yapı; istek `routers → services → models` yolunu izler:
  - `app/main.py` — uygulama girişi, lifespan (tablo oluşturma + demo seed), CORS, router bağlama
  - `app/core/` — `config.py` (`.env` ayarları), `database.py` (engine, `SessionLocal`, `Base`, `get_db`), `security.py` (bcrypt, JWT, refresh token), `errors.py` (`AppError` ve `{code, detail}` hata biçimi), `deps.py` (`DbSession`, `CurrentUserId`, `CurrentUser`), `timefmt.py`
  - `app/models/` — `user.py` (`User`, `Follow`, `RefreshToken`), `room.py` (`Room`, `RoomFollow`, `RoomAdmin`), `economy.py` (`Gift`, `CoinPackage`, `Transaction`), `message.py` (`Conversation`, `Message`); hepsi `models/__init__.py` içinde import edilir
  - `app/schemas/` — Pydantic istek/yanıt şemaları (alan başına bir dosya)
  - `app/services/` — iş kuralları: `auth_service`, `user_service`, `room_service`, `wallet_service` (bakiyeyi değiştiren tek yer: `change_balance`), `gift_service`, `message_service`, `moderation_service` (oda rolleri ve yetki kontrolleri)
  - `app/routers/` — ince HTTP katmanı: `auth`, `users`, `rooms`, `economy` (gifts/wallet/leaderboards), `conversations`, `content` (banners)
  - `app/realtime/` — `state.py` (`RoomStateStore` sözleşmesi + bellek içi uygulama: koltuk, dinleyici, odadan atılanlar, çevrimiçi), `hub.py` (`RoomHub` odaya yayın + kişiyi odadan çıkarma, `UserHub` kişiye özel yayın), `events.py` (event adları, WebSocket kapanış kodları), `room_socket.py` (`/ws/rooms/{id}?token=`), `user_socket.py` (`/ws/me?token=`, özel mesaj bildirimi)
  - `app/demo/` — `seed.py` (mock-data.js ile aynı örnek veri; tüm hesapların parolası `demo1234`), `content.py` (banner ve profil ekleri için sabit içerik)
  - `tests/` — uçtan uca API/WebSocket testleri (`python -m pytest`)
  - `.env` (git'e girmez, `SECRET_KEY` zorunlu) — örnek: `.env.example`
- `frontend/` — web demo (düz HTML/CSS/JS, ES modülleri, build adımı yok). Gerçek backend'e bağlıdır (`USE_MOCK = false`); `USE_MOCK = true` yapılırsa backend olmadan mock veriyle çalışır.
  - `index.html` — tek sayfa; `css/app.css` — tüm stiller ve tasarım değişkenleri
  - `js/config.js` — marka adı (`APP_NAME`, şu an "Muti"), `USE_MOCK`, API/WS adresleri, varsayılan avatar/kapak
  - `js/api.js` — tek veri katmanı: `mockApi` ve `httpApi` aynı metodları sunar. `httpApi` 401'de token'ı kendisi yeniler (`refreshSession`), para harcayan isteklere `Idempotency-Key` ekler
  - `js/inbox.js` — kişiye özel kanalın (`/ws/me`, `message:new`) sahibi: okunmamış rozeti ve yeni mesaj bildirimi; ekranlar `onInbox` ile abone olur
  - `js/realtime.js` — `connectUser` (kişiye özel kanal) ve oda kanalı (`chat:message`, `gift:sent`, `room:seats_updated`, `room:listener_count`, `room:user_joined`, `room:roles_updated`, `room:user_kicked`, `game:dice_rolled`, `error`; `room:speaking` yalnızca mock'ta); mock ve WebSocket sürümü aynı arayüzde, WebSocket koparsa yeniden bağlanır
  - `js/mock-data.js` — sahte kullanıcı/oda/hediye verisi (alan adları API JSON'u ile aynı)
  - `js/app.js` — hash yönlendirme (`#/home`, `#/explore`, `#/following`, `#/room/:id`, `#/messages`, `#/chat/:id`, `#/profile/:id`, `#/wallet`, `#/auth`) ve alt sekme çubuğu
  - `js/screens/` — ekran başına bir modül; her biri `render(root, { params, query })` ve isteğe bağlı temizlik fonksiyonu döner
  - `assets/` — yer tutucu görseller (kapaklar picsum.photos, avatarlar randomuser.me); yayın öncesi kendi görsellerimizle değiştirilecek

Olmayanlar: WebRTC (gerçek ses, `room:speaking`), Redis (oda state'i ve yayın bellek içi → tek süreç), PostgreSQL, migration (Alembic; şu an `create_all`), gerçek ödeme/makbuz doğrulama, HTTP hız sınırı, admin uçları, odaya özel `vip` rolü, uygulama kapalıyken bildirim (push).

## Çalıştırma

```bat
start.bat
```

Backend `http://127.0.0.1:8000` (API dokümanı: `/docs`), frontend `http://127.0.0.1:5500`. Dikkat: `start.bat` çalışan tüm `python.exe` süreçlerini öldürür.

Elle:

```bat
cd backend
venv\Scripts\activate
pip install -r requirements.txt
python -m app.main

cd frontend
python -m http.server 5500
```

Telefondan (aynı Wi-Fi) denemek için `backend/.env` içinde `HOST=0.0.0.0` olmalı; telefonda `http://<bilgisayarın IP'si>:5500` açılır (IP için `ipconfig`).

İlk kurulumda `backend/.env.example` dosyası `backend/.env` olarak kopyalanır ve `SECRET_KEY` doldurulur. Testler: `cd backend` → `python -m pytest`. Örnek veriyi sıfırlamak için sunucu durdurulup `backend/app.db` silinir.

## Ürün Modülleri

### A. Sesli Sohbet Odaları
- Oda listesi/keşfet, oda oluşturma, odaya katılma/ayrılma.
- Oda içi koltuk (seat) düzeni, mikrofon açma/kapama, metin sohbeti.
- Roller: `host`, `admin`, `vip`, `speaker`, `listener`.

### B. Çok Oyunculu Mini Oyunlar
- Sohbet akışını kesmeden oda içinde oynanır.
- Hamleler tüm oyuncu ve izleyicilere milisaniyeler içinde senkronize edilir.

### C. Sanal Ekonomi ve Hediyeleşme
- Gerçek parayla alınan sanal para (coin/diamond).
- Kullanıcılara ve yayıncılara anlık animasyonlu hediyeler.
- Bakiye düşme, transfer ve yayıncı geliri anlık ve hatasız (ACID).

## Frontend Kuralları (web demo)

- Düz HTML/CSS/JS, build adımı ve framework yok; `python -m http.server` ile açılabilmeli.
- Mobile-first: tasarım telefon genişliğine göre yapılır, masaüstünde ortalanmış telefon çerçevesi içinde gösterilir.
- Backend çağrıları tek bir API katmanında toplanır (`api.js` benzeri); mock veri ile gerçek API arasında geçiş tek yerden yapılır.
- Access token bellekte/`localStorage`'da tutulur ve `Authorization: Bearer` başlığıyla gönderilir.

## Backend Kuralları

- **API:** REST, sürümlü yol (`/api/v1/...`), kaynak adları çoğul ve İngilizce (`/rooms`, `/gifts`, `/wallet`). İstek/yanıt gövdeleri `schemas/` altında Pydantic modelleriyle tanımlanır.
- **Kimlik doğrulama:** OAuth2 Bearer + JWT, **PyJWT** kütüphanesi (FastAPI'nin güncel önerisi; `python-jose` bakımsız kaldığı için kullanılmaz). Kısa ömürlü access token + uzun ömürlü refresh token (mobil istemci için gerekli). Parolalar bcrypt ile hash'lenir. `SECRET_KEY` ve diğer sırlar `.env` üzerinden okunur, koda gömülmez.
- **Yapı:** yeni router `app/routers/` altına ve `app/main.py` içindeki `api_v1` listesine; yeni model `app/models/` altına ve `models/__init__.py` içine; şema `app/schemas/` altına. İş kuralı router'a değil `app/services/` altına yazılır; router yalnızca servisi çağırır.
- **Yorumlar:** kodu sonradan okuyacak kişi backend'e yeni; yorumlar ve docstring'ler sade Türkçe ile *neden* öyle yapıldığını anlatır, teknik terim ilk geçtiği yerde açıklanır.
- **Veritabanı:** şu an SQLite, hedef PostgreSQL. Şema ve sorgular PostgreSQL'e taşınabilir yazılır.
- **Para hareketleri:** her bakiye değişikliği tek transaction içinde ve atomik (`UPDATE ... SET coin_balance = coin_balance - :x WHERE coin_balance >= :x` veya satır kilidi). Tutarlar tamsayı, float yok. Her hareket `transactions` tablosuna değiştirilemez kayıt olarak yazılır; tekrar eden istekler için idempotency anahtarı.
- **Gerçek zamanlı:** metin sohbeti, hediye ve oyun event'leri WebSocket; ses WebRTC. Event adları `domain:action` biçiminde (`room:join`, `gift:send`, `game:move`), payload'lar şemalı. Sunucu otoritedir; istemciden gelen oyun/ekonomi verisine güvenilmez.
- **Ölçek:** oda/oyun state'i sunucu belleğinde değil Redis'te tutulur, sunucular arası yayın pub/sub ile yapılır (demo aşamasında bellek içi olabilir, arayüzü Redis'e geçişe uygun yazılır).
- **Güvenlik:** yetki kontrolleri (oda rolü, admin) her zaman sunucuda. CORS canlıda `*` olmaz.

## Çalışma Şekli

- Yüksek trafik ve gerçek zamanlı hız varsayılır; çözümler profesyonel, optimize ve güvenli olmalı.
- Sıra: önce frontend ekranı, sonra onu besleyen backend.
- Demo için alınan kısayollar (mock veri, bellek içi state, SQLite) açıkça işaretlenir ki mobil/canlı aşamasında değiştirilsin.
