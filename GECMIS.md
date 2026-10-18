# Geçmiş

Projede yapılan işlerin kaydı.

- **Şu an neredeyiz** bölümü güncel durumu özetler; her çalışma sonunda güncellenir.
- **Kayıtlar** bölümünde en yeni kayıt en üsttedir. Her kayıt aynı sırayı izler: amaç, ne yapıldı, doğrulama, açık kalanlar.

---

## Şu an neredeyiz

**Aşama:** Web demo. Frontend ekranları hazır ve gerçek backend'e bağlı (`USE_MOCK = false`).

**Çalışan:** giriş/kayıt/misafir, oda listesi, oda içi sohbet, koltuklar, zar ve rulet oyunları, kademeli hediye animasyonları, hediye gönderme, coin satın alma, özel mesajlar (anlık bildirimli), kullanıcı takibi, oda takibi, profil ve profil düzenleme, cüzdan, oda yöneticileri ve moderasyon (koltuk kilitleme, koltuktan indirme, odadan atma).

**Kod okuma turu (2026-10-14):** Auth, oda listesi akışı (`list_rooms` → `present_rooms` → `realtime/state.py`) ve `room_socket` okundu. Sırada ekonomi (`gift_service`, `wallet_service`) derinlemesine; diğer router/servisler yüzeysel; sonra `hub.py`.

**Ana sayfa (2026-10-18):** kullanıcının verdiği referans görsele göre yeniden tasarlandı. Alt çubuk: Ana Sayfa · Mesajlar · (+) · Cüzdan · Profil.

**2026-10-18 planı tamamlandı:** (1) Profili Düzenle + Oda Takip Et, (2) oda rolleri ve moderasyon, (3) özel mesajlarda anlık bildirim, (4) rulet oyunu ve hediye animasyonları.

**Kod nerede:** GitHub, private repo `tahayasinakbay460-spec/Muti` (dal `main`). Commit mesajlarına Claude/Co-Authored-By satırı eklenmez.

**Sıradaki adım (2026-10-19):** Müşteri bu hafta uygulamayı canlı görmek istiyor. Görüşmenin günü henüz belli değil; başlarken sorulacak. Sırayla:

1. **Demo yayını.** Ücretli, uyumayan hosting onaylandı (bütçe ~500 TL). Yapılacaklar:
   - Backend tek sunucuda çalışmalı (canlı durum bellek içi).
   - Frontend'de API/WS adresi ayarlanabilir olmalı ve `https` / `wss` kullanılmalı.
   - Yayın adresi CORS'a eklenmeli.
   - Demo verisiyle çalışan ayrı bir ayar modu (staging) gerekli, çünkü `production` modu demo modunu reddediyor.
2. **Giriş denemelerine hız sınırı.** Link herkese açılacağı için gerekli; demo hesapların parolası herkesçe bilinen `demo1234`.
3. **Gerçek ses (WebRTC).** Müşteri görüşmesine yetişirse.
4. **Kısa kod okuma.** Bugün eklenenler, özellikle WebSocket akışı (`room_socket`, `user_socket`, `hub`, `games`).

Bu bir demo yayını, mağaza yayını değil. Gerçek ses, gerçek ödeme ve kendi görsellerimiz henüz yok.

### Henüz elle denenmeyenler

- Telefondan erişim denenmedi. Windows Güvenlik Duvarı 8000 ve 5500 portlarına izin vermeli.

### Eksik özellikler

| Eksik | Not |
|---|---|
| Gerçek ses (WebRTC) | Koltuktaki "konuşuyor" halkası bu yüzden yanmıyor |
| Uygulama kapalıyken bildirim (push) | Anlık bildirim yalnızca uygulama açıkken (/ws/me bağlıyken) çalışır; mobilde APNs/FCM gerekir |
| Bilardo, 101 Okey, Candy | Ana sayfada kartları var, "Yakında" diyor. Oynanabilen oyunlar: Zar, Rulet |
| Oda içi `vip` rolü | `host` ve `admin` var; odaya özel VIP üyelik yazılmadı |
| Dinleyici listesi | Moderatör yalnızca koltuktaki birini atabilir; koltukta olmayan dinleyicileri gösteren liste yok |
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
| Oda durumu, odadan atma yasakları, rulet turları, oda ve kişi yayınları bellek içi (tek sunucu süreci) | `realtime/state.py`, `realtime/hub.py` (`RoomHub`, `UserHub`), `realtime/games.py` | Redis (aynı sözleşmeyle `RedisRoomStateStore`, pub/sub; yasaklar süreli anahtar) |
| Satın alma ödeme doğrulamadan coin ekliyor | `wallet_service.purchase` | App Store / Google Play makbuz doğrulama |
| Banner ve profil ekleri sabit içerik | `demo/content.py` | Tablo + servis |
| Avatar ve kapak yalnızca hazır listeden seçiliyor | `demo/content.py` (`AVATAR_CHOICES`, `COVER_CHOICES`) | Görsel yükleme (object storage + boyut/tür kontrolü) |
| Zaman etiketlerini ("3 gün önce") sunucu üretiyor | `core/timefmt.py` | İstemci `created_at` alanından üretir |
| Oda sırası ve liderlik her istekte hesaplanıyor | `state.room_ranks`, `gift_service.list_top_gifters` | Redis sorted set |
| Örnek odalarda sahte dinleyici sayısı | `demo/seed.py` | Kaldırılır |

---

# Kayıtlar

## 2026-10-18 — GitHub'a gönderim ve yarının planı

**Amaç:** Kodu GitHub'a koymak ve müşteri demosu için yol haritasını belirlemek.

### Ne yapıldı

- **GitHub:** kullanıcı private `Muti` reposunu açtı; `main` dalı `https://github.com/tahayasinakbay460-spec/Muti.git` adresine gönderildi.
- **Geçmiş temizlendi:** kullanıcı GitHub'da Claude simgesini görmek istemediği için, `Co-Authored-By: Claude` satırı taşıyan ilk 3 commit tek bir temiz başlangıç commit'inde birleştirildi ("Initial commit: FastAPI backend and mobile-first web demo"). Kod birebir aynı kaldı; günün 6 commit'i üstüne dizildi.
  - Eski geçmiş yerelde `backup-before-rewrite` dalında duruyor, GitHub'a gönderilmedi. Gerek kalmayınca `git branch -D backup-before-rewrite` ile silinebilir.
- **`auth.py`:** kullanıcının `routers/auth.py` içindeki kendi notu ayrı bir commit olarak eklendi. Bundan sonra kullanıcının koda bıraktığı notlar da normal şekilde commit'lenir.
- **Müşteri demosu kararları:** bu hafta canlı demo yapılacak. Ücretli hosting onaylandı; plan "Şu an neredeyiz" bölümünde.

### Doğrulama

- GitHub'daki `main`, yereldeki `main` ile aynı.
- Hiçbir commit mesajında Claude geçmiyor.
- `.env`, `app.db` ve test yardımcısı `_shot.html` repoya girmedi.

### Açık kalanlar

- Müşteri görüşmesinin günü bilinmiyor.
- Hosting sağlayıcısı henüz seçilmedi.

## 2026-10-18 — Rulet oyunu ve hediye animasyonları

**Amaç:** Odada zar dışında, herkesin aynı anda katıldığı gerçek bir çok oyunculu oyun olsun. Hediyeler değerine göre farklı büyüklükte animasyonla görünsün.

### Ne yapıldı

**Backend: Rulet (`realtime/games.py`, yeni)**

- **Akış:**
  - Odadaki biri turu başlatır (`game:roulette_start`); herkese `game:roulette_started` gider.
  - 10 saniye içinde herkes renk seçer (`game:roulette_bet` → `game:roulette_bet_placed`). Seçim süre içinde değiştirilebilir.
  - Süre bitince **sunucu** `secrets` ile 0-36 arası bir sayı çeker. Rengi bilenler kazanır: `game:roulette_result` `{ number, color, winners, player_count }`.
- **Kurallar:** odada aynı anda tek tur olur (`roulette_running`). Tur yokken seçim yapılamaz (`no_active_round`). Geçersiz renk reddedilir (`invalid_color`). Bağlantı başına 5 saniyede en fazla 5 işlem.
- **Coin bahsi yok**, oyun yalnızca eğlence. Paralı olursa `wallet_service` üzerinden yapılmalı (dosyada not var).
- **DEMO KISAYOLU:** tur durumu bellekte, süre `asyncio` zamanlayıcısıyla bitiyor. Çok sunucuda Redis + tek bitirici gerekir.
- `room_socket.py` yeni olayları `games.roulette`'a yönlendiriyor; olay adları `events.py`'de.
- 1 yeni test: tur başlatma, çift başlatma, geçersiz renk, seçim, sonucun ve kazananın sunucuda hesaplanması. Testte süre 0.3 sn'ye indiriliyor.

**Frontend**

- **Oyun paneli (`screens/room.js`):** "Rulet | Zar" sekmeleri.
  - Rulet sekmesinde: tur sürerken dönen çark, geri sayım, Kırmızı/Siyah/Yeşil düğmeleri, seçim yapanların avatarları (seçtikleri renkte halka). Sonuçta çarkın ortasında sayı ve renk görünüyor.
  - Rulet durumu panel kapalıyken de tutuluyor.
  - Sohbete "X rulet turu başlattı … [Katıl]" ve sonuç satırı düşüyor. Kazanana "🎉 Rulette kazandın!" bildirimi çıkıyor.
  - Eski "Yakında" oyun kutuları kaldırıldı.
- **Hediye animasyonları (toplam değer = fiyat × adet):**
  - 99'un altı: sağ alttan yukarı süzülen emojiler.
  - 99-998: ortada patlayan emoji ve isim şeridi (eski animasyon).
  - 999 ve üstü: tam ekran parıltı, konfeti, üstten kayan duyuru şeridi ve dev emoji. Büyük animasyonlar sıraya alınıyor, üst üste binmiyor. Büyük hediyede hediye paneli kapanıyor ki animasyon görünsün.
  - **Kombo:** aynı kişi aynı hediyeyi aynı kişiye 4 sn içinde tekrar gönderirse hediye akışında tek satırda sayaç artıyor (x3, altın renk).
- **`realtime.js`:** mock kanalı ruleti de taklit ediyor.
- **`screens/home.js`:** "Rulet" kartı artık "Yakında" demiyor; oyun odalarına götürüp nasıl oynanacağını söylüyor.

### Doğrulama

- Backend testleri 23/23 geçti.
- Tarayıcıda gerçek zamanlı denendi. Headless Chrome DevTools Protocol ile sürüldü; önceki ekran görüntüsü yöntemi saati hızlandırdığı için WebSocket akışlarında yanıltıcıydı.
  - Rulet turu başlatıldı, Kırmızı seçildi, sonuç "5 Kırmızı" geldi ve kazanma bildirimi çıktı.
  - Spor Araba (999) ile tam ekran animasyon görüldü.
  - 3 kez art arda gönderilen Gül ile süzülen emojiler ve x3 kombo görüldü.
- Denemede bulunup düzeltilen iki CSS hatası:
  - Konfeti kutusu ızgarada yer kaplayıp dev emojiyi itiyordu.
  - Emoji animasyonu yalnızca son karede `opacity` tanımladığı için baştan sona soluyordu.

### Açık kalanlar

- Odaya tur ortasında giren kişi o turu görmüyor; bir sonraki turdan itibaren görüyor (sunucu "şu an süren tur" bilgisini katılanlara göndermiyor).
- Bilardo, 101 Okey ve Candy hâlâ yok.
- Denemeler için demo veritabanında birkaç misafir hesabı, demo coin alımları ve hediye kayıtları oluştu (`app.db` silinirse sıfırlanır).

## 2026-10-18 — Özel mesajlarda anlık bildirim

**Amaç:** Karşı tarafın mesajı sohbet yeniden açılınca değil, anında görünsün. Uygulamanın başka bir ekranındayken de yeni mesaj haber verilsin.

### Ne yapıldı

**Backend**

- **Kişiye özel WebSocket `/ws/me?token=`** (`realtime/user_socket.py`): kullanıcı giriş yapmış olduğu sürece açık kalan hat.
  - İstemci yalnızca `ping` gönderir; sunucu bununla kişiyi çevrimiçi sayar. Başka olaylar `unknown_event` ile reddedilir.
  - Token geçersizse `4401` ile kapanır.
- **`realtime/hub.py`:** yeni `UserHub` (kullanıcı → bağlantıları). Bir kişi birden fazla sekme/cihazdan bağlıysa hepsine gider. Gönderme yardımcısı (`_send`) iki hub için ortak.
- **`message_service.send_message`:** mesaj kaydedildikten sonra karşı tarafa ve gönderenin diğer bağlantılarına `message:new` itiliyor: `{ conversation_id, sender, message }`. Her iki taraf `from_me` alanını kendi gözünden görür.
- **Yeni uçlar:**
  - `GET /conversations/unread-count`: toplam okunmamış (alt çubuk rozeti).
  - `POST /conversations/{id}/read`: sohbet açıkken gelen mesajı okundu sayar. Başkasının sohbetinde 404 döner.
- 2 yeni test: mesajın alıcıya itilmesi ve okunmamış sayacı; geçersiz token.

**Frontend**

- **`realtime.js`:** oda kanalı genel bir `WebSocketChannel(path)` sınıfına dönüştü (yeniden bağlanma mantığı ortak). `connectUser()` `/ws/me` kanalını açıyor ve 2 dakikada bir `ping` atıyor. Kanallara `off` eklendi.
- **`inbox.js` (yeni):** kişiye özel kanalın tek sahibi.
  - Giriş yapılıyken açık, giriş ekranında kapalı (`app.js`).
  - Alt çubukta "Mesajlar" sekmesine kırmızı okunmamış rozeti koyuyor.
  - Başka bir ekrandayken "💬 Merve: …" bildirimi gösteriyor.
  - Ekranlar `onInbox(event, handler)` ile abone olup temizlikte bırakıyor.
- **`screens/messages.js`:**
  - Liste ekranı yeni mesajda kendini tazeliyor.
  - Sohbet ekranında gelen mesaj anında ekleniyor ve okundu sayılıyor; o sohbet için bildirim çıkmıyor.
  - Aynı mesaj hem POST cevabı hem kanal üzerinden gelebildiği için `data-id` ile iki kez basılmıyor.

### Doğrulama

- Backend testleri 22/22 geçti.
- Headless Chrome ile, "muti" olarak açık sayfaya "merve" hesabından gerçek API ile mesaj gönderildi:
  - Ana sayfada "Mesajlar" sekmesine `1` rozeti geldi.
  - Cüzdan ekranında "💬 Merve: Neredesin? 😊" bildirimi çıktı.
  - Sohbet açıkken mesaj sayfa yenilenmeden eklendi; okunmamış sayacı 0 kaldı.

### Açık kalanlar

- Test sırasında Merve'den muti'ye giden 3 deneme mesajı demo veritabanında kaldı (`app.db` silinirse örnek veri sıfırlanır).
- "Yazıyor..." göstergesi ve okundu bilgisi (✓✓) yok.
- Uygulama kapalıyken bildirim (push notification) yok; mobil aşamanın işi.
- Rozet her ekran değişiminde sunucudan tazeleniyor (ekran başına bir küçük istek).

## 2026-10-18 — Oda rolleri ve moderasyon

**Amaç:** Odalarda oda sahibi dışında yönetici olabilsin; oda sahibi ve yöneticiler koltukları ve kişileri yönetebilsin. Bütün yetki kontrolleri sunucuda.

### Roller

- **Sıralama:** `host` (oda sahibi, `rooms.host_id`) > `admin` (oda sahibinin atadığı yönetici) > `listener` (diğer herkes; koltukta oturan da yetki bakımından listener).
- **Kural:** bir işlem ancak kendinden alt rütbedeki birine yapılabilir.
  - Yönetici, oda sahibine ya da başka bir yöneticiye dokunamaz (`target_outranks_you`).
  - Kimse kendine moderasyon işlemi yapamaz.

### Ne yapıldı

**Backend**

- **Yeni tablo `room_admins`** (`RoomAdmin`, `models/room.py`). `RoomOut.admin_ids` ile dönüyor; `present_rooms` içinde tek sorguyla hesaplanıyor.
- **Yeni servis `services/moderation_service.py`:** `get_role`, `set_admin`, `set_seat_lock`, `remove_from_seat`, `kick_from_room`.
- **Yeni uçlar (`routers/rooms.py`):**
  - `PUT` / `DELETE /rooms/{id}/admins/{user_id}`: yönetici yap / yöneticiliği al. Yalnızca oda sahibi.
  - `PUT` / `DELETE /rooms/{id}/seats/{index}/lock`: koltuğu kilitle / aç. Dolu koltuk kilitlenince oturan kişi indirilir (yetki yetiyorsa).
  - `DELETE /rooms/{id}/seats/{index}/user`: koltuktan indir; kişi dinleyici olarak odada kalır.
  - `POST /rooms/{id}/kicks/{user_id}`: odadan at.
- **Odadan atma akışı:**
  - Koltuk boşalır ve odaya `room:user_kicked` yayınlanır.
  - Atılan kişinin bütün WebSocket bağlantıları `4403` koduyla kapatılır.
  - Kişi 10 dakika boyunca odaya bağlanamaz; REST ile koltuğa da oturamaz (`room_banned`).
- **`realtime/state.py`:** sözleşmeye `clear_seat`, `set_seat_locked`, `ban_from_room`, `is_banned` eklendi. Yasaklar bellek içinde, süreli; Redis'te süreli anahtar olacak.
- **`realtime/hub.py`:** bağlantılar artık sahibiyle birlikte tutuluyor (`dict[WebSocket, user_id]`). `disconnect_user` bir kişinin odadaki bağlantılarını kapatıyor.
- **`realtime/events.py`:** `room:roles_updated`, `room:user_kicked` eklendi. WebSocket kapanış kodları (`4401`, `4403`, `4404`) buraya taşındı.
- **`room_socket.py`:** bağlanırken yasak kontrolü yapılıyor. Sunucu bağlantıyı kapattığında oluşan `RuntimeError` yakalanıyor.
- **İsim değişikliği:** `room_service._get_room_row` → `get_room_row` (artık iki servis kullanıyor).
- 2 yeni test: rol/koltuk kuralları; atılan kişinin bağlantısının kapanması ve yasak.

**Frontend**

- **`screens/room.js`:**
  - Koltuk altında "Oda Sahibi" (turuncu) ve "Yönetici" (mor) etiketi.
  - Moderatör boş bir koltuğa dokununca "Koltuğa otur / Koltuğu kilitle", kilitli koltuğa dokununca "Kilidi aç" paneli açılıyor.
  - Başkasının koltuğuna dokununca kullanıcı panelinde moderasyon bölümü var: Koltuktan indir, Yönetici yap / Yöneticilikten al (yalnızca oda sahibi), Odadan at. Yalnızca yetki yeten kişilerde görünüyor.
  - `room:roles_updated` ve `room:user_kicked` dinleniyor. Atılan kullanıcı ana sayfaya dönüyor ve "Bu odadan çıkarıldın" bildirimini görüyor.
- **`realtime.js`:** `4403` ile kapanan bağlantı yeniden bağlanmayı denemiyor, `room_banned` hatası veriyor.
- **`api.js`:** `setRoomAdmin`, `setSeatLock`, `removeFromSeat`, `kickFromRoom`. Mock sürümü sadeleştirilmiş yetki kontrolüyle.

### Doğrulama

- Backend testleri 20/20 geçti.
- Headless Chrome ile "Naz" (Gece Muhabbeti'nin sahibi) olarak denendi:
  - Kullanıcı panelinde moderasyon düğmeleri göründü.
  - "Yönetici yap" sonrası koltukta "Yönetici" etiketi çıktı.
  - Boş koltuk kilitlendi.
  - Denemeden sonra yöneticilik ve kilit API ile geri alındı.
- Odadan atma tarayıcıda değil, testte uçtan uca denendi (WebSocket kapanışı + yasak).

### Açık kalanlar

- Odaya özel `vip` rolü yok.
- Koltukta olmayan dinleyicileri listeleyen ekran yok; bu yüzden onlar arayüzden atılamıyor (uç hazır).
- "Mikrofonunu kapat" (zorla susturma) yok; kişi kendi mikrofonunu yine açabileceği için şimdilik eklenmedi.
- Yasak listesi bellek içinde: sunucu yeniden başlarsa yasaklar sıfırlanır.

## 2026-10-18 — Profili Düzenle ve Oda Takip Et

**Amaç:** Arayüzde olup arkasında backend olmayan iki özelliği çalışır hale getirmek: profil sayfasındaki "Profili Düzenle" ve oda başlığındaki "Takip Et".

### Ne yapıldı

**Backend**

- **`PATCH /api/v1/users/me`** (`ProfileUpdateRequest`): görünen ad, hakkımda, yaş, şehir, avatar ve kapak.
  - PATCH olduğu için yalnızca gönderilen alanlar değişir. Servis `model_fields_set` ile "alan gönderilmedi" ile "null gönderildi" durumlarını ayırır.
  - Kurallar: ad boş olamaz (1-40), yaş 13-99, hakkımda en çok 300, şehir en çok 60 karakter. Boşluklar kırpılır.
  - Avatar ve kapak yalnızca `demo/content.py` içindeki hazır listeden seçilebilir; dışarıdan rastgele bir adres yazılamaz (`invalid_avatar`, `invalid_cover`).
- **`GET /api/v1/users/me/media-options`:** seçilebilecek hazır görseller.
- **Yeni tablo `room_follows`** (`RoomFollow`, `models/room.py`): `(user_id, room_id)` birincil anahtar.
  - `create_all` yeni tabloyu mevcut `app.db` içinde de kendiliğinden oluşturur; eski tablolarda kolon değişmedi.
- **`POST /api/v1/rooms/{id}/follow`:** takip et / bırak. Kullanıcı takibiyle aynı kalıpta: önce silmeyi dener; aynı anda gelen çift tıklama `IntegrityError` ile yakalanır.
- **`GET /api/v1/rooms/followed`:** takip edilen açık odalar, en son takip edilen en üstte.
- **`RoomOut.is_following`:** bakan kişiye göre dolar. `present_rooms` içinde tek sorguyla hesaplanır; herkese giden yayınlarda `false` kalır.
- 2 yeni test eklendi: profil güncelleme kuralları ve oda takibi.

**Frontend**

- **`screens/edit-profile.js`** (yeni): alttan açılan panel. Yatay kaydırılan avatar ve kapak seçici (seçili olan ortaya kaydırılır), ad, hakkımda, yaş, şehir. Yalnızca değişen alanlar gönderilir; kaydedince profil ekranı yeniden çizilir.
- **`screens/room.js`:** "Takip Et" düğmesi artık API'ye bağlı. Açılışta `room.is_following` ile doğru durumda geliyor.
- **`screens/following.js`** (yeni, `#/following`): ana sayfadaki "Takip" sekmesi buraya gidiyor. Takip edilen oda yoksa açıklama ve "Odaları keşfet" düğmesi gösteriliyor.
- **`api.js`:** `updateProfile`, `getMediaOptions`, `toggleRoomFollow`, `listFollowedRooms`. Hem `httpApi` hem `mockApi` içinde var.
- **`app.css`:** `textarea`, iki kolonlu form satırı ve görsel seçici stilleri.

### Doğrulama

- Backend testleri 18/18 geçti.
- Headless Chrome ile gerçek backend'e karşı elle denendi:
  - Profili Düzenle paneli açıldı.
  - Avatar seçilip kaydedildi; profil yeni avatarla yeniden çizildi.
  - Odada "Takip Et" düğmesi "Takipte" oldu.
  - `#/following` takip edilen odayı listeledi.
- Denemede değişen demo verisi API ile eski haline döndürüldü.

### Açık kalanlar

- `USE_MOCK = true` modu tarayıcıda denenmedi; yalnızca sözdizimi kontrol edildi.
- Oda takip sayısı (kaç kişi takip ediyor) tutulmuyor ve gösterilmiyor.
- Takip edilen oda canlıya geçince bildirim yok.

## 2026-10-18 — Ana sayfa referans görsele göre yeniden tasarlandı

**Amaç:** Ana sayfa, kullanıcının paylaştığı TopTop benzeri ekran görüntüsüne benzesin. İlk denemede yalnızca bölümler eklendi ve düzen görsele benzemedi; ikinci denemede ekran görüntüsü alınarak görselle karşılaştırıldı.

### Ne yapıldı

- **`screens/home.js`** baştan yazıldı. Yukarıdan aşağıya:
  - Üst çubuk: logo, arama, bildirim, coin.
  - Üst sekmeler: Keşfet, Odalar, Oyunlar, Etkinlik, Takip.
  - Banner: yanda sonraki slaytın ucu görünüyor; başlığın son satırı pembe vurgulu.
  - 5 hızlı kategori.
  - "Sana Özel Öne Çıkan Odalar": yatay şerit, ekrana 3 kart sığıyor.
  - Oyunlar: 4 kare kart.
  - Popüler Yayıncılar: önce canlı odası olan ev sahipleri, sonra önerilen kişiler. Kullanıcının kendisi hariç; yalnızca ilk kişide taç ve CANLI etiketi var.
  - Haftanın Yıldızları ve Şu An Aktif.
- **Alt çubuk (`app.js`):** Keşfet sekmesi kalktı (aramadan ve "Odalar" sekmesinden açılıyor); yerine Cüzdan geldi. Cüzdan ekranının geri düğmesi kaldırıldı.
- **`css/app.css`:** ana sayfa bloğu yenilendi. Çok renkli logo harfi, altın "+" eklendi. Kullanılmayan `room-card`, `room-grid` ve `person` stilleri ile `roomCard` bileşeni silindi.
- **Banner metinleri:** `demo/content.py` ve `mock-data.js` içinde güncellendi ("Sesin, Sohbetin, Oyunların Muti'de!").
- **Marka adı:** `APP_NAME` `MUTI` yerine `Muti` oldu.
- Etkinlik, Takip, 81 İl Odası, VIP Odalar ve oyun kartları henüz "Yakında" bildirimi gösteriyor.

### Doğrulama

- Headless Chrome ile 390 px telefon genişliğinde ekran görüntüsü alındı ve referans görselle karşılaştırıldı.
- Backend testleri 16/16 geçti.

### Açık kalanlar

- Görseldeki insan fotoğrafları yok. Kartlar oda kapağını, avatarlar 128 px `randomuser` görsellerini kullanıyor; kendi görsellerimiz gelince düzelecek.
- Oyun kartları emoji ile çizildi, gerçek oyun görseli yok.

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
