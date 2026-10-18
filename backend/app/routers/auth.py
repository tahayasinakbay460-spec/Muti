"""
/api/v1/auth — kayıt, giriş, token yenileme, çıkış.

ROUTER NEDİR? İnternetten gelen isteği karşılayan en dış katman. Burada iş kuralı
YAZILMAZ: router yalnızca isteği alır, ilgili servisi çağırır, sonucu döner.
"""
from fastapi import APIRouter, status

from app.core.deps import DbSession
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: DbSession):
    """Yeni hesap açar ve doğrudan giriş yapmış olarak token döner."""
    return await auth_service.register(db, data)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: DbSession):
    return await auth_service.login(db, data)


@router.post("/guest", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def login_as_guest(db: DbSession):
    """Kayıt olmadan misafir olarak devam et."""
    return await auth_service.login_as_guest(db)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: DbSession):
    """Access token'ın süresi dolunca refresh token ile yenisini al."""
    return await auth_service.refresh(db, data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshRequest, db: DbSession):
    """Bu cihazdaki oturumu kapatır (refresh token'ı iptal eder)."""
    await auth_service.logout(db, data.refresh_token)
