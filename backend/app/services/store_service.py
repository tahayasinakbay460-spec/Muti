"""
Mağaza: kozmetik eşya kataloğu, satın alma, takma/çıkarma, kimin neyi taktığı.

Para hareketi wallet_service.change_balance ile yapılır; eşyanın verilmesi ile coinin
düşmesi aynı transaction içindedir (ya ikisi birden olur ya hiçbiri).
"""
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.logs import audit
from app.core.timefmt import as_utc
from app.models import StoreItem, User, UserItem
from app.schemas.store import OwnedItemOut, StoreItemOut, StorePurchaseResult
from app.schemas.user import EntryEffect
from app.services import wallet_service


# ── Takılı kozmetikler (her kullanıcı listesinde çağrılır) ─────────────────────

async def equipped_cosmetics(db: AsyncSession, user_ids: list[int]) -> dict[int, dict]:
    """
    Verilen kullanıcıların takılı ve süresi dolmamış eşyaları, TEK sorguyla:
    { kullanıcı id: {"frame": ..., "entry_effect": ..., "chat_bubble": ...} }
    """
    if not user_ids:
        return {}
    rows = await db.execute(
        select(UserItem.user_id, StoreItem)
        .join(StoreItem, StoreItem.id == UserItem.item_id)
        .where(UserItem.user_id.in_(user_ids), UserItem.is_equipped, UserItem.expires_at > utcnow())
    )
    result: dict[int, dict] = {}
    for user_id, item in rows:
        cosmetics = result.setdefault(user_id, {})
        if item.kind == "entry_effect":
            cosmetics["entry_effect"] = EntryEffect(name=item.name, style=item.style, emoji=item.emoji)
        else:
            # "frame" ve "chat_bubble" türlerinin adı UserOut'taki alan adıyla aynı.
            cosmetics[item.kind] = item.style
    return result


# ── Katalog ───────────────────────────────────────────────────────────────────

def _item_out(item: StoreItem, owned: UserItem | None, now: datetime) -> StoreItemOut:
    out = StoreItemOut.model_validate(item)
    if owned is not None and as_utc(owned.expires_at) > now:
        out.is_owned = True
        out.owned_until = as_utc(owned.expires_at)
        out.is_equipped = owned.is_equipped
    return out


async def list_items(db: AsyncSession, user_id: int, kind: str | None = None) -> list[StoreItemOut]:
    statement = select(StoreItem).where(StoreItem.is_active).order_by(StoreItem.kind, StoreItem.sort_order, StoreItem.id)
    if kind:
        statement = statement.where(StoreItem.kind == kind)
    items = list(await db.scalars(statement))
    owned = {
        row.item_id: row
        for row in await db.scalars(select(UserItem).where(UserItem.user_id == user_id))
    }
    now = utcnow()
    return [_item_out(item, owned.get(item.id), now) for item in items]


async def list_owned(db: AsyncSession, user_id: int) -> list[OwnedItemOut]:
    """Bir kullanıcının süresi dolmamış eşyaları (profilde herkes görebilir)."""
    rows = await db.execute(
        select(UserItem, StoreItem)
        .join(StoreItem, StoreItem.id == UserItem.item_id)
        .where(UserItem.user_id == user_id, UserItem.expires_at > utcnow())
        .order_by(StoreItem.kind, StoreItem.sort_order, StoreItem.id)
    )
    return [
        OwnedItemOut(
            id=item.id, kind=item.kind, name=item.name, style=item.style, emoji=item.emoji,
            owned_until=as_utc(owned.expires_at), is_equipped=owned.is_equipped,
        )
        for owned, item in rows
    ]


async def _get_item(db: AsyncSession, item_id: int) -> StoreItem:
    item = await db.get(StoreItem, item_id)
    if item is None or not item.is_active:
        raise NotFoundError("Eşya bulunamadı.")
    return item


# ── Eşya verme ve takma ───────────────────────────────────────────────────────

async def _unequip_others(db: AsyncSession, user_id: int, item: StoreItem) -> None:
    """
    Bu kullanıcının bu türden takılı DİĞER eşyasını çıkarır (her türden yalnızca biri takılı olur).
    Eşyanın kendisi hariç tutulur: o satır bellekte zaten yüklü; toplu güncelleme onu da
    değiştirseydi bellekteki kopya eskide kalır ve "tak" işlemi veritabanına yazılmazdı.
    """
    same_kind = select(StoreItem.id).where(StoreItem.kind == item.kind, StoreItem.id != item.id)
    await db.execute(
        update(UserItem)
        .where(UserItem.user_id == user_id, UserItem.item_id.in_(same_kind), UserItem.is_equipped)
        .values(is_equipped=False)
        .execution_options(synchronize_session=False)
    )


async def grant_item(
    db: AsyncSession, user_id: int, item: StoreItem, *, days: int | None = None,
    until: datetime | None = None, equip: bool = True,
) -> UserItem:
    """
    Kullanıcıya eşya verir. Mağaza alımı, VIP üyelik ve hediye paketi bunu kullanır.

    `days`: eşya zaten varsa ve süresi dolmadıysa süre KALAN sürenin üstüne eklenir
            (30 gün daha alan kişi kalan 5 gününü kaybetmesin).
    `until`: süreyi belirli bir ana kadar uzatır (VIP eşyaları üyelik bitince biter).
    DİKKAT: commit yapmaz; çağıran taraf para hareketiyle birlikte commit eder.
    """
    now = utcnow()
    owned = await db.scalar(select(UserItem).where(UserItem.user_id == user_id, UserItem.item_id == item.id))
    current_end = as_utc(owned.expires_at) if owned is not None else now
    start = max(current_end, now)
    new_end = start + timedelta(days=days) if days is not None else max(until, current_end)

    if equip:
        await _unequip_others(db, user_id, item)
    if owned is None:
        owned = UserItem(user_id=user_id, item_id=item.id, expires_at=new_end, is_equipped=equip)
        db.add(owned)
    else:
        owned.expires_at = new_end
        owned.is_equipped = equip or owned.is_equipped
    await db.flush()
    return owned


async def set_equipped(db: AsyncSession, user_id: int, item_id: int, equipped: bool) -> StoreItemOut:
    item = await _get_item(db, item_id)
    owned = await db.scalar(select(UserItem).where(UserItem.user_id == user_id, UserItem.item_id == item_id))
    now = utcnow()
    if owned is None or as_utc(owned.expires_at) <= now:
        raise ForbiddenError("Bu eşyaya sahip değilsin.", code="item_not_owned")
    if equipped:
        await _unequip_others(db, user_id, item)
    owned.is_equipped = equipped
    await db.commit()
    return _item_out(item, owned, now)


# ── Satın alma ────────────────────────────────────────────────────────────────

async def purchase_item(
    db: AsyncSession, user_id: int, item_id: int, days: int, idempotency_key: str | None,
) -> StorePurchaseResult:
    """
    Eşyayı coinle satın alır ve takar. Fiyatı sunucu belirler (istemci yalnızca süreyi seçer).
    Aynı idempotency anahtarı tekrar gelirse ikinci kez para düşmez, güncel durum döner.
    """
    async def replay() -> StorePurchaseResult:
        items = await list_items(db, user_id)
        return StorePurchaseResult(
            coin_balance=await wallet_service.get_coin_balance(db, user_id),
            item=next(i for i in items if i.id == item_id),
        )

    if await wallet_service.find_by_idempotency_key(db, user_id, idempotency_key):
        return await replay()

    item = await _get_item(db, item_id)
    user = await db.get(User, user_id)
    if item.vip_level_required and user.active_vip_level() < item.vip_level_required:
        raise ForbiddenError(f"Bu eşya VIP {item.vip_level_required} ve üstüne özel.", code="vip_required")
    price = item.price_7d if days == 7 else item.price_30d

    try:
        coin_balance = await wallet_service.change_balance(
            db, user_id=user_id, currency="coin", delta=-price, type="store_purchase",
            label=f"Mağaza: {item.name} ({days} gün)", item_id=item.id, idempotency_key=idempotency_key,
        )
        owned = await grant_item(db, user_id, item, days=days)
        await db.commit()
        audit("store_purchase", item_id=item.id, days=days, price=price)
    except IntegrityError:
        # Aynı anahtarla eşzamanlı ikinci istek ya da aynı eşyanın aynı anda iki kez alınması.
        await db.rollback()
        if await wallet_service.find_by_idempotency_key(db, user_id, idempotency_key):
            return await replay()
        raise ConflictError("İşlem çakıştı, tekrar dene.", code="purchase_conflict")
    except Exception:
        await db.rollback()
        raise
    return StorePurchaseResult(coin_balance=coin_balance, item=_item_out(item, owned, utcnow()))
