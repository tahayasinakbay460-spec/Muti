# Geçmiş

Projede yapılan işlerin kaydı.

- **Şu an neredeyiz** bölümü güncel durumu özetler; her çalışma sonunda güncellenir.
- **Kayıtlar** bölümünde en yeni kayıt en üsttedir. Her kayıt aynı sırayı izler: amaç, ne yapıldı, doğrulama, açık kalanlar.

---

## Şu an neredeyiz

**Aşama:** Web demo. Frontend ekranları hazır ve gerçek backend'e bağlı (`USE_MOCK = false`).

**Çalışan:** giriş/kayıt/misafir, oda listesi, oda içi sohbet, koltuklar, zar oyunu, hediye gönderme, coin satın alma, özel mesajlar, takip, profil, cüzdan.

**Kod okuma turu (2026-10-14):** Auth, oda listesi akışı (`list_rooms` → `present_rooms` → `realtime/state.py`) ve `room_socket` okundu. Sırada ekonomi (`gift_service`, `wallet_service`) derinlemesine; diğer router/servisler yüzeysel; sonra `hub.py`.

**Sıradaki adım:** `start.bat` çalıştırıp `http://127.0.0.1:5500` adresinde `muti` / `demo1234` ile giriş yapmak ve ekranları elle denemek. Şimdiye kadar yalnızca otomatik testler çalıştı.

### Henüz elle denenmeyenler

- Ekranlar tarayıcıda denenmedi.
- Telefondan erişim denenmedi. Windows Güvenlik Duvarı 8000 ve 5500 portlarına izin vermeli.

### Eksik özellikler

| Eksik | Not |
|---|---|
| Gerçek ses (WebRTC) | Koltuktaki "konuşuyor" halkası bu yüzden yanmıyor |
| Özel mesajlarda anlık bildirim | Karşı tarafın mesajı sohbet yeniden açılınca görünür |
| Oda takibi ("Takip Et") ve "Profili Düzenle" | Yalnızca arayüz var, backend ucu yok |
| Oda rolleri (`admin` / `vip`) ve koltuk kilitleme | Yazılmadı |
| Admin uçları | Eski admin sayfası silindi, yenisi yazılmadı |
| HTTP hız sınırı | Özellikle giriş denemeleri için gerekli |
| Görsel yükleme | `assets/` içindeki görseller hâlâ yer tutucu |

### Bilinen davranışlar

- Bağlantısı kopan kullanıcının koltuğu hemen boşalır; kısa kopmalar için bekleme süresi yok.
- Hiç WebSocket açmadan REST ile koltuğa oturan kullanıcı koltukta kalır.

### Demo kısayolları

Kodda "DEMO KISAYOLU" diye işaretlidir. Mobil/canlı aşamasında değiştirilecek.

| Kısayol | Yeri | Canlıda olması gereken |
|---|---|---|
| SQLite | `core/config.py` | PostgreSQL (`postgresql+asyncpg://`) |
| Tablolar `create_all` ile oluşuyor | `main.py` | Alembic migration |
| Oda durumu ve yayın bellek içi (tek sunucu süreci) | `realtime/state.py`, `realtime/hub.py` | Redis (aynı sözleşmeyle `RedisRoomStateStore`, pub/sub) |
| Satın alma ödeme doğrulamadan coin ekliyor | `wallet_service.purchase` | App Store / Google Play makbuz doğrulama |
| Banner ve profil ekleri sabit içerik | `demo/content.py` | Tablo + servis |
| Zaman etiketlerini ("3 gün önce") sunucu üretiyor | `core/timefmt.py` | İstemci `created_at` alanından üretir |
| Oda sırası ve liderlik her istekte hesaplanıyor | `state.room_ranks`, `gift_service.list_top_gifters` | Redis sorted set |
| Örnek odalarda sahte dinleyici sayısı | `demo/seed.py` | Kaldırılır |

---

# Kayıtlar

## 2026-10-14 — Oda listesi akışı kod okuma turu

**Amaç:** Kod değişikliği yok; kullanıcı `GET /rooms` akışını frontend'den veritabanı ve bellek deposuna kadar anlamak istedi.

### Konuşulanlar

- **Frontend:** `home.js` ve `explore.js` `api.listRooms` çağırıyor; `api.js` URL'yi kurup `Bearer` başlığını ekliyor. `limit`/`offset` gönderilmiyor.
- **Router (`rooms.py`):** `CurrentUserId` ve `DbSession` bağımlılıkları; `category`, `query`, `limit` (1-50), `offset` (≥0) URL'den okunuyor.
- **Servis (`list_rooms`):** aktif odalar, kategori süzmesi (`for_you` = hepsi), `ILIKE` ile arama (`%` ve `_` kaçırılıyor), `id DESC`, `limit`/`offset`.
- **`present_rooms`:** odaları `ensure_room` ile bellekte hazırlıyor; `get_seats`, `listener_counts`, `room_ranks` ile canlı bilgiyi alıyor; sahip ve koltuktaki kullanıcı id'lerini toplayıp tek sorguda `load_users_out` çağırıyor; oda başına `RoomOut` kuruyor.
- **`state.py`:** `ensure_room` yoksa boş koltuk listesi oluşturur. `get_seats` kopya döndürür. `listener_counts` kişi sayısını (`len`) verir. `room_ranks` tüm odaları kişi sayısına göre sıralayıp konum verir (demo kısayolu).
- **`viewer_id`:** isteği atan kişi. Oda listesinin kendisini değiştirmez; yalnızca kullanıcıya özel alanlar için (`user_service.present_users`, `is_me`, takip durumu) kullanılır.
- **`dict` içinde `dict`:** `_listeners` = `{oda: {kullanıcı: bağlantı_sayısı}}`; kişi sayısı iç sözlüğün anahtar sayısıdır.
- **`Annotated` / `Depends` / `Query`:** `Annotated` tipin yanına not iliştirir, FastAPI notu okur; `Depends` değeri bir fonksiyondan alır; `Query`, `Path`, `Header`, `Body` değerin istekte hangi bölgeden geleceğini söyler.

### Doğrulama

Kod değişmedi, test çalıştırılmadı. Tamamen kavramsal/öğretici bir oturum.

### Açık kalanlar

- `user_service.load_users_out` ve `present_users` içi okunmadı.
- `schemas/room.py` (`RoomOut`, `SeatOut`) okunmadı.
- `list_rooms`'un SQL kısmı özetle geçildi, satır satır değil.
- Frontend `limit`/`offset` göndermiyor; sayfalama arayüzü yok, ilk 30 oda görünüyor.

---

## 2026-10-13 — Kimlik doğrulama (JWT + refresh token) kod okuma turu

**Amaç:** Kod değişikliği yok; kullanıcı `backend/app/core/security.py`, `app/core/deps.py` ve `app/services/auth_service.py` dosyalarındaki JWT/refresh token mekanizmasını, masaüstündeki ayrı bir proje olan `EVA` (`EVA/backend/app/core/auth.py`, `python-jose`, tek token, 7 gün) ile karşılaştırarak öğrenmek istedi.

### Konuşulanlar

- **Eva vs TopTop:** Eva tek JWT (7 gün, iptal edilemez) kullanıyor; TopTop access (JWT, 15 dk, stateless) + refresh (rastgele string, 30 gün, DB'de hash'li, rotation + reuse detection) ayrımını kullanıyor. Eva `python-jose`, TopTop `PyJWT`.
- **JWT mekaniği:** `encode`/`decode`'un ne yaptığı (header.payload.signature, base64url + HMAC-SHA256), `exp`/`iat`/`type` alanlarının anlamı, imza doğrulamasının nasıl çalıştığı, payload'ın şifreli değil sadece kodlanmış olduğu (secret_key olmadan okunabilir) — canlı Python örnekleriyle ve PyJWT'nin kendi kaynağına (`api_jwt.py`, `api_jws.py`) bakılarak gösterildi.
- **bcrypt vs JWT:** ikisinin tamamen ayrı kütüphaneler olduğu, `hash_password`'ün JWT ile ilgisi olmadığı; `_DUMMY_PASSWORD_HASH`'in neden var olduğu (timing attack'e karşı sabit süreli reddetme).
- **`auth_service.py` akışı:** `_issue_tokens`'ı kimin çağırdığı (register/login/login_as_guest/refresh), `db.commit()` vs `db.flush()` farkı, `User.id`'nin flush anında DB tarafından üretilmesi, `register()`'daki ön kontrol ile `_create_user`'daki `flush`+`IntegrityError` kontrolünün neden ikisinin de gerekli olduğu (race condition), `db.refresh(user)`'ın "refresh token" ile ilgisiz bir ORM metodu olduğu.
- **Çoklu cihaz / `refresh()`:** `refresh_tokens` tablosunda `user_id`'nin unique olmadığı (bir kullanıcı → çok satır), `token_hash`'in unique olduğu; `refresh()`'in satır satır ne yaptığı (rotation, `WHERE revoked_at IS NULL` ile yarış durumu engeli, reuse tespitinde `_revoke_all`); refresh token süresinin "sliding window" olduğu (her kullanımda +30 gün yenilendiği için aktif kullanıcıda pratikte hiç bitmediği).
- Dependency injection: `Depends(get_db)`'nin yalnızca router'ın kendi imzasında bir kez çağrıldığı, alt fonksiyonlardaki `db: AsyncSession` tipinin sadece "bana zaten açılmış bir session ver" anlamına geldiği.

### Doğrulama

Kod değişmedi, test çalıştırılmadı. Tamamen kavramsal/öğretici bir oturum.

### Açık kalanlar

Yok — bir önceki kayıttaki "henüz elle denenmeyenler" ve "eksik özellikler" listeleri hâlâ geçerli (bkz. "Şu an neredeyiz").

---

## 2026-10-10 — Telefondan (aynı Wi-Fi) erişim

**Amaç:** Demoyu telefonun tarayıcısından açabilmek. Backend yalnızca `127.0.0.1` adresini dinlediği için telefondan ulaşılamıyordu.

### Ne yapıldı

- **`core/config.py`:** `HOST` ve `PORT` ayarı eklendi (varsayılan `127.0.0.1:8000`). `cors_lan_origin_regex` ile yerel ağ adreslerinden (192.168.x.x, 10.x.x.x, 172.16-31.x.x, port 5500) açılan frontend'e izin veriliyor.
- **`main.py`:** sunucu `settings.host` adresinde açılıyor. Yerel ağ CORS izni yalnızca geliştirmede geçerli, canlıda kapalı.
- **`backend/.env`:** `HOST=0.0.0.0` eklendi (bu bilgisayarda telefondan erişim açık). `.env.example` varsayılanı `127.0.0.1`.

### Nasıl kullanılır

Telefonda `http://<bilgisayarın IP'si>:5500` açılır. Frontend, backend adresini sayfanın açıldığı adresten türetir; ayrıca ayar gerekmez.

### Doğrulama

Testler 16/16 geçti. **Telefondan elle denenmedi.**

---

## 2026-10-09 — Kullanılmayan dosyalar silindi, frontend backend'e bağlandı

**Amaç:** Depoyu sadeleştirmek ve web demoyu sahte veri yerine gerçek API + WebSocket ile çalıştırmak.

### Silinenler

| Silinen | Neydi | Geri getirilebilir mi |
|---|---|---|
| `frontend/legacy/` | Eski Tailwind prototipi | Evet, git geçmişinde |
| `frontend/admin.html` | Kaldırılmış eski uçlara bağlı admin sayfası | Evet, git geçmişinde |
| `backend/toptop.db` | Eski prototipin veritabanı (12 test kullanıcısı, 0 işlem) | Hayır, git'te yoktu |
| `backend/env` | Tek satırlık boş ayar dosyası | Hayır, git'te yoktu |
| `backend/.pytest_cache/` | Test önbelleği | Kendiliğinden yeniden oluşur |

`mock-data.js` ve `mockApi` **silinmedi**: `USE_MOCK = true` ile backend olmadan demo göstermek hâlâ mümkün.

### Ne yapıldı

**Ayarlar — `js/config.js`**

- `USE_MOCK = false`.
- Backend adresi sayfanın açıldığı ada göre seçiliyor (`127.0.0.1` ya da `localhost`); ikisi de CORS listesinde.
- Görseli olmayan kullanıcı için `DEFAULT_AVATAR_URL` / `DEFAULT_COVER_URL`.

**Giriş ve token — `js/api.js`**

- 401 gelince `/auth/refresh` ile token yenilenir ve istek bir kez tekrarlanır.
- Aynı anda gelen 401'ler tek yenileme isteğini bekler (refresh token tek kullanımlık olduğu için).
- Yenilenemezse token'lar silinir ve `#/auth` açılır.
- Çıkış, sunucudaki oturumu da kapatır.
- Backend kapalıysa "Sunucuya ulaşılamıyor" hatası gösterilir.

**Para harcayan istekler — `js/api.js`**

- `sendGift` ve `purchaseCoins` `Idempotency-Key` gönderiyor. Bağlantı kopup istek iki kez gitse bile bakiye bir kez düşer.

**Oda kanalı — `js/realtime.js`**

- Bağlantı açılmadan gönderilenler kuyruğa alınır.
- Bağlantı kopunca yeniden bağlanır (en fazla 5 deneme). `4401` kapanış kodunda önce token yenilenir.
- İstemci artık yalnızca `chat:message { text }` ve `game:dice_rolled {}` gönderiyor.

**Oda ekranı — `js/screens/room.js`**

- Zar sonucu istemcide üretilmiyor; `game:dice_rolled` event'inden gösteriliyor.
- Koltuklar `room:seats_updated` ile güncelleniyor.
- Hediye animasyonu sunucunun `gift:sent` yayınından geliyor.
- Sunucunun `error` event'i bildirim olarak gösteriliyor.
- Odaya girişteki sahte sohbet satırları mock kanala taşındı.

**Diğer ekranlar**

- `messages.js`: sahte otomatik yanıt yalnızca mock'ta.
- `profile.js`, `home.js`, `ui.js`: yaşı/şehri/görseli olmayan kullanıcı (yeni kayıt, misafir) "null" yazmadan gösteriliyor.
- `auth.js`: demo hesabı ipucu (`muti` / `demo1234`), misafir girişinde hata yakalama.

### Doğrulama

`api.js` ve `realtime.js`, Node üzerinden çalışan backend'e karşı geçici bir veritabanıyla denendi. 24 kontrolün hepsi geçti:

- giriş, 401'de otomatik yenileme, oturum sonu
- oda listesi, oda açma
- WebSocket: sohbet, zar, koltuk, hediye yayını
- satın alma, mesajlar, takip
- misafir girişi, kayıt

**Ekranlar tarayıcıda elle denenmedi.**

### Açık kalanlar

- Özel mesajlarda anlık bildirim yok: karşı tarafın mesajı sohbet yeniden açılınca görünür.
- "Konuşuyor" halkası gerçek modda hiç yanmaz (`room:speaking` WebRTC ile gelecek).
- Odadaki "Takip Et" (oda takibi) ve profildeki "Profili Düzenle" hâlâ yalnızca arayüz; backend ucu yok.
- Kalan `assets/` görselleri hâlâ yer tutucu.

---

## 2026-10-09 — Backend sıfırdan yazıldı (`/api/v1` + oda WebSocket'i)

**Amaç:** Frontend'in `js/api.js` içindeki `httpApi` sözleşmesini ve `js/realtime.js` içindeki oda kanalını karşılayan; modüler, okunabilir, mobil istemciye uygun bir backend.

### Eski prototip neden kaldırıldı

- Parolalar düz yazı saklanıyordu.
- `SECRET_KEY` kodun içindeydi.
- Adlar Türkçeydi.
- Bakiye "oku-sonra-yaz" ile değişiyordu (çifte harcamaya açık).

Kaldırılan dosyalar: `app/database.py`, `app/routers/{users,jeton,admin}.py`, `app/models/{users,transactions}.py`, `core/auth.py`, `schemas/users.py`, `seed_users.py`, `reset_db.py`, `inspect_db.py`. Yeni veritabanı `backend/app.db`.

### Ne yapıldı

**Yapı**

- Katmanlı: `routers → services → models`, yanında `schemas`, `core`, `realtime`, `demo`. Dosya haritası `CLAUDE.md` içinde.
- Her hata `{ "code": "...", "detail": "Türkçe mesaj" }` biçiminde döner (frontend'in beklediği biçim).

**Kimlik**

- Kayıt, giriş, misafir girişi, token yenileme, çıkış.
- Access token: JWT, 15 dakika, veritabanına gitmeden doğrulanır.
- Refresh token: rastgele, 30 gün, veritabanında hash'i saklanır, her kullanımda yenilenir. İptal edilmiş bir token tekrar gelirse kullanıcının tüm oturumları kapanır.
- Parolalar bcrypt ile hash'lenir.

**Kullanıcılar**

- Profil, takip et/bırak (sayaçlar veritabanında atomik artar), önerilen kullanıcılar.

**Odalar**

- Listeleme (kategori + arama), oluşturma, koltuğa oturma/kalkma, mikrofon.
- Kalıcı bilgi veritabanında; koltuk/dinleyici/çevrimiçi bilgisi `realtime/state.py` deposunda.

**Ekonomi**

- Hediye kataloğu, hediye gönderme, coin paketleri, satın alma, işlem geçmişi, en çok hediye gönderenler.
- Bakiye yalnızca `wallet_service.change_balance` ile değişir: tek `UPDATE ... WHERE coin_balance >= x` komutu.
- Her hareket `transactions` defterine yazılır.
- `Idempotency-Key` başlığı ile tekrar eden istek ikinci kez işlenmez.
- Hediyede alıcıya tutarın %50'si elmas olarak geçer (`GIFT_RECEIVER_SHARE_PERCENT`).

**Özel mesajlar**

- Sohbet listesi, sohbet açma, mesaj gönderme, okunmamış sayacı.

**WebSocket — `/ws/rooms/{id}?token=`**

- Event'ler: `chat:message`, `game:dice_rolled`, `gift:sent`, `room:user_joined`, `room:listener_count`, `room:seats_updated`, `error`.
- Sunucu otoritedir: mesajın sahibini token'dan bilir, zarı sunucu atar, hediye yalnızca gerçekten ödenmişse yayınlanır.
- Sohbet ve zar için bağlantı başına hız sınırı var.

**Örnek veri**

- `mock-data.js` ile aynı kullanıcılar/odalar/hediyeler ilk açılışta yüklenir.
- Tüm örnek hesapların parolası `demo1234` (ana kullanıcı: `muti`).

**Diğer**

- `requirements.txt` yenilendi: `python-jose` çıktı; `PyJWT`, `aiosqlite`, `pydantic-settings`, `pytest`, `httpx` girdi.
- `backend/.env` yerelde rastgele `SECRET_KEY` ile oluşturuldu, `.env.example` eklendi.
- `start.bat` backend'i artık `venv` içindeki Python ile başlatıyor.
- `CLAUDE.md` güncellendi.

### Doğrulama

`backend/tests/` altında 16 uçtan uca test; hepsi geçiyor. Aynı anda 12 hediye isteğiyle çifte harcama denemesi dahil.

### Açık kalanlar

- ~~Frontend henüz backend'e bağlı değil.~~ Bir sonraki kayıtta yapıldı.
- ~~`frontend/admin.html` çalışmıyor.~~ Bir sonraki kayıtta silindi. Yeni admin uçları hâlâ yazılmadı.
- Yok: WebRTC (gerçek ses, `room:speaking`), HTTP hız sınırı (giriş denemeleri için gerekli), oda rolleri (`admin`/`vip`) ve koltuk kilitleme ucu, özel mesajlarda anlık bildirim, görsel yükleme.
- Bağlantısı kopan kullanıcının koltuğu hemen boşalıyor (kısa kopmalar için bekleme süresi yok); hiç WebSocket açmadan REST ile oturan kullanıcı koltukta kalır.
