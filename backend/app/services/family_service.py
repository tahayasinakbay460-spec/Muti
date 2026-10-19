"""
Aile (klan): kurma, katılma, ayrılma, üye yönetimi, aile sohbeti.

Roller: owner (kurucu) > admin (yönetici) > member (üye).
  - Kurucu aileden ayrılamaz; isterse aileyi dağıtır.
  - Yönetici ve kurucu kendinden düşük rütbedeki üyeyi çıkarabilir, ailenin sloganını/rozetini değiştirebilir.
  - Rol vermeyi yalnızca kurucu yapar.

Aile seviyesi ve haftalık puan, üyelerin gönderdiği hediyelerin coin toplamından hesaplanır
(ayrı bir sayaç tutulmaz; para defteri `transactions` zaten her hediyeyi kaydediyor).
DEMO KISAYOLU: Bu toplamlar her istekte defterden hesaplanıyor; kalabalıkta günlük özet
tablosu ya da Redis sayacı kullanılmalı.
"""
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.logs import audit
from app.core.timefmt import period_start
from app.models import Family, FamilyMember, FamilyMessage, Transaction, User
from app.realtime import events
from app.realtime.hub import user_hub
from app.schemas.engagement import (
    FamilyCreateRequest, FamilyDetail, FamilyMemberOut, FamilyMessageOut, FamilyOut, FamilyUpdateRequest,
)
from app.services import notification_service, user_service, wallet_service

FAMILY_CREATE_PRICE = 2_000      # coin
FAMILY_MAX_MEMBERS = 50
FAMILY_LEVEL_STEP = 50_000       # her 50.000 coinlik hediye aileyi bir seviye yükseltir
ROLE_RANK = {"owner": 3, "admin": 2, "member": 1}


# ── Okuma ─────────────────────────────────────────────────────────────────────

async def _gift_totals(db: AsyncSession, family_ids: list[int], since=None) -> dict[int, int]:
    """Aile id → üyelerinin (şu anki üyeler) gönderdiği hediyelerin coin toplamı."""
    if not family_ids:
        return {}
    total = func.coalesce(func.sum(-Transaction.amount), 0)
    statement = (
        select(FamilyMember.family_id, total)
        .join(Transaction, Transaction.user_id == FamilyMember.user_id)
        .where(FamilyMember.family_id.in_(family_ids), Transaction.type == "gift_sent")
        .group_by(FamilyMember.family_id)
    )
    if since is not None:
        statement = statement.where(Transaction.created_at >= since)
    return dict((await db.execute(statement)).all())


async def present_families(db: AsyncSession, families: list[Family], viewer_id: int | None) -> list[FamilyOut]:
    ids = [family.id for family in families]
    week = await _gift_totals(db, ids, since=period_start("week"))
    total = await _gift_totals(db, ids)
    my = await db.scalar(select(FamilyMember).where(FamilyMember.user_id == viewer_id)) if viewer_id else None
    return [
        FamilyOut(
            id=family.id, name=family.name, badge=family.badge, slogan=family.slogan, owner_id=family.owner_id,
            member_count=family.member_count, max_members=FAMILY_MAX_MEMBERS,
            week_coins=week.get(family.id, 0), level=1 + total.get(family.id, 0) // FAMILY_LEVEL_STEP,
            my_role=my.role if my and my.family_id == family.id else None,
        )
        for family in families
    ]


async def _get_family(db: AsyncSession, family_id: int) -> Family:
    family = await db.get(Family, family_id)
    if family is None:
        raise NotFoundError("Aile bulunamadı.")
    return family


async def list_families(db: AsyncSession, viewer_id: int, query: str = "") -> list[FamilyOut]:
    statement = select(Family).order_by(Family.member_count.desc(), Family.id).limit(50)
    text = query.strip()
    if text:
        escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(Family.name.ilike(f"%{escaped}%", escape="\\"))
    families = await present_families(db, list(await db.scalars(statement)), viewer_id)
    # En aktif aileler üstte: bu haftanın hediye toplamına göre.
    return sorted(families, key=lambda f: (-f.week_coins, -f.member_count))


async def get_detail(db: AsyncSession, viewer_id: int, family_id: int) -> FamilyDetail:
    family = await _get_family(db, family_id)
    out = (await present_families(db, [family], viewer_id))[0]
    rows = list(await db.scalars(select(FamilyMember).where(FamilyMember.family_id == family.id)))
    users = await user_service.load_users_out(db, {row.user_id for row in rows}, viewer_id)
    since = period_start("week")
    week = dict((await db.execute(
        select(Transaction.user_id, func.sum(-Transaction.amount))
        .where(Transaction.user_id.in_(list(users)), Transaction.type == "gift_sent", Transaction.created_at >= since)
        .group_by(Transaction.user_id)
    )).all())
    members = [
        FamilyMemberOut(user=users[row.user_id], role=row.role, week_coins=week.get(row.user_id, 0))
        for row in rows if row.user_id in users
    ]
    members.sort(key=lambda m: (-ROLE_RANK[m.role], -m.week_coins))
    return FamilyDetail(**out.model_dump(), members=members)


async def my_family_id(db: AsyncSession, user_id: int) -> int | None:
    return await db.scalar(select(FamilyMember.family_id).where(FamilyMember.user_id == user_id))


# ── Kurma, katılma, ayrılma ───────────────────────────────────────────────────

async def create_family(db: AsyncSession, user_id: int, data: FamilyCreateRequest) -> FamilyDetail:
    if await my_family_id(db, user_id):
        raise ConflictError("Zaten bir ailedesin. Önce ailenden ayrıl.", code="already_in_family")
    try:
        await wallet_service.change_balance(
            db, user_id=user_id, currency="coin", delta=-FAMILY_CREATE_PRICE, type="family_create",
            label=f"Aile kurma: {data.name}",
        )
        family = Family(name=data.name, badge=data.badge, slogan=data.slogan, owner_id=user_id, member_count=1)
        db.add(family)
        await db.flush()
        db.add(FamilyMember(user_id=user_id, family_id=family.id, role="owner"))
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        # Aile adı benzersiz; ya da aynı anda başka bir aileye katıldı (üyelik de benzersiz).
        if await my_family_id(db, user_id):
            raise ConflictError("Zaten bir ailedesin.", code="already_in_family") from error
        raise ConflictError("Bu aile adı alınmış.", code="family_name_taken") from error
    except Exception:
        await db.rollback()
        raise
    audit("family_created", family_id=family.id, name=family.name, price=FAMILY_CREATE_PRICE)
    return await get_detail(db, user_id, family.id)


async def join_family(db: AsyncSession, user_id: int, family_id: int) -> FamilyDetail:
    await _get_family(db, family_id)
    if await my_family_id(db, user_id):
        raise ConflictError("Zaten bir ailedesin. Önce ailenden ayrıl.", code="already_in_family")
    # "Yer varsa sayacı artır" tek komutla: son boş yere aynı anda iki kişi gelse bile yalnızca biri girer.
    reserved = await db.execute(
        update(Family).where(Family.id == family_id, Family.member_count < FAMILY_MAX_MEMBERS)
        .values(member_count=Family.member_count + 1)
    )
    if reserved.rowcount != 1:
        await db.rollback()
        raise ConflictError("Bu aile dolu.", code="family_full")
    try:
        db.add(FamilyMember(user_id=user_id, family_id=family_id, role="member"))
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise ConflictError("Zaten bir ailedesin.", code="already_in_family") from error
    audit("family_joined", family_id=family_id)
    return await get_detail(db, user_id, family_id)


async def _remove_member(db: AsyncSession, family_id: int, user_id: int) -> None:
    removed = await db.execute(
        delete(FamilyMember).where(FamilyMember.user_id == user_id, FamilyMember.family_id == family_id)
    )
    if removed.rowcount == 1:
        await db.execute(update(Family).where(Family.id == family_id).values(member_count=Family.member_count - 1))


async def leave_family(db: AsyncSession, user_id: int) -> None:
    member = await db.scalar(select(FamilyMember).where(FamilyMember.user_id == user_id))
    if member is None:
        raise AppError("Bir ailede değilsin.", code="not_in_family")
    if member.role == "owner":
        raise AppError("Kurucu aileden ayrılamaz; aileyi dağıtabilirsin.", code="owner_cannot_leave")
    await _remove_member(db, member.family_id, user_id)
    await db.commit()
    audit("family_left", family_id=member.family_id)


async def _require_role(db: AsyncSession, family_id: int, user_id: int, minimum: str) -> FamilyMember:
    member = await db.scalar(
        select(FamilyMember).where(FamilyMember.user_id == user_id, FamilyMember.family_id == family_id)
    )
    if member is None or ROLE_RANK[member.role] < ROLE_RANK[minimum]:
        raise ForbiddenError("Bu işlem için yetkin yok.", code="not_family_manager")
    return member


async def kick_member(db: AsyncSession, actor_id: int, family_id: int, target_id: int) -> FamilyDetail:
    family = await _get_family(db, family_id)
    actor = await _require_role(db, family_id, actor_id, "admin")
    target = await db.scalar(
        select(FamilyMember).where(FamilyMember.user_id == target_id, FamilyMember.family_id == family_id)
    )
    if target is None:
        raise NotFoundError("Bu kişi ailede değil.")
    if ROLE_RANK[target.role] >= ROLE_RANK[actor.role]:
        raise ForbiddenError("Kendi rütbende ya da üstündeki birini çıkaramazsın.", code="cannot_kick_higher")
    await _remove_member(db, family_id, target_id)
    await db.commit()
    audit("family_member_kicked", family_id=family_id, target_id=target_id)
    await notification_service.notify(db, target_id, "family_kicked", f"{family.name} ailesinden çıkarıldın.")
    return await get_detail(db, actor_id, family_id)


async def set_role(db: AsyncSession, actor_id: int, family_id: int, target_id: int, role: str) -> FamilyDetail:
    await _require_role(db, family_id, actor_id, "owner")
    changed = await db.execute(
        update(FamilyMember)
        .where(FamilyMember.user_id == target_id, FamilyMember.family_id == family_id, FamilyMember.role != "owner")
        .values(role=role)
    )
    if changed.rowcount != 1:
        raise NotFoundError("Bu kişi ailede değil ya da kurucu.")
    await db.commit()
    audit("family_role_set", family_id=family_id, target_id=target_id, role=role)
    return await get_detail(db, actor_id, family_id)


async def update_family(db: AsyncSession, actor_id: int, family_id: int, data: FamilyUpdateRequest) -> FamilyDetail:
    family = await _get_family(db, family_id)
    await _require_role(db, family_id, actor_id, "admin")
    if data.slogan is not None:
        family.slogan = data.slogan
    if data.badge is not None:
        family.badge = data.badge
    await db.commit()
    audit("family_updated", family_id=family_id, fields=sorted(data.model_fields_set))
    return await get_detail(db, actor_id, family_id)


async def disband_family(db: AsyncSession, actor_id: int, family_id: int) -> None:
    family = await _get_family(db, family_id)
    await _require_role(db, family_id, actor_id, "owner")
    member_ids = list(await db.scalars(select(FamilyMember.user_id).where(FamilyMember.family_id == family_id)))
    # Üyelik ve mesajlar veritabanında "ondelete=CASCADE" ile aileyle birlikte silinir.
    await db.delete(family)
    await db.commit()
    audit("family_disbanded", family_id=family_id, name=family.name, members=len(member_ids))
    for member_id in member_ids:
        if member_id != actor_id:
            await notification_service.notify(db, member_id, "family_disbanded", f"{family.name} ailesi dağıtıldı.")


# ── Aile sohbeti ──────────────────────────────────────────────────────────────

async def list_messages(db: AsyncSession, user_id: int, family_id: int, before_id: int | None = None) -> list[FamilyMessageOut]:
    await _require_role(db, family_id, user_id, "member")
    statement = (
        select(FamilyMessage).where(FamilyMessage.family_id == family_id).order_by(FamilyMessage.id.desc()).limit(50)
    )
    if before_id is not None:
        statement = statement.where(FamilyMessage.id < before_id)
    rows = list(await db.scalars(statement))
    users = await user_service.load_users_out(db, {row.sender_id for row in rows}, viewer_id=None)
    # Eskiden yeniye (ekranda yukarıdan aşağıya) sıralı döner.
    return [
        FamilyMessageOut(id=row.id, sender=users[row.sender_id], text=row.text, created_at=row.created_at)
        for row in reversed(rows) if row.sender_id in users
    ]


async def send_message(db: AsyncSession, user_id: int, family_id: int, text: str) -> FamilyMessageOut:
    await _require_role(db, family_id, user_id, "member")
    message = FamilyMessage(family_id=family_id, sender_id=user_id, text=text)
    db.add(message)
    await db.commit()
    sender = await user_service.present_user(db, await db.get(User, user_id), viewer_id=None)
    out = FamilyMessageOut(id=message.id, sender=sender, text=message.text, created_at=message.created_at)
    # Mesaj, uygulamada olan bütün üyelere kişiye özel kanaldan anında gider.
    payload = {"family_id": family_id, "message": out.model_dump(mode="json")}
    for member_id in await db.scalars(select(FamilyMember.user_id).where(FamilyMember.family_id == family_id)):
        await user_hub.publish(member_id, events.FAMILY_MESSAGE, payload)
    return out
