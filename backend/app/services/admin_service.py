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
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.logs import audit
from app.core.timefmt import as_utc, local_day_start, local_today, time_ago_label
from app.models import Report, Room, Transaction, User
from app.realtime import events
from app.realtime.hub import room_hub, user_hub
from app.realtime.state import room_state
from app.schemas.admin import AdminReportOut, AdminRoomOut, AdminStats, AdminUserOut, BalanceAdjustResult
from app.schemas.economy import TransactionOut
from app.services import auth_service, moderation_service, user_service, wallet_service

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


async def search_users(db: AsyncSession, query: str) -> list[AdminUserOut]:
    text = query.strip().lstrip("@")
    statement = select(User).where(~User.username.startswith("deleted_")).order_by(User.id.desc()).limit(30)
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
