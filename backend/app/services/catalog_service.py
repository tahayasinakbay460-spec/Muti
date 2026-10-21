"""
Başlangıç kataloğu: hediyeler, mağaza eşyaları, coin ve hediye paketleri.

Bunlar örnek veri değil, uygulamanın satış listesidir; canlıda da gerekir (yoksa hediye
paneli ve mağaza boş açılır). Veritabanında hiç hediye yoksa bir kez eklenir; sonrası
yönetim panelinden (Katalog) düzenlenir. Frontend mock verisi (js/mock-data.js) bununla aynıdır.
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import sync_id_sequences
from app.models import CoinPackage, Gift, StoreItem

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


async def ensure_starter_catalog(db: AsyncSession) -> None:
    """Katalog boşsa ekler (commit'i çağıran yapar). Doluysa hiçbir şeye dokunmaz."""
    if await db.scalar(select(func.count(Gift.id))):
        return
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
    # id'ler elle verildi; panelden eklenecek yeni hediye/paket çakışmasın.
    await sync_id_sequences(db)
