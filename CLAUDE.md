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
  - `app/core/` — `config.py` (`.env` ayarları), `database.py` (engine, `SessionLocal`, `Base`, `get_db`), `security.py` (bcrypt, JWT, refresh token), `errors.py` (`AppError` ve `{code, detail}` hata biçimi), `deps.py` (`DbSession`, `CurrentUserId` — banlı kontrolü dahil, `CurrentUser`, `CurrentAdmin`), `timefmt.py`, `logs.py` (kayıt: her isteğe `X-Request-ID`, `muti.access` erişim kaydı, `muti.audit` güvenlik/para/moderasyon kaydı — `audit("olay_adi", alan=...)`; parola/token asla yazılmaz; `.env` `LOG_LEVEL`, `LOG_JSON`, `LOG_FILE`)
  - `app/models/` — `user.py` (`User`, `Follow`, `RefreshToken`), `room.py` (`Room`, `RoomFollow`, `RoomMember` = odaya özel `admin`/`vip` rolü), `economy.py` (`Gift` — `is_lucky` şanslı hediye, `CoinPackage` — eşyalı hediye paketi alanları, `Transaction`), `store.py` (`StoreItem` kozmetik katalog, `UserItem` kimde ne var / süresi / takılı mı), `engagement.py` (`DailyCheckIn`, `TaskCounter`, `TaskClaim`, `Event`), `family.py` (`Family`, `FamilyMember`, `FamilyMessage`, `Couple`; kullanıcıda `cp_partner_id`), `agency.py` (`Agency`, `AgencyMember`), `social.py` `Report` karar alanları (`resolved_by`, `action`, `resolution_note`), `message.py` (`Conversation`, `Message`), `social.py` (`UserBlock`, `Report`, `Notification`); hepsi `models/__init__.py` içinde import edilir
  - `app/schemas/` — Pydantic istek/yanıt şemaları (alan başına bir dosya)
  - `app/services/` — iş kuralları: `auth_service` (parola değiştirme, hesap silme dahil), `user_service` (takip, arama, engelleme kontrolü), `room_service` (oda rolleri `get_role`, ses giriş bilgisi), `wallet_service` (bakiyeyi değiştiren tek yer: `change_balance`; elmas → coin çevirme, yayıncı geliri), `gift_service` (şanslı hediye çekilişi `LUCKY_TABLE`), `store_service` (mağaza: satın alma, süre uzatma, takma; `equipped_cosmetics` her kullanıcı listesine çerçeve/efekt/balon ekler), `vip_service` (3 kademe `VIP_TIERS`, günlük ödül), `treasure_service` (oda hazine sandığı; DEMO: bellek içi), `engagement_service` (günlük giriş 7 günlük döngü, görevler `TASKS` + sayaç `record`), `family_service` (aile, rütbe, aile sohbeti), `couple_service` (CP teklif/kabul/iade, tek CP kuralı atomik), `leaderboard_service` (zengin/çekici/oda/aile × gün/hafta/ay, defterden), `event_service` (süreli etkinlik, ödülü bitince bir kez dağıtır), `activity_service` (oda PK'si, birlikte izleme YouTube senkronu, karaoke sırası; DEMO: bellek içi), `admin_service` (yönetim paneli: özet, şikâyet kararı, ban — anında etkili, banlı listesi bellekte/DEMO, bakiye düzeltme, oda kapatma), `agency_service` (ajans daveti, aylık hedef, tahmini komisyon; ödeme yok), `message_service`, `moderation_service` (rol verme, susturma, mesaj silme, koltuğa davet, oda ayarları/kapatma), `level_service` (deneyim puanı ve seviye), `notification_service` (bildirim merkezi), `social_service` (engelleme, şikâyet)
  - `app/routers/` — ince HTTP katmanı: `auth`, `users`, `rooms`, `economy` (gifts/wallet/leaderboards), `store` (store/items, users/{id}/items, vip), `engagement` (rewards/checkin, tasks, families, couples, leaderboards, events), `activities` (rooms/{id}/activities, pk, media, karaoke), `admin` (/admin/..., yalnızca `CurrentAdmin`), `agency` (/agencies/me/...), `conversations`, `social` (notifications/reports), `content` (banners)
  - `app/realtime/` — `state.py` (`RoomStateStore` sözleşmesi + bellek içi uygulama: koltuk, dinleyici, odadan atılanlar, sohbet susturma, mikrofon engeli, koltuk davetleri, son 50 sohbet mesajı, çevrimiçi), `hub.py` (`RoomHub` odaya yayın + kişiyi odadan çıkarma, `UserHub` kişiye özel yayın), `events.py` (event adları, WebSocket kapanış kodları), `room_socket.py` (`/ws/rooms/{id}?token=`; sohbet, son mesajlar, oyunlar, mesh ses sinyali `voice:signal`), `user_socket.py` (`/ws/me?token=`, özel mesaj ve bildirim), `games.py` (oda içi rulet: tur durumu ve sunucunun çektiği sonuç), `duels.py` (iki kişilik masalar: Dört Bağla, Taş-Kağıt-Makas; hamle süresi, hükmen yenilgi; seçimler rakipten gizli)
  - `app/voice/` — sesli görüşme (WebRTC) sağlayıcı katmanı. `base.py` sözleşme (`VoiceProvider`), `mesh.py` (tarayıcılar arası doğrudan ses, sunucumuz yalnızca sinyal taşır), `livekit.py` (açık kaynak SFU; kalabalık odalar için, henüz canlı sunucuyla denenmedi), `ice.py` (STUN/TURN, coturn uyumlu süreli TURN parolası). Sağlayıcı `.env` `VOICE_PROVIDER` ile seçilir; yeni sağlayıcı = yeni sınıf + frontend `js/voice/` altında aynı arayüzde istemci
  - `app/demo/` — `seed.py` (mock-data.js ile aynı örnek veri; tüm hesapların parolası `demo1234`; yönetici hesabı `admin`), `content.py` (banner ve profil ekleri için sabit içerik)
  - `tests/` — uçtan uca API/WebSocket testleri (`python -m pytest`). WebSocket testinde bağlanır bağlanmaz mesaj gönderme: önce odaya katılmayı (`chat:history`) ya da `/ws/me` kaydını (`wait_until_registered`) bekle, yoksa test ara sıra sonsuza kadar takılır
  - `.env` (git'e girmez, `SECRET_KEY` zorunlu) — örnek: `.env.example`
- `frontend/` — web demo (düz HTML/CSS/JS, ES modülleri, build adımı yok). Gerçek backend'e bağlıdır (`USE_MOCK = false`); `USE_MOCK = true` yapılırsa backend olmadan mock veriyle çalışır.
  - `index.html` — tek sayfa; `css/app.css` — tüm stiller ve tasarım değişkenleri
  - `js/config.js` — marka adı (`APP_NAME`, şu an "Muti"), `USE_MOCK`, API/WS adresleri, varsayılan avatar/kapak
  - `js/api.js` — tek veri katmanı: `mockApi` ve `httpApi` aynı metodları sunar. `httpApi` 401'de token'ı kendisi yeniler (`refreshSession`), para harcayan isteklere `Idempotency-Key` ekler
  - `js/inbox.js` — kişiye özel kanalın (`/ws/me`) sahibi: okunmamış mesaj rozeti, bildirim zili rozeti, yeni mesaj/bildirim uyarısı; ekranlar `onInbox` ile abone olur
  - `js/realtime.js` — `connectUser` (kişiye özel kanal: `message:new`, `notification:new`, `family:message`, `couple:updated`) ve oda kanalı (`chat:message`, `chat:history`, `chat:message_deleted`, `gift:sent`, `room:seats_updated`, `room:listener_count`, `room:user_joined`, `room:user_left`, `room:roles_updated`, `room:user_kicked`, `room:chat_muted`, `room:seat_invite`, `room:updated`, `room:closed`, `room:chest_updated`, `room:chest_claimed`, `room:pk_updated`, `room:media_updated`, `room:karaoke_updated`, `game:duel_updated` / `_closed`, `voice:signal`, `game:dice_rolled`, `game:roulette_started` / `_bet_placed` / `_result`, `error`; `room:speaking` yalnızca mock'ta); mock ve WebSocket sürümü aynı arayüzde, WebSocket koparsa yeniden bağlanır
  - `js/voice/` — sesli görüşme istemcisi: `index.js` (sunucunun söylediği sağlayıcıyı yükler), `mesh.js`, `livekit.js`, `speaking.js` ("kim konuşuyor" ses şiddetinden tarayıcıda hesaplanır)
  - `js/mock-data.js` — sahte kullanıcı/oda/hediye verisi (alan adları API JSON'u ile aynı)
  - `js/app.js` — hash yönlendirme (`#/home`, `#/explore`, `#/following`, `#/room/:id`, `#/messages`, `#/chat/:id`, `#/profile/:id`, `#/wallet`, `#/store`, `#/vip`, `#/tasks`, `#/admin`, `#/agency`, `#/leaderboard`, `#/families`, `#/family/:id`, `#/events`, `#/event/:id`, `#/notifications`, `#/settings`, `#/auth`) ve alt sekme çubuğu
  - `js/screens/room-activities.js` — oda ekranına bağlanan PK çubuğu, YouTube oynatıcı (IFrame API), karaoke, oyun masaları
  - `js/screens/` — ekran başına bir modül; her biri `render(root, { params, query })` ve isteğe bağlı temizlik fonksiyonu döner
  - `assets/` — yer tutucu görseller (kapaklar picsum.photos, avatarlar randomuser.me); yayın öncesi kendi görsellerimizle değiştirilecek
  - Kozmetikler `UserOut` içinde gelir (`frame`, `entry_effect`, `chat_bubble` = CSS sınıfı adları); çerçeve CSS'i `--frame` değişkeniyle çizilir, avatar için `ui.js` `framedAvatar`
- `.github/workflows/ci.yml` — her push'ta: backend lint (ruff 0.13.0) + testler, bağımlılık güvenlik taraması (pip-audit), frontend JS sözdizimi (`frontend/package.json` `"type": "module"` şart: yoksa `node --check` import içeren dosyadaki sözdizimi hatasını görmez), sızmış sır taraması (gitleaks, ayarı `.gitleaks.toml`). test kapsamı %90 altına düşerse kırmızı (`.coveragerc`, async kod için `concurrency = greenlet, thread` şart). CI kırmızıysa iş bitmiş sayılmaz. Yeni para/güvenlik/moderasyon işlemi eklenince `audit(...)` kaydı ve testi de eklenir
- `learning/` — kullanıcının öğrenme dersleri (projeden bağımsız; ör. `learning/websocket/`)

Olmayanlar: kendi TURN sunucumuz (sıkı ağlarda ses bağlanmayabilir), LiveKit'in canlı denenmesi, Redis (oda state'i ve yayın bellek içi → tek süreç), PostgreSQL, migration (Alembic; şu an `create_all` → şema değişince `backend/app.db` silinir), gerçek ödeme/makbuz doğrulama, elmasların gerçek paraya çekimi, HTTP hız sınırı, uygulama kapalıyken bildirim (push), frontend dosyaları için önbellek stratejisi (build adımı yok: yayında sunucu `Cache-Control: no-cache` vermezse tarayıcı eski ve yeni JS modüllerini karıştırıp boş sayfa gösterebilir; 2026-10-19 tarayıcı denemesinde yaşandı).

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

### D. Hedef Özellikler (rakip araştırması, 2026-10-19)

TopTop, Yalla, SoulChill, Kafu, Azal ve Zimo Live'ın mağaza sayfaları ve tanıtımları incelendi. Bu uygulamaların gücü oda/sohbetten çok **kullanıcıyı geri getiren ve para harcatan sistemlerde**. Aşağıdakiler bizde henüz yok; öncelik sırasıyla:

1. **Para kazandıran (gelir) sistemleri**
   - **VIP / soylu (aristokrasi) kademeleri:** aylık abonelik (TopTop'ta "diamond" üyelik ~3,99 $ / 31 gün, iki kademe). Ayrıcalıklar: özel rozet, avatar çerçevesi, odaya giriş efekti, günlük ücretsiz coin/elmas, ayrıcalıklı oda.
   - **Mağaza (kozmetik):** avatar çerçevesi, giriş efekti ("binek/araba"), sohbet balonu, oda arka planı, profil süsü, özel/güzel ID numarası. Süreli (7/30 gün) veya kalıcı satılır.
   - **Şanslı hediye:** gönderene rastgele coin geri döner; kazanç odada duyurulur.
   - **Hazine sandığı / şans çekilişi:** odada açılan, coin kazandıran sandık.
   - **Hediye paketleri:** etkinliklere özel indirimli paketler.
2. **Kullanıcıyı geri getiren (bağlılık) sistemleri**
   - **Günlük giriş ödülü ve görevler:** günlük/haftalık görevler ("3 hediye gönder", "10 dk mikrofonda kal") → coin/deneyim ödülü.
   - **Sıralamalar:** şu an yalnızca en çok hediye gönderenler var (`/leaderboards/gifters`). Eksik: günlük/haftalık/aylık ayrımı; en çok hediye gönderen (zengin), en çok kazanan yayıncı (çekici), en iyi aile, en popüler oda.
   - **Aile (klan):** aile kurma/katılma, aile sohbeti, aile seviyesi ve sıralaması, aile rozeti.
   - **CP (çift) sistemi:** iki kullanıcı profilde birbirine bağlanır, ortak seviye/rozet. (Araştırmada doğrulanmadı; bölge uygulamalarında yaygın olduğu biliniyor.)
   - **Etkinlikler:** süreli kampanyalar, ödüllü yarışmalar, özel hediyeler.
3. **Oda içi eğlence**
   - **Oda PK'si:** iki oda ya da iki koltuk süreli hediye yarışı yapar; canlı ilerleme çubuğu, kaybedene "ceza" aşaması.
   - **Daha çok oyun:** TopTop'ta ~16 oyun var: Ludo, Domino (Domino Battle), Carrom (Carrom Battle), UNO, Jackaro, Baloot, Tavla, Satranç, Dört Bağla, Draw & Guess (çiz-tahmin et), Mafya/Kurt Adam, Mayın Tarlası, Monopoly, şarkı tahmini, eşleştirme. Oyun masası odadaki aynı kişilerle açılır.
   - **Odada birlikte etkinlik:** şarkı söyleme (karaoke), birlikte film/video izleme, hikâye anlatma.
   - Görüntü yok, yalnızca ses (TopTop'un vurguladığı: kamera açmak gerekmez).
4. **İşletme tarafı**
   - **Ajans sistemi:** yayıncıları yöneten ajanslar; yayıncı hedefleri, maaş/gelir paylaşımı, ajans paneli.
   - **Uygulama geneli admin paneli:** şikâyet inceleme, banlama, içerik ve ekonomi yönetimi.
   - **Coin satışı:** mağaza içi paketler (TopTop: 0,99 $ – 99,99 $); bayi/top-up satış kanalları da var.

Demo öncesi önerilen sıra (gösterişli ve hızlı): giriş efekti + avatar çerçevesi + mağaza → günlük ödül + sıralama ekranı → oda PK'si. Aile, ajans, yeni oyunlar demodan sonra.

**Yapılanlar:** 1. grup (2026-10-19): mağaza (çerçeve, giriş efekti, sohbet balonu; 7/30 gün), VIP (3 kademe, coinle — DEMO; günlük ödül), şanslı hediye, hazine sandığı, hediye paketleri. 2. grup (2026-10-19): günlük giriş + görevler, sıralamalar (4 tür × 3 dönem), aile (sohbetli), CP, etkinlikler. 3. grup (2026-10-19): oda PK'si, Dört Bağla + Taş-Kağıt-Makas, birlikte izleme, karaoke sırası (Ludo/Domino/UNO gibi büyük oyunlar henüz yok). 4. grup (2026-10-19): yönetim paneli (özet, şikâyet, kullanıcı ban/bakiye, oda, ajans kurma) ve ajans sistemi. Dört grup tamam; sırada genel eksik/fazla değerlendirmesi ve canlıya çıkış yol haritası.

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
