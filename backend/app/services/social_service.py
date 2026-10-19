"""
Engelleme ve şikâyet.

ENGELLEME iki yönlü etki eder (kim engellediyse engellesin):
  - Birbirlerine özel mesaj atamaz, hediye gönderemez, birbirini takip edemez.
  - Varsa takipleri iki yönde de kalkar.
  - Birbirlerinden bildirim almazlar.
Engellenen kişiye "engellendin" denmez; yalnızca işlem reddedilir.

ŞİKÂYET bir kayıt oluşturur; yöneticiler inceler (yönetim paneli henüz yok).
"""
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError
from app.models import Report, Room, User, UserBlock
from app.schemas.social import ReportRequest
from app.schemas.user import UserOut
from app.services import user_service


async def set_block(db: AsyncSession, me: int, target_id: int, blocked: bool) -> bool:
    if target_id == me:
        raise AppError("Kendini engelleyemezsin.", code="cannot_block_self")
    await user_service.get_user(db, target_id)

    if not blocked:
        await db.execute(delete(UserBlock).where(UserBlock.blocker_id == me, UserBlock.blocked_id == target_id))
        await db.commit()
        return False

    db.add(UserBlock(blocker_id=me, blocked_id=target_id))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()   # zaten engelliymiş
        return True
    # Takipleri iki yönde de kaldır (sayaçlar da düzelir).
    await user_service.set_follow(db, me, target_id, follow=False)
    await user_service.set_follow(db, target_id, me, follow=False)
    await db.commit()
    return True


async def list_blocked(db: AsyncSession, me: int) -> list[UserOut]:
    users = await db.scalars(
        select(User).join(UserBlock, UserBlock.blocked_id == User.id)
        .where(UserBlock.blocker_id == me).order_by(UserBlock.created_at.desc())
    )
    return await user_service.present_users(db, list(users), me)


async def create_report(db: AsyncSession, me: int, data: ReportRequest) -> None:
    if data.target_type == "user":
        if data.target_id == me:
            raise AppError("Kendini şikâyet edemezsin.", code="cannot_report_self")
        await user_service.get_user(db, data.target_id)
    elif await db.get(Room, data.target_id) is None:
        raise NotFoundError("Oda bulunamadı.")

    # Aynı kişinin aynı hedefi defalarca şikâyet etmesi inceleme listesini doldurmasın:
    # açık bir şikâyeti varsa yenisi yazılmaz (kullanıcıya yine "alındı" denir).
    already_open = await db.scalar(
        select(Report.id).where(
            Report.reporter_id == me, Report.target_type == data.target_type,
            Report.target_id == data.target_id, Report.status == "open",
        )
    )
    if already_open is None:
        db.add(Report(
            reporter_id=me, target_type=data.target_type, target_id=data.target_id,
            reason=data.reason, details=data.details,
        ))
        await db.commit()
