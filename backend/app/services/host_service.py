"""
Yayıncılık: başvuru, panelde onay/ret, yayıncılığı geri alma (bkz. models/host.py).

KURALLAR
  - Misafir hesap başvuramaz (kimliği belirsiz).
  - 18 yaşından küçük başvuramaz: yaşı doğum tarihinden SUNUCU hesaplar.
  - Aynı anda tek bekleyen başvuru. Reddedilen kişi REAPPLY_DAYS gün sonra yeniden başvurabilir
    (panel aynı kişinin yüzlerce başvurusuyla dolmasın).
  - Onay ve ret yalnızca `hosts.review` yetkili personelde; her karar personel işlem kaydına ve
    audit kaydına yazılır, kişiye bildirim gider.
  - Yayıncılık geri alınınca kişi ajansından da çıkar (ajans yalnızca yayıncılar içindir).
"""
from datetime import date, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.logs import audit
from app.core.timefmt import as_utc, local_today
from app.models import AgencyMember, HostApplication, User
from app.schemas.host import HostApplicationAdminOut, HostApplicationOut, HostApplyRequest, HostStatus
from app.services import notification_service, staff_service, user_service

MIN_AGE = 18
REAPPLY_DAYS = 7


def age_on(birth: date, today: date) -> int:
    """Tam yaş: bu yılki doğum günü gelmediyse bir eksik."""
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def _out(application: HostApplication) -> HostApplicationOut:
    return HostApplicationOut(
        id=application.id, status=application.status, intro=application.intro, review_note=application.review_note,
        created_at=as_utc(application.created_at),
        reviewed_at=as_utc(application.reviewed_at) if application.reviewed_at else None,
    )


async def _latest(db: AsyncSession, user_id: int) -> HostApplication | None:
    return await db.scalar(
        select(HostApplication).where(HostApplication.user_id == user_id)
        .order_by(HostApplication.id.desc()).limit(1)
    )


async def status(db: AsyncSession, user: User) -> HostStatus:
    latest = await _latest(db, user.id)
    reapply_after = None
    can_apply = not user.is_host and not user.is_guest
    if latest is not None and latest.status == "pending":
        can_apply = False
    elif latest is not None and latest.status == "rejected" and latest.reviewed_at:
        reapply_after = as_utc(latest.reviewed_at) + timedelta(days=REAPPLY_DAYS)
        if reapply_after > utcnow():
            can_apply = False
        else:
            reapply_after = None
    return HostStatus(
        is_host=user.is_host, host_since=as_utc(user.host_since) if user.host_since else None,
        application=_out(latest) if latest else None, can_apply=can_apply, reapply_after=reapply_after,
    )


async def apply(db: AsyncSession, user: User, data: HostApplyRequest) -> HostStatus:
    if user.is_guest:
        raise ForbiddenError("Yayıncı olmak için hesap oluştur.", code="guest_cannot_apply")
    if user.is_host:
        raise ConflictError("Zaten yayıncısın.", code="already_host")
    age = age_on(data.birth_date, local_today())
    if age < MIN_AGE:
        raise ForbiddenError("Yayıncı olmak için 18 yaşından büyük olmalısın.", code="underage")
    if age > 100:
        raise AppError("Doğum tarihini kontrol et.", code="invalid_birth_date")
    current = await status(db, user)
    if not current.can_apply:
        raise ConflictError("Bekleyen bir başvurun var ya da yeniden başvuru süresi dolmadı.", code="cannot_apply_now")
    db.add(HostApplication(user_id=user.id, birth_date=data.birth_date, intro=data.intro))
    await db.commit()
    audit("host_applied", age=age)
    return await status(db, user)


# ── Panel ─────────────────────────────────────────────────────────────────────

async def list_applications(db: AsyncSession, status_filter: str = "pending") -> list[HostApplicationAdminOut]:
    rows = list(await db.scalars(
        select(HostApplication).where(HostApplication.status == status_filter)
        .order_by(HostApplication.id.desc() if status_filter != "pending" else HostApplication.id).limit(100)
    ))
    users = await user_service.load_users_out(db, {row.user_id for row in rows}, viewer_id=None)
    today = local_today()
    return [
        HostApplicationAdminOut(**_out(row).model_dump(), user=users[row.user_id], birth_date=row.birth_date,
                                age=age_on(row.birth_date, today))
        for row in rows if row.user_id in users
    ]


async def review(db: AsyncSession, staff_id: int, application_id: int, approve: bool, note: str) -> HostApplicationAdminOut:
    application = await db.get(HostApplication, application_id)
    if application is None:
        raise NotFoundError("Başvuru bulunamadı.")
    now = utcnow()
    # "Yalnızca hâlâ bekliyorsa" değiştir: iki moderatör aynı anda karar verirse ikincisi boşa düşer.
    changed = await db.execute(
        update(HostApplication).where(HostApplication.id == application_id, HostApplication.status == "pending")
        .values(status="approved" if approve else "rejected", review_note=note.strip() or None,
                reviewed_by=staff_id, reviewed_at=now)
    )
    if not changed.rowcount:
        await db.rollback()
        raise ConflictError("Bu başvuru zaten karara bağlanmış.", code="already_reviewed")
    if approve:
        await db.execute(update(User).where(User.id == application.user_id).values(is_host=True, host_since=now))
    await db.commit()

    decision = "host_approved" if approve else "host_rejected"
    audit(decision, application_id=application_id, target_id=application.user_id)
    await staff_service.record(db, staff_id, decision, "user", application.user_id, note.strip())
    text = ("🎙️ Yayıncı başvurun onaylandı! Artık ajanslara katılabilirsin." if approve
            else f"Yayıncı başvurun reddedildi.{f' Sebep: {note.strip()}' if note.strip() else ''}")
    await notification_service.notify(db, application.user_id, decision, text)
    await db.refresh(application)
    users = await user_service.load_users_out(db, {application.user_id}, viewer_id=None)
    return HostApplicationAdminOut(**_out(application).model_dump(), user=users[application.user_id],
                                   birth_date=application.birth_date, age=age_on(application.birth_date, local_today()))


async def revoke(db: AsyncSession, staff_id: int, user_id: int, note: str) -> None:
    """Yayıncılığı geri alır (kural ihlali vb.). Kişi ajansından da çıkar."""
    user = await user_service.get_user(db, user_id)
    if not user.is_host:
        raise AppError("Bu kişi yayıncı değil.", code="not_host")
    user.is_host, user.host_since = False, None
    await db.execute(delete(AgencyMember).where(AgencyMember.user_id == user_id))
    await db.commit()
    audit("host_revoked", target_id=user_id)
    await staff_service.record(db, staff_id, "host_revoked", "user", user_id, note.strip())
    await notification_service.notify(db, user_id, "host_revoked",
                                      f"Yayıncılığın kaldırıldı.{f' Sebep: {note.strip()}' if note.strip() else ''}")


async def require_host(db: AsyncSession, user_id: int, message: str = "Önce yayıncı olmalısın.") -> None:
    """Ajans işlemlerinde: kişi onaylı yayıncı değilse hata."""
    if not await db.scalar(select(User.is_host).where(User.id == user_id)):
        raise ForbiddenError(message, code="not_host")
