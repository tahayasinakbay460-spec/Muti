"""
Ajans sistemi: yönetici ajans kurar, ajans sahibi yayıncıları davet eder ya da yayıncı ajansa
başvurur; karşı taraf kabul edince yayıncı ajansa bağlanır. Ajans sahibi üyelerinin bu ayki
elmas kazancını, hedeflerini, seviyelerini ve tahmini komisyonunu görür.

Diğer sesli sohbet uygulamalarındaki (Yalla, Sugo, Bigo...) kalıp: yayıncı ajansa bağlanır,
ay içinde topladığı elmasa göre bir seviyeye (maaş tablosu) girer, her seviyenin ay sonu bonusu
vardır; ajans da yayıncılarının kazancından komisyon alır. Bir yayıncı aynı anda tek ajansa bağlıdır.

Kazançlar para defterinden (transactions, gift_received) hesaplanır: ayrı sayaç yok.

YAYINCI ŞARTI: Ajansa yalnızca onaylı yayıncılar (User.is_host, bkz. host_service) katılabilir.

AY SONU KOMİSYONU (settle_month): Komisyon BİZİM payımızdan ödenir, yayıncının kazancı düşmez.
Ay bitince panelden "ayı kapat" denir: ajans sahibine, aktif yayıncılarının o ay hediyelerden
kazandığı elmasın yüzde komisyonu kadar elmas eklenir. Her ajans her ay için bir kez (tablo
kuralı + idempotency anahtarı). Henüz bitmemiş ay kapatılamaz.
DEMO KISAYOLU: Ödeme elmas olarak; gerçek para (fatura, banka) elmas çekimiyle birlikte gelecek.
"""
from datetime import date, datetime
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.logs import audit
from app.core.timefmt import as_utc, local_day_start, local_today, period_start
from app.models import Agency, AgencyMember, AgencySettlement, Transaction, User
from app.schemas.admin import AgencyDashboard, AgencyMemberOut, AgencyOut, AgencySettlementOut, AgencyTier, MyAgency
from app.services import host_service, notification_service, staff_service, user_service, wallet_service


# Yayıncı seviyeleri (maaş tablosu): aylık elmasa göre. Sıra önemli, küçükten büyüğe.
# DEMO KISAYOLU: bonus yalnızca gösteriliyor; ay sonu ödemesi elmas → para çekimiyle birlikte yazılacak.
AGENCY_TIERS = [
    AgencyTier(name="Yeni Yayıncı", emoji="🌱", min_diamonds=0, bonus_percent=0),
    AgencyTier(name="Bronz", emoji="🥉", min_diamonds=10_000, bonus_percent=2),
    AgencyTier(name="Gümüş", emoji="🥈", min_diamonds=50_000, bonus_percent=4),
    AgencyTier(name="Altın", emoji="🥇", min_diamonds=150_000, bonus_percent=6),
    AgencyTier(name="Elmas", emoji="💎", min_diamonds=500_000, bonus_percent=10),
]


def tier_index(month_diamonds: int) -> int:
    """Bu ayki elmasa göre hangi seviyede (AGENCY_TIERS sırası)."""
    return max(i for i, tier in enumerate(AGENCY_TIERS) if month_diamonds >= tier.min_diamonds)


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


async def _present_many(db: AsyncSession, agencies: list[Agency]) -> list[AgencyOut]:
    """Ajans listesi: sahipler ve üye sayıları tek sorguda (ajans başına sorgu atılmaz)."""
    if not agencies:
        return []
    owner_ids = {agency.owner_id for agency in agencies}
    owners = {user.id: user for user in await db.scalars(select(User).where(User.id.in_(owner_ids)))}
    for agency in agencies:
        owner = owners.get(agency.owner_id)
        if owner is None or not owner.is_active:
            # `user_service.get_user` ile aynı davranış: sahibi silinmiş/banlı ajans gösterilmez.
            raise NotFoundError("Kullanıcı bulunamadı.")
    outs = await user_service.present_users(db, [owners[agency.owner_id] for agency in agencies], viewer_id=None)
    counts = dict((await db.execute(
        select(AgencyMember.agency_id, func.count())
        .where(AgencyMember.agency_id.in_([agency.id for agency in agencies]), AgencyMember.status == "active")
        .group_by(AgencyMember.agency_id)
    )).all())
    return [
        AgencyOut(id=agency.id, name=agency.name, owner=owner, commission_percent=agency.commission_percent,
                  member_count=counts.get(agency.id, 0))
        for agency, owner in zip(agencies, outs)
    ]


async def _present(db: AsyncSession, agency: Agency) -> AgencyOut:
    return (await _present_many(db, [agency]))[0]


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
    return await _present_many(db, list(await db.scalars(select(Agency).order_by(Agency.id))))


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
                                       month_diamonds=earned, progress_percent=progress,
                                       tier_index=tier_index(earned)))
    # Önce üyeler (kazanca göre), sonra başvurular, en sonda davetler
    order = {"active": 0, "applied": 1, "invited": 2}
    members.sort(key=lambda m: (order[m.status], -m.month_diamonds))
    total = sum(diamonds.values())
    return AgencyDashboard(agency=await _present(db, agency), members=members, month_diamonds=total,
                           estimated_commission=total * agency.commission_percent // 100,
                           settlements=await my_settlements(db, agency))


async def invite(db: AsyncSession, owner_id: int, user_id: int) -> AgencyDashboard:
    agency = await _owned_agency(db, owner_id)
    if user_id == owner_id:
        raise AppError("Kendini davet edemezsin.", code="cannot_invite_self")
    target = await user_service.get_user(db, user_id)
    if await db.scalar(select(Agency.id).where(Agency.owner_id == user_id)):
        raise ConflictError("Bu kişi bir ajans sahibi.", code="target_is_owner")
    await host_service.require_host(db, user_id, "Yalnızca onaylı yayıncılar ajansa davet edilebilir.")
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
        return MyAgency(role="owner", dashboard=await _dashboard(db, owned), tiers=AGENCY_TIERS)
    # Ajansı olmayan da kendi seviyesini görsün: ajansa katılınca nereden başlayacağını bilir.
    earned = (await _month_diamonds(db, [user_id])).get(user_id, 0)
    base = {"my_month_diamonds": earned, "my_tier_index": tier_index(earned), "tiers": AGENCY_TIERS}
    membership = await db.scalar(select(AgencyMember).where(AgencyMember.user_id == user_id))
    if membership is None:
        return MyAgency(role=None, **base)
    agency = await _present(db, await db.get(Agency, membership.agency_id))
    if membership.status == "invited":
        return MyAgency(role=None, invite=agency, **base)
    if membership.status == "applied":
        return MyAgency(role=None, application=agency, **base)
    return MyAgency(role="member", agency=agency, my_target=membership.monthly_target, **base)


async def list_public(db: AsyncSession, query: str = "") -> list[AgencyOut]:
    """Başvurulabilecek ajanslar. Ada ya da ajans numarasına göre aranır."""
    statement = select(Agency).order_by(Agency.id)
    text = query.strip()
    if text:
        # Kullanıcının yazdığı % ve _ SQL'de joker anlamına gelir; düz karakter sayılsın diye kaçırıyoruz.
        escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        condition = Agency.name.ilike(f"%{escaped}%", escape="\\")
        if text.isdigit():
            condition = condition | (Agency.id == int(text))
        statement = statement.where(condition)
    return await _present_many(db, list(await db.scalars(statement.limit(50))))


async def apply(db: AsyncSession, user_id: int, agency_id: int) -> MyAgency:
    """Yayıncı ajansa başvurur; ajans sahibi kabul edince üye olur."""
    agency = await db.get(Agency, agency_id)
    if agency is None:
        raise NotFoundError("Ajans bulunamadı.")
    if await db.scalar(select(Agency.id).where(Agency.owner_id == user_id)):
        raise ConflictError("Ajans sahipleri başka ajansa başvuramaz.", code="owner_cannot_apply")
    await host_service.require_host(db, user_id, "Ajansa başvurmak için önce yayıncı ol.")
    try:
        # Birincil anahtar user_id: zaten bir ajansı, daveti ya da başvurusu varsa yazılamaz.
        db.add(AgencyMember(user_id=user_id, agency_id=agency.id, status="applied"))
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise ConflictError("Zaten bir ajansın, davetin ya da başvurun var.", code="already_in_agency") from error
    audit("agency_applied", agency_id=agency.id)
    applicant = await user_service.get_user(db, user_id)
    await notification_service.notify(
        db, agency.owner_id, "agency_application", f"🏢 {applicant.display_name} ajansına yayıncı olarak başvurdu.",
        actor_id=user_id, data={"agency_id": agency.id, "user_id": user_id},
    )
    return await my_agency(db, user_id)


async def withdraw_application(db: AsyncSession, user_id: int) -> MyAgency:
    removed = await db.execute(
        delete(AgencyMember).where(AgencyMember.user_id == user_id, AgencyMember.status == "applied")
    )
    if removed.rowcount != 1:
        raise NotFoundError("Bekleyen bir başvurun yok.")
    await db.commit()
    audit("agency_application_withdrawn")
    return await my_agency(db, user_id)


async def accept_application(db: AsyncSession, owner_id: int, user_id: int) -> AgencyDashboard:
    """Ajans sahibi başvuruyu kabul eder. Reddetmek = remove_member (satır silinir)."""
    agency = await _owned_agency(db, owner_id)
    await host_service.require_host(db, user_id, "Bu kişi artık yayıncı değil.")
    changed = await db.execute(
        update(AgencyMember)
        .where(AgencyMember.user_id == user_id, AgencyMember.agency_id == agency.id, AgencyMember.status == "applied")
        .values(status="active", joined_at=utcnow())
    )
    if changed.rowcount != 1:
        raise NotFoundError("Bu kişinin bekleyen bir başvurusu yok.")
    await db.commit()
    audit("agency_application_accepted", agency_id=agency.id, target_id=user_id)
    await notification_service.notify(
        db, user_id, "agency_joined", f"🏢 {agency.name} başvurunu kabul etti, artık ajans yayıncısısın!",
        actor_id=owner_id, data={"agency_id": agency.id},
    )
    return await _dashboard(db, agency)


async def answer_invite(db: AsyncSession, user_id: int, accept: bool) -> MyAgency:
    membership = await db.scalar(
        select(AgencyMember).where(AgencyMember.user_id == user_id, AgencyMember.status == "invited")
    )
    if membership is None:
        raise NotFoundError("Bekleyen bir ajans davetin yok.")
    agency_id = membership.agency_id
    if accept:
        await host_service.require_host(db, user_id, "Daveti kabul etmek için önce yayıncı ol.")
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


# ── Ay sonu komisyonu (panel) ─────────────────────────────────────────────────

def _month_range(month: str) -> tuple[datetime, datetime]:
    """"2026-10" → o ayın başı ve bir sonraki ayın başı (yerel takvime göre, UTC an olarak)."""
    try:
        year, number = (int(part) for part in month.split("-"))
        first = date(year, number, 1)
    except ValueError as error:
        raise AppError("Ay biçimi YYYY-AA olmalı.", code="invalid_month") from error
    following = date(year + (number == 12), number % 12 + 1, 1)
    return local_day_start(first), local_day_start(following)


async def _host_diamonds(db: AsyncSession, agency_id: int, month: str) -> tuple[int, int]:
    """
    Ajansın aktif yayıncılarının o ay kazandığı elmas ve yayıncı sayısı.
    Yalnızca yayıncının ajansa KATILDIKTAN sonraki kazancı sayılır. Yoksa ajans sahibi, ay kapanmadan
    hemen önce o ay çok kazanmış birini ajansa alıp onun eski kazancından da komisyon alabilirdi.
    """
    start, end = _month_range(month)
    members = list(await db.execute(select(AgencyMember.user_id, AgencyMember.joined_at).where(
        AgencyMember.agency_id == agency_id, AgencyMember.status == "active")))
    total = 0
    for user_id, joined_at in members:
        since = max(start, as_utc(joined_at)) if joined_at else start
        total += int(await db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.user_id == user_id, Transaction.type == "gift_received",
                   Transaction.created_at >= since, Transaction.created_at < end)
        ))
    return total, len(members)


def _settlement_out(row: AgencySettlement, agency: Agency) -> AgencySettlementOut:
    return AgencySettlementOut(
        agency_id=agency.id, agency_name=agency.name, month=row.month, host_diamonds=row.host_diamonds,
        commission_percent=row.commission_percent, commission_diamonds=row.commission_diamonds,
        member_count=row.member_count, settled=True, created_at=row.created_at,
    )


async def month_overview(db: AsyncSession, month: str) -> list[AgencySettlementOut]:
    """Panel: her ajansın o ayki durumu. Kapatılmışsa ödenen, değilse şu anki hesap gösterilir."""
    _month_range(month)
    agencies = list(await db.scalars(select(Agency).order_by(Agency.id)))
    settled = {row.agency_id: row for row in await db.scalars(
        select(AgencySettlement).where(AgencySettlement.month == month))}
    result = []
    for agency in agencies:
        if agency.id in settled:
            result.append(_settlement_out(settled[agency.id], agency))
            continue
        diamonds, member_count = await _host_diamonds(db, agency.id, month)
        result.append(AgencySettlementOut(
            agency_id=agency.id, agency_name=agency.name, month=month, host_diamonds=diamonds,
            commission_percent=agency.commission_percent,
            commission_diamonds=diamonds * agency.commission_percent // 100, member_count=member_count, settled=False,
        ))
    return result


async def settle_month(db: AsyncSession, staff_id: int, agency_id: int, month: str) -> AgencySettlementOut:
    """
    Ajansın bir ayını kapatır ve komisyonu ajans sahibine elmas olarak öder.
    Kapatıldığı andaki aktif yayıncıların o ayki kazancı esas alınır.
    """
    agency = await db.get(Agency, agency_id)
    if agency is None:
        raise NotFoundError("Ajans bulunamadı.")
    start, _end = _month_range(month)
    if start >= period_start("month"):
        raise AppError("Yalnızca bitmiş aylar kapatılabilir.", code="month_not_finished")
    diamonds, member_count = await _host_diamonds(db, agency.id, month)
    commission = diamonds * agency.commission_percent // 100
    row = AgencySettlement(
        agency_id=agency.id, month=month, host_diamonds=diamonds, commission_percent=agency.commission_percent,
        commission_diamonds=commission, member_count=member_count, settled_by=staff_id,
    )
    db.add(row)
    try:
        # Satır ve ödeme tek transaction'da: ya ikisi ya hiçbiri.
        await db.flush()
        if commission > 0:
            await wallet_service.change_balance(
                db, user_id=agency.owner_id, currency="diamond", delta=commission, type="agency_commission",
                label=f"Ajans komisyonu · {agency.name} · {month}",
                idempotency_key=f"agency:{agency.id}:{month}",
            )
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise ConflictError("Bu ay bu ajans için zaten kapatılmış.", code="already_settled") from error
    audit("agency_month_settled", agency_id=agency.id, month=month, host_diamonds=diamonds, commission_diamonds=commission)
    await staff_service.record(db, staff_id, "agency_month_settled", "agency", agency.id,
                               f"{agency.name} · {month} · {commission} elmas")
    await notification_service.notify(
        db, agency.owner_id, "agency_commission",
        f"🏢 {agency.name}: {month} komisyonun hesabına geçti (+{commission} elmas).",
    )
    await db.refresh(row)
    return _settlement_out(row, agency)


async def my_settlements(db: AsyncSession, agency: Agency) -> list[AgencySettlementOut]:
    rows = await db.scalars(select(AgencySettlement).where(AgencySettlement.agency_id == agency.id)
                            .order_by(AgencySettlement.month.desc()).limit(12))
    return [_settlement_out(row, agency) for row in rows]


def last_month() -> str:
    """Bir önceki ay, "YYYY-AA" (panelin varsayılan seçimi)."""
    first = local_today().replace(day=1)
    previous = date(first.year - (first.month == 1), (first.month - 2) % 12 + 1, 1)
    return f"{previous.year}-{previous.month:02d}"
