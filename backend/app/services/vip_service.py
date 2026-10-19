"""
VIP üyelik: 30 günlük kademeli üyelik (1 Gümüş, 2 Altın, 3 Elmas).

Üyelik şunları verir: profilde ve sohbette VIP rozeti, üyelik süresince takılı gelen
eşyalar (çerçeve, giriş efekti, sohbet balonu), VIP'e özel mağaza eşyaları, her gün
alınabilen coin ödülü.

DEMO KISAYOLU: Üyelik coinle alınıyor. Canlıda gerçek TopTop gibi App Store / Google Play
aboneliği (otomatik yenilenen) olacak; mağazanın sunucusu yenilemeyi bize bildirecek.
"""
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.core.errors import ConflictError, ForbiddenError
from app.core.logs import audit
from app.core.timefmt import as_utc, local_today
from app.models import StoreItem, User
from app.schemas.store import DailyRewardResult, StoreItemBrief, VipPurchaseResult, VipStatus, VipTierOut
from app.services import store_service, wallet_service

VIP_DAYS = 30


@dataclass(frozen=True)
class VipTier:
    level: int
    name: str
    price_30d: int
    daily_coins: int
    item_ids: tuple[int, ...]   # üyelikle verilen mağaza eşyaları (bkz. demo/seed.py STORE_ITEMS)
    perks: tuple[str, ...]


# Kademeler kod içinde sabit: değiştirmek iş kararıdır, veritabanından değil koddan yapılır.
VIP_TIERS = {
    1: VipTier(1, "Gümüş", 3_000, 60, (3, 204), (
        "VIP 1 rozeti", "Altın çerçeve", "Neon sohbet balonu", "Her gün 60 coin",
    )),
    2: VipTier(2, "Altın", 8_000, 180, (8, 104, 204), (
        "VIP 2 rozeti", "Kraliyet çerçevesi", "Taç giriş efekti", "Neon sohbet balonu", "Her gün 180 coin",
    )),
    3: VipTier(3, "Elmas", 20_000, 500, (8, 105, 204), (
        "VIP 3 rozeti", "Kraliyet çerçevesi", "Ejderha giriş efekti", "Neon sohbet balonu", "Her gün 500 coin",
        "Bütün VIP eşyalarını satın alabilme",
    )),
}


async def get_status(db: AsyncSession, user: User) -> VipStatus:
    all_ids = {item_id for tier in VIP_TIERS.values() for item_id in tier.item_ids}
    items = {item.id: item for item in await db.scalars(select(StoreItem).where(StoreItem.id.in_(all_ids)))}
    level = user.active_vip_level()
    return VipStatus(
        level=level,
        expires_at=as_utc(user.vip_expires_at) if level and user.vip_expires_at else None,
        daily_reward_available=bool(level) and user.vip_daily_claimed_on != local_today(),
        tiers=[
            VipTierOut(
                level=tier.level, name=tier.name, price_30d=tier.price_30d, daily_coins=tier.daily_coins,
                perks=list(tier.perks),
                items=[StoreItemBrief.model_validate(items[i]) for i in tier.item_ids if i in items],
            )
            for tier in VIP_TIERS.values()
        ],
    )


async def purchase(db: AsyncSession, user: User, level: int, idempotency_key: str | None) -> VipPurchaseResult:
    """
    VIP üyelik alır ya da uzatır.
    - Aynı seviyeyi tekrar almak süreyi kalan sürenin üstüne 30 gün uzatır.
    - Daha yüksek seviyeye geçiş hemen başlar, 30 gün yeniden sayılır.
    - Daha yüksek bir üyelik sürerken düşük seviye alınamaz.
    """
    async def result() -> VipPurchaseResult:
        await db.refresh(user)
        return VipPurchaseResult(coin_balance=user.coin_balance, status=await get_status(db, user))

    if await wallet_service.find_by_idempotency_key(db, user.id, idempotency_key):
        return await result()

    tier = VIP_TIERS[level]
    current = user.active_vip_level()
    if current > level:
        raise ConflictError("Daha yüksek bir VIP üyeliğin zaten var.", code="vip_higher_active")
    if current >= level and user.vip_expires_at is None:
        raise ConflictError("Süresiz VIP üyeliğin var.", code="vip_permanent")

    now = utcnow()
    start = as_utc(user.vip_expires_at) if current == level else now
    expires_at = max(start, now) + timedelta(days=VIP_DAYS)

    try:
        await wallet_service.change_balance(
            db, user_id=user.id, currency="coin", delta=-tier.price_30d, type="vip_purchase",
            label=f"VIP {level} · {tier.name} ({VIP_DAYS} gün)", idempotency_key=idempotency_key,
        )
        user.vip_level = level
        user.vip_expires_at = expires_at
        # Üyelik eşyaları üyelikle birlikte biter ve hemen takılır.
        for item in await db.scalars(select(StoreItem).where(StoreItem.id.in_(tier.item_ids))):
            await store_service.grant_item(db, user.id, item, until=expires_at)
        await db.commit()
        audit("vip_purchase", vip_level=level, price=tier.price_30d, expires_at=expires_at.isoformat())
    except IntegrityError:
        await db.rollback()
        if await wallet_service.find_by_idempotency_key(db, user.id, idempotency_key):
            return await result()
        raise
    except Exception:
        await db.rollback()
        raise
    return await result()


async def claim_daily_reward(db: AsyncSession, user: User) -> DailyRewardResult:
    """Günlük VIP ödülü. Günde bir kez; iki istek aynı anda gelse bile yalnızca biri kazanır."""
    level = user.active_vip_level()
    if not level:
        raise ForbiddenError("Günlük ödül VIP üyelere özel.", code="vip_required")
    today = local_today()

    # "Bugün almadıysa bugün aldı olarak işaretle" tek komutla: aynı anda gelen ikinci
    # istek hiçbir satırı değiştiremez ve reddedilir (para kuralındaki yöntemin aynısı).
    marked = await db.execute(
        update(User)
        .where(User.id == user.id, or_(User.vip_daily_claimed_on.is_(None), User.vip_daily_claimed_on != today))
        .values(vip_daily_claimed_on=today)
        .execution_options(synchronize_session=False)
    )
    if marked.rowcount != 1:
        await db.rollback()
        raise ConflictError("Bugünkü ödülünü zaten aldın.", code="daily_reward_claimed")

    # Eski kayıtlarda 3'ten büyük seviye kalmışsa en üst kademe sayılır.
    coins = VIP_TIERS[min(level, max(VIP_TIERS))].daily_coins
    try:
        balance = await wallet_service.change_balance(
            db, user_id=user.id, currency="coin", delta=coins, type="vip_daily", label=f"VIP {level} günlük ödül",
        )
        await db.commit()
        audit("vip_daily_reward", vip_level=level, coins=coins)
    except Exception:
        await db.rollback()
        raise
    return DailyRewardResult(coins=coins, coin_balance=balance)
