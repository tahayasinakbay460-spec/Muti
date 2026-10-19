"""
Ajans sistemi: yönetici ajans kurar, ajans sahibi yayıncıları davet eder, yayıncı kabul eder.
Ajans sahibi üyelerinin bu ayki elmas kazancını, hedeflerini ve tahmini komisyonunu görür.

Kazançlar para defterinden (transactions, gift_received) hesaplanır: ayrı sayaç yok.
DEMO KISAYOLU: Komisyon yalnızca gösteriliyor; gerçek hesaplaşma ve ödeme yok (bkz. models/agency.py).
"""
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.logs import audit
from app.core.timefmt import period_start
from app.models import Agency, AgencyMember, Transaction
from app.schemas.admin import AgencyDashboard, AgencyMemberOut, AgencyOut, MyAgency
from app.services import notification_service, user_service


async def _month_diamonds(db: AsyncSession, user_ids: list[int]) -> dict[int, int]:
    if not user_ids:
        return {}
    rows = await db.execute(
        select(Transaction.user_id, func.sum(Transaction.amount))
        .where(Transaction.user_id.in_(user_ids), Transaction.type == "gift_received",
               Transaction.created_at >= period_start("month"))
        .group_by(Transaction.user_id)
    )
    return dict(rows.all())


async def _present(db: AsyncSession, agency: Agency) -> AgencyOut:
    owner = await user_service.present_user(db, await user_service.get_user(db, agency.owner_id), viewer_id=None)
    count = await db.scalar(
        select(func.count()).select_from(AgencyMember)
        .where(AgencyMember.agency_id == agency.id, AgencyMember.status == "active")
    )
    return AgencyOut(id=agency.id, name=agency.name, owner=owner, commission_percent=agency.commission_percent,
                     member_count=count or 0)


# ── Yönetici ──────────────────────────────────────────────────────────────────

async def create_agency(db: AsyncSession, name: str, owner_id: int, commission_percent: int) -> AgencyOut:
    await user_service.get_user(db, owner_id)
    if await db.scalar(select(AgencyMember.user_id).where(AgencyMember.user_id == owner_id, AgencyMember.status == "active")):
        raise ConflictError("Bu kişi başka bir ajansın yayıncısı.", code="owner_is_member")
    agency = Agency(name=name, owner_id=owner_id, commission_percent=commission_percent)
    db.add(agency)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise ConflictError("Bu ad alınmış ya da kişinin zaten bir ajansı var.", code="agency_conflict") from error
    audit("agency_created", agency_id=agency.id, owner_id=owner_id, commission_percent=commission_percent)
    await notification_service.notify(db, owner_id, "agency_created", f"🏢 {name} ajansının sahibi oldun!")
    return await _present(db, agency)


async def list_agencies(db: AsyncSession) -> list[AgencyOut]:
    return [await _present(db, agency) for agency in await db.scalars(select(Agency).order_by(Agency.id))]


# ── Ajans sahibi ──────────────────────────────────────────────────────────────

async def _owned_agency(db: AsyncSession, user_id: int) -> Agency:
    agency = await db.scalar(select(Agency).where(Agency.owner_id == user_id))
    if agency is None:
        raise ForbiddenError("Bir ajansın sahibi değilsin.", code="not_agency_owner")
    return agency


async def _dashboard(db: AsyncSession, agency: Agency) -> AgencyDashboard:
    rows = list(await db.scalars(select(AgencyMember).where(AgencyMember.agency_id == agency.id)))
    users = await user_service.load_users_out(db, {row.user_id for row in rows}, viewer_id=None)
    diamonds = await _month_diamonds(db, [row.user_id for row in rows if row.status == "active"])
    members = []
    for row in rows:
        if row.user_id not in users:
            continue
        earned = diamonds.get(row.user_id, 0)
        progress = min(100, earned * 100 // row.monthly_target) if row.monthly_target else 0
        members.append(AgencyMemberOut(user=users[row.user_id], status=row.status, monthly_target=row.monthly_target,
                                       month_diamonds=earned, progress_percent=progress))
    members.sort(key=lambda m: (m.status != "active", -m.month_diamonds))
    total = sum(diamonds.values())
    return AgencyDashboard(agency=await _present(db, agency), members=members, month_diamonds=total,
                           estimated_commission=total * agency.commission_percent // 100)


async def invite(db: AsyncSession, owner_id: int, user_id: int) -> AgencyDashboard:
    agency = await _owned_agency(db, owner_id)
    if user_id == owner_id:
        raise AppError("Kendini davet edemezsin.", code="cannot_invite_self")
    target = await user_service.get_user(db, user_id)
    if await db.scalar(select(Agency.id).where(Agency.owner_id == user_id)):
        raise ConflictError("Bu kişi bir ajans sahibi.", code="target_is_owner")
    try:
        # Birincil anahtar user_id: kişinin zaten bir ajansı ya da bekleyen daveti varsa yazılamaz.
        db.add(AgencyMember(user_id=user_id, agency_id=agency.id, status="invited"))
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise ConflictError("Bu kişinin zaten bir ajansı ya da bekleyen daveti var.", code="already_in_agency") from error
    audit("agency_invited", agency_id=agency.id, target_id=user_id)
    await notification_service.notify(db, target.id, "agency_invite", f"🏢 {agency.name} ajansı seni yayıncı olarak davet etti.",
                                      data={"agency_id": agency.id})
    return await _dashboard(db, agency)


async def set_target(db: AsyncSession, owner_id: int, user_id: int, target: int) -> AgencyDashboard:
    agency = await _owned_agency(db, owner_id)
    changed = await db.execute(
        update(AgencyMember).where(AgencyMember.user_id == user_id, AgencyMember.agency_id == agency.id)
        .values(monthly_target=target)
    )
    if changed.rowcount != 1:
        raise NotFoundError("Bu kişi ajansında değil.")
    await db.commit()
    audit("agency_target_set", agency_id=agency.id, target_id=user_id, monthly_target=target)
    return await _dashboard(db, agency)


async def remove_member(db: AsyncSession, owner_id: int, user_id: int) -> AgencyDashboard:
    """Üyeyi çıkarır ya da bekleyen daveti geri çeker."""
    agency = await _owned_agency(db, owner_id)
    removed = await db.execute(
        delete(AgencyMember).where(AgencyMember.user_id == user_id, AgencyMember.agency_id == agency.id)
    )
    if removed.rowcount != 1:
        raise NotFoundError("Bu kişi ajansında değil.")
    await db.commit()
    audit("agency_member_removed", agency_id=agency.id, target_id=user_id)
    return await _dashboard(db, agency)


# ── Yayıncı ───────────────────────────────────────────────────────────────────

async def my_agency(db: AsyncSession, user_id: int) -> MyAgency:
    owned = await db.scalar(select(Agency).where(Agency.owner_id == user_id))
    if owned is not None:
        return MyAgency(role="owner", dashboard=await _dashboard(db, owned))
    membership = await db.scalar(select(AgencyMember).where(AgencyMember.user_id == user_id))
    if membership is None:
        return MyAgency(role=None)
    agency = await _present(db, await db.get(Agency, membership.agency_id))
    if membership.status == "invited":
        return MyAgency(role=None, invite=agency)
    earned = (await _month_diamonds(db, [user_id])).get(user_id, 0)
    return MyAgency(role="member", agency=agency, my_month_diamonds=earned, my_target=membership.monthly_target)


async def answer_invite(db: AsyncSession, user_id: int, accept: bool) -> MyAgency:
    membership = await db.scalar(
        select(AgencyMember).where(AgencyMember.user_id == user_id, AgencyMember.status == "invited")
    )
    if membership is None:
        raise NotFoundError("Bekleyen bir ajans davetin yok.")
    agency_id = membership.agency_id
    if accept:
        membership.status, membership.joined_at = "active", utcnow()
    else:
        await db.delete(membership)
    await db.commit()
    audit("agency_invite_accepted" if accept else "agency_invite_declined", agency_id=agency_id)
    return await my_agency(db, user_id)


async def leave(db: AsyncSession, user_id: int) -> MyAgency:
    removed = await db.execute(
        delete(AgencyMember).where(AgencyMember.user_id == user_id, AgencyMember.status == "active")
    )
    if removed.rowcount != 1:
        raise AppError("Bir ajansa üye değilsin.", code="not_in_agency")
    await db.commit()
    audit("agency_left")
    return await my_agency(db, user_id)
