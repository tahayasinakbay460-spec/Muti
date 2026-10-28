"""
Yönetim paneli personeli: panel oturumu açma, rol verme/alma, personel işlem kaydı.

Rollerin hangi yetkileri verdiği core/permissions.py içinde; panel token'ının nasıl çalıştığı
core/security.py "Panel oturumu" bölümünde.
"""
import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.core.config import settings
from app.core.logs import audit
from app.core.permissions import ROLE_LABELS, permissions_of
from app.core.security import create_staff_token, verify_password
from app.core.timefmt import as_utc
from app.models import StaffAction, User
from app.schemas.admin import StaffActionOut, StaffMemberOut, StaffSessionOut
from app.services import user_service


def session_out(user: User, auth_time: int) -> StaffSessionOut:
    token, expires_in = create_staff_token(user.id, auth_time)
    return StaffSessionOut(
        staff_token=token, expires_in=expires_in, role=user.staff_role,
        role_label=ROLE_LABELS[user.staff_role], permissions=sorted(permissions_of(user.staff_role)),
        idle_minutes=settings.staff_idle_minutes,
    )


async def start_session(user: User, password: str) -> StaffSessionOut:
    """
    Şifreyi yeniden doğrulayıp panel token'ı verir. Hem panele ilk girişte hem kritik
    işlemden önce ("şifreni yeniden gir") çağrılır; her seferinde `auth_time` yenilenir.
    """
    if not user.staff_role:
        raise ForbiddenError("Bu hesap yönetim ekibinde değil.", code="staff_only")
    if not (user.password_hash and await verify_password(password, user.password_hash)):
        audit("staff_session_failed", log_level=logging.WARNING, staff_id=user.id)
        # 401 ama kodu "staff_" ile başlar: frontend bunu "access token'ın süresi doldu"
        # sanıp boş yere yenilemeye çalışmasın.
        raise UnauthorizedError("Şifre hatalı.", code="staff_password_invalid")
    audit("staff_session_started", staff_id=user.id, role=user.staff_role)
    return session_out(user, int(time.time()))


async def record(
    db: AsyncSession, actor_id: int, action: str, target_type: str, target_id: int | None, detail: str = "",
) -> None:
    """Personel işlem kaydına bir satır yazar (panelde "İşlem kaydı")."""
    db.add(StaffAction(actor_id=actor_id, action=action, target_type=target_type, target_id=target_id,
                       detail=detail[:300]))
    await db.commit()


async def list_staff(db: AsyncSession) -> list[StaffMemberOut]:
    users = list(await db.scalars(
        select(User).where(User.staff_role.is_not(None), User.is_active.is_(True)).order_by(User.id)
    ))
    presented = await user_service.present_users(db, users, viewer_id=None)
    return [StaffMemberOut(user=out, role=u.staff_role, role_label=ROLE_LABELS[u.staff_role])
            for u, out in zip(users, presented)]


async def set_role(db: AsyncSession, actor: User, user_id: int, role: str | None) -> StaffMemberOut | None:
    """
    Personel rolü verir, değiştirir ya da (role=None) panel erişimini kaldırır. Etkisi anında:
    yetki her istekte veritabanından okunduğu için kişinin açık paneli bir sonraki istekte
    yeni rolüyle çalışır ya da kapanır.
    """
    if user_id == actor.id:
        # Kendi rolünü düşürüp son yöneticiyi kaybetmek ya da kendini yükseltmek olmasın.
        raise ForbiddenError("Kendi rolünü değiştiremezsin; başka bir yönetici değiştirmeli.", code="cannot_change_own_role")
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise NotFoundError("Kullanıcı bulunamadı ya da banlı.", code="user_not_found")
    if role and not user.password_hash:
        # Panel her girişte şifre ister; misafir hesabın şifresi yok.
        raise AppError("Misafir hesaba panel rolü verilemez.", code="guest_account")
    if user.staff_role == role:
        raise ConflictError("Bu kişinin rolü zaten bu.", code="role_unchanged")

    previous = user.staff_role
    user.staff_role = role
    audit("staff_role_changed", target_id=user.id, previous=previous, role=role)
    await record(db, actor.id, "staff_role_changed", "user", user.id,
                 f"{ROLE_LABELS.get(previous or '', 'yok')} → {ROLE_LABELS.get(role or '', 'yok')}")
    if role is None:
        return None
    return StaffMemberOut(user=await user_service.present_user(db, user, viewer_id=None),
                          role=role, role_label=ROLE_LABELS[role])


async def list_actions(
    db: AsyncSession, actor_id: int | None, before_id: int | None, limit: int,
) -> list[StaffActionOut]:
    statement = select(StaffAction).order_by(StaffAction.id.desc()).limit(limit)
    if actor_id:
        statement = statement.where(StaffAction.actor_id == actor_id)
    if before_id:
        statement = statement.where(StaffAction.id < before_id)
    rows = list(await db.scalars(statement))
    actor_ids = {r.actor_id for r in rows if r.actor_id}
    actors = list(await db.scalars(select(User).where(User.id.in_(actor_ids)))) if actor_ids else []
    by_id = dict(zip([a.id for a in actors], await user_service.present_users(db, actors, viewer_id=None)))
    return [StaffActionOut(id=r.id, actor=by_id.get(r.actor_id), action=r.action, target_type=r.target_type,
                           target_id=r.target_id, detail=r.detail, created_at=as_utc(r.created_at)) for r in rows]
