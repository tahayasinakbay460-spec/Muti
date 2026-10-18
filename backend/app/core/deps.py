"""
Router'ların ortak "bağımlılıkları" (dependencies).

FastAPI'de bir endpoint fonksiyonunun parametresine aşağıdaki tiplerden birini
yazarsan, FastAPI o değeri senin yerine hazırlar:

    async def get_me(user: CurrentUser, db: DbSession): ...

  DbSession      → bu isteğe özel veritabanı oturumu
  CurrentUserId  → token'dan okunan kullanıcı id'si (veritabanına GİTMEZ, çok hızlı)
  CurrentUser    → veritabanından yüklenmiş kullanıcı satırı (banlı mı diye de bakar)

Token yoksa ya da geçersizse endpoint hiç çalışmaz, istemciye 401 döner.
"""
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import UnauthorizedError
from app.core.security import decode_access_token
from app.models import User
from app.realtime.state import room_state

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
