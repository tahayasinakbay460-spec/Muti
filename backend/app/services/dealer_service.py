"""
Coin bayileri: panel bayiyi tanımlar ve stok yükler, bayi kullanıcılara coin satar.
Kurallar ve para akışı: models/dealer.py.

Bakiye/stok değişikliklerinin hepsi wallet_service.change_balance ile yapılır (tek kapı kuralı);
burada yalnızca bayiye özgü kurallar var: durum, günlük sınır, kime satılabilir.
"""
from sqlalchemy import case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.logs import audit
from app.core.timefmt import as_utc, local_today
from app.models import CoinDealer, DealerStockOrder, Transaction, User
from app.schemas.dealer import (
    DealerAdminDetail, DealerAdminOut, DealerPanel, DealerPublicOut, DealerSaleOut, DealerSaleResult,
    DealerStockOrderOut,
)
from app.services import notification_service, staff_service, user_service, wallet_service

RECENT_SALES = 30


def _today() -> str:
    return local_today().isoformat()


def _sold_today(dealer: CoinDealer) -> int:
    """Sayaç başka güne aitse bugün henüz satış yok demektir."""
    return dealer.sold_today if dealer.sold_day == _today() else 0


async def _sales(db: AsyncSession, dealer_id: int, limit: int = RECENT_SALES) -> list[DealerSaleOut]:
    rows = list(await db.scalars(
        select(Transaction).where(Transaction.user_id == dealer_id, Transaction.type == "dealer_sale")
        .order_by(Transaction.id.desc()).limit(limit)
    ))
    users = await user_service.load_users_out(db, {row.counterparty_id for row in rows if row.counterparty_id}, None)
    return [
        DealerSaleOut(id=row.id, user=users.get(row.counterparty_id), coins=-row.amount, created_at=as_utc(row.created_at))
        for row in rows
    ]


# ── Kullanıcı tarafı ──────────────────────────────────────────────────────────

async def list_public(db: AsyncSession, viewer_id: int) -> list[DealerPublicOut]:
    """Resmi bayiler. Kullanıcı yalnızca bu listedekilerden almalı (sahte "bayi" dolandırıcılığına karşı)."""
    dealers = list(await db.scalars(
        select(CoinDealer).join(User, User.id == CoinDealer.user_id)
        .where(CoinDealer.status == "active", User.is_active).order_by(CoinDealer.created_at)
    ))
    users = await user_service.load_users_out(db, {d.user_id for d in dealers}, viewer_id)
    return [DealerPublicOut(user=users[d.user_id], note=d.note) for d in dealers if d.user_id in users]


async def _my_dealer(db: AsyncSession, user_id: int) -> CoinDealer:
    dealer = await db.get(CoinDealer, user_id)
    if dealer is None:
        raise ForbiddenError("Bayi değilsin.", code="not_dealer")
    return dealer


async def my_panel(db: AsyncSession, user_id: int) -> DealerPanel:
    dealer = await _my_dealer(db, user_id)
    return DealerPanel(status=dealer.status, stock=dealer.stock, daily_limit=dealer.daily_limit,
                       sold_today=_sold_today(dealer), recent_sales=await _sales(db, user_id))


async def _sale_replay(db: AsyncSession, dealer_id: int, previous: Transaction) -> DealerSaleResult:
    """Aynı idempotency anahtarı tekrar geldi: ikinci kez satma, ilk satışı dön."""
    dealer = await db.get(CoinDealer, dealer_id)
    await db.refresh(dealer)
    buyer = (await user_service.load_users_out(db, {previous.counterparty_id}, None)).get(previous.counterparty_id)
    return DealerSaleResult(stock=dealer.stock, sold_today=_sold_today(dealer), sale=DealerSaleOut(
        id=previous.id, user=buyer, coins=-previous.amount, created_at=as_utc(previous.created_at)))


async def sell(db: AsyncSession, dealer_id: int, buyer_id: int, coins: int, idempotency_key: str | None) -> DealerSaleResult:
    """
    Bayi bir kullanıcıya coin gönderir: bayinin stoğu düşer, kullanıcının coin'i artar, bugünkü satış
    sayacı artar. Üçü tek transaction'da; biri olmazsa hiçbiri olmaz.
    """
    previous = await wallet_service.find_by_idempotency_key(db, dealer_id, idempotency_key)
    if previous:
        return await _sale_replay(db, dealer_id, previous)
    dealer = await _my_dealer(db, dealer_id)
    if dealer.status != "active":
        raise ForbiddenError("Bayiliğin askıya alındı. Müşteri hizmetleriyle görüş.", code="dealer_suspended")
    if buyer_id == dealer_id:
        raise AppError("Kendine coin gönderemezsin.", code="cannot_sell_to_self")
    buyer = await user_service.get_user(db, buyer_id)
    if buyer.is_guest:
        # Misafir hesap telefon değişince kaybolur; alınan coin de gider ve şikâyet bize gelir.
        raise AppError("Misafir hesaba coin gönderilemez. Kişi önce hesabını kaydetmeli.", code="buyer_is_guest")

    today = _today()
    sold_before = case((CoinDealer.sold_day == today, CoinDealer.sold_today), else_=0)
    try:
        # GÜNLÜK SINIR TEK KOMUTLA: "bugünkü satış + bu satış ≤ sınır" kontrolü ve sayacın artması aynı
        # UPDATE'te. Aynı anda iki satış gelse de ikisi birlikte sınırı aşamaz (bakiyedeki kuralla aynı fikir).
        counted = await db.execute(
            update(CoinDealer)
            .where(CoinDealer.user_id == dealer_id, CoinDealer.status == "active",
                   sold_before + coins <= CoinDealer.daily_limit)
            .values(sold_today=sold_before + coins, sold_day=today)
            .returning(CoinDealer.sold_today)
            .execution_options(synchronize_session=False)
        )
        sold_today = counted.scalar_one_or_none()
        if sold_today is None:
            raise ConflictError(
                f"Günlük satış sınırın doldu (kalan {max(0, dealer.daily_limit - _sold_today(dealer))} coin).",
                code="dealer_daily_limit",
            )
        stock = await wallet_service.change_balance(
            db, user_id=dealer_id, currency="dealer_coin", delta=-coins, type="dealer_sale",
            label=f"Coin satışı → {buyer.display_name} (ID {buyer.id})", counterparty_id=buyer.id,
            idempotency_key=idempotency_key,
        )
        dealer_user = await user_service.get_user(db, dealer_id)
        await wallet_service.change_balance(
            db, user_id=buyer.id, currency="coin", delta=coins, type="dealer_topup",
            label=f"Bayiden coin: {dealer_user.display_name}", counterparty_id=dealer_id,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        previous = await wallet_service.find_by_idempotency_key(db, dealer_id, idempotency_key)
        if previous is None:
            raise
        return await _sale_replay(db, dealer_id, previous)
    except Exception:
        # Yetersiz stok dahil: sayaç artışı da geri alınır.
        await db.rollback()
        raise
    audit("dealer_sale", dealer_id=dealer_id, buyer_id=buyer.id, coins=coins)
    await notification_service.notify(
        db, buyer.id, "dealer_topup", f"🪙 {dealer_user.display_name} hesabına {coins} coin gönderdi.", actor_id=dealer_id,
    )
    sale = (await _sales(db, dealer_id, limit=1))[0]
    return DealerSaleResult(stock=stock, sold_today=sold_today, sale=sale)


# ── Panel (yönetim) ───────────────────────────────────────────────────────────

async def _admin_out(db: AsyncSession, dealers: list[CoinDealer]) -> list[DealerAdminOut]:
    if not dealers:
        return []
    ids = [d.user_id for d in dealers]
    users = await user_service.load_users_out(db, set(ids), None)
    totals = {row.dealer_id: row for row in await db.execute(
        select(DealerStockOrder.dealer_id, func.sum(DealerStockOrder.coins).label("coins"),
               func.sum(DealerStockOrder.paid_kurus).label("paid"))
        .where(DealerStockOrder.dealer_id.in_(ids)).group_by(DealerStockOrder.dealer_id)
    )}
    return [
        DealerAdminOut(
            user=users[d.user_id], status=d.status, stock=d.stock, daily_limit=d.daily_limit,
            sold_today=_sold_today(d), note=d.note,
            total_loaded=int(totals[d.user_id].coins) if d.user_id in totals else 0,
            total_paid_kurus=int(totals[d.user_id].paid) if d.user_id in totals else 0,
            created_at=as_utc(d.created_at),
        )
        for d in dealers if d.user_id in users
    ]


async def list_dealers(db: AsyncSession) -> list[DealerAdminOut]:
    return await _admin_out(db, list(await db.scalars(select(CoinDealer).order_by(CoinDealer.created_at.desc()))))


async def _get_dealer(db: AsyncSession, user_id: int) -> CoinDealer:
    dealer = await db.get(CoinDealer, user_id)
    if dealer is None:
        raise NotFoundError("Bayi bulunamadı.")
    return dealer


async def dealer_detail(db: AsyncSession, user_id: int) -> DealerAdminDetail:
    dealer = await _get_dealer(db, user_id)
    orders = list(await db.scalars(
        select(DealerStockOrder).where(DealerStockOrder.dealer_id == user_id).order_by(DealerStockOrder.id.desc()).limit(50)
    ))
    staff = await user_service.load_users_out(db, {o.created_by for o in orders if o.created_by}, None)
    return DealerAdminDetail(
        dealer=(await _admin_out(db, [dealer]))[0],
        orders=[DealerStockOrderOut(id=o.id, coins=o.coins, paid_kurus=o.paid_kurus, payment_ref=o.payment_ref,
                                    created_by=staff.get(o.created_by), created_at=as_utc(o.created_at)) for o in orders],
        sales=await _sales(db, user_id, limit=50),
        suggested_kurus_per_1000=settings.coin_price_per_1000_kurus * (100 - settings.dealer_discount_percent) // 100,
    )


async def create_dealer(db: AsyncSession, staff_id: int, user_id: int, daily_limit: int | None, note: str) -> DealerAdminDetail:
    user = await user_service.get_user(db, user_id)
    if user.is_guest:
        raise AppError("Misafir hesap bayi olamaz.", code="guest_cannot_be_dealer")
    db.add(CoinDealer(user_id=user.id, daily_limit=daily_limit or settings.dealer_default_daily_limit, note=note,
                      created_by=staff_id))
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise ConflictError("Bu kişi zaten bayi.", code="already_dealer") from error
    audit("dealer_created", target_id=user.id, daily_limit=daily_limit or settings.dealer_default_daily_limit)
    await staff_service.record(db, staff_id, "dealer_created", "user", user.id, note)
    await notification_service.notify(db, user.id, "dealer_created", "🪙 Artık resmi Muti coin bayisisin! Profil > Cüzdan > Bayi paneli.")
    return await dealer_detail(db, user.id)


async def update_dealer(
    db: AsyncSession, staff_id: int, user_id: int, status: str | None, daily_limit: int | None, note: str | None,
) -> DealerAdminDetail:
    dealer = await _get_dealer(db, user_id)
    changes = {k: v for k, v in {"status": status, "daily_limit": daily_limit, "note": note}.items() if v is not None}
    for key, value in changes.items():
        setattr(dealer, key, value)
    await db.commit()
    audit("dealer_updated", target_id=user_id, **changes)
    await staff_service.record(db, staff_id, "dealer_updated", "user", user_id,
                               ", ".join(f"{k}={v}" for k, v in changes.items()))
    return await dealer_detail(db, user_id)


async def load_stock(
    db: AsyncSession, staff_id: int, user_id: int, coins: int, paid_kurus: int, payment_ref: str,
    idempotency_key: str | None,
) -> DealerAdminDetail:
    """
    Bayiye toptan stok yükler (eksi = geri alır). Ödeme kaydı ve stok artışı tek transaction'da.
    İdempotency anahtarı personelin hesabına değil BAYİNİN hareketine yazılır: aynı form iki kez
    gönderilse de stok bir kez yüklenir.
    """
    if coins == 0:
        raise AppError("Miktar sıfır olamaz.", code="invalid_amount")
    await _get_dealer(db, user_id)
    if await wallet_service.find_by_idempotency_key(db, user_id, idempotency_key):
        return await dealer_detail(db, user_id)
    try:
        db.add(DealerStockOrder(dealer_id=user_id, coins=coins, paid_kurus=paid_kurus, payment_ref=payment_ref,
                                created_by=staff_id))
        await wallet_service.change_balance(
            db, user_id=user_id, currency="dealer_coin", delta=coins, type="dealer_stock",
            label=f"{'Toptan stok' if coins > 0 else 'Stok düzeltme'} · {payment_ref}", idempotency_key=idempotency_key,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        if await wallet_service.find_by_idempotency_key(db, user_id, idempotency_key) is None:
            raise
        return await dealer_detail(db, user_id)
    except Exception:
        await db.rollback()
        raise
    audit("dealer_stock_loaded", target_id=user_id, coins=coins, paid_kurus=paid_kurus, payment_ref=payment_ref)
    await staff_service.record(db, staff_id, "dealer_stock_loaded", "user", user_id,
                               f"{coins:+} coin · {paid_kurus / 100:.2f} TL · {payment_ref}")
    if coins > 0:
        await notification_service.notify(db, user_id, "dealer_stock", f"🪙 Bayi stoğuna {coins} coin yüklendi.")
    return await dealer_detail(db, user_id)
