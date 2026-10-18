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
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.core.security import hash_password
from app.models import CoinPackage, Conversation, Follow, Gift, Message, Room, Transaction, User
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

# (id, coins, bonus, price_label, is_popular, is_best_value)
COIN_PACKAGES = [
    (1, 600, 0, "₺29,99", False, False), (2, 1500, 150, "₺69,99", False, False),
    (3, 3200, 480, "₺149,99", True, False), (4, 6800, 1360, "₺299,99", False, False),
    (5, 14000, 3500, "₺599,99", False, False), (6, 36000, 10800, "₺1.499,99", False, True),
]

# Ana kullanıcının sohbetleri: (karşıdaki kişi, okunmamış sayısı, [(ben mi yazdım, metin, kaç dakika önce)])
CONVERSATIONS = [
    (2001, 2, [(False, "Bu akşam odaya gelecek misin?", 14), (True, "Gelirim, 10 dakikaya oradayım.", 11), (False, "Süper, koltuk ayırıyorum 🎤", 10)]),
    (2010, 1, [(False, "Zar turnuvasına takım lazım, var mısın?", 150)]),
    (2003, 0, [(True, "Dünkü şarkının adı neydi?", 1500), (False, "Listeyi sana atıyorum 🎵", 1490)]),
    (2008, 0, [(False, "Hediye için teşekkürler 🌹", 4400), (True, "Rica ederim 🙂", 4390)]),
]

# Liderlik tablosu dolu görünsün diye geçmiş hediye toplamları: (kullanıcı, toplam coin)
TOP_GIFTERS = [(2001, 184500), (2012, 126300), (2015, 98750), (2003, 61200), (2010, 40800)]


async def seed_database(db: AsyncSession) -> None:
    """Veritabanı boşsa örnek veriyi ekler. Doluysa hiçbir şey yapmaz."""
    if await db.scalar(select(func.count(User.id))):
        return

    now = utcnow()
    # Parolayı bir kez hash'leyip herkese aynı hash'i veriyoruz (bcrypt yavaş, 16 kez beklemeyelim).
    password_hash = await hash_password(DEMO_PASSWORD)

    for (uid, username, name, age, city, avatar, cover, bio, vip, level, verified, _online,
         joined_days, followers, following, friends, visitors) in USERS:
        db.add(User(
            id=uid, username=username, email=f"{username}@demo.local", password_hash=password_hash,
            display_name=name, age=age, city=city,
            avatar_url=f"assets/avatars/{avatar}.jpg", cover_url=f"assets/covers/{cover}.jpg",
            bio=bio, vip_level=vip, level=level, is_verified=verified,
            followers_count=followers, following_count=following, friends_count=friends, visitors_count=visitors,
            coin_balance=12450 if uid == MAIN_USER_ID else 5000,
            created_at=now - timedelta(days=joined_days),
        ))
    await db.flush()   # kullanıcılar önce yazılsın; aşağıdaki satırlar onlara bağlı

    for rid, title, category, cover, is_live, _listeners, host_id, announcement, seats in ROOMS:
        db.add(Room(
            id=rid, title=title, category=category, cover_url=f"assets/covers/{cover}.jpg",
            is_live=is_live, host_id=host_id, announcement=announcement, seat_count=len(seats),
        ))
    for gid, name, emoji, price in GIFTS:
        db.add(Gift(id=gid, name=name, emoji=emoji, price=price))
    for pid, coins, bonus, price_label, popular, best in COIN_PACKAGES:
        db.add(CoinPackage(id=pid, coins=coins, bonus=bonus, price_label=price_label, is_popular=popular, is_best_value=best))
    await db.flush()

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
    for uid, total in TOP_GIFTERS:
        db.add(Transaction(user_id=uid, type="gift_sent", currency="coin", amount=-total, balance_after=5000,
                           label="Hediyeler (örnek veri)", created_at=now - timedelta(days=5)))

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
