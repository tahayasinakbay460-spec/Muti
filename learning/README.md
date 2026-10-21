# Öğrenme Haritası

Bu projede geçen kavramların listesi. Her başlıkta önce kısa ve sade bir açıklama var, sonra **bizim projede nerede kullanıldığı**, en sonda da **aramak için anahtar kelimeler**. Anahtar kelimeleri YouTube'a ya da Google'a yazarak (İngilizcesi genelde daha çok sonuç verir) derinleşebilirsin.

İşaretler:
- ⭐ = önce bunu öğren, projeyi anlamak için şart
- 🔜 = henüz projede yok ama yakında lazım olacak
- 💡 = bilmek iyi, acelesi yok

Önerilen sıra en altta.

---

## 1. İnternetin temelleri

### ⭐ İstemci (client) ve sunucu (server)
- **Nedir:** İstemci, isteği yapan taraftır: senin tarayıcın ya da telefonun. Sunucu ise cevabı veren, 7/24 açık duran bilgisayardır. Lokanta örneği: sen (istemci) sipariş verirsin, mutfak (sunucu) yemeği hazırlar.
- **Projede:** `frontend/` istemci, `backend/` sunucu.
- **Ara:** `client server model explained`

### ⭐ HTTP ve HTTPS
- **Nedir:** Tarayıcıyla sunucunun konuştuğu dil. Mektuplaşmaya benzer: bir istek gider, bir cevap gelir, sonra iş biter. HTTPS bunun şifreli halidir; aradaki kimse (ör. kafedeki Wi-Fi) içeriği okuyamaz. Tarayıcı mikrofonu **yalnızca HTTPS'te** açar.
- **Projede:** her API çağrısı (`/api/v1/...`) bir HTTP isteği. Canlıda https zorunlu.
- **Ara:** `HTTP request response`, `HTTP methods GET POST`, `HTTP status codes`, `how HTTPS works`, `TLS certificate`

### ⭐ IP adresi, port, localhost
- **Nedir:** IP adresi bilgisayarın internetteki adresidir (ör. `192.168.1.5`). Port aynı bilgisayardaki "kapı numarası"dır: bir adreste birden fazla program çalışabilir (bizde backend 8000, frontend 5500). `localhost` ya da `127.0.0.1` "bu bilgisayarın kendisi" demektir.
- **Ara:** `IP address explained`, `what is a port`, `localhost vs 0.0.0.0`

### ⭐ Alan adı (domain) ve DNS
- **Nedir:** `muti.com` gibi akılda kalan bir ad. DNS internetin telefon rehberidir: adı IP adresine çevirir.
- **Projede:** henüz alan adımız yok, Railway'in verdiği adresi kullanacağız. 🔜
- **Ara:** `how DNS works`, `domain name registrar`, `DNS A record CNAME`

### ⭐ REST API ve JSON
- **Nedir:** API, iki programın birbirine nasıl istek atacağını belirleyen kurallardır. REST bunun yaygın bir düzenidir: kaynaklara adres verilir (`/rooms`, `/gifts`), işlem HTTP metoduyla söylenir (GET oku, POST oluştur). JSON da verinin taşındığı metin biçimidir: `{"coin_balance": 500}`.
- **Projede:** `backend/app/routers/`; dokümanı görmek için sunucu açıkken `http://127.0.0.1:8000/docs`.
- **Ara:** `REST API explained`, `JSON tutorial`, `API versioning`

### ⭐ CORS
- **Nedir:** Tarayıcının bir güvenlik kuralı: bir sitedeki kod, başka bir adresteki sunucuya ancak o sunucu izin verirse istek atabilir. Böylece kötü bir site senin adına başka sitelere istek atamaz.
- **Projede:** geliştirmede site 5500'de, API 8000'de olduğu için CORS ayarı gerekiyor. Canlıda ikisi aynı adreste olduğundan sorun çıkmıyor.
- **Ara:** `CORS explained`, `same origin policy`

### ⭐ Önbellek (cache)
- **Nedir:** Tarayıcı, bir dosyayı her seferinde indirmesin diye saklar. Hızlıdır ama güncelleme sonrası eski dosya kalabilir; 19 Ekim'de yaşadığımız "boş sayfa" sorunu buydu.
- **Projede:** `Cache-Control: no-cache` başlığı, `backend/app/main.py` içindeki `NoCacheStaticFiles`.
- **Ara:** `HTTP caching Cache-Control`, `ETag 304 not modified`, `cache busting`

---

## 2. Gerçek zamanlı iletişim

### ⭐ WebSocket
- **Nedir:** HTTP mektuplaşmaysa WebSocket açık bir telefon hattıdır. Bağlantı bir kez kurulur, iki taraf da istediği an mesaj gönderir. Sohbet ve oyun gibi "anında" olması gereken işler için kullanılır.
- **Projede:** `backend/app/realtime/room_socket.py` (oda), `user_socket.py` (kişiye özel). Dersler: `learning/websocket/`.
- **Ara:** `WebSocket vs HTTP`, `WebSocket tutorial`, `wss secure websocket`

### ⭐ Olay (event) ve yük (payload)
- **Nedir:** WebSocket'ten giden her mesajın bir adı (`gift:sent`) ve taşıdığı bir verisi vardır (`{"gift_id": 3}`). Böylece karşı taraf mesajın ne olduğunu anlar.
- **Projede:** `backend/app/realtime/events.py`
- **Ara:** `event driven architecture`, `websocket message protocol`

### 🔜 Pub/Sub ve Redis
- **Nedir:** Pub/Sub, "yayınla / abone ol" demektir. Bir sunucu "bu odaya hediye geldi" diye yayınlar, o odayı dinleyen bütün sunucular haberi alır. Redis çok hızlı, bellekte çalışan bir veri deposudur; pub/sub, sayaç ve sıralama işleri için kullanılır.
- **Projede:** şimdilik yok. Bu yüzden şu an **tek sunucu** çalışabiliyor. Kullanıcı sayısı artınca gerekecek.
- **Ara:** `Redis tutorial`, `Redis pub sub`, `Redis sorted set leaderboard`, `horizontal scaling websocket`

---

## 3. Ses: sesli sohbet nasıl çalışır?

Ses sistemini bir telefon görüşmesi gibi düşün. Önce iki tarafın birbirini bulması gerekir; buna **tanışma** (signaling) denir. Sonra ses akmaya başlar. Ses ya iki taraf arasında doğrudan gider ya da bir aracı sunucudan geçer.

### ⭐ WebRTC
- **Nedir:** Tarayıcıların ve telefonların, ek bir program kurmadan gerçek zamanlı ses ve görüntü göndermesini sağlayan teknoloji. Google Meet ve Discord'un web sürümü bunu kullanır.
- **Projede:** `frontend/js/voice/mesh.js`, `backend/app/voice/`
- **Ara:** `WebRTC explained`, `WebRTC for beginners`, `RTCPeerConnection`, `getUserMedia microphone`

### ⭐ Signaling (tanışma)
- **Nedir:** WebRTC iki cihazı doğrudan bağlar ama önce birbirlerinin adresini ve hangi ses biçimlerini konuşabildiklerini öğrenmeleri gerekir. Bu "tanışma" mesajları başka bir yoldan, bizde WebSocket'ten taşınır. Sesin kendisi bu yoldan geçmez.
- **Projede:** `voice:signal` olayı, `room_socket.py`
- **Ara:** `WebRTC signaling server`, `SDP offer answer`

### ⭐ SDP ve ICE
- **Nedir:** SDP, "ben şu ses biçimlerini destekliyorum" diyen bir tanıtım metnidir (teklif/cevap, yani offer/answer). ICE ise iki cihaz arasında çalışan bir yol bulmak için bütün olası adresleri sırayla deneyen yöntemdir. Bu adayların her birine "ICE candidate" denir.
- **Ara:** `SDP WebRTC`, `ICE candidates explained`, `trickle ICE`

### ⭐ NAT
- **Nedir:** Evindeki modem, içerideki bütün cihazlar için dışarıya tek bir IP adresi kullanır; buna NAT denir. Dışarıdan bakan biri senin telefonunu doğrudan bulamaz. WebRTC'nin bütün zorluğu bu engeli aşmaktır.
- **Ara:** `NAT explained`, `NAT traversal`, `symmetric NAT`

### ⭐ STUN sunucusu
- **Nedir:** Cihaza "dışarıdan sen böyle görünüyorsun" diyen küçük bir yardımcı sunucu. Cihaz bu bilgiyle karşı tarafa doğrudan adresini verebilir. Ucuzdur, ses üzerinden geçmez.
- **Projede:** Google'ın ücretsiz STUN sunucusu (`VOICE_STUN_URLS`).
- **Ara:** `STUN server explained`

### ⭐ TURN sunucusu
- **Nedir:** Bazı ağlarda (mobil operatörler, şirket ağları, sıkı NAT) doğrudan bağlantı hiç kurulamaz. TURN araya giren bir **aktarıcıdır**: ses önce ona gider, o da karşı tarafa iletir. Sesi taşıdığı için internet trafiği harcar ve maliyetlidir. Bağlantıların yaklaşık %10–20'si TURN'e muhtaç kalır.
- **Projede:** 🔜 henüz yok, bazı kullanıcılarda ses bağlanmayabilir. Hazır servisler: Metered, Cloudflare. Kendin kurmak istersen: **coturn**.
- **Ara:** `TURN server explained`, `STUN vs TURN`, `coturn setup`

### ⭐ Mesh, SFU, MCU: odada çok kişi varken
- **Mesh:** herkes herkese doğrudan ses gönderir. Sunucu masrafı yoktur ama kişi sayısı arttıkça telefon zorlanır, çünkü 10 kişide herkes 9 ayrı ses akışı yollar. **Bizde şu an bu var.**
- **SFU (Selective Forwarding Unit):** herkes sesini tek bir kez sunucuya yollar, sunucu dağıtır. Kalabalık odalar için standart yöntem budur. **LiveKit** açık kaynak bir SFU'dur.
- **MCU:** sunucu bütün sesleri tek bir akışta karıştırır. Sunucuya çok yük bindirir, artık nadir kullanılır.
- **Projede:** `VOICE_PROVIDER=mesh` ya da `livekit` (`backend/app/voice/`).
- **Ara:** `mesh vs SFU vs MCU`, `LiveKit tutorial`, `selective forwarding unit`

### 💡 Codec (Opus)
- **Nedir:** Sesi küçültüp (sıkıştırıp) gönderen, karşı tarafta geri açan yöntem. WebRTC'de ses için standart codec **Opus**'tur.
- **Ara:** `Opus codec`, `audio codec explained`, `bitrate`

### 💡 Gecikme (latency), jitter, paket kaybı
- **Nedir:** Gecikme, sesin karşıya ulaşma süresidir (150 ms'nin altı iyidir). Jitter, paketlerin düzensiz aralıklarla gelmesidir. Paket kaybı, sesin bir kısmının yolda kaybolmasıdır. Ses kalitesini belirleyen üç ölçü bunlardır.
- **Ara:** `latency jitter packet loss`, `WebRTC getStats`

### 💡 Yankı engelleme, gürültü bastırma, otomatik kazanç
- **Nedir:** Hoparlörden çıkan sesin tekrar mikrofona girmesini önler (yankı engelleme), arka plan gürültüsünü azaltır (gürültü bastırma) ve ses seviyesini dengeler (otomatik kazanç). Tarayıcı bunları kendisi yapar, biz yalnızca açarız.
- **Ara:** `echoCancellation noiseSuppression autoGainControl getUserMedia`

### ⭐ "Kim konuşuyor" (VAD, Voice Activity Detection)
- **Nedir:** Ses şiddetine bakıp bir kişinin konuşup konuşmadığını anlamak. Koltuktaki yanıp sönen halka bu yöntemle çalışır.
- **Projede:** `frontend/js/voice/speaking.js`
- **Ara:** `voice activity detection`, `Web Audio API AnalyserNode`

### 🔜 STT (Speech-to-Text): sesi metne çevirme
- **Nedir:** Konuşmayı yazıya döker. Odalarda otomatik altyazı ya da küfür denetimi (moderasyon) için kullanılabilir. Örnek araçlar: Whisper (OpenAI, açık kaynak), Google Speech-to-Text, Deepgram.
- **Projede:** yok. İleride sesli moderasyon için düşünülebilir. Not: konuşmaları yazıya dökmek KVKK açısından ayrıca bilgilendirme gerektirir.
- **Ara:** `speech to text`, `Whisper speech recognition`, `real-time transcription`

### 🔜 TTS (Text-to-Speech): metni sese çevirme
- **Nedir:** Yazıyı yapay sesle okur. Odada bot duyuruları ya da erişilebilirlik için kullanılabilir. Örnek araçlar: ElevenLabs, Google TTS, Piper (açık kaynak).
- **Projede:** yok.
- **Ara:** `text to speech API`, `Piper TTS`

> Kısaltmaları karıştırma: STT = sesi yazıya çevirir, TTS = yazıyı sese çevirir. **STUN** ise ses dönüştürmeyle ilgisi olmayan, bağlantı kurmaya yarayan bir sunucudur (bkz. yukarı).

---

## 4. Backend (sunucu tarafı)

### ⭐ Python, FastAPI
- **Nedir:** Backend'imiz Python diliyle yazıldı. FastAPI, Python'da API yazmayı kolaylaştıran bir çerçevedir (framework).
- **Projede:** `backend/app/main.py`, `routers/`
- **Ara:** `FastAPI tutorial`, `FastAPI dependency injection`

### ⭐ Katmanlı yapı: router, servis, model
- **Nedir:** İsteği karşılayan katman (router), iş kurallarını uygulayan katman (servis) ve veritabanı tabloları (model) ayrı tutulur. Bir şey değişince nereye bakacağın bellidir.
- **Projede:** `routers/` → `services/` → `models/`
- **Ara:** `layered architecture backend`, `service layer pattern`

### ⭐ async / await
- **Nedir:** Sunucu veritabanından cevap beklerken boş durmaz, o sırada başka kullanıcıların işine bakar. Bir garsonun mutfağın önünde beklemeden başka masalara servis yapması gibi.
- **Ara:** `Python asyncio explained`, `async await`

### ⭐ ORM (SQLAlchemy) ve Pydantic
- **Nedir:** ORM, veritabanı tablolarını Python sınıfları gibi kullanmanı sağlar; SQL yazmadan `User` nesnesiyle çalışırsın. Pydantic ise gelen JSON'u kontrol eder: "yaş bir sayı mı, kullanıcı adı en fazla 24 karakter mi?"
- **Projede:** `models/`, `schemas/`
- **Ara:** `SQLAlchemy ORM tutorial`, `Pydantic validation`

---

## 5. Veritabanı

### ⭐ SQL, tablo, satır, kolon
- **Nedir:** Veritabanı, verilerin Excel tablolarına benzer tablolarda tutulduğu yerdir. SQL bu tablolara soru sorma dilidir: `SELECT * FROM users WHERE id = 5`.
- **Ara:** `SQL for beginners`, `SQL joins`

### ⭐ SQLite ve PostgreSQL
- **Nedir:** SQLite tek bir dosyada çalışan küçük bir veritabanıdır, denemeler için idealdir. PostgreSQL ayrı bir sunucu olarak çalışan, aynı anda binlerce kullanıcıyı kaldıran profesyonel bir veritabanıdır.
- **Projede:** bilgisayarda SQLite (`backend/app.db`), canlıda PostgreSQL.
- **Ara:** `SQLite vs PostgreSQL`, `PostgreSQL tutorial`

### ⭐ Transaction ve ACID
- **Nedir:** Transaction, birkaç işlemin "ya hepsi ya hiçbiri" şeklinde yapılmasıdır. Hediye gönderirken gönderenden coin düşer ve alıcıya elmas eklenir; biri olup diğeri olmazsa para kaybolur. ACID bu güvencenin dört kuralının baş harfleridir.
- **Projede:** `services/wallet_service.py` (`change_balance`)
- **Ara:** `database transaction ACID`, `race condition`, `row locking`

### ⭐ Migration (Alembic)
- **Nedir:** Veritabanı şemasının değişiklik defteri. "Kullanıcıya telefon kolonu ekle" gibi her değişiklik numaralı bir dosyaya yazılır ve canlı veritabanına sırayla uygulanır. Veriler silinmez.
- **Projede:** `backend/migrations/`, sunucu her açılışta `alembic upgrade head` çalıştırır.
- **Ara:** `database migration explained`, `Alembic tutorial`

### 💡 Index (dizin)
- **Nedir:** Kitabın sonundaki dizin gibi: bütün tabloyu taramadan aranan satırı hızlıca bulur.
- **Ara:** `database index explained`

### 🔜 Yedek (backup)
- **Nedir:** Veritabanının düzenli kopyası. Sunucu bozulursa ya da yanlışlıkla bir şey silinirse geri dönmeyi sağlar.
- **Ara:** `pg_dump backup`, `point in time recovery`

### 💡 Idempotency (tekrara dayanıklılık)
- **Nedir:** Kullanıcı "satın al" düğmesine iki kez basarsa ya da internet koptuğu için istek iki kez giderse, para iki kez çekilmemeli. Her isteğe benzersiz bir anahtar verilir; aynı anahtar ikinci kez gelirse işlem tekrar yapılmaz.
- **Projede:** `Idempotency-Key` başlığı (`frontend/js/api.js`)
- **Ara:** `idempotency key API`

---

## 6. Kimlik ve güvenlik

### ⭐ Parola hash'leme (bcrypt)
- **Nedir:** Parolanın kendisi hiçbir zaman saklanmaz; geri çevrilemeyen bir "parmak izi" (hash) saklanır. Veritabanı çalınsa bile parolalar okunamaz.
- **Ara:** `password hashing bcrypt`, `salt`

### ⭐ JWT, access token, refresh token
- **Nedir:** Giriş yapınca sunucu sana imzalı bir "bilet" (JWT) verir. Her istekte bu bileti gösterirsin. Access token kısa ömürlüdür (15 dk); süresi dolunca uzun ömürlü refresh token'la yenisini alırsın.
- **Projede:** `core/security.py`, `services/auth_service.py`
- **Ara:** `JWT explained`, `access token refresh token`, `token rotation`

### ⭐ Hız sınırı (rate limit)
- **Nedir:** Aynı yerden kısa sürede çok fazla istek gelirse durdurmak. Parola tahmin saldırısını ve sahte hesap yağmurunu yavaşlatır.
- **Projede:** `core/ratelimit.py` (dakikada 10 giriş denemesi)
- **Ara:** `rate limiting`, `sliding window rate limit`, `brute force attack`

### ⭐ Ortam değişkenleri ve sırlar (`.env`, secrets)
- **Nedir:** Parola ve gizli anahtar gibi bilgiler koda yazılmaz; sunucunun ayarlarında saklanır. Kod GitHub'da olsa bile sırlar orada olmaz.
- **Projede:** `backend/.env` (git'e girmez), Railway'de "Variables" sekmesi.
- **Ara:** `environment variables`, `secrets management`, `12 factor app config`

### 💡 Yaygın saldırılar
- **Ara:** `OWASP top 10`, `XSS`, `SQL injection`, `CSRF`

---

## 7. Yayın (DevOps): kodu internete çıkarmak

### ⭐ Git ve GitHub
- **Nedir:** Git kodun bütün geçmişini tutar: her kayda commit denir, hata olursa geri dönülebilir. GitHub da bu geçmişin internette saklandığı yerdir.
- **Ara:** `git tutorial for beginners`, `git commit push pull`, `git branch`

### ⭐ CI/CD
- **Nedir:** CI (Continuous Integration): her push'ta testler, güvenlik taramaları ve kontroller kendiliğinden çalışır. CD (Continuous Deployment): CI yeşilse kod kendiliğinden yayına çıkar. "GitHub'a attım, site güncellendi" dediğin şey budur.
- **Projede:** `.github/workflows/ci.yml` (GitHub Actions), Railway otomatik yayın.
- **Ara:** `CI CD explained`, `GitHub Actions tutorial`

### ⭐ Docker
- **Nedir:** Uygulamayı içinde Python, kütüphaneler ve kod hazır olacak şekilde bir **kutuya** koymak. "Benim bilgisayarımda çalışıyordu" sorununu bitirir, çünkü kutu her yerde aynı çalışır. Kutunun tarifine **image** (kalıp), çalışan haline **container** (kap) denir. Tarif dosyası `Dockerfile`'dır.
- **Projede:** kök dizindeki `Dockerfile`
- **Ara:** `Docker explained for beginners`, `Dockerfile tutorial`, `image vs container`

### ⭐ Hosting ve PaaS (Railway)
- **Nedir:** Hosting, uygulamanın 7/24 açık bir bilgisayarda çalışmasıdır. PaaS (Platform as a Service) sunucu yönetimini senin yerine yapar: kodu verirsin, o çalıştırır. Railway, Render ve Fly.io bu türdendir. VPS ise boş bir sunucu kiralayıp her şeyi kendin kurmaktır (ör. Hetzner, DigitalOcean).
- **Ara:** `PaaS vs VPS`, `Railway deploy tutorial`

### ⭐ Log (kayıt), healthcheck
- **Nedir:** Log, sunucunun "şu an ne oldu" günlüğüdür; hata olunca ilk bakılacak yer burasıdır. Healthcheck ise hosting'in arada bir "ayakta mısın?" diye sorduğu adrestir (bizde `/health`).
- **Projede:** `core/logs.py`
- **Ara:** `structured logging`, `health check endpoint`

### 🔜 Hata takibi (Sentry) ve izleme (monitoring)
- **Nedir:** Kullanıcının ekranında bir hata olunca sana haber veren servisler. Biri şikâyet etmeden sorunu görürsün.
- **Ara:** `Sentry error tracking`, `observability logs metrics traces`

### 💡 Ölçekleme (scaling), load balancer, replica
- **Nedir:** Kullanıcı artınca sunucuyu büyütmeye dikey ölçekleme, sunucu sayısını artırmaya yatay ölçekleme denir. Load balancer gelen istekleri sunucular arasında dağıtır. Bizde şimdilik **tek kopya (replica = 1)** çalışmak zorunda, çünkü oda bilgisi bellekte; bunun çözümü Redis'tir.
- **Ara:** `horizontal vs vertical scaling`, `load balancer explained`, `stateless server`

### 💡 Yük testi
- **Nedir:** Sahte binlerce kullanıcıyla sunucunun nerede zorlandığını ölçmek.
- **Ara:** `load testing k6`, `locust load test`

---

## 8. Mobil (sonraki aşama)

### 🔜 PWA (Progressive Web App)
- **Nedir:** Web sitesinin telefonda "ana ekrana ekle" ile uygulama gibi açılması. Mağaza gerektirmez ve web sitemizden kolayca yapılabilir. Mobil uygulamadan önce iyi bir ara adımdır.
- **Ara:** `PWA tutorial`, `web app manifest`, `service worker`

### 🔜 Yerli (native) ve çapraz platform (React Native, Expo, Flutter)
- **Nedir:** Native uygulama iOS için Swift, Android için Kotlin ile ayrı ayrı yazılır. React Native ve Flutter ise tek kodla iki platforma birden uygulama çıkarır. Expo, React Native'i kolaylaştıran bir araçtır; "Expo Go" ile telefonda hızlıca deneme yapılır.
- **Ara:** `React Native vs Flutter`, `Expo tutorial`, `EAS build`

### 🔜 APK, AAB, App Store incelemesi
- **Nedir:** APK, Android'in kurulum dosyasıdır; Google Play'e AAB biçimi yüklenir. Apple'da TestFlight ile deneme yapılır ve uygulama yayından önce incelemeden geçer.
- **Ara:** `APK vs AAB`, `TestFlight`, `App Store review guidelines`

### 🔜 Push bildirimi (APNs, FCM)
- **Nedir:** Uygulama kapalıyken gelen bildirim. Apple'da APNs, Android'de FCM (Firebase) üzerinden gönderilir.
- **Ara:** `push notifications APNs FCM`

---

## 9. Para ve hukuk

### 🔜 Uygulama içi satın alma (IAP) ve ödeme sağlayıcısı
- **Nedir:** Mobilde coin satışı Apple ve Google'ın kendi ödeme sistemiyle yapılmak zorundadır (IAP; komisyon %15–30). Web'de ise iyzico, PayTR, Stripe gibi bir ödeme sağlayıcısı kullanılır; bunlar için şirket ya da şahıs işletmesi gerekir.
- **Ara:** `in app purchase receipt validation`, `iyzico entegrasyon`, `Stripe checkout`

### 🔜 KYC ve para çekme
- **Nedir:** KYC (Know Your Customer), parayı çekecek kişinin kimliğinin doğrulanmasıdır. Yayıncıya ya da ajansa gerçek para ödemek için gerekir.
- **Ara:** `KYC verification`

### ⭐ KVKK
- **Nedir:** Türkiye'nin kişisel veri kanunu. Kullanıcıya hangi veriyi neden topladığını anlatman (aydınlatma metni) ve veriyi koruman zorunludur. Avrupa'daki karşılığı GDPR'dır.
- **Projede:** `frontend/legal.html` (taslak)
- **Ara:** `KVKK aydınlatma metni`, `KVKK yurt dışına aktarım`, `VERBİS`

### 🔜 Şans oyunu mevzuatı
- **Nedir:** Parayla alınan coinle rastgele ödül vermek (şanslı hediye, hazine sandığı) bazı ülkelerde kumar sayılabilir; olasılıkların açıkça gösterilmesi istenebilir.
- **Ara:** `loot box regulation`, `şans oyunu mevzuatı dijital`

---

## Önerilen sıra

1. **İnternetin temelleri:** istemci-sunucu, HTTP/HTTPS, IP/port, DNS, REST/JSON. Bunlar olmadan diğer konular havada kalır.
2. **Git ve GitHub, CI/CD, Docker, hosting.** Bugünkü yayın işini anlamak için gerekli.
3. **WebSocket.** `learning/websocket/` derslerine devam.
4. **Ses:** WebRTC → signaling → NAT → STUN → TURN → mesh/SFU.
5. **Veritabanı:** SQL → transaction → migration.
6. **Kimlik ve güvenlik:** hash, JWT, rate limit, sırlar.
7. **Redis ve ölçekleme**, sonra **mobil**, sonra **para ve hukuk**.

Bir konuyu çalışırken anlamadığın yeri bana sor. İstersen `learning/websocket/` gibi küçük, çalışan örnek dersler de hazırlarım (ör. iki tarayıcı sekmesi arasında WebRTC ile ses gönderme).
