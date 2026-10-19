# Kod Okuma Notları

Bu dosya kişisel öğrenme kaydı. Backend kodunu anlamak için Claude ile yapılan
sohbetlerin özeti. Yeni oturumda buradan devam edilir; her konu "Nerede kalındı"
bölümünde güncellenir.

## Nerede kalındı

**Son işlenen konu:** Oda listesi akışı (`GET /rooms`) uçtan uca:
frontend → `rooms.py` → `room_service.list_rooms` / `present_rooms` →
`realtime/state.py`. **Sıradaki:** ekonomi (`gift_service.py`,
`wallet_service.py` — bakiye değişimi, idempotency). Sonra diğer router ve
servisler yüzeysel, en son `realtime/hub.py`.

**Açık kalanlar:** `user_service.load_users_out` / `present_users`,
`schemas/room.py`.

**WebSocket temeli (2026-10-19):** projeden bağımsız dersler `learning/websocket/` altında (echo → herkese yayın → event/payload). Sırada: `voice:signal` ve sohbet mesajının `room_socket.py` + `hub.py` içindeki yolu, sonra ses sunucuları.

---

## 1. `main.py` — `lifespan` ve uygulama açılışı

- `lifespan` fonksiyonu `@asynccontextmanager` ile sarılı bir async generator.
  `yield`'in **üstü** = sunucu açılırken bir kez çalışan kod, `yield`'in
  **altı** = sunucu kapanırken çalışan kod.
- `yield`'i ilerleten FastAPI/Starlette'tir; biz "next" çağırmıyoruz, Starlette
  sunucu açılış/kapanışında bunu kendisi tetikliyor.
- `settings.is_production` → `environment == "production"` mı diye bakan bir
  `property`, sadece `True`/`False` döner.
  - `True` ise: `demo_mode` açıksa veya CORS `*` ise `RuntimeError` fırlatılır,
    sunucu hiç açılmaz (canlıda yanlış ayarla açılmaktan daha güvenli).
  - `False` (şu anki durum, development) ise: `engine.begin()` ile bağlantı
    açılıp transaction başlatılır, `connection.run_sync(Base.metadata.create_all)`
    çağrılır.
- `engine.begin()` → `engine` bizim nesnemiz (`create_async_engine(...)` ile
  kurulan bağlantı havuzu), `.begin()` SQLAlchemy'nin hazır metodu: bağlantı
  alır + transaction başlatır, blok bitince otomatik commit/rollback yapar.
- `run_sync` → `create_all` senkron bir fonksiyon, bağlantımız async; `run_sync`
  senkron fonksiyonu async bağlantı içinde çalıştırmamızı sağlıyor.
- `create_all` → `Base`'den miras alan (ve `models/__init__.py` üzerinden
  import edilmiş) tüm modellere bakıp eksik tabloları oluşturur, var olana
  dokunmaz.
- `demo_mode` (ayrı bir ayar, `is_production`'dan bağımsız): açıksa
  `seed.seed_database(db)` (veritabanına örnek kullanıcı/oda/hediye yazar) ve
  `seed.seed_live_state(room_state)` (bellekteki canlı oda durumunu — koltuk,
  dinleyici sayısı — doldurur, sunucu kapanınca silinir, her açılışta yeniden
  dolar) çalışır.

## 2. Router kayıt zinciri — `api_v1`, `include_router`

- Her router dosyasında değişken adı aynı: `router = APIRouter(...)`. Çakışmaz
  çünkü her biri kendi modülünün içinde yaşar; `main.py`'de `rooms.router`,
  `auth.router` gibi modül adıyla erişiliyor.
- `APIRouter` bir adres listesi gibi: `@router.get(...)` / `@router.post(...)`
  dekoratörleri listeye "bu adrese bu metodla istek gelirse bu fonksiyonu
  çalıştır" satırı ekler.
- `include_router(diğer_router)` → bir router'ın satırlarını başka bir
  router'a **kopyalar**, kopyalarken kendi prefix'ini öne ekler.
- Zincir: her modülün router'ı → `api_v1` (prefix `/api/v1`) → `app`. Sonuçta
  `app`'in içinde tek, birleşmiş bir route listesi oluşuyor; `/docs` bu listeyi
  gösteriyor.
- `room_socket.router` bilerek `api_v1`'e değil direkt `app`'e ekleniyor; o
  yüzden adresi `/ws/rooms/{room_id}` (başında `/api/v1` yok). `/health` de
  aynı şekilde sürümün dışında.
- Ara router (`api_v1`) zorunlu değil (`app.include_router(module.router,
  prefix="/api/v1")` de yazılabilirdi), ama ileride `/api/v2` açmak veya tüm
  v1 uçlarına ortak ayar eklemek kolaylaşıyor diye tercih edilmiş.

## 3. CORS — tarayıcı güvenliği

- `core/` klasörü ile CORS ayrı şeyler (isim benzerliği var, ilgisiz). CORS
  `main.py`'deki `CORSMiddleware`.
- Sorun: frontend (5500) ve backend (8000) portları farklı olduğu için tarayıcı
  bunları iki ayrı site sayar; bir sitenin JS'i başka sitenin cevabını
  okuyamaz, karşı taraf izin vermedikçe.
- `CORSMiddleware` ne yapıyor: isteğin `Origin` başlığına bakar, `allow_origins`
  listesindeyse cevaba `Access-Control-Allow-Origin` başlığı ekler.
- **Engellemeyi tarayıcı yapar, sunucu değil.** Sunucu sadece başlık ekler/
  eklemez; tarayıcı o başlığı görmezse JS'e cevabı vermez. Mobil uygulama/
  Postman bu kurala hiç bakmaz — CORS yalnızca tarayıcıyı ilgilendirir, asıl
  güvenlik token kontrolüdür.
- Canlıda `*` yasak: `*` = "her site API'me istek atabilir" demek.

## 4. Giriş akışı (`POST /auth/login`) — uçtan uca

Frontend tarafı:
1. `screens/auth.js` → `api.login({ username, password })`.
2. `api.js` → `POST /api/v1/auth/login`, henüz token yok, `Authorization`
   başlığı gönderilmiyor.
3. Tarayıcı farklı port olduğu için önce `OPTIONS` ile CORS ön kontrolü yapar.

Backend tarafı — **routers → services → core** katman ayrımı:
- `routers/auth.py` → sadece HTTP katmanı: JSON'u doğrulatır (`LoginRequest`
  şeması üzerinden, FastAPI otomatik), `db: DbSession` ile `get_db`'den oturum
  alır, işi `auth_service.login(db, data)`'ya devreder. **İş kuralı yok.**
- `services/auth_service.py` → iş kuralı burada: kullanıcıyı bul, parolayı
  `verify_password` ile kontrol et, hesap engelli mi bak, token'ları üret
  (`_issue_tokens`).
  - Kullanıcı yoksa bile sahte bir bcrypt hash ile kontrol yapılıyor (zamanlama
    saldırısına karşı — "kullanıcı yok" cevabının "parola yanlış" cevabından
    daha hızlı dönmesini engellemek için).
  - Hata mesajı da tek: hangisinin yanlış olduğu söylenmiyor (401
    `invalid_credentials`).
- `core/security.py` → saf teknik araç kutusu, karar yok: `create_access_token`
  (JWT imzalama), `verify_password` (bcrypt karşılaştırma, `asyncio.to_thread`
  ile ayrı thread'de — bcrypt bilerek yavaş, ana akışı kilitlememek için).
- Token'lar: **access token** (JWT, 15 dk, veritabanına yazılmaz, imza ile
  doğrulanır — stateless) + **refresh token** (rastgele uzun string, 30 gün,
  veritabanına SHA-256 hash'i yazılır, kendisi değil — sızarsa işe yaramasın).
- Önceden tek dosyada (`core/auth.py` benzeri) yapılan HTTP + karar + kripto
  işi şimdi üçe bölünmüş: router (HTTP), service (karar), core (mekanik).
  Sebep: 4 farklı akış (`register`/`login`/`guest`/`refresh`) aynı token
  üretme işini (`_issue_tokens`) tekrarsız paylaşıyor; test yazarken de HTTP'yi
  hiç karıştırmadan servisi direkt çağırabiliyorsun.

Cevap dönüşü:
- `response_model=TokenResponse` → fonksiyon **tamamen bitip** bir değer
  döndürdükten **sonra** devreye giriyor; FastAPI dönen nesneyi bu şemadan
  geçirip JSON'a çevirir.
- `response_model=` bir "özel syntax" değil, `router.post(...)` fonksiyonunun
  tanımlı bir parametre adı (FastAPI kütüphanesi öyle tanımlamış, biz
  `cevap_model` diyemeyiz — parametre adı bizim seçimimiz değil).
- Fonksiyona `-> TokenResponse` dönüş tipi yazsak, `response_model=` yazmaya
  bile gerek kalmaz — FastAPI tip ipucundan aynı şemayı otomatik çıkarır. İkisi
  aynı işi görür, biri elle (`response_model=`), biri otomatik (tip ipucu).
- Fazla alan varsa → hata yok, sessizce kesilip atılır (güvenlik filtresi gibi
  çalışıyor, ör. yanlışlıkla `password_hash` eklenseydi dışarı sızmazdı).
- Eksik alan / yanlış tip varsa → bu bizim hatamız sayılır, kullanıcıya genel
  **500 Internal Server Error** (detaysız) döner, detaylı Pydantic hatası
  sadece sunucu terminalinde (traceback) görünür.
- Girdi hatası (`RequestValidationError`, 422) ile çıktı hatası farkı: girdi
  hatası kullanıcının suçu → detaylı mesaj gösterilir; çıktı hatası bizim
  suçumuz → kullanıcıya detay verilmez (iç yapıyı göstermemek için bilinçli).

## 5. Dekoratör mekaniği (`@router.post(...)`)

- `@dekoratör` süslemesi, fonksiyonu tanımladıktan sonra "bunu bir işleme sok"
  demenin kısayolu: `login = router.post(...)(login)` ile aynı şey.
- `router.post(...)` çağrısı bir fonksiyon döner, o fonksiyon `login`'i alıp
  route listesine kaydeder ve geri verir.
- Fonksiyonun "biter, iş durur" sezgisi doğru — fark şu: öncesinde/sonrasında
  devreye giren ek katman (route kaydı, response_model filtresi) **sunucu
  açılırken bir kez kurulur**, her istekte yeniden kurulmaz.

## 6. Hata yönetimi — `core/errors.py` ve "try/except nerede?"

- Bizim kodumuzda üç `exception_handler` var:
  1. `AppError` → bizim `raise`'lediğimiz hatalar (`UnauthorizedError`,
     `NotFoundError`, `ConflictError` vb.) → `{code, detail}` JSON.
  2. `RequestValidationError` → **girdi** şeması hatalı (422).
  3. `StarletteHTTPException` → FastAPI'nin kendi ürettiği hatalar (404 vb.).
- **Çıktı** şeması hatası (`response_model` uyuşmazlığı) bu üçünün hiçbirine
  girmiyor — bizim kodumuzda onu yakalayan bir `try/except` **yok**.
- O hatayı asıl yakalayan, Starlette'in kütüphane içindeki en dıştaki genel
  sarmalayıcı (`ServerErrorMiddleware`): bizim yazmadığımız bir `try/except`,
  her isteği otomatik sarıyor. Yakalayamadığı (bizim handler'larımızın
  kapsamadığı) her hata buraya düşüyor → terminale tam traceback, kullanıcıya
  sade `{"detail": "Internal Server Error"}` + 500.
- Zincir: fonksiyon hata fırlatır → bizim 3 handler'dan biri eşleşir mi? →
  eşleşmezse en dıştaki genel ağ yakalar → genel 500.

---

## 7. Oda listesi / odaya girme akışı

- **`routers/rooms.py`** — auth'taki gibi ince HTTP katmanı: JSON doğrulama,
  `CurrentUserId`/`DbSession`, işi `room_service`'e devretme. Karar yok.

- **`services/room_service.py`** — Bir odanın bilgisi iki kaynaktan birleşiyor:
  **kalıcı** (ad, sahip, kategori → veritabanı) ve **canlı** (koltuklar,
  dinleyici sayısı → bellek deposu). Ayrılma sebebi: canlı bilgi saniyede
  defalarca değişiyor, her değişimde diske yazmak yavaş/gereksiz.
  - `present_rooms()` ikisini birleştirip `RoomOut`'a döker; **N+1 sorgu
    yok** — kaç oda olursa olsun kullanıcı bilgisi tek sorguda
    (`user_service.load_users_out`), koltuklar tek toplu çağrıda
    (`get_seats(room_ids)`) geliyor.
  - Koltuk işlemleri (`take_seat`/`leave_seat`/`toggle_mute`) hep aynı kalıp:
    odayı doğrula → canlı depoda değiştir → `publish_seats` ile odadaki
    herkese yeni düzeni yayınla → isteği atana son hali dön.

- **`realtime/state.py`** — `RoomStateStore` soyut sözleşme (ABC),
  `InMemoryRoomStateStore` şu anki uygulaması (Python sözlükleri: `_seats`,
  `_listeners`, `_last_seen`). Tasarım amacı: Redis'e geçince aynı sözleşmeyi
  uygulayan `RedisRoomStateStore` yazılacak, dosyanın en altındaki tek satır
  (`room_state = InMemoryRoomStateStore()`) değişecek, geri kalan kod
  dokunulmadan çalışacak.
  - **Kilit (lock) yok ama güvenli:** Python asyncio'da bir fonksiyon içinde
    `await` olmadığı sürece kesintiye uğramaz (cooperative scheduling).
    `take_seat` gibi metodların gövdesinde `await` yok → "iki kişi aynı anda
    aynı koltuğa oturdu" imkansız. Redis sürümünde aynı garanti Lua script /
    `HSETNX` ile sağlanacak.
  - `_listeners` kişi sayısı değil **bağlantı sayısı** tutar
    (`dict[kullanıcı, açık bağlantı sayısı]`) — aynı kişi iki sekmeden
    bağlanabildiği için. `add_listener`/`remove_listener` "bu kişinin
    İLK/SON bağlantısı mıydı" diye `bool` döner, koltuk boşaltma kararı ona
    göre verilir.

- **`realtime/hub.py`** — Oda id → o odaya bağlı WebSocket'ler sözlüğü tutan
  yayın merkezi. `publish()` bilerek ikiye bölünmüş (`publish` /
  `_deliver_local`): Redis'e geçince `publish` mesajı pub/sub kanalına
  bırakacak, her sunucu kendi `_deliver_local`'ıyla kendi bağlantılarına
  dağıtacak — çok sunuculu kurulumda A sunucusundaki kullanıcı B
  sunucusundakine ulaşabilsin diye arayüz şimdiden buna göre yazılmış.

- **`realtime/room_socket.py`** — WebSocket el sıkışması, 4 adım:
  1. **Önce `accept()`, sonra doğrula.** Reddederken istemciye anlamlı kapanış
     kodu (`4401` token yenile, `4404` oda yok) gönderebilmek için önce
     bağlantı kabul ediliyor.
  2. DB oturumu token/oda kontrolü için açılıp **hemen kapatılıyor** —
     WebSocket saatlerce açık kalabilir, o süre boyunca DB bağlantısı meşgul
     edilseydi binlerce kullanıcıda bağlantı havuzu (connection pool)
     tükenirdi.
  3. Mesaj döngüsünde hız sınırı (`RateLimiter` sınıfı, her bağlantıya kendi
     örneği: sohbet 5sn'de 5, zar 1.5sn'de 1).
  4. **Sunucu otoritedir** somut olarak burada: zar `secrets.randbelow` ile
     sunucuda atılır (istemcininki yok sayılır), sohbette `user` alanı
     token'dan doldurulur (başkasının adına yazılamaz), `gift:sent`
     istemciden gelirse yok sayılır (gerçek yayın yalnızca
     `gift_service.send_gift` başarılı olunca sunucudan yapılır).
  - `finally` bloğu ne olursa olsun (normal çıkış/hata) çalışır: hub'dan
    çıkar, dinleyiciyi düşür, son bağlantıysa koltuğu boşalt ve yeni koltuk
    düzenini yayınla.

- **`realtime/events.py`** — Event adları (`alan:eylem` biçiminde) sabit
  olarak burada tanımlı, elle yazılmıyor — yazım hatası olursa program daha
  çalışmadan fark edilir. İstemciden gelen veri şemaları da burada
  (`ChatMessageIn`): `text` alanı dışındakiler (`user` gibi) bilerek
  okunmaz/yok sayılır.

**Genel ilke (auth akışıyla aynı):** router hiçbir şeye karar vermiyor,
servis karar veriyor, altyapı (`state`/`hub`) yalnızca mekanik sağlıyor.

---

## 8. Oda listesi (`GET /rooms`) — uçtan uca

1. **Frontend** (`home.js`, `explore.js`): `api.listRooms({category, query})` → `api.js` URL'yi kurar, `Bearer` ekler, `fetch` yapar.
2. **Router** (`rooms.py:list_rooms`): `CurrentUserId` token'dan `user_id` çıkarır, `DbSession` oturum açar; `category`, `query`, `limit`, `offset` URL'den gelir ve kurallarından geçer.
3. **Servis** (`room_service.list_rooms`): aktif odalar → kategori süzmesi (`for_you` = hepsi) → arama (`ILIKE`, özel karakterler kaçırılır) → `id DESC` → `offset`/`limit`. Sonuç `present_rooms`'a verilir.
4. **Birleştirme** (`present_rooms`): her oda için `ensure_room`; sonra `get_seats`, `listener_counts`, `room_ranks` (hepsi `state.py`); sahip ve koltuktaki kullanıcı id'leri tek kümede → `load_users_out` tek sorgu; oda başına `RoomOut`.
5. **Dönüş:** liste JSON olur. `home.js` `hourly_rank`'e göre sıralayıp kartları çizer; `seats` dizisinden koltuk düzenini çizer (`user` `null` ise boş koltuk).

Dikkat: `viewer_id` oda listesini değiştirmez; sadece kullanıcıya özel alanları etkiler.

---

## 9. Öğrenilen kavramlar (sade özet)

- **Bearer / HTTPBearer / `auto_error`:** `Authorization: Bearer <token>` başlığı. `HTTPBearer` başlığı okur, token'ı doğrulamaz. `auto_error=False` ile başlık yoksa hata bizim JSON biçimimizle (401) döner.
- **`Annotated[Tip, not]`:** Python notu görmezden gelir; FastAPI notun içindeki `Depends`, `Query`, `Header` gibi işaretlere bakar.
- **`Depends(f)`:** "bu değeri `f` fonksiyonunu çalıştırarak al" talimatı. `DbSession` ve `CurrentUserId` birer takma ad.
- **`Query` / `Path` / `Header` / `Body`:** değerin isteğin hangi bölgesinden okunacağı. Düz tip yazmak da çoğu zaman `Query` gibi davranır; `Query(ge=1)` gibi ek kurallar için kullanılır.
- **`dataclass` vs Pydantic:** `dataclass` sunucunun iç verisi için (tip kontrolü yok). Pydantic dışarıdan gelen/giden veri için (doğrulama ve çevirme).
- **Somut vs abstract metot:** abstract olan alt sınıfa "bunu sen yaz" zorunluluğu koyar. `RoomStateStore` bu şekilde bir sözleşme; `InMemory` ve ileride `Redis` uygulaması.
- **`await` ve tek iş parçacığı:** `await` olmayan bir fonksiyon bitene kadar başka async iş araya giremez. Bu yüzden bellek deposunda kilit yok; `await` eklenirse bu garanti bozulur.
- **`self`:** metodun çağrıldığı depo nesnesi; `self._seats` o nesnenin koltuk defteri.

## Dosya haritası (şimdiye kadar değinilenler)

- `app/main.py` — giriş noktası, `lifespan`, router/middleware bağlama
- `app/core/config.py` — `settings` (ortam ayarları, `.env`)
- `app/core/database.py` — `engine`, `SessionLocal`, `Base`, `get_db`
- `app/core/security.py` — bcrypt + JWT mekaniği (karar yok, sadece araç)
- `app/core/errors.py` — `AppError` ailesi + 3 exception handler
- `app/routers/auth.py` — `/auth` HTTP katmanı
- `app/services/auth_service.py` — giriş/kayıt/token iş kuralları
- `app/schemas/auth.py` — `LoginRequest`, `TokenResponse` vb.
- `app/routers/rooms.py` — `/rooms` HTTP katmanı (liste, oluştur, koltuk, mute)
- `app/services/room_service.py` — oda + canlı durum birleştirme, koltuk
  işlemleri
- `app/schemas/room.py` — `RoomOut`, `SeatOut`, `RoomCreateRequest`
- `app/realtime/state.py` — `RoomStateStore` sözleşmesi + bellek içi uygulama
  (koltuk, dinleyici, çevrimiçi)
- `app/realtime/hub.py` — oda yayın merkezi (`publish`/`_deliver_local`)
- `app/realtime/room_socket.py` — `/ws/rooms/{room_id}` canlı hat (tam işlendi)
- `app/realtime/events.py` — event adları + istemci şemaları
- `frontend/js/api.js`, `frontend/js/screens/auth.js` — giriş ekranının
  istek/token saklama kısmı
- `app/core/deps.py` — `DbSession`, `CurrentUserId`, `CurrentUser` takma adları
