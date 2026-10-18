"""
Güvenlik yardımcıları: parola hash'leme ve token üretme/doğrulama.

İki çeşit token var:

  ACCESS TOKEN (JWT, 15 dk)
    Her istekte `Authorization: Bearer <token>` başlığıyla gelir. İçinde kullanıcının
    id'si yazar ve bizim gizli anahtarımızla imzalıdır. Doğrulamak için veritabanına
    gitmeye gerek yoktur (stateless) → çok hızlıdır, sunucu sayısı artınca sorun çıkmaz.

  REFRESH TOKEN (rastgele uzun bir yazı, 30 gün)
    Access token'ın süresi dolunca yenisini almak için kullanılır. Veritabanında
    saklanır ki "çıkış yap" dendiğinde iptal edebilelim. Veritabanına token'ın
    kendisini değil hash'ini yazarız: veritabanı sızsa bile token'lar kullanılamaz.
"""
import asyncio
import hashlib
import secrets
from datetime import timedelta

import bcrypt
import jwt

from app.core.config import settings
from app.core.database import utcnow
from app.core.errors import UnauthorizedError

# ── Parola ────────────────────────────────────────────────────────────────────
# bcrypt bilerek yavaştır (~0.2 sn) ki şifre deneme saldırıları pahalı olsun.
# Bu yavaş işi ana akışta yaparsak o sırada bütün sunucu bekler; bu yüzden
# `asyncio.to_thread` ile ayrı bir iş parçacığına (thread) veriyoruz.


async def hash_password(password: str) -> str:
    hashed = await asyncio.to_thread(bcrypt.hashpw, password.encode(), bcrypt.gensalt())
    return hashed.decode()


async def verify_password(password: str, password_hash: str) -> bool:
    return await asyncio.to_thread(bcrypt.checkpw, password.encode(), password_hash.encode())


# ── Access token ──────────────────────────────────────────────────────────────

def create_access_token(user_id: int) -> str:
    now = utcnow()
    payload = {
        "sub": str(user_id),   # subject: token kimin?
        "type": "access",      # refresh token yerine kullanılmasın diye tip yazıyoruz
        "iat": now,            # issued at: ne zaman üretildi
        "exp": now + timedelta(minutes=settings.access_token_minutes),  # ne zaman biter
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int:
    """Token geçerliyse içindeki kullanıcı id'sini döner, değilse 401 hatası fırlatır."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        # İstemci bu kodu görünce /auth/refresh çağırıp yeni token almalı.
        raise UnauthorizedError("Oturum süresi doldu.", code="token_expired")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Geçersiz oturum.", code="invalid_token")

    if payload.get("type") != "access" or not str(payload.get("sub", "")).isdigit():
        raise UnauthorizedError("Geçersiz oturum.", code="invalid_token")
    return int(payload["sub"])


# ── Refresh token ─────────────────────────────────────────────────────────────

def generate_refresh_token() -> str:
    """Tahmin edilemez, rastgele bir yazı üretir (kullanıcıya bu gönderilir)."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Veritabanına yazılacak hali. Token zaten rastgele olduğu için hızlı SHA-256 yeterli."""
    return hashlib.sha256(token.encode()).hexdigest()
