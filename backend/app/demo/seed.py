"""
DEMO KISAYOLU — örnek veri.

Uygulama ilk açıldığında ekranlar boş görünmesin diye örnek kullanıcılar, odalar,
hediyeler ve sohbetler yükler. Veriler frontend'deki js/mock-data.js ile aynıdır.

Yalnızca DEMO_MODE=true iken çalışır. İki parçadır:
  seed_database    → veritabanı boşsa kalıcı verileri bir kez ekler
  seed_live_state  → koltuklarda kimin oturduğu gibi canlı verileri HER açılışta
                     yeniden kurar (bellekte tutulduğu için sunucu kapanınca silinir)

Bütün örnek hesapların parolası: demo1234   (ör. kullanıcı adı: muti)
Sıfırdan başlamak için sunucuyu durdurup backend/app.db dosyasını silmek yeterli.

Not: Burada satırlara elle id veriyoruz. PostgreSQL'e geçildiğinde bu, otomatik id
sayaçlarını geride bırakır; seed sonrasında sayaçların (sequence) ileri alınması gerekir.
"""
import random
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.core.security import hash_password
from app.models import (
    Agency, AgencyMember, CoinPackage, Report, Conversation, Couple, Event, Family, FamilyMember, FamilyMessage, Follow, Gift, Message, Room,
    RoomMessage, StoreItem, Transaction, User,
)
from app.services import store_service, vip_service
from app.realtime.state import InMemoryRoomStateStore, RoomStateStore

DEMO_PASSWORD = "demo1234"
MAIN_USER_ID = 102938   # "muti": web demodaki ana kullanıcı

# (id, username, display_name, age, city, avatar, cover, bio, vip, level, verified, online,
#  joined_days, followers, following, friends, visitors)
USERS = [
    (MAIN_USER_ID, "muti", "Muti", 26, "Ankara", "m1", "profile", "Güzel insanlar, güzel sohbetler... 🌿", 6, 28, True, False, 428, 1200, 328, 56, 12),
    (2001, "merve", "Merve", 25, "İzmir", "w1", "coast", "Havuz Sohbeti her akşam 21:00 🌴", 8, 41, True, True, 610, 8400, 210, 132, 94),
    (2002, "kaan", "Kaan", 27, "Bursa", "m2", "city", "Gitar, kahve, gece sohbeti.", 3, 19, False, True, 201, 640, 180, 44, 8),
    (2003, "selin", "Selin", 23, "İstanbul", "w2", "sky", "Müzik olmadan olmaz 🎵", 5, 33, True, True, 390, 3100, 402, 88, 31),
    (2004, "emre", "Emre", 26, "İstanbul", "m3", "night", "Okey ve tavla ustası.", 2, 15, False, True, 120, 410, 256, 37, 5),
    (2005, "ada", "Ada", 22, "Antalya", "w3", "beach", "Yeni insanlarla tanışmayı severim.", 4, 22, False, True, 95, 980, 150, 61, 17),
    (2006, "burak", "Burak", 29, "Ankara", "m4", "mountain", "Dağ, kamp, sohbet.", 1, 9, False, False, 60, 150, 90, 20, 3),
    (2007, "ece", "Ece", 24, "Eskişehir", "w4", "canal", "Kitap kulübü odasının sahibi 📚", 3, 17, False, True, 240, 720, 310, 52, 9),
    (2008, "zeynep", "Zeynep", 24, "Ankara", "w5", "terrace", "Kahve ve uzun sohbetler ☕", 2, 12, False, True, 75, 530, 204, 40, 11),
    (2009, "defne", "Defne", 23, "İzmir", "w6", "lighthouse", "Şarkı söylemeyi çok severim.", 4, 25, True, True, 310, 2200, 180, 73, 26),
    (2010, "can", "Can", 28, "Adana", "m5", "canyon", "Her akşam oyun odasındayım 🎲", 5, 30, False, True, 280, 1500, 260, 69, 14),
    (2011, "elif", "Elif", 25, "Muğla", "w7", "coast", "Deniz, güneş, müzik.", 1, 8, False, False, 40, 210, 120, 18, 4),
    (2012, "mert", "Mert", 30, "İstanbul", "m6", "guitar", "Canlı müzik odası, her cuma.", 7, 38, True, True, 520, 5600, 300, 110, 48),
    (2013, "irem", "İrem", 22, "Konya", "w8", "sky", "Yeni buradayım, selam 👋", 0, 3, False, True, 6, 45, 60, 7, 2),
    (2014, "onur", "Onur", 27, "Trabzon", "m7", "mountain", "Futbol ve tavla.", 2, 14, False, True, 150, 380, 220, 33, 6),
    (2015, "naz", "Naz", 24, "İstanbul", "w9", "night", "Gece kuşu 🌙", 6, 35, True, True, 400, 4300, 190, 95, 39),
]

# (id, title, category, cover, is_live, demo dinleyici sayısı, host_id, announcement,
#  koltuklar: sırayla oturan kullanıcı id'si | None=boş | "locked"=kilitli;  eksi id = mikrofonu kapalı)
ROOMS = [
    (102938, "Havuz Sohbeti 🌴", "chat", "beach", False, 28, 2001, "Yeni gelenler kendini tanıtsın, herkese saygı şart.",
     [2001, -2002, 2003, 2004, 2005, -2006, 2007, "locked"]),
    (104211, "Gece Muhabbeti", "chat", "night", True, 18, 2015, "Gece 3'e kadar buradayız.",
     [2015, 2008, -2014, None, 2011, None, None, "locked"]),
    (105876, "Canlı Müzik", "music", "music", False, 32, 2012, "İstek parça için sohbete yazın.",
     [2012, 2009, -2003, 2002, None, None, None, None]),
    (107340, "Oyun Odası", "game", "game", True, 21, 2010, "Zar turnuvası 22:00'de başlıyor.",
     [2010, 2004, 2014, -2006, None, None, None, None]),
    (108102, "Kahve Molası ☕", "new_people", "cafe", False, 14, 2008, "Yeni gelenlere özel tanışma odası.",
     [2008, 2013, None, None, 2005, None, None, None]),
    (109455, "Akustik Akşamlar", "music", "guitar", True, 26, 2002, "Bu akşam Türkçe akustik.",
     [2002, 2009, 2007, None, None, None, None, "locked"]),
    (110027, "Kitap Kulübü 📚", "chat", "terrace", False, 9, 2007, "Bu hafta: Kürk Mantolu Madonna.",
     [2007, 2013, None, None, None, None, None, None]),
    (111390, "Yeni Tanışanlar", "new_people", "city", True, 37, 2005, "Herkes kısaca kendini tanıtsın.",
     [2005, 2011, 2014, 2013, 2006, None, None, None]),
]

GIFTS = [
    (1, "Gül", "🌹", 10), (2, "Kalp", "💖", 20), (3, "Kahve", "☕", 30), (4, "Mikrofon", "🎤", 50),
    (5, "Pasta", "🎂", 99), (6, "Taç", "👑", 299), (7, "Spor Araba", "🏎️", 999), (8, "Yat", "🛥️", 2999),
    (9, "Şato", "🏰", 5999), (10, "Roket", "🚀", 9999), (11, "Ejderha", "🐉", 19999), (12, "Gezegen", "🪐", 49999),
]
# Şanslı hediyeler: (id, ad, emoji, fiyat). Gönderen coin geri kazanabilir (bkz. gift_service).
LUCKY_GIFTS = [(13, "Şanslı Yonca", "🍀", 10), (14, "Şans Kurabiyesi", "🥠", 50), (15, "Altın Zar", "🎲", 100)]

# Mağaza eşyaları: (id, tür, ad, CSS sınıfı, emoji, 7 gün fiyatı, 30 gün fiyatı, gereken VIP seviyesi)
# Çerçeve id'leri 1-8, giriş efektleri 101-, sohbet balonları 201-. VIP kademeleri bu id'leri
# kullanır (bkz. services/vip_service.py VIP_TIERS).
STORE_ITEMS = [
    (1, "frame", "Klasik", "frame-classic", "", 300, 900, 0),
    (2, "frame", "Neon", "frame-neon", "", 500, 1500, 0),
    (3, "frame", "Altın", "frame-gold", "", 1000, 3000, 0),
    (4, "frame", "Buz", "frame-ice", "", 500, 1500, 0),
    (5, "frame", "Alev", "frame-fire", "", 800, 2400, 0),
    (6, "frame", "Orman", "frame-forest", "", 500, 1500, 0),
    (7, "frame", "Galaksi", "frame-galaxy", "", 1500, 4500, 0),
    (8, "frame", "Kraliyet", "frame-royal", "", 2500, 7500, 2),
    (101, "entry_effect", "Kıvılcım", "entry-spark", "✨", 500, 1500, 0),
    (102, "entry_effect", "Spor Araba", "entry-car", "🏎️", 1200, 3600, 0),
    (103, "entry_effect", "Roket", "entry-rocket", "🚀", 2000, 6000, 0),
    (104, "entry_effect", "Taç", "entry-crown", "👑", 3000, 9000, 2),
    (105, "entry_effect", "Ejderha", "entry-dragon", "🐉", 5000, 15000, 3),
    (201, "chat_bubble", "Pembe", "bubble-pink", "💗", 300, 900, 0),
    (202, "chat_bubble", "Okyanus", "bubble-ocean", "🌊", 300, 900, 0),
    (203, "chat_bubble", "Altın", "bubble-gold", "⭐", 800, 2400, 0),
    (204, "chat_bubble", "Neon", "bubble-neon", "💜", 1200, 3600, 1),
]

# (id, coins, bonus, price_label, is_popular, is_best_value)
COIN_PACKAGES = [
    (1, 600, 0, "₺29,99", False, False), (2, 1500, 150, "₺69,99", False, False),
    (3, 3200, 480, "₺149,99", True, False), (4, 6800, 1360, "₺299,99", False, False),
    (5, 14000, 3500, "₺599,99", False, False), (6, 36000, 10800, "₺1.499,99", False, True),
]

# Hediye paketleri: (id, başlık, coin, bonus, fiyat, eşya id, eşya gün, tek seferlik mi)
GIFT_BUNDLES = [
    (7, "Başlangıç Paketi", 600, 300, "₺19,99", 2, 7, True),
    (8, "Kraliyet Paketi", 8000, 2000, "₺399,99", 103, 30, False),
]

# Aileler: (id, ad, rozet, slogan, kurucu, [(üye, rol)]). Ana kullanıcı hiçbirinde değil:
# demoda aileye katılma ya da aile kurma gösterilebilsin.
FAMILIES = [
    (1, "Gece Kuşları", "🦉", "Sabaha kadar sohbet, oyun ve müzik.", 2001,
     [(2003, "admin"), (2008, "member"), (2011, "member"), (2015, "member")]),
    (2, "Aslanlar", "🦁", "Hediyede, oyunda, sohbette bir numara.", 2012,
     [(2010, "admin"), (2004, "member"), (2014, "member")]),
    (3, "Müzik Kulübü", "🎵", "Her akşam canlı müzik odası.", 2009, [(2007, "member"), (2013, "member")]),
]
FAMILY_MESSAGES = [
    (1, 2001, "Bu akşam 21:00'de aile odasında buluşuyoruz 🎉", 180),
    (1, 2003, "Ben geliyorum, şarkı listesini hazırladım 🎵", 170),
    (1, 2015, "Haftalık sıralamada ilk 3'e girelim!", 60),
]
# CP: (kullanıcı, kullanıcı, durum, teklif eden). Ada'nın ana kullanıcıya bekleyen teklifi var.
COUPLES = [(2002, 2003, "active", 2002), (2005, MAIN_USER_ID, "pending", 2005)]

# Yönetim paneli için demo yönetici hesabı (kullanıcı adı: admin, parola: demo1234).
ADMIN_USER_ID = 1
# Ajans: (id, ad, sahibi, komisyon %, [(yayıncı, durum, aylık elmas hedefi)]). Ana kullanıcıya davet bekliyor.
AGENCIES = [
    (1, "Yıldız Ajans", 2012, 15, [(2001, "active", 200_000), (2003, "active", 100_000), (MAIN_USER_ID, "invited", 0)]),
]
# İnceleme bekleyen şikâyetler: (şikâyet eden, tür, hedef, sebep, açıklama)
REPORTS = [
    (2004, "user", 2006, "spam", "Odada sürekli aynı reklam mesajını atıyor."),
    (2007, "user", 2006, "harassment", "Özel mesajdan rahatsız edici mesajlar gönderdi."),
    (2005, "room", 108102, "inappropriate", "Oda başlığı ve duyurusu uygunsuz."),
]

# Oda sohbet geçmişi (yönetim panelinde görünsün): (oda, kullanıcı, mesaj, kaç dakika önce)
ROOM_CHAT = [
    (104211, 2015, "Herkese iyi geceler, hoş geldiniz 🌙", 95), (104211, 2001, "Bu akşamki şarkı listesi harika", 90),
    (104211, 2004, "Koltuğa oturabilir miyim?", 70), (104211, 2015, "Tabii, 3. koltuk boş 🎤", 68),
    (102938, 2001, "Yeni gelenler kendini tanıtsın lütfen", 50), (102938, 2005, "Merhaba ben Ada, Antalya'dan 👋", 48),
    (102938, 2006, "Ucuz coin için profilime bakın!!!", 40), (102938, 2001, "Reklam yasak, lütfen dikkat", 39),
    (107340, 2010, "Zar turnuvası 22:00'de başlıyor", 30), (107340, 2014, "Ben varım, takım kuralım", 25),
]
# Yönetim panelinin grafikleri dolu görünsün diye son 30 günün örnek satış ve hediye geçmişi.
# Sabit tohumlu rastgelelik: her kurulumda aynı sayılar çıkar. Bakiyeler bu geçmişten
# hesaplanmaz (örnek veri), yalnızca grafik ve listeler için.
HISTORY_DAYS = 30
HISTORY_USERS = [2001, 2002, 2003, 2004, 2005, 2007, 2008, 2010, 2012, 2015]

# Ana kullanıcının sohbetleri: (karşıdaki kişi, okunmamış sayısı, [(ben mi yazdım, metin, kaç dakika önce)])
CONVERSATIONS = [
    (2001, 2, [(False, "Bu akşam odaya gelecek misin?", 14), (True, "Gelirim, 10 dakikaya oradayım.", 11), (False, "Süper, koltuk ayırıyorum 🎤", 10)]),
    (2010, 1, [(False, "Zar turnuvasına takım lazım, var mısın?", 150)]),
    (2003, 0, [(True, "Dünkü şarkının adı neydi?", 1500), (False, "Listeyi sana atıyorum 🎵", 1490)]),
    (2008, 0, [(False, "Hediye için teşekkürler 🌹", 4400), (True, "Rica ederim 🙂", 4390)]),
]

# Liderlik tablosu dolu görünsün diye geçmiş hediye toplamları: (kullanıcı, toplam coin)
TOP_GIFTERS = [(2001, 184500), (2012, 126300), (2015, 98750), (2003, 61200), (2010, 40800)]
# Bu hediyeleri kim aldı, hangi odada (sıralamaların "Çekiciler" ve "Odalar" sekmeleri dolsun):
# gönderen → (alan, oda). Hepsi birkaç saat önce: "bugün / bu hafta / bu ay" dönemlerinin hepsinde görünür.
GIFT_TARGETS = {2001: (2015, 104211), 2012: (2003, 102938), 2015: (2001, 104211), 2003: (2012, 102938), 2010: (2005, 107340)}


async def seed_database(db: AsyncSession) -> None:
    """Veritabanı boşsa örnek veriyi ekler. Doluysa hiçbir şey yapmaz."""
    if await db.scalar(select(func.count(User.id))):
        return

    now = utcnow()
    # Parolayı bir kez hash'leyip herkese aynı hash'i veriyoruz (bcrypt yavaş, 16 kez beklemeyelim).
    password_hash = await hash_password(DEMO_PASSWORD)

    for (uid, username, name, age, city, avatar, cover, bio, vip, level, verified, _online,
         joined_days, followers, following, friends, visitors) in USERS:
        # Örnek verideki eski VIP sayıları (1-8) üç kademeye indirilir. Ana kullanıcı VIP
        # değildir: demoda VIP satın alma gösterilebilsin.
        vip = 0 if uid == MAIN_USER_ID or not vip else 1 if vip <= 2 else 2 if vip <= 5 else 3
        db.add(User(
            id=uid, username=username, email=f"{username}@demo.local", password_hash=password_hash,
            display_name=name, age=age, city=city,
            avatar_url=f"assets/avatars/{avatar}.jpg", cover_url=f"assets/covers/{cover}.jpg",
            bio=bio, vip_level=vip, level=level, is_verified=verified,
            followers_count=followers, following_count=following, friends_count=friends, visitors_count=visitors,
            coin_balance=12450 if uid == MAIN_USER_ID else 5000,
            created_at=now - timedelta(days=joined_days),
        ))
    db.add(User(
        id=ADMIN_USER_ID, username="admin", email="admin@demo.local", password_hash=password_hash,
        display_name="Muti Yönetim", is_admin=True, is_verified=True, created_at=now - timedelta(days=500),
    ))
    await db.flush()   # kullanıcılar önce yazılsın; aşağıdaki satırlar onlara bağlı

    for rid, title, category, cover, is_live, _listeners, host_id, announcement, seats in ROOMS:
        db.add(Room(
            id=rid, title=title, category=category, cover_url=f"assets/covers/{cover}.jpg",
            is_live=is_live, host_id=host_id, announcement=announcement, seat_count=len(seats),
        ))
    for gid, name, emoji, price in GIFTS:
        db.add(Gift(id=gid, name=name, emoji=emoji, price=price))
    for gid, name, emoji, price in LUCKY_GIFTS:
        db.add(Gift(id=gid, name=name, emoji=emoji, price=price, is_lucky=True))
    for iid, kind, name, style, emoji, price_7d, price_30d, vip_required in STORE_ITEMS:
        db.add(StoreItem(id=iid, kind=kind, name=name, style=style, emoji=emoji, price_7d=price_7d,
                         price_30d=price_30d, vip_level_required=vip_required, sort_order=iid))
    await db.flush()   # paketler eşyalara bağlı; eşyalar önce yazılsın
    for pid, coins, bonus, price_label, popular, best in COIN_PACKAGES:
        db.add(CoinPackage(id=pid, coins=coins, bonus=bonus, price_label=price_label, is_popular=popular, is_best_value=best))
    for pid, title, coins, bonus, price_label, item_id, item_days, one_time in GIFT_BUNDLES:
        db.add(CoinPackage(id=pid, title=title, coins=coins, bonus=bonus, price_label=price_label,
                           item_id=item_id, item_days=item_days, is_one_time=one_time))
    await db.flush()

    # Kozmetikler: ana kullanıcı birkaç eşyaya sahip; VIP örnek kullanıcılar kademe eşyalarını takıyor.
    items = {item.id: item for item in await db.scalars(select(StoreItem))}
    for item_id, days, equip in ((2, 30, True), (1, 7, False), (102, 30, True), (201, 7, True)):
        await store_service.grant_item(db, MAIN_USER_ID, items[item_id], days=days, equip=equip)
    for user in await db.scalars(select(User).where(User.vip_level > 0)):
        for item_id in vip_service.VIP_TIERS[user.vip_level].item_ids:
            await store_service.grant_item(db, user.id, items[item_id], days=365)

    # Ana kullanıcı Merve ve Selin'i takip ediyor.
    db.add_all([Follow(follower_id=MAIN_USER_ID, followee_id=uid) for uid in (2001, 2003)])

    # Ana kullanıcının cüzdan geçmişi (son bakiye 12450 olacak şekilde).
    db.add_all([
        Transaction(user_id=MAIN_USER_ID, type="purchase", currency="coin", amount=3680, balance_after=12699,
                    label="Coin satın alma (₺149,99)", package_id=3, created_at=now - timedelta(days=3)),
        Transaction(user_id=MAIN_USER_ID, type="gift_sent", currency="coin", amount=-299, balance_after=12400,
                    label="Hediye: Taç x1 → Merve", counterparty_id=2001, gift_id=6, quantity=1,
                    created_at=now - timedelta(days=2)),
        Transaction(user_id=MAIN_USER_ID, type="reward", currency="coin", amount=50, balance_after=12450,
                    label="Günlük giriş ödülü", created_at=now - timedelta(days=1)),
    ])
    for hours, (uid, total) in enumerate(TOP_GIFTERS, start=1):
        receiver_id, room_id = GIFT_TARGETS[uid]
        sent_at = now - timedelta(hours=hours)
        db.add(Transaction(user_id=uid, type="gift_sent", currency="coin", amount=-total, balance_after=5000,
                           label="Hediyeler (örnek veri)", counterparty_id=receiver_id, room_id=room_id, created_at=sent_at))
        db.add(Transaction(user_id=receiver_id, type="gift_received", currency="diamond", amount=total // 2,
                           balance_after=total // 2, label="Hediyeler (örnek veri)", counterparty_id=uid,
                           room_id=room_id, created_at=sent_at))

    # Aileler, CP ve etkinlikler
    for fid, name, badge, slogan, owner_id, members in FAMILIES:
        db.add(Family(id=fid, name=name, badge=badge, slogan=slogan, owner_id=owner_id, member_count=len(members) + 1))
    await db.flush()
    for fid, _name, _badge, _slogan, owner_id, members in FAMILIES:
        db.add(FamilyMember(user_id=owner_id, family_id=fid, role="owner"))
        db.add_all([FamilyMember(user_id=uid, family_id=fid, role=role) for uid, role in members])
    db.add_all([
        FamilyMessage(family_id=fid, sender_id=uid, text=text, created_at=now - timedelta(minutes=minutes))
        for fid, uid, text, minutes in FAMILY_MESSAGES
    ])
    for a, b, status, requested_by in COUPLES:
        low, high = min(a, b), max(a, b)
        db.add(Couple(user_low_id=low, user_high_id=high, requested_by=requested_by, status=status,
                      accepted_at=now - timedelta(days=12) if status == "active" else None))
        if status == "active":
            for uid, partner in ((a, b), (b, a)):
                (await db.get(User, uid)).cp_partner_id = partner
        else:
            # Teklif edenin yüzük bedeli ödenmiş olsun (reddedilirse iade defterle tutarlı kalsın).
            db.add(Transaction(user_id=requested_by, type="cp_proposal", currency="coin", amount=-520,
                               balance_after=5000 - 520, label="CP teklifi → Muti", counterparty_id=MAIN_USER_ID,
                               created_at=now - timedelta(hours=3)))
    db.add_all([
        Event(title="Hafta Sonu Hediye Yarışı", emoji="🏆", metric="gifts_sent", rewards=[5000, 3000, 1000],
              description="Etkinlik süresince en çok hediye gönderen ilk 3 kişi coin kazanır.",
              starts_at=now - timedelta(days=1), ends_at=now + timedelta(days=6)),
        Event(title="Yıldızlar Gecesi", emoji="⭐", metric="gifts_received", rewards=[3000, 2000, 1000],
              description="En çok hediye alan yayıncılar ödüllendirildi.",
              starts_at=now - timedelta(days=10), ends_at=now - timedelta(days=1)),
    ])

    # Son 30 günün örnek satış ve hediye geçmişi (bugün hariç; bugünün hareketleri yukarıda)
    rng = random.Random(42)
    packages = {pid: coins + bonus for pid, coins, bonus, *_ in COIN_PACKAGES}
    gift_prices = [price for _gid, _name, _emoji, price in GIFTS]
    for days_ago in range(1, HISTORY_DAYS):
        day = now - timedelta(days=days_ago)
        # Hafta sonu daha hareketli
        activity = 1.6 if day.weekday() >= 5 else 1.0
        for _ in range(int(rng.randint(2, 6) * activity)):
            pid = rng.choice(list(packages))
            db.add(Transaction(user_id=rng.choice(HISTORY_USERS), type="purchase", currency="coin", amount=packages[pid],
                               balance_after=5000, label="Coin satın alma (örnek veri)", package_id=pid,
                               created_at=day - timedelta(minutes=rng.randint(0, 600))))
        for _ in range(int(rng.randint(6, 16) * activity)):
            sender, receiver = rng.sample(HISTORY_USERS, 2)
            price = rng.choice(gift_prices[:8]) * rng.choice([1, 1, 1, 5, 10])
            at = day - timedelta(minutes=rng.randint(0, 600))
            db.add(Transaction(user_id=sender, type="gift_sent", currency="coin", amount=-price, balance_after=5000,
                               label="Hediye (örnek veri)", counterparty_id=receiver, created_at=at))
            db.add(Transaction(user_id=receiver, type="gift_received", currency="diamond", amount=price // 2,
                               balance_after=price // 2, label="Hediye alındı (örnek veri)", counterparty_id=sender,
                               created_at=at))
        if rng.random() < 0.35:
            db.add(Transaction(user_id=rng.choice(HISTORY_USERS), type="vip_purchase", currency="coin",
                               amount=-rng.choice([3000, 8000]), balance_after=5000, label="VIP (örnek veri)",
                               created_at=day - timedelta(minutes=rng.randint(0, 600))))
    db.add_all([
        RoomMessage(room_id=rid, user_id=uid, public_id=f"seed{index}", text=text,
                    created_at=now - timedelta(minutes=minutes))
        for index, (rid, uid, text, minutes) in enumerate(ROOM_CHAT)
    ])

    # Ajans ve şikâyetler (yönetim paneli demoda dolu görünsün)
    for aid, name, owner_id, commission, members in AGENCIES:
        db.add(Agency(id=aid, name=name, owner_id=owner_id, commission_percent=commission))
        await db.flush()
        db.add_all([
            AgencyMember(user_id=uid, agency_id=aid, status=status, monthly_target=target,
                         joined_at=now - timedelta(days=20) if status == "active" else None)
            for uid, status, target in members
        ])
    db.add_all([
        Report(reporter_id=reporter, target_type=kind, target_id=target, reason=reason, details=details,
               created_at=now - timedelta(hours=index + 1))
        for index, (reporter, kind, target, reason, details) in enumerate(REPORTS)
    ])

    for other_id, unread, messages in CONVERSATIONS:
        low, high = min(MAIN_USER_ID, other_id), max(MAIN_USER_ID, other_id)
        last_from_me, last_text, last_minutes = messages[-1]
        conversation = Conversation(
            user_low_id=low, user_high_id=high,
            unread_low=unread if low == MAIN_USER_ID else 0,
            unread_high=unread if high == MAIN_USER_ID else 0,
            last_message_text=last_text,
            last_message_sender_id=MAIN_USER_ID if last_from_me else other_id,
            last_message_at=now - timedelta(minutes=last_minutes),
        )
        db.add(conversation)
        await db.flush()
        db.add_all([
            Message(conversation_id=conversation.id, sender_id=MAIN_USER_ID if from_me else other_id,
                    text=text, created_at=now - timedelta(minutes=minutes))
            for from_me, text, minutes in messages
        ])

    await db.commit()


async def seed_live_state(state: RoomStateStore) -> None:
    """Örnek odaların koltuklarını doldurur ve örnek kullanıcıları çevrimiçi gösterir."""
    # Bu "sahte kalabalık" yalnızca bellek içi demo deposunda var; Redis sürümünde olmayacak.
    if not isinstance(state, InMemoryRoomStateStore):
        return

    for rid, _title, _category, _cover, _is_live, listeners, _host_id, _announcement, seats in ROOMS:
        await state.ensure_room(rid, len(seats))
        state.demo_listener_base[rid] = listeners
        for index, occupant in enumerate(seats):
            if occupant == "locked":
                state.demo_set_seat(rid, index, is_locked=True)
            elif occupant is not None:
                # Eksi id = "bu kişi oturuyor ama mikrofonu kapalı" (yukarıdaki ROOMS notuna bak).
                state.demo_set_seat(rid, index, user_id=abs(occupant), is_muted=occupant < 0)

    state.demo_always_online = {user[0] for user in USERS if user[11]}
