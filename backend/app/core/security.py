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

  PANEL TOKEN'I (JWT, 15 dk hareketsizlikte biter)
    Yalnızca yönetim panelinde, access token'ın YANINDA `X-Staff-Token` başlığıyla gelir.
    Panele girerken şifre yeniden sorulur ve bu token verilir. Bkz. aşağıda "Panel oturumu".
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


# ── Panel oturumu ─────────────────────────────────────────────────────────────
# Uygulamadaki oturum 30 gün açık kalır (refresh token). Panelde bu tehlikeli: masada açık
# kalan bir bilgisayardan biri kullanıcıları banlayabilir, bakiye değiştirebilir. Sektörde
# yaygın çözüm ayrı ve kısa bir "yönetici oturumu":
#
#   - Panele girerken şifre yeniden sorulur → panel token'ı verilir.
#   - Token 15 dk geçerlidir; ama her başarılı panel isteğinde süresi yeniden 15 dk'ya
#     uzatılır (sunucu cevapta yenisini gönderir). Yani çalışırken hiç şifre sorulmaz,
#     15 dk dokunulmazsa panel kilitlenir ("kayan pencere", sliding window).
#   - Token'da şifrenin girildiği an (`auth_time`) yazar ve uzatmalarda değişmez. Kritik
#     işlemler bu anın 5 dk'dan eski olmamasını ister; eskiyse şifre bir kez daha sorulur
#     (GitHub'ın "sudo mode"u gibi). Başkası açık paneli bulsa bile ban/bakiye yapamaz.
#   - `auth_time`'dan 12 saat sonra uzatma durur: en geç vardiya sonunda şifre sorulur.
#
# Token'da rol YAZMAZ: yetki her istekte veritabanındaki güncel rolden hesaplanır.

def create_staff_token(user_id: int, auth_time: int) -> tuple[str, int]:
    """Panel token'ı üretir. (token, kaç saniye geçerli) döner."""
    now = utcnow()
    hard_limit = auth_time + settings.staff_session_max_hours * 3600
    expires_at = min(int(now.timestamp()) + settings.staff_idle_minutes * 60, hard_limit)
    payload = {"sub": str(user_id), "type": "staff", "auth_time": auth_time, "iat": now, "exp": expires_at}
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, max(0, expires_at - int(now.timestamp()))


def decode_staff_token(token: str, user_id: int) -> int:
    """
    Panel token'ı geçerliyse şifrenin girildiği anı (`auth_time`, saniye) döner.
    Token başka bir kullanıcıya aitse de reddedilir: çalınmış bir panel token'ı tek başına işe
    yaramaz, aynı kişinin access token'ı da gerekir.
    """
    expired = UnauthorizedError("Panel oturumu kapandı, şifreni yeniden gir.", code="staff_session_required")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError:   # süresi dolmuş da buraya düşer
        raise expired
    if payload.get("type") != "staff" or payload.get("sub") != str(user_id) or not isinstance(payload.get("auth_time"), int):
        raise expired
    return payload["auth_time"]
