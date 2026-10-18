"""
/api/v1/users — profil, takip, öneriler.
"""
from fastapi import APIRouter

from app.core.deps import CurrentUser, CurrentUserId, DbSession
from app.demo import content
from app.schemas.user import FollowResult, ProfileExtras, UserOut
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])

# SIRA ÖNEMLİ: "/me" ve "/suggested" gibi sabit adresler, "/{user_id}" adresinden
# ÖNCE tanımlanmalı. Yoksa FastAPI "me" kelimesini bir kullanıcı id'si sanmaya çalışır.


@router.get("/me", response_model=UserOut)
async def get_me(user: CurrentUser, db: DbSession):
    """Giriş yapmış kullanıcının kendi profili (bakiye dahil)."""
    return await user_service.present_user(db, user, viewer_id=user.id)


@router.get("/suggested", response_model=list[UserOut])
async def list_suggested(user_id: CurrentUserId, db: DbSession):
    return await user_service.list_suggested(db, user_id)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int, viewer_id: CurrentUserId, db: DbSession):
    user = await user_service.get_user(db, user_id)
    return await user_service.present_user(db, user, viewer_id)


@router.get("/{user_id}/profile", response_model=ProfileExtras)
async def get_profile_extras(user_id: int, _viewer_id: CurrentUserId, db: DbSession):
    """Profil ekranının alt bölümleri. DEMO KISAYOLU: herkes için aynı sabit içerik."""
    await user_service.get_user(db, user_id)
    return content.PROFILE_EXTRAS


@router.post("/{user_id}/follow", response_model=FollowResult)
async def toggle_follow(user_id: int, viewer_id: CurrentUserId, db: DbSession):
    """Takip ediyorsan bırakır, etmiyorsan takip eder."""
    return FollowResult(is_following=await user_service.toggle_follow(db, viewer_id, user_id))
