"""
Giriş / kayıt JSON şemaları.
"""
from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserOut


class RegisterRequest(BaseModel):
    # Yalnızca harf, rakam, alt çizgi ve nokta; 3-20 karakter.
    username: str = Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9_.]+$")
    email: EmailStr
    # bcrypt en fazla 72 baytı dikkate alır; üst sınır bu yüzden var.
    password: str = Field(min_length=6, max_length=64)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=64)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    """Giriş, kayıt ve token yenileme sonrası dönen cevap."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int      # access token kaç saniye sonra geçersiz olur
    user: UserOut
