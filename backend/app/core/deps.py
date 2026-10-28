"""
Router'ların ortak "bağımlılıkları" (dependencies).

FastAPI'de bir endpoint fonksiyonunun parametresine aşağıdaki tiplerden birini
yazarsan, FastAPI o değeri senin yerine hazırlar:

    async def get_me(user: CurrentUser, db: DbSession): ...

  DbSession      → bu isteğe özel veritabanı oturumu
  CurrentUserId  → token'dan okunan kullanıcı id'si (veritabanına GİTMEZ, çok hızlı)
  CurrentUser    → veritabanından yüklenmiş kullanıcı satırı (banlı mı diye de bakar)
  Staff("yetki") → yönetim paneli personeli; panel oturumu açık ve o yetkisi var

Token yoksa ya da geçersizse endpoint hiç çalışmaz, istemciye 401 döner.
"""
import time
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.logs import user_id_var
from app.core.permissions import permissions_of
from app.core.security import create_staff_token, decode_access_token, decode_staff_token
from app.models import User
from app.realtime.state import room_state
from app.services import admin_service

# `Authorization: Bearer <token>` başlığını okur. auto_error=False: başlık yoksa
# hatayı FastAPI değil biz üretelim (kendi JSON biçimimizle).
_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> int:
    if credentials is None:
        raise UnauthorizedError("Bu işlem için giriş yapmalısın.", code="not_authenticated")
    user_id = decode_access_token(credentials.credentials)
    # Banlanan kişinin elindeki token'ın süresi dolmamış olsa bile hemen reddedilir.
    # (Bellekte bir küme kontrolü; veritabanına gitmez. Bkz. services/admin_service.py)
    if admin_service.is_banned(user_id):
        raise UnauthorizedError("Hesabın engellendi.", code="account_disabled")
    # Bu isteğin bütün kayıtlarında kim olduğu görünsün (bkz. core/logs.py).
    user_id_var.set(user_id)
    # Her istekte "bu kullanıcı şu an aktif" damgasını yenile (çevrimiçi göstergesi için).
    await room_state.touch_presence(user_id)
    return user_id


CurrentUserId = Annotated[int, Depends(get_current_user_id)]


async def get_current_user(user_id: CurrentUserId, db: DbSession) -> User:
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Hesap bulunamadı veya engellenmiş.", code="account_disabled")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@dataclass(frozen=True)
class StaffContext:
    """Panel isteğini yapan personel: kim, rolü, yetkileri, şifresini en son ne zaman girdi."""
    user: User
    role: str
    permissions: frozenset[str]
    auth_time: int   # şifrenin girildiği an (Unix zamanı, saniye)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


async def get_current_staff(
    user: CurrentUser,
    response: Response,
    x_staff_token: Annotated[str | None, Header()] = None,
) -> StaffContext:
    """
    Panel uçlarının ortak kapısı:
      1. Hesabın bir panel rolü olmalı (yoksa 403).
      2. Panel token'ı (`X-Staff-Token`) geçerli olmalı (yoksa 401 staff_session_required →
         panel şifreyi yeniden sorar).
      3. Her başarılı istekte token'ın süresi uzatılır ve cevapla geri gönderilir.
    """
    if not user.staff_role:
        raise ForbiddenError("Bu sayfa yalnızca yönetim ekibine açık.", code="staff_only")
    if not x_staff_token:
        raise UnauthorizedError("Panel için şifreni gir.", code="staff_session_required")
    auth_time = decode_staff_token(x_staff_token, user.id)
    renewed, _ = create_staff_token(user.id, auth_time)
    response.headers["X-Staff-Token"] = renewed
    return StaffContext(user=user, role=user.staff_role, permissions=permissions_of(user.staff_role), auth_time=auth_time)


CurrentStaff = Annotated[StaffContext, Depends(get_current_staff)]


def require_recent_auth(staff: StaffContext) -> None:
    """Kritik işlemden önce: şifre son birkaç dakikada girilmemişse yeniden sorulsun."""
    if time.time() - staff.auth_time > settings.staff_reauth_minutes * 60:
        raise UnauthorizedError("Bu işlem için şifreni yeniden gir.", code="staff_reauth_required")


def Staff(permission: str, recent_auth: bool = False):  # noqa: N802 (tip gibi kullanılıyor)
    """
    Router'da parametre tipi olarak yazılır:

        async def ban_user(staff: Staff("users.ban", recent_auth=True), ...)

    Personelin bu yetkisi yoksa 403; `recent_auth=True` ise şifre de taze olmalı.
    """
    async def dependency(staff: CurrentStaff) -> StaffContext:
        if not staff.can(permission):
            raise ForbiddenError("Rolünün bu işleme yetkisi yok.", code="permission_denied")
        if recent_auth:
            require_recent_auth(staff)
        return staff

    return Annotated[StaffContext, Depends(dependency)]
