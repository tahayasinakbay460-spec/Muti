"""
Uygulama geneli yönetim paneli: özet sayılar, şikâyet inceleme, kullanıcı ban, bakiye düzeltme,
oda kapatma. Buradaki her işlem yalnızca `is_admin` kullanıcılara açıktır (bkz. core/deps.py
CurrentAdmin) ve her biri denetim kaydına (audit) yazılır: "hangi yönetici, kime, ne yaptı".

BAN ANINDA ETKİLİ OLMALI: Hesap kapanır, bütün refresh token'lar iptal edilir, açık WebSocket
bağlantıları kesilir. Elindeki access token'ın süresi (15 dk) dolmamış olsa bile bir sonraki
istekte reddedilir: her istekte `is_banned` kontrol edilir (bkz. core/deps.py).
DEMO KISAYOLU: Banlı listesi bu sürecin belleğinde (açılışta veritabanından yüklenir). Birden
fazla sunucuda Redis set'i (SISMEMBER) kullanılmalı.
"""
from datetime import timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import utcnow
from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.logs import audit
from app.core.timefmt import as_utc, local_day_start, local_today, time_ago_label
from app.models import (
    CoinPackage, Conversation, Gift, Message, Report, Room, RoomMessage, StoreItem, Transaction, User,
)
from app.realtime import events
from app.realtime.hub import room_hub, user_hub
from app.realtime.state import room_state
from app.schemas.admin import (
    AdminConversationOut, AdminMessageOut, AdminReportOut, AdminRoomOut, AdminStats, AdminTransactionOut, AdminUserOut,
    BalanceAdjustResult, BroadcastResult, CatalogGiftOut, CatalogGiftUpdate, CatalogPackageOut, CatalogPackageUpdate,
    DailyPoint, FinanceSummary, TopUser,
)
from app.schemas.economy import TransactionOut
from app.services import (
    auth_service, leaderboard_service, moderation_service, notification_service, store_service, user_service,
    vip_service, wallet_service,
)

_banned_ids: set[int] = set()


def is_banned(user_id: int) -> bool:
    return user_id in _banned_ids


async def load_bans(db: AsyncSession) -> None:
    """Sunucu açılırken banlı kullanıcıları belleğe alır."""
    _banned_ids.clear()
    _banned_ids.update(await db.scalars(select(User.id).where(User.is_active.is_(False))))


# ── Özet ──────────────────────────────────────────────────────────────────────

async def get_stats(db: AsyncSession) -> AdminStats:
    today = local_day_start(local_today())

    async def count(statement) -> int:
        return await db.scalar(statement) or 0

    async def tx_sum(kind: str, sign: int) -> int:
        return await count(
            select(func.coalesce(func.sum(Transaction.amount * sign), 0))
            .where(Transaction.type == kind, Transaction.created_at >= today)
        )

    user_ids = list(await db.scalars(select(User.id).where(User.is_active)))
    return AdminStats(
        users_total=len(user_ids),
        users_today=await count(select(func.count(User.id)).where(User.created_at >= today)),
        online_now=len(await room_state.online_user_ids(user_ids)),
        rooms_active=await count(select(func.count(Room.id)).where(Room.is_active)),
        coins_sold_today=await tx_sum("purchase", 1),
        gift_coins_today=await tx_sum("gift_sent", -1),
        open_reports=await count(select(func.count(Report.id)).where(Report.status == "open")),
        banned_users=await count(select(func.count(User.id)).where(User.is_active.is_(False), ~User.username.startswith("deleted_"))),
    )


# ── Şikâyetler ────────────────────────────────────────────────────────────────

async def list_reports(db: AsyncSession, status: str = "open") -> list[AdminReportOut]:
    statement = select(Report).order_by(Report.id.desc()).limit(100)
    statement = statement.where(Report.status == "open") if status == "open" else statement.where(Report.status != "open")
    reports = list(await db.scalars(statement))

    user_target_ids = {r.target_id for r in reports if r.target_type == "user"}
    room_target_ids = {r.target_id for r in reports if r.target_type == "room"}
    names = dict((await db.execute(select(User.id, User.display_name).where(User.id.in_(user_target_ids)))).all())
    titles = dict((await db.execute(select(Room.id, Room.title).where(Room.id.in_(room_target_ids)))).all())
    reporters = await user_service.load_users_out(db, {r.reporter_id for r in reports}, viewer_id=None)

    return [
        AdminReportOut(
            id=r.id, reporter=reporters.get(r.reporter_id), target_type=r.target_type, target_id=r.target_id,
            target_label=(names if r.target_type == "user" else titles).get(r.target_id, "(silinmiş)"),
            reason=r.reason, details=r.details, status=r.status, created_at=as_utc(r.created_at),
            action=r.action, resolution_note=r.resolution_note,
            resolved_at=as_utc(r.resolved_at) if r.resolved_at else None,
        )
        for r in reports
    ]


async def resolve_report(db: AsyncSession, admin_id: int, report_id: int, action: str, note: str) -> None:
    """
    Şikâyeti karara bağlar. Aynı hedef hakkındaki diğer açık şikâyetler de aynı kararla kapanır
    (bir kişi için gelen 10 şikâyeti tek tek kapatmak gerekmesin).
    """
    report = await db.get(Report, report_id)
    if report is None:
        raise NotFoundError("Şikâyet bulunamadı.")
    if report.status != "open":
        raise ConflictError("Bu şikâyet zaten karara bağlandı.", code="report_already_resolved")
    if action == "ban_user" and report.target_type != "user":
        raise AppError("Oda şikâyetinde kullanıcı banlanamaz; odayı kapat.", code="invalid_report_action")
    if action == "close_room" and report.target_type != "room":
        raise AppError("Kullanıcı şikâyetinde oda kapatılamaz.", code="invalid_report_action")

    target_type, target_id = report.target_type, report.target_id
    if action == "ban_user":
        await ban_user(db, admin_id, target_id, note or f"Şikâyet #{report_id}")
    elif action == "close_room":
        room = await db.get(Room, target_id)
        if room is not None and room.is_active:
            await moderation_service.shut_down_room(db, room)

    closed = await db.execute(
        update(Report)
        .where(Report.target_type == target_type, Report.target_id == target_id, Report.status == "open")
        .values(status="dismissed" if action == "dismiss" else "resolved", resolved_by=admin_id,
                resolved_at=utcnow(), action=action, resolution_note=note)
    )
    await db.commit()
    audit("report_resolved", report_id=report_id, action=action, target_type=target_type,
          target_id=target_id, closed_reports=closed.rowcount)


# ── Kullanıcılar ──────────────────────────────────────────────────────────────

async def _admin_user_out(db: AsyncSession, user: User, with_transactions: bool) -> AdminUserOut:
    reports = await db.scalar(
        select(func.count(Report.id)).where(Report.target_type == "user", Report.target_id == user.id)
    ) or 0
    transactions = []
    if with_transactions:
        rows = await db.scalars(
            select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.id.desc()).limit(20)
        )
        transactions = [
            TransactionOut(id=t.id, type=t.type, currency=t.currency, label=t.label, amount=t.amount,
                           created_at=as_utc(t.created_at), time_label=time_ago_label(t.created_at))
            for t in rows
        ]
    return AdminUserOut(
        user=await user_service.present_user(db, user, viewer_id=None), email=user.email,
        is_active=user.is_active, is_admin=user.is_admin, coin_balance=user.coin_balance,
        diamond_balance=user.diamond_balance, reports_against=reports, recent_transactions=transactions,
    )


async def _get_any_user(db: AsyncSession, user_id: int) -> User:
    """Banlı kullanıcılar da dahil (user_service.get_user onları bulunamadı sayar)."""
    user = await db.get(User, user_id)
    if user is None or user.username.startswith("deleted_"):
        raise NotFoundError("Kullanıcı bulunamadı.")
    return user


async def search_users(db: AsyncSession, query: str, sort: str = "newest") -> list[AdminUserOut]:
    """sort: newest (en yeni üye), richest (en çok coin), reported (en çok şikâyet edilen)."""
    text = query.strip().lstrip("@")
    statement = select(User).where(~User.username.startswith("deleted_")).limit(50)
    if sort == "richest":
        statement = statement.order_by(User.coin_balance.desc(), User.id)
    elif sort == "reported":
        reports = (
            select(func.count(Report.id)).where(Report.target_type == "user", Report.target_id == User.id)
            .correlate(User).scalar_subquery()
        )
        statement = statement.order_by(reports.desc(), User.id.desc())
    else:
        statement = statement.order_by(User.id.desc())
    if text:
        escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions = [User.username.ilike(pattern, escape="\\"), User.display_name.ilike(pattern, escape="\\"),
                      User.email.ilike(pattern, escape="\\")]
        if text.isdigit():
            conditions.append(User.id == int(text))
        statement = statement.where(or_(*conditions))
    return [await _admin_user_out(db, user, with_transactions=False) for user in await db.scalars(statement)]


async def get_user_detail(db: AsyncSession, user_id: int) -> AdminUserOut:
    return await _admin_user_out(db, await _get_any_user(db, user_id), with_transactions=True)


async def ban_user(db: AsyncSession, admin_id: int, user_id: int, reason: str) -> AdminUserOut:
    user = await _get_any_user(db, user_id)
    if user.id == admin_id or user.is_admin:
        raise ForbiddenError("Yönetici hesapları banlanamaz.", code="cannot_ban_admin")
    if not user.is_active:
        raise ConflictError("Bu kullanıcı zaten banlı.", code="already_banned")
    user.is_active = False
    await auth_service.revoke_all_sessions(db, user.id)   # commit eder
    _banned_ids.add(user.id)
    # Açık bağlantıları kes: odalardan atılır (koltuğu boşalır), kişiye özel kanal kapanır.
    await room_hub.disconnect_user_everywhere(user.id, events.CLOSE_UNAUTHORIZED)
    await user_hub.disconnect(user.id, events.CLOSE_UNAUTHORIZED)
    audit("user_banned", target_id=user.id, reason=reason)
    return await _admin_user_out(db, user, with_transactions=True)


async def unban_user(db: AsyncSession, user_id: int) -> AdminUserOut:
    user = await _get_any_user(db, user_id)
    if user.is_active:
        raise ConflictError("Bu kullanıcı banlı değil.", code="not_banned")
    user.is_active = True
    await db.commit()
    _banned_ids.discard(user.id)
    audit("user_unbanned", target_id=user.id)
    return await _admin_user_out(db, user, with_transactions=True)


async def adjust_balance(
    db: AsyncSession, user_id: int, currency: str, amount: int, reason: str,
) -> BalanceAdjustResult:
    """Yönetici bakiye düzeltmesi. Bakiye de diğer her para hareketi gibi change_balance ile değişir."""
    user = await _get_any_user(db, user_id)
    try:
        balance = await wallet_service.change_balance(
            db, user_id=user.id, currency=currency, delta=amount, type="admin_adjustment",
            label=f"Yönetici düzeltmesi: {reason}",
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    audit("balance_adjusted", target_id=user.id, currency=currency, amount=amount, reason=reason)
    return BalanceAdjustResult(currency=currency, balance=balance)


# ── Odalar ────────────────────────────────────────────────────────────────────

async def list_rooms(db: AsyncSession) -> list[AdminRoomOut]:
    rooms = list(await db.scalars(select(Room).where(Room.is_active).order_by(Room.id.desc()).limit(100)))
    counts = await room_state.listener_counts([room.id for room in rooms])
    hosts = await user_service.load_users_out(db, {room.host_id for room in rooms}, viewer_id=None)
    out = [
        AdminRoomOut(id=room.id, title=room.title, host=hosts.get(room.host_id), listener_count=counts.get(room.id, 0),
                     is_live=room.is_live, created_at=as_utc(room.created_at))
        for room in rooms
    ]
    return sorted(out, key=lambda r: -r.listener_count)


async def close_room(db: AsyncSession, room_id: int, reason: str) -> None:
    room = await db.get(Room, room_id)
    if room is None or not room.is_active:
        raise NotFoundError("Oda bulunamadı.")
    await moderation_service.shut_down_room(db, room)
    audit("room_closed_by_admin", room_id=room_id, reason=reason)


# ── Finans (masaüstü panel) ───────────────────────────────────────────────────

# Grafiklerde gösterilen işlem türleri → (DailyPoint alanı, işaret). İşaret, eksi kayıtlı
# harcamaları (ör. gift_sent -299) artı tutara çevirir.
_DAILY_FIELDS = {
    "purchase": ("coins_sold", 1), "gift_sent": ("gift_coins", -1),
    "vip_purchase": ("vip_coins", -1), "store_purchase": ("store_coins", -1),
}


async def finance_summary(db: AsyncSession, days: int = 14) -> FinanceSummary:
    """
    Son `days` günün günlük serileri ve dönem toplamları.
    DEMO KISAYOLU: Defter satırları her istekte okunup Python'da günlere bölünüyor. Kalabalıkta
    gece çalışan bir iş günlük özet tablosu doldurur, panel oradan okur.
    """
    today = local_today()
    first_day = today - timedelta(days=days - 1)
    since = local_day_start(first_day)
    offset = timedelta(hours=settings.display_utc_offset_hours)
    series = {
        (first_day + timedelta(days=i)).isoformat(): DailyPoint(
            day=(first_day + timedelta(days=i)).isoformat(), coins_sold=0, gift_coins=0, vip_coins=0,
            store_coins=0, new_users=0,
        )
        for i in range(days)
    }
    totals: dict[str, int] = {}
    rows = await db.execute(
        select(Transaction.type, Transaction.amount, Transaction.created_at).where(Transaction.created_at >= since)
    )
    for kind, amount, created_at in rows:
        totals[kind] = totals.get(kind, 0) + abs(amount)
        if kind in _DAILY_FIELDS:
            point = series.get((as_utc(created_at) + offset).date().isoformat())
            if point is not None:
                field_name, sign = _DAILY_FIELDS[kind]
                setattr(point, field_name, getattr(point, field_name) + amount * sign)
    for (created_at,) in await db.execute(select(User.created_at).where(User.created_at >= since)):
        point = series.get((as_utc(created_at) + offset).date().isoformat())
        if point is not None:
            point.new_users += 1

    spenders = await leaderboard_service.user_scores(db, "gifts_sent", since, limit=5)
    earners = await leaderboard_service.user_scores(db, "gifts_received", since, limit=5)
    users = await user_service.load_users_out(db, {uid for uid, _ in spenders + earners}, viewer_id=None)
    rooms_board = await leaderboard_service.get_leaderboard(db, viewer_id=0, kind="rooms", period="month")
    return FinanceSummary(
        days=list(series.values()), totals=totals,
        top_spenders=[TopUser(user=users[uid], amount=amount) for uid, amount in spenders if uid in users],
        top_earners=[TopUser(user=users[uid], amount=amount) for uid, amount in earners if uid in users],
        top_rooms=[{**entry.room, "coins": entry.score} for entry in rooms_board.entries[:5]],
    )


async def list_transactions(
    db: AsyncSession, kind: str | None, user_id: int | None, before_id: int | None, limit: int = 50,
) -> list[AdminTransactionOut]:
    """Bütün para hareketleri (yeniden eskiye), türe ve kullanıcıya göre süzülebilir."""
    statement = select(Transaction).order_by(Transaction.id.desc()).limit(limit)
    if kind:
        statement = statement.where(Transaction.type == kind)
    if user_id:
        statement = statement.where(Transaction.user_id == user_id)
    if before_id:
        statement = statement.where(Transaction.id < before_id)
    rows = list(await db.scalars(statement))
    users = await user_service.load_users_out(db, {row.user_id for row in rows}, viewer_id=None)
    return [
        AdminTransactionOut(id=row.id, user=users.get(row.user_id), type=row.type, currency=row.currency,
                            amount=row.amount, balance_after=row.balance_after, label=row.label,
                            created_at=as_utc(row.created_at))
        for row in rows
    ]


# ── Mesajlar ──────────────────────────────────────────────────────────────────
# DEMO KISAYOLU: Yönetici bütün özel mesajları ve oda sohbetlerini okuyabiliyor (müşteri isteği).
# Canlıda: yalnızca şikâyet edilen konuşmaya erişim ve gizlilik metninde açık bilgilendirme (KVKK,
# mağaza kuralları). Her görüntüleme yine de denetim kaydına yazılır: hangi yönetici neyi okudu.

async def list_conversations(db: AsyncSession, user_id: int | None, before_id: int | None) -> list[AdminConversationOut]:
    statement = select(Conversation).order_by(Conversation.id.desc()).limit(50)
    if user_id:
        statement = statement.where(or_(Conversation.user_low_id == user_id, Conversation.user_high_id == user_id))
    if before_id:
        statement = statement.where(Conversation.id < before_id)
    rows = list(await db.scalars(statement))
    counts = dict((await db.execute(
        select(Message.conversation_id, func.count(Message.id))
        .where(Message.conversation_id.in_([row.id for row in rows])).group_by(Message.conversation_id)
    )).all())
    users = await user_service.load_users_out(
        db, {row.user_low_id for row in rows} | {row.user_high_id for row in rows}, viewer_id=None,
    )
    out = [
        AdminConversationOut(
            id=row.id, users=[users[uid] for uid in (row.user_low_id, row.user_high_id) if uid in users],
            last_message_text=row.last_message_text,
            last_message_at=as_utc(row.last_message_at) if row.last_message_at else None,
            message_count=counts.get(row.id, 0),
        )
        for row in rows
    ]
    # Son mesajı en yeni olan üstte; hiç mesajı olmayan sohbetler en sonda.
    return sorted(out, key=lambda c: c.last_message_at.timestamp() if c.last_message_at else 0, reverse=True)


async def conversation_messages(db: AsyncSession, conversation_id: int) -> list[AdminMessageOut]:
    if await db.get(Conversation, conversation_id) is None:
        raise NotFoundError("Sohbet bulunamadı.")
    rows = list(await db.scalars(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id.desc()).limit(200)
    ))
    users = await user_service.load_users_out(db, {row.sender_id for row in rows}, viewer_id=None)
    audit("admin_viewed_conversation", conversation_id=conversation_id, messages=len(rows))
    return [AdminMessageOut(id=r.id, sender=users.get(r.sender_id), text=r.text, created_at=as_utc(r.created_at))
            for r in reversed(rows)]


async def room_messages(db: AsyncSession, room_id: int, before_id: int | None) -> list[AdminMessageOut]:
    if await db.get(Room, room_id) is None:
        raise NotFoundError("Oda bulunamadı.")
    statement = select(RoomMessage).where(RoomMessage.room_id == room_id).order_by(RoomMessage.id.desc()).limit(200)
    if before_id:
        statement = statement.where(RoomMessage.id < before_id)
    rows = list(await db.scalars(statement))
    users = await user_service.load_users_out(db, {row.user_id for row in rows}, viewer_id=None)
    audit("admin_viewed_room_chat", room_id=room_id, messages=len(rows))
    return [
        AdminMessageOut(id=r.id, sender=users.get(r.user_id), text=r.text, created_at=as_utc(r.created_at),
                        deleted_at=as_utc(r.deleted_at) if r.deleted_at else None)
        for r in reversed(rows)
    ]


# ── Katalog: hediyeler ve coin paketleri ──────────────────────────────────────

def _gift_out(g: Gift) -> CatalogGiftOut:
    return CatalogGiftOut(id=g.id, name=g.name, emoji=g.emoji, price=g.price, is_lucky=g.is_lucky, is_active=g.is_active)


async def list_catalog_gifts(db: AsyncSession) -> list[CatalogGiftOut]:
    return [_gift_out(g) for g in await db.scalars(select(Gift).order_by(Gift.price, Gift.id))]


async def update_gift(db: AsyncSession, gift_id: int, data: CatalogGiftUpdate) -> CatalogGiftOut:
    gift = await db.get(Gift, gift_id)
    if gift is None:
        raise NotFoundError("Hediye bulunamadı.")
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    for field_name, value in changes.items():
        setattr(gift, field_name, value)
    await db.commit()
    audit("gift_updated", gift_id=gift_id, changes=changes)
    return _gift_out(gift)


def _package_out(p: CoinPackage) -> CatalogPackageOut:
    return CatalogPackageOut(id=p.id, title=p.title, coins=p.coins, bonus=p.bonus, price_label=p.price_label,
                             is_popular=p.is_popular, is_best_value=p.is_best_value, is_active=p.is_active)


async def list_catalog_packages(db: AsyncSession) -> list[CatalogPackageOut]:
    return [_package_out(p) for p in await db.scalars(select(CoinPackage).order_by(CoinPackage.id))]


async def update_package(db: AsyncSession, package_id: int, data: CatalogPackageUpdate) -> CatalogPackageOut:
    package = await db.get(CoinPackage, package_id)
    if package is None:
        raise NotFoundError("Paket bulunamadı.")
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    for field_name, value in changes.items():
        setattr(package, field_name, value)
    await db.commit()
    audit("package_updated", package_id=package_id, changes=changes)
    return _package_out(package)


# ── VIP verme ve duyuru ───────────────────────────────────────────────────────

async def grant_vip(db: AsyncSession, user_id: int, level: int, days: int) -> AdminUserOut:
    """Ücretsiz VIP verir (ör. kampanya, telafi). Üyelik eşyaları da verilir; para hareketi yok."""
    user = await _get_any_user(db, user_id)
    now = utcnow()
    same_level = user.vip_expires_at is not None and user.active_vip_level(now) == level
    start = max(as_utc(user.vip_expires_at), now) if same_level else now
    expires_at = start + timedelta(days=days)
    user.vip_level, user.vip_expires_at = level, expires_at
    for item in await db.scalars(select(StoreItem).where(StoreItem.id.in_(vip_service.VIP_TIERS[level].item_ids))):
        await store_service.grant_item(db, user.id, item, until=expires_at)
    await db.commit()
    audit("vip_granted", target_id=user.id, vip_level=level, days=days)
    await notification_service.notify(db, user.id, "vip_granted", f"👑 Sana {days} günlük VIP {level} hediye edildi!")
    return await _admin_user_out(db, user, with_transactions=True)


async def broadcast(db: AsyncSession, text: str) -> BroadcastResult:
    """
    Bütün aktif kullanıcılara sistem bildirimi gönderir (uygulamadaysa anında görür).
    DEMO KISAYOLU: Kişi kişi döngü. Binlerce kullanıcıda arka plan kuyruğu ve uygulama
    kapalıyken push bildirim gerekir.
    """
    user_ids = list(await db.scalars(select(User.id).where(User.is_active, User.is_admin.is_(False))))
    for user_id in user_ids:
        await notification_service.notify(db, user_id, "system", f"📢 {text}")
    audit("broadcast_sent", recipients=len(user_ids), text=text)
    return BroadcastResult(sent=len(user_ids))
