# Geçmiş

Projede yapılan işlerin kaydı.

- **Şu an neredeyiz** bölümü güncel durumu özetler; her çalışma sonunda güncellenir.
- **Kayıtlar** bölümünde en yeni kayıt en üsttedir. Her kayıt aynı sırayı izler: amaç, ne yapıldı, doğrulama, açık kalanlar.

---

## Şu an neredeyiz

**Aşama:** Web demo. Frontend ekranları hazır ve gerçek backend'e bağlı (`USE_MOCK = false`).

**Çalışan:** giriş/kayıt/misafir, oda listesi, oda içi sohbet, koltuklar, zar ve rulet oyunları, kademeli hediye animasyonları, hediye gönderme, coin satın alma, özel mesajlar (anlık bildirimli), kullanıcı takibi, oda takibi, profil ve profil düzenleme, cüzdan, **gerçek ses (WebRTC, mesh)** ve konuşan koltukta halka, kişi arama, bildirim merkezi, ayarlar (şifre değiştirme, engellenenler, hesap silme), engelleme ve şikâyet, seviye sistemi, yayıncı geliri (elmas → coin), oda rolleri (oda sahibi, yönetici, VIP) ve tam moderasyon: dinleyici listesi, koltuk kilitleme, koltuktan indirme, koltuğa davet, başkasının mikrofonunu kapatma, sohbette süreli susturma, mesaj silme, odadan atma, oda ayarları, odayı kapatma.

**Kod okuma turu (2026-10-14):** Auth, oda listesi akışı (`list_rooms` → `present_rooms` → `realtime/state.py`) ve `room_socket` okundu. Sırada ekonomi (`gift_service`, `wallet_service`) derinlemesine; diğer router/servisler yüzeysel; sonra `hub.py`.

**Ana sayfa (2026-10-18):** kullanıcının verdiği referans görsele göre yeniden tasarlandı. Alt çubuk: Ana Sayfa · Mesajlar · (+) · Cüzdan · Profil.

**2026-10-18 planı tamamlandı:** (1) Profili Düzenle + Oda Takip Et, (2) oda rolleri ve moderasyon, (3) özel mesajlarda anlık bildirim, (4) rulet oyunu ve hediye animasyonları.

**Kod nerede:** GitHub, private repo `tahayasinakbay460-spec/Muti` (dal `main`). Commit mesajlarına Claude/Co-Authored-By satırı eklenmez.

**2026-10-19 kullanıcı kararı:** Sıra şöyle değişti: (1) moderasyonu tamamla ✅, (2) gerçek ses (WebRTC) ✅, (3) eksik temel özellikler: arama, ayarlar ekranı, bildirim merkezi, engelleme ve şikâyet, yayıncı geliri, seviye sistemi ✅. Commit edildi (GitHub'a gönderilmedi).

**Öğrenme (2026-10-19):** `learning/websocket/` dersleri hazır (WebSocket temeli). Sırada: ses sinyali WebSocket'te nasıl taşınıyor, sonra ses sunucuları.

**Yarın buradan devam (2026-10-20):** Kayıtlar bölümünün en üstündeki "Gün özeti" kaydını oku: önerilen sıra, kararlar, açık sorular orada.

**Yapılmayanlar listesi (2026-10-19 akşam, kullanıcıyla konuşuldu):**
- *Ürün:* Ludo/Domino/UNO/101 Okey gibi büyük oyunlar; fotoğraf yükleme (avatar, mesajda resim/ses); profil duvarı ve başarımlar hâlâ sabit içerik (`demo/content.py`); şifremi unuttum, e-posta/telefon doğrulama, Google/Apple ile giriş; çok dil; arkadaş eşleştirme; yönetici rol seviyeleri ve panelden banner/mağaza/VIP fiyatı düzenleme; rulet/zar hız sınırı sessiz atıyor; mock modu yeni özelliklerin çoğunda eksik.
- *Para:* gerçek ödeme (App Store / Google Play satın alma doğrulaması, web için ödeme sağlayıcısı), gerçek abonelik (VIP şu an coinle), elmas → para çekimi ve ajans komisyon ödemesi (KYC, fatura).
- *Altyapı:* hosting + alan adı + HTTPS, PostgreSQL + Alembic migration (şema değişince veritabanı siliniyor), Redis (oda durumu, banlılar, sayaçlar; birden fazla sunucu), Docker, TURN (coturn), LiveKit canlı deneme, zamanlanmış işler (etkinlik ödülü, eski mesaj silme), veritabanı yedeği, HTTP hız sınırı, frontend önbellek başlıkları, log toplama + Sentry + uyarılar, yük testi, kendi görsellerimiz.
- *Mobil:* iOS/Android uygulaması yok; push bildirim; mağaza hesapları ve incelemesi.
- *Hukuk:* KVKK aydınlatma metni, gizlilik politikası, kullanım şartları; yaş sınırı; küfür/içerik filtresi; yöneticinin mesaj okuma politikası; şanslı hediye ve hazine sandığı (parayla alınan coinle rastgele ödül) için olasılıkların gösterilmesi ve şans oyunu mevzuatı kontrolü.

**Yönetim paneli (2026-10-19 akşam):** masaüstü panel `frontend/admin.html` (giriş: `admin` / `demo1234`); finans grafikleri, para hareketleri, kullanıcı yönetimi, bütün özel mesajlar ve oda sohbet geçmişi (DEMO, KVKK notu), katalog düzenleme, duyuru.

**İşletme (2026-10-19):** yönetim paneli ve ajans sistemi hazır; hedef özelliklerin dört grubu da tamam. Sırada: genel eksik/fazla değerlendirmesi ve canlıya çıkış yol haritası (kullanıcı hiç ürün yayınlamadı; adımlar sade anlatılacak).

**Oda içi eğlence (2026-10-19):** PK, Dört Bağla, Taş-Kağıt-Makas, birlikte izleme, karaoke sırası hazır. Sırada 4. grup (ajans, admin paneli), ardından genel eksik değerlendirmesi ve canlıya çıkış yol haritası.

**Bağlılık sistemleri (2026-10-19):** günlük giriş, görevler, aile (sohbetli), CP, sıralamalar, etkinlikler hazır. Sırada 3. grup (oda PK'si, yeni oyunlar, karaoke/birlikte izleme), sonra 4. grup (ajans, admin paneli).

**Gelir sistemleri (2026-10-19):** mağaza (çerçeve, giriş efekti, sohbet balonu), VIP (3 kademe, günlük ödül), şanslı hediye, hazine sandığı, hediye paketleri hazır. GitHub'da CI var (`.github/workflows/ci.yml`). Kullanıcı CLAUDE.md "D. Hedef Özellikler" 2-4. grupların da yapılmasını istedi; sırada 2. grup (günlük giriş ödülü/görevler, sıralamalar, aile, CP, etkinlikler).

**Sıradaki adım:** demo yayını ve giriş hız sınırı (aşağıdaki plan). Yayında ses için kendi TURN sunucumuz (coturn) gerekecek; https zorunlu (tarayıcı mikrofonu yalnızca güvenli adreste açar). WebRTC sağlayıcı değiştirilebilir kurulacak: bugün kullanılan servis ileride açık kaynak bir servisle ya da başka bir sağlayıcıyla değiştirilebilmeli. Demo yayını bunlardan sonra.

**Demo yayını planı (2026-10-18'de yazıldı):** Müşteri bu hafta uygulamayı canlı görmek istiyor. Görüşmenin günü henüz belli değil; başlarken sorulacak. Sırayla:

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
| TURN sunucusu | Ses mesh ile çalışıyor; sıkı ağlarda (bazı mobil operatörler, şirket ağları) doğrudan bağlantı kurulamazsa TURN gerekir. coturn kurulup `VOICE_TURN_URLS` / `VOICE_TURN_SECRET` doldurulacak |
| Kalabalık oda sesi | Mesh ~30 kişiye kadar. Daha kalabalık odalar için `VOICE_PROVIDER=livekit` hazır ama canlı LiveKit sunucusuyla denenmedi |
| Elmasların gerçek paraya çekimi | Ödeme altyapısı ve kimlik doğrulama (KYC) gerekir; `WITHDRAWALS_ENABLED=false` |
| Kullanım koşulları / gizlilik politikası sayfaları | Ayarlarda "yakında" diyor; mağaza yayını için zorunlu |
| Uygulama kapalıyken bildirim (push) | Anlık bildirim yalnızca uygulama açıkken (/ws/me bağlıyken) çalışır; mobilde APNs/FCM gerekir |
| Bilardo, 101 Okey, Candy | Ana sayfada kartları var, "Yakında" diyor. Oynanabilen oyunlar: Zar, Rulet |
| Admin uçları | Uygulama geneli yönetim (kullanıcı banlama, şikâyet inceleme) yazılmadı; oda içi moderasyon var |
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
| Oda durumu, odadan atma yasakları, sohbette susturma, mikrofon engeli, koltuk davetleri, son 50 sohbet mesajı, rulet turları, oda ve kişi yayınları bellek içi (tek sunucu süreci) | `realtime/state.py`, `realtime/hub.py` (`RoomHub`, `UserHub`), `realtime/games.py` | Redis (aynı sözleşmeyle `RedisRoomStateStore`, pub/sub; yasaklar süreli anahtar) |
| Satın alma ödeme doğrulamadan coin ekliyor | `wallet_service.purchase` | App Store / Google Play makbuz doğrulama |
| Banner ve profil ekleri sabit içerik | `demo/content.py` | Tablo + servis |
| Avatar ve kapak yalnızca hazır listeden seçiliyor | `demo/content.py` (`AVATAR_CHOICES`, `COVER_CHOICES`) | Görsel yükleme (object storage + boyut/tür kontrolü) |
| Zaman etiketlerini ("3 gün önce") sunucu üretiyor | `core/timefmt.py` | İstemci `created_at` alanından üretir |
| Oda sırası ve liderlik her istekte hesaplanıyor | `state.room_ranks`, `gift_service.list_top_gifters` | Redis sorted set |
| Örnek odalarda sahte dinleyici sayısı | `demo/seed.py` | Kaldırılır |

---

# Kayıtlar

## 2026-10-19 — Gün özeti: konuşulanlar, kararlar, yarın nereden devam

**Yarın buradan başla:** Önerilen sıra (kullanıcı henüz seçmedi): (1) PostgreSQL + Alembic migration — şema değişince veritabanı silinmesin; (2) canlıya çıkış: Docker, sunucu, alan adı, HTTPS, TURN, giriş hız sınırı, Sentry; (3) gerçek ödeme + yasal metinler; (4) mobil uygulama + mağaza; (5) büyük oyunlar ve kalan özellikler. Kullanıcı hiç ürün yayınlamadı: her adım ne işe yarar, sade ve örnekle anlatılacak. Tam liste: "Yapılmayanlar listesi" (yukarıda).

**Kullanıcıya anlatılanlar (soru-cevap):**
- *"Oturumun sona erdi" neden çıktı:* veritabanı sıfırlanınca tarayıcıdaki refresh token sunucuda bulunamıyor. Access token (JWT) 15 dk, refresh token 30 gün; JWT kullanmamaktan değil süresi dolunca biter; refresh ilk istekte, tek kullanımlık (rotation), sunucu üretir. Sekmeyi kapatmak çıkış değildir ("beni hatırla"); çalınma tespiti, çıkış, şifre değişikliği koruması anlatıldı.
- *Telefondan girmek:* kod hazır (`HOST=0.0.0.0`, adres sayfadan alınıyor); engel Windows güvenlik duvarı (Wi-Fi "Ortak" profilde, 5500/8000 portları kapalı) — çözüm: ağı "Özel" yap + port kuralı. `127.0.0.1` / `0.0.0.0` / `192.168.x.x` farkı anlatıldı. Telefonda mikrofon http'de çalışmaz (HTTPS gerekir).
- *Ses nasıl çalışıyor:* şu an mesh WebRTC (LiveKit kurulu değil). Sunucu yalnızca "tanışma" mesajlarını (`voice:signal`) WebSocket'ten taşır, ses tarayıcıdan tarayıcıya doğrudan gider. STUN / TURN / SFU (LiveKit) farkı anlatıldı.
- *WebSocket:* HTTP (mektup) ile WebSocket (açık telefon hattı) farkı; `learning/websocket/` altında 3 ders (echo, herkese yayın, event/payload). Kullanıcı ders planının devamını (çoklu oda, token, yeniden bağlanma, tarayıcı, ses tanışması) sonra yapmak istedi.
- *Log nedir, sektörde nasıl izlenir:* uvicorn'un eski satırları ile yeni kayıtların farkı (istek numarası, kullanıcı, süre, güvenlik/para olayları); sektörde merkezi log (Loki/ELK/Datadog), uyarılar, Sentry, metrik ve izleme (observability). Not: "CP hatasını log sayesinde buldum" ifadesi abartıydı, düzeltildi.
- *Mesajlar nerede tutuluyor:* özel ve aile mesajları veritabanında; oda sohbeti önceden yalnızca bellekteydi, artık `room_messages` tablosunda. Veritabanı DB Browser for SQLite ile görülebilir (canlıda PostgreSQL + DBeaver/pgAdmin). Yöneticinin mesaj okumasının KVKK/mağaza riski anlatıldı; önerilen şikâyete bağlı erişim.

**Kullanıcı kararları:**
- Müşteri demosu acil değil; önce özellikler, sonra genel değerlendirme ve yayın.
- Hedef özelliklerin 4 grubu da yapılsın (yapıldı). Süre tahmini verme ("haftalar sürer" demek yanlıştı).
- Çalışma şekli: her işte test, güvenlik taraması, tarayıcıda deneme, CI yeşil, GECMIS kaydı (Claude hafızasına da yazıldı).
- Demo için yönetici bütün özel mesajları ve oda mesajlarını görebilsin (her okuma denetim kaydında; canlıda yeniden konuşulacak).
- Yönetim paneli gerçek sesli sohbet uygulamaları gibi, zengin olsun (masaüstü panel yapıldı).

**Kullanıcının açık sorusu:** "CLAUDE.md seni iyi kontrol edemiyor galiba." Öneri verildi (kritik kuralları dosyanın başına kısa liste, uzun dosya haritasını ayrı dosyaya; kesin kurallar için hook), kullanıcının hangi durumu kastettiği henüz konuşulmadı. Bugün bulunan sapma: "önce frontend sonra backend" kuralına uyulmadı.

**Gün içinde bulunan önemli sorunlar (ayrıntıları ilgili kayıtlarda):** starlette'te 14 güvenlik açığı (FastAPI güncellendi); ara sıra takılan WebSocket testleri; CI JS kontrolünün `import` içeren dosyalarda hatayı görmemesi (`frontend/package.json` ile çözüldü); tarayıcı önbelleğinin eski JS dosyası yüzünden boş sayfa (yayında `Cache-Control` gerekli); hız sınırında hamlelerin sessizce kaybolması; `backend/.coverage` dosyasının yanlışlıkla commit'lenmesi; `backend/app.db.bak` yedeğinin kaybolması (sebep bulunamadı).

**Giriş bilgileri (demo):** uygulama `http://127.0.0.1:5500` (hesap `muti` / `demo1234`), yönetim paneli `http://127.0.0.1:5500/admin.html` (`admin` / `demo1234`). Veritabanı bugün birkaç kez sıfırlandı; açınca yeniden giriş gerekebilir.

## 2026-10-19 — Masaüstü yönetim paneli ve mesaj inceleme

**Amaç:** Kullanıcı (müşteri isteği): yönetici kullanıcıların özel mesajlarını ve oda mesajlarını görebilsin; panel gerçek bir sesli sohbet uygulamasının yönetim paneli gibi olsun (coin alım-satımı vb.). Hukuki risk konuşuldu (KVKK, mağaza kuralları, önerilen: şikâyete bağlı erişim); kullanıcı kararı: demo için hepsi görünsün.

**Ne yapıldı:**
- **Oda sohbeti artık kalıcı:** `RoomMessage` tablosu; mesaj ve günlük görev sayacı tek işlemde yazılır; odadan silinen mesaj kayıtta kalır, `deleted_at` ile işaretlenir (şikâyet kanıtı).
- **Masaüstü yönetim paneli** (`frontend/admin.html`, ayrı sayfa, solda menü): Genel Bakış (8 özet kartı, 14 günlük coin satışı/hediye ve yeni kullanıcı grafikleri — bağımlılıksız SVG, en çok harcayan/kazanan/oda), Finans (7/14/30/90 gün, harcama dağılımı, işlem türüne göre toplamlar), Para Hareketleri (tür ve kullanıcı süzgeci, sayfalama), Kullanıcılar (sıralama: en yeni / en zengin / en çok şikâyet; sağdan açılan detay: bakiye, ban, bakiye düzeltme, ücretsiz VIP verme, özel sohbetleri, son hareketler), Mesajlar (bütün özel sohbetler ve konuşma; KVKK uyarısı ekranda), Odalar (sohbet geçmişi, odaya git, kapat), Şikâyetler, Hediye & Paketler (fiyat, şanslı, satışta; paket coin/bonus/etiket — kullanıcılar hemen görür), Ajanslar, Duyuru (bütün kullanıcılara bildirim).
- Telefon içindeki küçük yönetim ekranı kaldırıldı (iki panel bakımı olmasın); profil menüsü masaüstü paneli yeni sekmede açar.
- Yeni uçlar: `/admin/finance`, `/admin/transactions`, `/admin/conversations(/{id}/messages)`, `/admin/rooms/{id}/messages`, `/admin/catalog/gifts|packages`, `/admin/users/{id}/vip`, `/admin/broadcast`, `/admin/users?sort=`. Her mesaj görüntüleme `admin_viewed_conversation` / `admin_viewed_room_chat` olarak denetim kaydına yazılır.
- Örnek veri: son 30 günün sabit tohumlu satış/hediye/VIP geçmişi (grafikler dolu görünsün; bakiyeler bundan hesaplanmaz), oda sohbet örnekleri (biri reklam: şikâyet kanıtı).

**Doğrulama:** 86 test (yeni 6), kapsam %95, takım 3 kez art arda geçti; ruff, pip-audit, JS sözdizimi temiz. Tarayıcıda gerçek backend'le: giriş ekranı, genel bakış grafikleri, kullanıcı tablosu ve detay paneli, mesajlar, oda sohbet geçmişi, finans; diğer sayfalar içerik okunarak; konsolda hata yok. Detay panelinde etiketlerin şeride dönmesi düzeltildi.

**Açık kalanlar:** Mesaj okuma canlıda şikâyete bağlanmalı ve gizlilik metni yazılmalı (avukat). Yönetici rolleri tek seviye (süper yönetici / moderatör ayrımı yok). Panel ayarları (banner, mağaza eşyaları, VIP fiyatları) henüz düzenlenemiyor. Örnek verideki bugünkü büyük hediye toplamları grafikte bugünü çok yüksek gösteriyor.

## 2026-10-19 — İşletme (4. grup): yönetim paneli ve ajans sistemi

**Amaç:** CLAUDE.md "D. Hedef Özellikler" 4. grup. Bununla dört grup tamamlandı.

**Ne yapıldı:**
- **Yönetim paneli** (`#/admin`, yalnızca `is_admin`; demo hesabı `admin` / `demo1234`): özet sayılar; şikâyet listesi (açık / karara bağlanan) ve karar (reddet / kullanıcıyı banla / odayı kapat; aynı hedefin bütün açık şikâyetleri birlikte kapanır, karar notu saklanır); kullanıcı arama (banlılar dahil), detay, son 20 para hareketi; ban/ban kaldırma; gerekçeli bakiye düzeltme (`admin_adjustment` olarak deftere); oda listesi ve kapatma; ajans kurma.
- **Ban anında etkili:** hesap kapanır, refresh token'lar iptal, açık WebSocket'ler 4401 ile kesilir, elindeki access token bir sonraki istekte reddedilir (her istekte bellekteki banlı kümesi kontrolü; açılışta veritabanından yüklenir; DEMO: canlıda Redis set). Yönetici başka yöneticiyi/kendini banlayamaz.
- **Ajans:** yönetici kurar (sahibi + komisyon %0-50); sahibi yayıncıyı ID ile davet eder; yayıncı kabul/ret; sahibi aylık elmas hedefi koyar, çıkarır ya da daveti geri çeker; panelde üyelerin bu ayki kazancı, hedef ilerlemesi ve tahmini komisyon. Bir yayıncı aynı anda tek ajansta (birincil anahtar). Gerçek hesaplaşma/ödeme yok (DEMO).
- Ortaklaştırma: `moderation_service.shut_down_room` (oda sahibi ve yönetici aynı kapatma yolunu kullanır), `auth_service.revoke_all_sessions`, hub'lara "kişinin bütün bağlantılarını kes" yardımcıları.
- Örnek veri: yönetici hesabı, "Yıldız Ajans" (Mert; Merve ve Selin üye, muti'ye davet), 3 açık şikâyet.

**Doğrulama:** 80 test (yeni 8), kapsam %94, takım 3 kez art arda geçti; ruff, pip-audit, JS sözdizimi temiz. Tarayıcıda gerçek backend'le (ekran görüntüsü aracı takıldığı için sayfa içeriği okunarak): yönetim panelinin 5 sekmesi gerçek verilerle, muti'nin ajans davetini kabulü (yayıncı sayısı 2→3), Mert'in ajans paneli (kazanç, %15 komisyon, hedef ilerlemesi); konsolda hata yok.

**Bulunan sorun:** Tarayıcı `report.js`'in önbellekteki eski sürümünü kullandı ve yeni `admin.js` onu içe aktaramayınca uygulama boş açıldı. Build adımı olmadığı için yayında da olabilir; çözüm canlıya çıkışta sunucunun `Cache-Control: no-cache` vermesi ya da dosya adlarına sürüm eklemek (CLAUDE.md "Olmayanlar"a yazıldı).

**Açık kalanlar:** Ajans komisyonunun gerçek ödemesi; yönetici işlemlerinin ayrı bir "yönetici geçmişi" ekranı (şimdilik denetim kayıtlarında); uygulama ayarları (banner, hediye kataloğu, fiyatlar) panelden düzenlenemiyor.

## 2026-10-19 — Oda içi eğlence (3. grup): PK, iki kişilik oyunlar, birlikte izleme, karaoke

**Amaç:** CLAUDE.md "D. Hedef Özellikler" 3. grup. (Kullanıcı kararı: müşteri demosu acil değil; önce 3-4. gruplar, sonra genel eksik değerlendirmesi.)

**Ne yapıldı:**
- **Oda PK'si** (`activity_service`): oda sahibi/yönetici 1/3/5/10 dk başlatır; koltukların ilk yarısı kırmızı, ikinci yarısı mavi. Süre boyunca takım koltuğuna giden hediyeler puan olur (gift_service bağlar), sonunda kazanan ve MVP duyurulur; erken bitirilebilir. Arayüzde canlı skor çubuğu, geri sayım, takım renkli koltuklar.
- **İki kişilik oyunlar** (`realtime/duels.py`, WebSocket): Dört Bağla (sıra, sütun doluluğu, 4 yönde kazanma kontrolü) ve Taş-Kağıt-Makas (3 turdan 2; seçim iki taraf seçene kadar rakibe de gizli). Hamle süresi 45 sn, süre dolarsa ya da oyuncu odadan/masadan çıkarsa hükmen yenilgi; rakipsiz masa 2 dk sonra kapanır; odada en fazla 3 masa. İzleyiciler de tahtayı canlı görür.
- **Birlikte izleme:** yalnızca YouTube (bağlantıdan kimlik sunucuda ayıklanır, başka site gömülemez). Sunucu video trafiği taşımaz; "hangi video, hangi saniye" bilgisini paylaşır, tarayıcılar YouTube IFrame API ile senkron oynatır (2 sn'den küçük kaymada atlama yok, sunucu saat farkı düzeltilir). Oynat/durdur/sar/kapat yalnızca yönetici.
- **Karaoke sırası:** odadakiler sıraya girer/çıkar, yönetici sıradakine geçer; şarkıcı odada şeritte gösterilir; odadan çıkan sıradan düşer.
- `room_service.require_moderator` ortak hale getirildi (moderasyon da bunu kullanıyor). Oda arayüzü ayrı modülde (`room-activities.js`), room.js yalnızca bağlıyor.
- **Bulunan sorun:** oyun mesajlarındaki hız sınırı aşılınca mesaj sessizce atılıyordu; hızlı oynayan kullanıcının hamlesi uyarısız kayboluyordu (test takıldığı için fark edildi). Düellolara ayrı, daha geniş sınır; aşılırsa `rate_limited` hatası döner.

**Doğrulama:** 72 test (yeni 12), kapsam %94, takım 3 kez art arda geçti; ruff, pip-audit, JS sözdizimi temiz. Tarayıcıda gerçek backend'le ikinci kullanıcı (merve) WebSocket'ten yönetilerek: PK başlatma ve mavi takıma hediye (skor çubuğu, renkli koltuklar), YouTube videosunun odada oynaması, Dört Bağla'da iki oyuncunun hamlelerinin senkronu, etkinlik paneli; konsolda hata yok.

**Açık kalanlar:** Ludo, Domino, UNO gibi büyük oyunlar yok (her biri ayrı iş). Rulet/zar mesajlarında hız sınırı hâlâ sessiz atıyor. Karaoke'de şarkı sözü/altyapı yok (sıra yönetimi var; altyapı birlikte izleme ile açılabilir). Oyunlarda coin bahsi yok (bilinçli).

## 2026-10-19 — Bağlılık sistemleri (2. grup): günlük giriş, görevler, aile, CP, sıralamalar, etkinlikler

**Amaç:** CLAUDE.md "D. Hedef Özellikler" 2. grubu: kullanıcıyı her gün geri getiren sistemler.

**Ne yapıldı:**
- **Günlük giriş:** 7 günlük döngü (10 → 200 coin), gün atlanırsa baştan. (kullanıcı, gün) benzersiz: aynı gün iki ödül yazılamaz. Ana sayfada günde bir kez hatırlatma penceresi.
- **Görevler:** 4 günlük görev (odaya gir, 5 mesaj, 3 hediye, takip). Sayaçlar tek komutluk UPSERT ile artar (eşzamanlı işlemde sayım kaybolmaz); hediye sayacı hediyeyle aynı transaction'da. DEMO: sayaçlar veritabanında, canlıda Redis.
- **Aile:** kurma (2.000 coin), katılma (50 üye sınırı tek komutla korunur), ayrılma, kurucu/yönetici/üye rütbeleri, üye çıkarma, slogan/rozet, dağıtma, aile sohbeti (`/ws/me` üzerinden `family:message` ile anında). Aile rozeti profilde, sohbette ve sıralamada.
- **CP:** teklif (520 coin), kabul / red / geri çekme (iade), ayrılık. "Tek CP" kuralı kabulde iki kullanıcı satırına "boşsa yaz" ile atomik; CP olunca diğer bekleyen teklifler iadeyle kapanır. Profilde CP kartı ve teklif listesi; başkasının profilinde "CP teklif et".
- **Sıralamalar:** zenginler / çekiciler / odalar / aileler × bugün / bu hafta / bu ay (takvim dönemi); kişi sıralamalarında kendi sıran. Puanlar para defterinden.
- **Etkinlikler:** süreli kampanya; bitince ilk bakışta ödüller tek komutla "dağıtıldı" işaretlenip bir kez dağıtılır. DEMO: zamanlayıcı yok, canlıda cron.
- Örnek veri: 3 aile (muti hiçbirinde değil), Selin-Kaan aktif CP, Ada'dan muti'ye bekleyen teklif, biri süren biri biten etkinlik; örnek hediyeler birkaç saat önceye alındı (Pazartesi "bu hafta" sıralaması boş kalıyordu).
- **CI'daki JS kontrolünün kör noktası bulundu:** `node --check`, içinde `import` olan `.js` dosyasında sözdizimi hatası olsa bile başarılı dönüyordu (profildeki `'CP'siniz'` kesme işareti hatası bu yüzden kaçtı, sayfa açılmadı). `frontend/package.json` (`"type": "module"`) eklendi; artık yakalıyor, tüm dosyalar temiz.
- Sıralama sekmelerinde degrade arka plan Chrome'da çizimi kilitliyordu (ekran görüntüsü alınamıyordu); ortak `.segmented` stiline geçildi. Çerçeveli avatarın uzun satırlarda yumurta gibi esnemesi düzeltildi.
- Yakalanan hatalar: CP ayrılığında commit sonrası eski nesneye erişim (500; yeni log sistemi tam dökümle gösterdi), VIP denetim kaydının sessizce kaybolması (`audit(level=)` çakışması, önceki kayıtta). Ara sıra başarısız olan eski bir arama testi (rastgele misafir adında "2001" geçebiliyordu) düzeltildi.

**Doğrulama:** 60 test geçiyor (yeni 8), kapsam %94, takım 5 kez art arda geçti; ruff, pip-audit, JS sözdizimi temiz. Tarayıcıda gerçek backend'le: günlük giriş penceresi ve ödül, görevler, sıralama (kürsü + aile rozetleri), aileye katılma ve aile sohbeti, profilde CP teklifini kabul, etkinlik listesi ve detayı; konsolda hata yok.

**Açık kalanlar:** Kişinin "toplam aile katkısı" ayrılınca aileden düşer (şimdiki üyeler sayılıyor; bilinçli). Etkinlik ödülü zamanlayıcıyla değil ilk bakışta dağıtılıyor. Aile/CP mock'ları basitleştirilmiş (kur/teklif mock'ta yok). `backend/app.db.bak` yedeği bir noktada kayboldu; neyin sildiği bulunamadı (içerik yalnızca o sabah oluşturulan örnek veriydi).

## 2026-10-19 — Kayıt (log) sistemi, test kapsamı ölçümü ve eksik testler

**Amaç:** Kullanıcı sordu: "Yeterince testimiz var mı, log tutuyor muyuz?" Cevap: log neredeyse yoktu; testlerin gerçek kapsamı bilinmiyordu.

**Ne yapıldı:**
- `app/core/logs.py`: her HTTP isteğine numara (`X-Request-ID`, yanıt başlığında da), erişim kaydı (`muti.access`: yöntem, yol, sonuç, süre, kullanıcı), güvenlik/para kaydı (`muti.audit`: giriş başarılı/başarısız, refresh token tekrar kullanımı, kayıt, misafir, şifre değişikliği, hesap silme, coin/mağaza/VIP alımı, elmas çevirme, sandık, şikâyet, bütün moderasyon işlemleri). Beklenmedik hata tam dökümüyle kaydedilir; kullanıcıya yalnızca `internal_error` + destek numarası döner. WebSocket oda giriş/çıkışı kaydedilir. Geliştirmede okunabilir satır, canlıda `LOG_JSON=true` ile JSON; `LOG_FILE` ile dönen dosya. İstemciden gelen istek numarası yalnızca güvenli biçimdeyse kabul edilir (sahte kayıt satırı sokulamasın).
- Test kapsamı ölçümü: `pytest-cov` + `.coveragerc`. İlk ölçüm %77 gösterdi ama yanlıştı: SQLAlchemy async (greenlet) ayarı olmadan çalışan satırlar görülmüyordu. Doğru ölçüm %93. CI'a %90 alt sınırı eklendi.
- Kapsamın gösterdiği önemli boşluklara test (`test_gaps.py`): çıkış yapınca refresh token'ın geçersizleşmesi, bilinmeyen token, VIP'te çift istek, sandığın süre dolunca kapanması, şanslı hediyenin gerçek çekilişi. Kayıt testleri (`test_logging.py`): istek numarası, erişim kaydı, parolanın kayda girmediği, para/moderasyon kayıtları, iç ayrıntı sızdırmayan 500.
- Yazarken yakalanan hata: `audit(..., level=...)` hem log seviyesi hem alan adı olabiliyordu; VIP kaydı sessizce kaybolacaktı. Parametre `log_level` yapıldı.

**Doğrulama:** 52 test geçiyor, kapsam %94; takım 5 kez art arda geçti; ruff ve pip-audit temiz; gerçek sunucuda kayıt satırları görüldü (başarısız giriş ve erişim kaydı aynı istek numarasıyla).

**Açık kalanlar:** Kayıtlar bir log servisine gönderilmiyor (canlıda hosting paneli / Loki). Hata izleme servisi (Sentry gibi) yok. Frontend'de hata ekranı istek numarasını henüz göstermiyor.

## 2026-10-19 — Gelir sistemleri (mağaza, VIP, şanslı hediye, hazine sandığı, hediye paketi) ve CI

**Amaç:** CLAUDE.md "D. Hedef Özellikler" 1. grubu (para kazandıran sistemler). Ardından GitHub'a gönderim ve Eva_Agent projesindeki (dal `phase-0-skeleton`) CI'a benzer bir kalite kapısı.

**Ne yapıldı:**
- **Mağaza:** `models/store.py` (`StoreItem`, `UserItem`), `store_service`, `routers/store.py`. Çerçeve (8), giriş efekti (5), sohbet balonu (4); 7/30 gün; tekrar alınca süre kalan sürenin üstüne eklenir; her türden bir eşya takılı. Takılı eşyalar `UserOut.frame / entry_effect / chat_bubble` olarak her yerde (oda yayınları dahil) gelir. Profildeki sabit çerçeve listesi (`content.py avatar_frames`) kaldırıldı, yerine gerçek eşyalar.
- **VIP:** `vip_service` (Gümüş 3.000 / Altın 8.000 / Elmas 20.000 coin, 30 gün; DEMO: coinle, canlıda mağaza aboneliği). Üyelik eşyaları üyelikle biter. Günlük ödül tek komutluk atomik güncellemeyle günde bir kez. `User.vip_expires_at`, `vip_daily_claimed_on`; süresi dolan üyelik `active_vip_level()` ile 0 görünür. Örnek verideki VIP 1-8 değerleri 1-3'e indirildi; ana kullanıcı `muti` VIP değil (demoda VIP alınabilsin).
- **Şanslı hediye:** `Gift.is_lucky`; 3 hediye (Yonca, Kurabiye, Altın Zar). Çarpanı sunucu çeker (`LUCKY_TABLE`, beklenen geri dönüş %77,5; testle korunuyor). Alıcı payı %10. Kazanç aynı transaction'da, odaya `gift:sent` içinde duyurulur; x10 ve üstü büyük şerit.
- **Hazine sandığı:** `treasure_service` (DEMO: bellek içi). Odadaki hediyeler doldurur (hedef 10.000 coin), açılınca 60 sn; havuz %10; kişi başı bir kez, odada olmak şart. Olaylar `room:chest_updated`, `room:chest_claimed`; uçlar `GET/POST /rooms/{id}/chest(/claim)`.
- **Hediye paketleri:** `CoinPackage.title / item_id / item_days / is_one_time`. Başlangıç Paketi (tek seferlik, 7 gün Neon çerçeve), Kraliyet Paketi (30 gün Roket efekti).
- **Frontend:** `#/store`, `#/vip` ekranları; odada koltuk/sohbet çerçevesi, sohbet balonu, giriş efekti şeridi, şanslı etiket ve duyuru, sandık göstergesi; cüzdanda paketler ve Mağaza/VIP kısayolu; profilde "Eşyalar" sekmesi. Mock API aynı metodları sunar.
- **CI:** `.github/workflows/ci.yml` (ruff lint + pytest, pip-audit, JS sözdizimi, gitleaks) ve `.gitleaks.toml`. pip-audit, starlette 0.38.6'da 14 bilinen açık buldu → FastAPI 0.115.0 → 0.148.0 (starlette 1.9.0); testler değişmeden geçti. ruff'ın bulduğu 3 küçük sorun düzeltildi.
- **Testlerdeki ara sıra takılma çözüldü:** WebSocket açılınca kişi odaya hemen eklenmiyor; test o arada sinyal/bildirim gönderirse mesaj düşüyor ve test sonsuza kadar bekliyordu. Testler artık önce katılımı (`chat:history`) ya da `/ws/me` kaydını (`wait_until_registered`) bekliyor.
- `.gitignore`: `*.db.bak` eklendi. Eski veritabanı `backend/app.db.bak` olarak yedeklendi (şema değişti, yeni `app.db` örnek veriyle oluşur).

**Doğrulama:** 44 test geçiyor; tüm takım art arda 10 kez çalıştırıldı, 10'u da geçti. ruff, JS sözdizimi ve pip-audit yerelde temiz. Tarayıcıda (gerçek backend) denendi: mağaza, giriş efekti sekmesi, VIP satın alma (bakiye 12.450 → 9.450), odada balon/çerçeve/sandık açılıp coin kapma, cüzdan paketleri, profil eşyaları; konsolda hata yok. gitleaks yerelde çalıştırılamadı (yalnızca GitHub'da).

**Açık kalanlar:** Hedef özelliklerin 2-4. grupları. Kullanıcının `backend/venv`'i yeni FastAPI'ye güncellendi; başka makinede `pip install -r requirements.txt` gerekir. Tek seferlik paket aynı anda iki farklı istekle alınırsa iki kez verilebilir (demo için kabul edildi; canlıda benzersiz kısıt). Sandık ve VIP günlük ödülü PostgreSQL'de denenmedi.

## 2026-10-19 — Birleşik arama ve rakip araştırması

**Amaç:** Arama kutusu hem odaları hem kişileri arasın, sonuçlar süzülebilsin. TopTop benzeri uygulamalarda olup bizde olmayan özellikler araştırılsın.

**Ne yapıldı:** Keşfet ekranı tek kutu + Tümü / Odalar / Kişiler sekmeleri (`explore.js`); Tümü'de kişilerden 3, odalardan 5 sonuç ve "Tümünü gör". Odalar ID ile de aranabiliyor (`room_service.list_rooms`, mock da). Ana sayfa arama simgesi klavyeyi açıyor (`?focus=1`), "Popüler Yayıncılar → Tümünü Gör" Kişiler sekmesine gidiyor. Araştırma sonucu CLAUDE.md'ye "D. Hedef Özellikler" olarak yazıldı (VIP/soylu, mağaza, şanslı hediye, günlük ödül/görev, sıralamalar, aile, CP, oda PK'si, oyunlar, ajans, admin paneli).

**Doğrulama:** Yeni test `test_room_search_by_title_and_id`; tüm testler geçti (35). Arayüz tarayıcıda denenmedi.

**Açık kalanlar:** Hedef özelliklerden hangisiyle başlanacağı kullanıcıya soruldu (öneri: giriş efekti + çerçeve + mağaza → günlük ödül + sıralama → oda PK'si).

## 2026-10-19 — WebSocket öğrenme dersleri

**Amaç:** Kullanıcı ses sistemine geçmeden önce WebSocket mantığını projeden bağımsız, basit örneklerle öğrenmek istedi.

**Ne yapıldı:** `learning/websocket/` klasörü: `1_echo` (açık kalan hat), `2_broadcast` (odadaki herkese yayın, sunucunun kendiliğinden konuşması), `3_events` (`event`/`payload` biçimi, sunucu otoritesi). Her derste `server.py` + `client.py`, nasıl çalıştırılacağı `README.md`'de. Proje koduna dokunulmadı.

**Doğrulama:** Ders 3 sunucusu iki istemciyle denendi: sohbet herkese gitti, `/hile` ile gönderilen 6-6 ve sahte isim yok sayıldı, bozuk mesajda hata sadece gönderene gitti.

**Açık kalanlar:** Sıradaki dersler: (2) ses sinyalinin (`voice:signal`) WebSocket'te taşınması ve sohbet mesajının projedeki yolu, (3) ses sunucuları (STUN/TURN/LiveKit).

## 2026-10-19 — Gerçek ses (WebRTC) ve eksik temel özellikler

**Amaç:**

- Odada gerçek sesli sohbet. Kullanıcının isteği: ses altyapısı sağlayıcı değiştirilebilir kurulsun. Bugün kullanılan servis yarın açık kaynak bir servisle ya da başka bir sağlayıcıyla değiştirilebilmeli.
- TopTop'ta olup bizde olmayan temel özellikleri eklemek: arama, ayarlar, bildirim merkezi, engelleme ve şikâyet, yayıncı geliri, seviye sistemi.

### Ne yapıldı: Ses

**Mimari: sağlayıcı katmanı.** Oda, koltuk ve yetki kuralları hep bizde. Sesin nasıl taşındığı ise değiştirilebilir bir parça.

- **Backend `app/voice/`:**
  - `base.py`: sözleşme (`VoiceProvider`).
    - `join_info`: istemciye "nasıl bağlanacağını" verir.
    - Kancalar: `sync_publishers` (koltuklar değişince), `remove_participant` (odadan atma), `close_room`.
  - `mesh.py`: tarayıcılar sesi birbirine doğrudan gönderir; bizim sunucu yalnızca bağlantı mesajlarını taşır. Ek sunucu ve ücret yok. Odada ~30 kişiye kadar uygundur.
  - `livekit.py`: açık kaynak (Apache 2.0) medya sunucusu LiveKit için hazır sağlayıcı. Kendi sunucumuza kurulabilir ya da LiveKit Cloud kullanılabilir.
    - Konuşma izni sunucu tarafında açılıp kapanır. Koltuktan inen ya da mikrofonu engellenen kişinin sesini LiveKit keser.
    - **Canlı LiveKit sunucusuyla denenmedi.** Token biçimi testle doğrulandı.
  - `ice.py`: STUN/TURN listesi. TURN parolası coturn'ün "use-auth-secret" yöntemiyle bir saatlik üretiliyor, hiçbir yerde saklanmıyor.
  - Seçim `.env` ile: `VOICE_PROVIDER=mesh|livekit`. Yeni bir sağlayıcı = yeni bir sınıf + `voice/__init__.py`'ye bir satır.
  - Uç: `GET /rooms/{id}/voice` → `{ provider, can_publish, ice_servers | url + token }`.
  - Mesh sinyali: oda WebSocket'inde `voice:signal`. Sunucu biçimi doğrular ve yalnızca odadaki iki kişi arasında, en az biri koltuktaysa iletir; iki dinleyici kendi aralarında ses kanalı açamaz. Gönderen kimliğini sunucu yazar.
- **Frontend `js/voice/`:**
  - `index.js`: sunucunun söylediği sağlayıcının istemcisini yükler. Arayüz: `start / update(seats) / removePeer / close`.
  - `mesh.js`:
    - Kim kime bağlanır: dinleyici → konuşmacılara; konuşmacılar arasında küçük id'li olan bağlantıyı açar.
    - Her bağlantıda iki yönlü tek ses kanalı var. Koltuğa oturunca mikrofon kanala takılıyor, kalkınca çıkarılıyor; bağlantı yeniden kurulmuyor.
    - Aynı anda iki teklif gelirse "perfect negotiation" yöntemi kullanılıyor.
    - Herkes, koltukta olmayan ya da mikrofonu kapalı/engelli görünen birinin sesini kendi tarafında kısıyor. Değiştirilmiş bir istemci kuralı çiğnese bile sesi duyulmuyor.
  - `livekit.js`: LiveKit istemcisi (CDN'den yüklenir).
  - `speaking.js`: "kim konuşuyor" halkası. Sunucudan gelmiyor; tarayıcı duyduğu sesin şiddetinden hesaplıyor.
  - Tarayıcı sesi kullanıcı dokunmadan çalmazsa ilk dokunuşta başlatılıyor.
- `publish_seats` artık önce ses sağlayıcısına "kimler konuşabilir" bildiriyor, sonra koltukları yayınlıyor.

### Ne yapıldı: Temel özellikler

| Özellik | Backend | Frontend |
|---|---|---|
| **Kişi arama** | `GET /users/search?query=`: ad, @kullanıcı adı ya da ID. Engellenenler görünmez | Keşfet'te "Odalar / Kişiler" sekmesi; arama boşken önerilen kişiler |
| **Bildirim merkezi** | `notifications` tablosu. `GET /notifications`, `/notifications/unread-count`, `POST /notifications/read`. Kişi bağlıysa `/ws/me` üzerinden anında `notification:new`. Türler: takip, hediye alındı, seviye atlandı, odada rol verildi | `#/notifications` ekranı; ana sayfadaki zilde okunmamış noktası; yeni bildirimde kısa uyarı |
| **Engelleme** | `user_blocks` tablosu. `PUT/DELETE /users/{id}/block`, `GET /users/me/blocks`. İki yönlü etki: mesaj, hediye ve takip yok; takipler iki yönde kalkar; bildirim gitmez. Hata kodu `user_blocked` (kimin engellediği söylenmez) | Başkasının profil menüsünde Engelle / Engeli kaldır; Ayarlar'da engellenenler listesi |
| **Şikâyet** | `reports` tablosu, `POST /reports` (kullanıcı ya da oda + sebep). Aynı hedefe açık şikâyeti olan tekrar yazamaz | Profil ve oda menüsünde "Şikâyet et" (sebep seçimi + açıklama) |
| **Seviye** | `users.experience` kolonu, `level_service`. Hediyede harcanan her coin 1 XP. Lv.n için 100 × (n−1)² XP. Seviye hediyeyle aynı transaction'da artar ve yalnızca yükselir | Kendi profilinde seviye çubuğu (XP / sonraki seviye) |
| **Yayıncı geliri** | `GET /wallet/income`: bugün, 7 gün, toplam elmas, en çok destek olan 5 kişi. `POST /wallet/exchange`: elmas → coin, tek transaction, idempotency anahtarlı. Oran `DIAMOND_TO_COIN_RATE` (1) | Cüzdanda "Coin / Gelir" sekmeleri: elmas bakiyesi, istatistikler, çevirme formu, destekçiler, elmas geçmişi |
| **Ayarlar** | `POST /auth/change-password`: diğer cihazlar kapanır, bu cihaza yeni token. `DELETE /users/me`: parola onaylı; kişisel bilgiler silinir, takipler kalkar, açtığı odalar kapanır. Para defteri yasal kayıt olarak kalır | `#/settings`: şifre değiştir, engellenenler, çıkış, hesabı sil (onaylı). Profil menüsünden açılır |

### Doğrulama

- `python -m pytest`: **34 test geçti**. 8'i yeni:
  - ses giriş bilgisi ve sinyal iletim kuralları;
  - TURN parolası ve LiveKit token biçimi;
  - kişi arama;
  - engellemenin mesaj, hediye, takip ve aramaya etkisi;
  - şikâyet;
  - hediye → XP, seviye, bildirim, gelir ve elmas çevirme (idempotency dahil);
  - takip ve rol bildirimleri;
  - şifre değiştirme ve hesap silme.
- **Ses tarayıcıda denendi.** İki ayrı sekmede iki ayrı kullanıcı vardı; mikrofon yerine test sesi (440 Hz ton) kullanıldı. Sonuçlar:
  - Dinleyici, koltuktaki oda sahibine bağlandı (`connected`). Sesi aldı, oda sahibinin koltuğunda "konuşuyor" halkası yandı.
  - Oda sahibi mikrofonunu kapatınca halka söndü.
  - Misafir koltuğa oturunca aynı bağlantı yeniden kurulmadan iki yönlü oldu; oda sahibi misafiri duydu.
  - Oda sahibi misafirin mikrofonunu engelleyince oda sahibinin tarafında misafirin sesi kısıldı ve koltukta kırmızı kilit göründü.
- **Yeni ekranlar tarayıcıda görülmedi.** Bu ekranlar: bildirimler, ayarlar, kişi arama, cüzdan "Gelir" sekmesi, profil seviye çubuğu.
  - Sebep: tarayıcı eklentisinin bağlantısı koptu.
  - Yapılan kontroller:
    - Bütün JS dosyalarının sözdizimi kontrol edildi.
    - Her `import` edilen adın gerçekten dışa aktarıldığı ve ekranların çağırdığı her `api` metodunun `httpApi`'de bulunduğu bir betikle kontrol edildi.
    - Çalışan sunucuya bu ekranların çağırdığı uçlar istek atılarak denendi; hepsi 200 döndü.
- `backend/app.db` yeniden oluşturuldu (yeni kolon ve tablolar).

### Açık kalanlar

- Yeni ekranlar (bildirimler, ayarlar, kişi arama, gelir sekmesi, seviye çubuğu) tarayıcıda elle denenmeli.
- Gerçek mikrofonla ve telefondan ses denenmedi. Telefonda mikrofon yalnızca `https` adreste açılır; yerel ağdaki `http://192.168...` adresinde açılmaz. Bu yüzden ses için yayın (https) gerekiyor.
- TURN sunucusu yok: bazı mobil ağlarda ses bağlanmayabilir.
- LiveKit sağlayıcısı canlı sunucuyla denenmedi.
- Bildirimler yalnızca uygulama açıkken anlık; push (APNs/FCM) mobil aşamada `notification_service.notify` içinden tetiklenecek.
- Şikâyetleri inceleyecek yönetim paneli yok.
- Kullanım koşulları ve gizlilik politikası sayfaları yok.
- Hesap silmede kişinin gönderdiği özel mesajlar duruyor (karşı tarafın sohbet geçmişi). Mağaza yayını öncesi gözden geçirilmeli.

## 2026-10-19 — Oda moderasyonu tamamlandı

**Amaç:** Oda yöneticisinin TopTop'taki gibi odayı gerçekten yönetebilmesi. Önceden yalnızca koltuktaki biri atılabiliyordu; koltukta olmayan dinleyiciye ulaşılamıyordu, kimse susturulamıyordu.

### Ne yapıldı

**Roller**

- `room_admins` tablosu yerine **`room_members`** (`room_id`, `user_id`, `role`) geldi. `role`: `admin` ya da `vip`. Rolü olmayan herkes dinleyicidir.
- Rütbe sırası: oda sahibi > yönetici > VIP > dinleyici. Kural aynı: bir işlem yalnızca alt rütbedeki birine yapılır.
- Yönetici atamayı yalnızca oda sahibi yapar. VIP'i oda sahibi ve yöneticiler verir. VIP'in yönetim yetkisi yok; koltuklar davetle açıldığında bile kendisi oturabilir.
- Uç: `PUT /rooms/{id}/roles/{user_id}` `{ role: "admin" | "vip" | "listener" }`. Eski `PUT/DELETE /rooms/{id}/admins/{user_id}` kaldırıldı.
- `RoomOut` alanlarına `vip_ids` ve `free_seating` eklendi; `room:roles_updated` artık `{ admin_ids, vip_ids }` gönderiyor.

**Yeni moderasyon işlemleri (hepsi `moderation_service`, yetki sunucuda)**

| İşlem | Uç | Not |
|---|---|---|
| Dinleyici listesi | `GET /rooms/{id}/members` | Odaya bağlı herkes; rol, koltuk, susturma ve mikrofon durumu ile. Herkes görebilir |
| Mikrofonu kapatma | `PUT/DELETE /rooms/{id}/mic-blocks/{user_id}` | Kişi kendisi açamaz (`mic_blocked`). Koltuktan kalkıp yeniden otursa da sürer. `SeatOut.is_mic_blocked` |
| Sohbette susturma | `PUT /rooms/{id}/chat-mutes/{user_id}` `{ minutes: 5/30/60/1440 }`, `DELETE` ile kaldırma | Susturulan yazınca `chat_muted` hatası alır. Yayın: `room:chat_muted` |
| Mesaj silme | `DELETE /rooms/{id}/messages/{message_id}` | Kendi mesajını herkes, başkasınınkini üst rütbedeki yönetici siler. Yayın: `chat:message_deleted` |
| Koltuğa davet | `POST /rooms/{id}/seat-invites/{user_id}` | Yalnızca davet edilene `room:seat_invite` gider. 60 sn geçerli, tek kullanımlık. Dolu koltuğu denemek daveti harcamaz |
| Oda ayarları | `PATCH /rooms/{id}` | Ad, kategori, duyuru, kapak (hazır listeden), `free_seating`. Yayın: `room:updated` |
| Odayı kapatma | `DELETE /rooms/{id}` | Yalnızca oda sahibi. Satır silinmez (`is_active = false`); herkes 4404 koduyla çıkarılır. Yayın: `room:closed` |

- **Koltuk kuralı (`rooms.free_seating`):** kapalıysa koltuğa kendisi yalnızca oda sahibi, yönetici ve VIP oturur; diğerleri davetle (`seat_requires_invite`).

**Sohbet**

- Her mesajın artık sunucunun ürettiği bir `id`'si ve `created_at`'i var (silinebilsin diye).
- Odanın son 50 mesajı canlı depoda tutuluyor. Odaya giren kişiye yalnızca kendisine `chat:history` gönderiliyor; sohbetin ortasına boş ekranla düşmüyor.
- Odadan tamamen çıkan kişi için `room:user_left { user_id }` yayınlanıyor (sesli görüşmede bağlantıyı kapatmak için de gerekli).

**Canlı durum deposu (`realtime/state.py`)**

- Sözleşmeye eklenenler: `seat_index_of`, `set_mic_blocked` / `mic_blocked_ids`, `mute_chat` / `chat_mute_remaining`, `grant_seat_invite` / `consume_seat_invite`, `append_chat` / `recent_chat` / `remove_chat`, `listener_ids`, `is_in_room`, `drop_room`.
- Süreli kayıtlar (atma yasağı, sohbet susturması, koltuk daveti) tek bir yapıda tutuluyor. Redis'te her biri süreli anahtar olacak. Son mesajlar Redis'te `RPUSH` + `LTRIM` olacak.
- `RoomHub`'a `send_to_user` (odadaki tek kişiye) ve `disconnect_room` (herkesi çıkar) eklendi.

**Frontend (`screens/room.js`)**

- Üstteki avatar grubuna dokununca **Odadakiler** listesi açılıyor. Birine dokununca kişi paneli açılıyor.
- Kişi panelinde yalnızca yetkimiz olan işlemler görünüyor: koltuğa davet et, koltuktan indir, mikrofonunu kapat / engeli kaldır, sohbette sustur (süre seçimi) / susturmayı kaldır, VIP yap / al, yönetici yap / al (yalnızca oda sahibi), odadan at.
- Sohbetteki bir mesaja dokununca: kendi mesajını ya da yetki varsa başkasınınkini silme.
- Koltuğa davet gelince "Koltuğa otur" paneli çıkıyor; ilk boş koltuğa oturtuyor.
- Menüde (⋮) "Oda ayarları" (yöneticiler) ve "Odayı kapat" (onaylı, yalnızca oda sahibi).
- Koltukta ve sohbette rol etiketleri (Oda Sahibi / Yönetici / VIP). Mikrofonu engellenen koltukta kırmızı kilit simgesi.
- `api.js`: yeni metodlar hem `httpApi` hem `mockApi`'de (mock sadeleştirilmiş).

### Doğrulama

- `python -m pytest`: **26 test geçti** (3'ü yeni: mikrofon engeli + susturma + mesaj silme + son mesajlar; dinleyici listesi + davetle koltuk; oda ayarları + kapatma). Eski moderasyon testi yeni rol ucuna göre güncellendi.
- Tarayıcıda (oda sahibi `muti` + ayrı bir misafir bağlantısı) denendi:
  - Dinleyici listesi açıldı.
  - Kişi panelindeki işlemler göründü.
  - Sohbette 5 dk susturma: misafirin mesajı `chat_muted` ile reddedildi.
  - Mesaj silme çalıştı.
  - Oda ayarlarından ad ve duyuru değişti, ekrana anında yansıdı.

### Açık kalanlar

- **Veritabanı şeması değişti** (`rooms.free_seating` kolonu, `room_members` tablosu). Migration aracı (Alembic) olmadığı için eski `backend/app.db` silindi; açılışta örnek veriyle yeniden oluştu. Eski veritabanında açılmaya çalışılırsa hata verir; çözümü dosyayı silmek.
- Mikrofon engelini şimdilik istemci uyguluyor. Sesi sunucu tarafında kesmek SFU'lu ses sağlayıcısıyla mümkün olacak (WebRTC aşaması).
- Koltuğa davet paneli tarayıcıda elle denenmedi; davet akışını backend testi kapsıyor.
- Uygulama geneli yönetim (kullanıcı banlama, şikâyet inceleme) yok.

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
