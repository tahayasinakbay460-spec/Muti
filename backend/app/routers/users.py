"""
/api/v1/users — profil, profil düzenleme, hesap silme, takip, arama, öneriler, engelleme.
"""
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.core.deps import CurrentUser, CurrentUserId, DbSession
from app.demo import content
from app.schemas.auth import DeleteAccountRequest
from app.schemas.social import BlockResult
from app.schemas.user import FollowResult, MediaOptions, ProfileExtras, ProfileUpdateRequest, UserOut
from app.services import auth_service, social_service, user_service

router = APIRouter(prefix="/users", tags=["users"])

# SIRA ÖNEMLİ: "/me" ve "/suggested" gibi sabit adresler, "/{user_id}" adresinden
# ÖNCE tanımlanmalı. Yoksa FastAPI "me" kelimesini bir kullanıcı id'si sanmaya çalışır.


@router.get("/me", response_model=UserOut)
async def get_me(user: CurrentUser, db: DbSession):
    """Giriş yapmış kullanıcının kendi profili (bakiye dahil)."""
    return await user_service.present_user(db, user, viewer_id=user.id)


@router.patch("/me", response_model=UserOut)
async def update_me(data: ProfileUpdateRequest, user: CurrentUser, db: DbSession):
    """Kendi profilini düzenler. Yalnızca gönderilen alanlar değişir."""
    return await user_service.update_profile(db, user, data)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(data: DeleteAccountRequest, user: CurrentUser, db: DbSession):
    """Hesabı siler (kişisel bilgiler temizlenir, oturumlar kapanır). Parola sorulur."""
    await auth_service.delete_account(db, user, data.password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/blocks", response_model=list[UserOut])
async def list_blocked(user_id: CurrentUserId, db: DbSession):
    """Engellediğim kişiler (ayarlar ekranı)."""
    return await social_service.list_blocked(db, user_id)


@router.get("/search", response_model=list[UserOut])
async def search_users(user_id: CurrentUserId, db: DbSession, query: Annotated[str, Query(max_length=40)] = ""):
    """Ada, kullanıcı adına ya da ID numarasına göre kişi arar."""
    return await user_service.search_users(db, user_id, query)


@router.get("/me/media-options", response_model=MediaOptions)
async def get_media_options(_user_id: CurrentUserId):
    """Profil düzenlemede seçilebilecek hazır avatar/kapak listesi. DEMO KISAYOLU: görsel yükleme yok."""
    return MediaOptions(avatars=content.AVATAR_CHOICES, covers=content.COVER_CHOICES)


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


@router.put("/{user_id}/block", response_model=BlockResult)
async def block_user(user_id: int, viewer_id: CurrentUserId, db: DbSession):
    """Kişiyi engeller: birbirinize mesaj ve hediye gönderemez, birbirinizi takip edemezsiniz."""
    return BlockResult(is_blocked=await social_service.set_block(db, viewer_id, user_id, blocked=True))


@router.delete("/{user_id}/block", response_model=BlockResult)
async def unblock_user(user_id: int, viewer_id: CurrentUserId, db: DbSession):
    return BlockResult(is_blocked=await social_service.set_block(db, viewer_id, user_id, blocked=False))
