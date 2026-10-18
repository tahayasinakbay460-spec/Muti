# Geçmiş

Projede yapılan işlerin kaydı. En yeni kayıt en üstte. Her kayıt: ne yapıldı, neden, hangi dosyalar, açık kalanlar.

---

## 2026-10-10 — Telefondan (aynı Wi-Fi) erişim

**Amaç:** Demoyu telefonun tarayıcısından açabilmek. Backend yalnızca `127.0.0.1` adresini dinlediği için telefondan ulaşılamıyordu.

- `core/config.py`: `HOST` ve `PORT` ayarı (varsayılan `127.0.0.1:8000`); `cors_lan_origin_regex` ile yerel ağ adreslerinden (192.168.x.x, 10.x.x.x, 172.16-31.x.x, port 5500) açılan frontend'e izin.
- `main.py`: sunucu `settings.host` adresinde açılıyor; yerel ağ CORS izni yalnızca geliştirmede geçerli, canlıda kapalı.
- `backend/.env`: `HOST=0.0.0.0` eklendi (bu bilgisayarda telefondan erişim açık). `.env.example` varsayılanı `127.0.0.1`.
- Telefondan adres: `http://<bilgisayarın IP'si>:5500` (frontend backend adresini sayfanın açıldığı addan türetiyor).
- Testler: 16/16 geçti. **Telefondan elle denenmedi**; Windows Güvenlik Duvarı 8000 ve 5500 portlarına izin vermeli.

---

## 2026-10-09 — Kullanılmayan dosyalar silindi, frontend backend'e bağlandı

**Amaç:** Depoyu sadeleştirmek ve web demoyu sahte veri yerine gerçek API + WebSocket ile çalıştırmak.

### Silinenler

- `frontend/legacy/` (eski Tailwind prototipi) ve `frontend/admin.html` (kaldırılmış eski uçlara bağlıydı). İkisi de git geçmişinde duruyor.
- `backend/toptop.db` (eski prototipin veritabanı; 12 test kullanıcısı, 0 işlem), `backend/env` (tek satırlık boş ayar dosyası), `backend/.pytest_cache/`. Bunlar git'te yoktu, geri getirilemez.
- `mock-data.js` ve `mockApi` **silinmedi**: `USE_MOCK = true` ile backend olmadan demo göstermek hâlâ mümkün.

### Ne yapıldı

- `js/config.js`: `USE_MOCK = false`. Backend adresi sayfanın açıldığı ada göre seçiliyor (`127.0.0.1` ya da `localhost`), ikisi de CORS listesinde. Görseli olmayan kullanıcı için `DEFAULT_AVATAR_URL` / `DEFAULT_COVER_URL`.
- `js/api.js`: 401 gelince `/auth/refresh` ile token yenilenip istek bir kez tekrarlanıyor. Aynı anda gelen 401'ler tek yenileme isteğini bekler (refresh token tek kullanımlık). Yenilenemezse token'lar silinir ve `#/auth` açılır. `sendGift` ve `purchaseCoins` `Idempotency-Key` gönderiyor. Çıkış sunucudaki oturumu da kapatıyor. Backend kapalıysa "Sunucuya ulaşılamıyor" hatası.
- `js/realtime.js`: WebSocket kanalı bağlantı açılmadan gönderilenleri kuyruğa alıyor; kopunca yeniden bağlanıyor (en fazla 5 deneme), `4401` kapanış kodunda önce token yeniliyor. İstemci artık yalnızca `chat:message { text }` ve `game:dice_rolled {}` gönderiyor.
- `js/screens/room.js`: zar sonucu istemcide üretilmiyor, `game:dice_rolled` event'inden gösteriliyor. Koltuklar `room:seats_updated` ile güncelleniyor. Hediye animasyonu sunucunun `gift:sent` yayınından geliyor. Sunucunun `error` event'i bildirim olarak gösteriliyor. Odaya girişteki sahte sohbet satırları mock kanala taşındı.
- `js/screens/messages.js`: sahte otomatik yanıt yalnızca mock'ta.
- `js/screens/profile.js`, `home.js`, `ui.js`: yaşı/şehri/görseli olmayan kullanıcı (yeni kayıt, misafir) "null" yazmadan gösteriliyor.
- `js/screens/auth.js`: demo hesabı ipucu (`muti` / `demo1234`), misafir girişinde hata yakalama.

### Doğrulama

`api.js` ve `realtime.js` Node üzerinden çalışan backend'e karşı denendi (geçici veritabanıyla): giriş, 401'de otomatik yenileme, oda listesi, WebSocket sohbet/zar/koltuk/hediye yayını, satın alma, mesajlar, takip, oda açma, misafir, kayıt, oturum sonu — 24 kontrolün hepsi geçti. **Ekranlar tarayıcıda elle denenmedi.**

### Açık kalanlar

- Özel mesajlarda anlık bildirim yok: karşı tarafın mesajı sohbet yeniden açılınca görünür.
- "Konuşuyor" halkası gerçek modda hiç yanmaz (`room:speaking` WebRTC ile gelecek).
- Odadaki "Takip Et" (oda takibi) ve profil "Profili Düzenle" hâlâ yalnızca arayüz; backend ucu yok.
- Kalan `assets/` görselleri hâlâ yer tutucu.

---

## 2026-10-09 — Backend sıfırdan yazıldı (`/api/v1` + oda WebSocket'i)

**Amaç:** Frontend'in `js/api.js` içindeki `httpApi` sözleşmesini ve `js/realtime.js` içindeki oda kanalını karşılayan; modüler, okunabilir, mobil istemciye uygun bir backend.

### Ne yapıldı

- **Eski prototip kaldırıldı:** `app/database.py`, `app/routers/{users,jeton,admin}.py`, `app/models/{users,transactions}.py`, `core/auth.py`, `schemas/users.py`, `seed_users.py`, `reset_db.py`, `inspect_db.py`. Sebep: parolalar düz yazı saklanıyordu, `SECRET_KEY` kodun içindeydi, adlar Türkçeydi, bakiye "oku-sonra-yaz" ile değişiyordu (çifte harcamaya açık). Eski `toptop.db` dosyasına dokunulmadı; yeni veritabanı `backend/app.db`.
- **Katmanlı yapı kuruldu:** `routers → services → models`, yanında `schemas`, `core`, `realtime`, `demo`. Dosya haritası `CLAUDE.md` içinde.
- **Kimlik:** kayıt, giriş, misafir girişi, token yenileme, çıkış. Access token JWT (15 dk, veritabanına gitmeden doğrulanır), refresh token rastgele (30 gün, veritabanında hash'i saklanır, her kullanımda yenilenir; iptal edilmiş token tekrar gelirse kullanıcının tüm oturumları kapanır). Parolalar bcrypt.
- **Kullanıcılar:** profil, takip et/bırak (sayaçlar veritabanında atomik artar), önerilen kullanıcılar.
- **Odalar:** listeleme (kategori + arama), oluşturma, koltuğa oturma/kalkma, mikrofon. Kalıcı bilgi veritabanında; koltuk/dinleyici/çevrimiçi bilgisi `realtime/state.py` deposunda.
- **Ekonomi:** hediye kataloğu, hediye gönderme, coin paketleri, satın alma, işlem geçmişi, en çok hediye gönderenler. Bakiye yalnızca `wallet_service.change_balance` ile değişir: tek `UPDATE ... WHERE coin_balance >= x` komutu, her hareket `transactions` defterine yazılır, `Idempotency-Key` başlığı ile tekrar eden istek ikinci kez işlenmez. Hediyede alıcıya tutarın %50'si elmas olarak geçer (`GIFT_RECEIVER_SHARE_PERCENT`).
- **Özel mesajlar:** sohbet listesi, sohbet açma, mesaj gönderme, okunmamış sayacı.
- **WebSocket** `/ws/rooms/{id}?token=`: `chat:message`, `game:dice_rolled`, `gift:sent`, `room:user_joined`, `room:listener_count`, ek olarak `room:seats_updated` ve `error`. Sunucu otoritedir: mesajın sahibini token'dan bilir, zarı sunucu atar, hediye yalnızca gerçekten ödenmişse yayınlanır. Sohbet ve zar için bağlantı başına hız sınırı var.
- **Hata biçimi:** her hata `{ "code": "...", "detail": "Türkçe mesaj" }` döner (frontend'in beklediği biçim).
- **Örnek veri:** `mock-data.js` ile aynı kullanıcılar/odalar/hediyeler ilk açılışta yüklenir. Tüm örnek hesapların parolası `demo1234` (ana kullanıcı: `muti`).
- **Testler:** `backend/tests/` altında 16 uçtan uca test; hepsi geçiyor. Aynı anda 12 hediye isteğiyle çifte harcama denemesi dahil.
- **Diğer:** `requirements.txt` yenilendi (`python-jose` çıktı, `PyJWT`, `aiosqlite`, `pydantic-settings`, `pytest`, `httpx` girdi). `backend/.env` yerelde rastgele `SECRET_KEY` ile oluşturuldu, `.env.example` eklendi. `start.bat` backend'i artık `venv` içindeki Python ile başlatıyor. `CLAUDE.md` güncellendi.

### Demo kısayolları (kodda "DEMO KISAYOLU" diye işaretli)

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

### Açık kalanlar

- **Frontend henüz backend'e bağlı değil** (`js/config.js` içinde `USE_MOCK = true`). Bağlarken: `api.js` içinde 401 `token_expired` gelince `/auth/refresh` çağrılmalı; `sendGift` ve `purchaseCoins` `Idempotency-Key` göndermeli; zar panelindeki sonuç istemcide üretilmek yerine `game:dice_rolled` event'inden gösterilmeli; koltuklar `room:seats_updated` ile güncellenmeli.
- `frontend/admin.html` kaldırılan eski uçlara bağlıydı, çalışmaz. Yeni admin uçları yazılmadı.
- Yok: WebRTC (gerçek ses, `room:speaking`), HTTP hız sınırı (giriş denemeleri için gerekli), oda rolleri (`admin`/`vip`) ve koltuk kilitleme ucu, özel mesajlarda anlık bildirim, görsel yükleme.
- Bağlantısı kopan kullanıcının koltuğu hemen boşalıyor (kısa kopmalar için bekleme süresi yok); hiç WebSocket açmadan REST ile oturan kullanıcı koltukta kalır.
