"""
Kimlik işlemleri: kayıt, giriş, misafir girişi, token yenileme, çıkış,
parola değiştirme, hesap silme.
"""
import logging
import secrets
from datetime import timedelta

import bcrypt
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import utcnow
from app.core.errors import AppError, ConflictError, UnauthorizedError
from app.core.logs import audit
from app.core.security import (
    create_access_token, generate_refresh_token, hash_password, hash_refresh_token, verify_password,
)
from app.core.timefmt import as_utc
from app.models import Follow, RefreshToken, Room, User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RegisterRequest, TokenResponse
from app.services import user_service, wallet_service

# Olmayan bir kullanıcı adıyla giriş denendiğinde de bir parola kontrolü yapabilmek
# için hazır tutulan sahte hash (neden gerektiği `login` içinde anlatılıyor).
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(secrets.token_bytes(16), bcrypt.gensalt()).decode()


async def _issue_tokens(db: AsyncSession, user: User) -> TokenResponse:
    """Kullanıcıya yeni bir access + refresh token çifti verir ve commit eder."""
    refresh_token = generate_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
    ))
    await db.commit()
    # Commit'ten sonra kullanıcıyı tazele: bakiye gibi alanlar az önce değişmiş olabilir.
    await db.refresh(user)
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=refresh_token,
        expires_in=settings.access_token_minutes * 60,
        user=await user_service.present_user(db, user, viewer_id=user.id),
    )


async def _create_user(db: AsyncSession, user: User) -> None:
    """Kullanıcıyı ekler ve hoş geldin bonusunu verir (commit'i çağıran yapar)."""
    db.add(user)
    try:
        await db.flush()   # id burada oluşur; kullanıcı adı/e-posta çakışırsa hata burada çıkar
    except IntegrityError:
        await db.rollback()
        raise ConflictError("Bu kullanıcı adı veya e-posta zaten kullanılıyor.", code="already_registered")

    if settings.signup_bonus_coins > 0:
        await wallet_service.change_balance(
            db, user_id=user.id, currency="coin", delta=settings.signup_bonus_coins,
            type="reward", label="Hoş geldin bonusu",
        )


async def register(db: AsyncSession, data: RegisterRequest) -> TokenResponse:
    username = data.username.lower()
    email = data.email.lower()

    # Kullanıcıya hangisinin dolu olduğunu söyleyebilmek için önce bakıyoruz.
    # (Asıl güvence veritabanındaki unique kuralıdır; bkz. _create_user.)
    existing = await db.scalar(select(User).where(or_(User.username == username, User.email == email)))
    if existing:
        if existing.username == username:
            raise ConflictError("Bu kullanıcı adı alınmış.", code="username_taken")
        raise ConflictError("Bu e-posta zaten kayıtlı.", code="email_taken")

    user = User(
        username=username,
        email=email,
        password_hash=await hash_password(data.password),
        display_name=data.username,   # ekranda yazıldığı haliyle (büyük/küçük harf korunur)
    )
    await _create_user(db, user)
    audit("user_registered", new_user_id=user.id, username=username)
    return await _issue_tokens(db, user)


async def login(db: AsyncSession, data: LoginRequest) -> TokenResponse:
    user = await db.scalar(select(User).where(User.username == data.username.lower()))

    # Kullanıcı yoksa bile sahte bir hash ile parola kontrolü yapıyoruz. Yapmasaydık
    # "kullanıcı yok" cevabı çok hızlı, "parola yanlış" cevabı yavaş dönerdi ve bir
    # saldırgan cevap süresinden hangi kullanıcı adlarının kayıtlı olduğunu anlardı.
    password_hash = user.password_hash if user and user.password_hash else _DUMMY_PASSWORD_HASH
    password_ok = await verify_password(data.password, password_hash)

    # Aynı sebeple hata mesajı da tek: hangisinin yanlış olduğunu söylemiyoruz.
    if user is None or not user.password_hash or not password_ok:
        # Kayıtta sebep yazılır (kullanıcıya söylenmez): aynı ada art arda gelen başarısız
        # denemeler parola tahmin saldırısının işaretidir. Denenen parola ASLA yazılmaz.
        audit("login_failed", log_level=logging.WARNING, username=data.username.lower(),
              reason="unknown_user" if user is None else "bad_password")
        raise UnauthorizedError("Kullanıcı adı veya şifre hatalı.", code="invalid_credentials")
    if not user.is_active:
        audit("login_failed", log_level=logging.WARNING, username=user.username, reason="account_disabled")
        raise UnauthorizedError("Bu hesap engellenmiş.", code="account_disabled")

    audit("login_succeeded", login_user_id=user.id)
    return await _issue_tokens(db, user)


async def login_as_guest(db: AsyncSession) -> TokenResponse:
    """Kayıt olmadan dolaşmak isteyenler için parolasız, geçici bir hesap açar."""
    suffix = secrets.token_hex(4)
    user = User(
        username=f"guest_{suffix}",
        display_name=f"Misafir {suffix[:4].upper()}",
        is_guest=True,
    )
    await _create_user(db, user)
    audit("guest_created", new_user_id=user.id)
    return await _issue_tokens(db, user)


async def refresh(db: AsyncSession, refresh_token: str) -> TokenResponse:
    """
    Refresh token ile yeni bir token çifti verir.

    "ROTATION" (döndürme): Her refresh token yalnızca BİR kez kullanılır. Kullanılınca
    iptal edilir ve yenisi verilir. Bu sayede token çalınırsa fark ederiz: iptal
    edilmiş bir token tekrar geliyorsa, ya saldırgan ya gerçek kullanıcı eski token'ı
    kullanıyordur. Hangisi olduğunu bilemeyiz, o yüzden o kullanıcının BÜTÜN
    oturumlarını kapatırız; gerçek kullanıcı yeniden giriş yapar, saldırgan dışarıda kalır.
    """
    invalid = UnauthorizedError("Oturum geçersiz, tekrar giriş yap.", code="invalid_refresh_token")

    stored = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
    )
    if stored is None:
        raise invalid

    if stored.revoked_at is not None:
        # Kullanılmış bir token tekrar geldi: çalınmış olabilir. Bütün oturumlar kapatılır.
        audit("refresh_token_reuse", log_level=logging.WARNING, affected_user_id=stored.user_id)
        await _revoke_all(db, stored.user_id)
        raise invalid

    if as_utc(stored.expires_at) <= utcnow():
        raise invalid

    # "Hâlâ iptal edilmemişse iptal et" işlemini tek komutla yapıyoruz. Aynı token'la
    # iki istek aynı anda gelirse yalnızca biri bir satır günceller; diğeri reddedilir.
    revoked = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == stored.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    if revoked.rowcount != 1:
        raise invalid

    user = await db.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise invalid
    return await _issue_tokens(db, user)


async def logout(db: AsyncSession, refresh_token: str) -> None:
    """Bu cihazın refresh token'ını iptal eder. Token zaten geçersizse sessizce geçer."""
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(refresh_token), RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    await db.commit()


async def _revoke_all(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    await db.commit()


# ── Hesap ayarları ────────────────────────────────────────────────────────────

async def change_password(db: AsyncSession, user: User, data: ChangePasswordRequest) -> TokenResponse:
    """
    Parolayı değiştirir. Diğer cihazlardaki bütün oturumlar kapatılır (parola çalındıysa
    saldırgan da dışarıda kalsın); bu cihaz için yeni bir token çifti döner.
    """
    if not user.password_hash:
        raise AppError("Misafir hesabın parolası yok. Önce kayıt ol.", code="guest_account")
    if not await verify_password(data.current_password, user.password_hash):
        raise UnauthorizedError("Mevcut şifre hatalı.", code="invalid_credentials")
    user.password_hash = await hash_password(data.new_password)
    await _revoke_all(db, user.id)   # commit eder
    audit("password_changed")
    return await _issue_tokens(db, user)


async def delete_account(db: AsyncSession, user: User, password: str | None) -> None:
    """
    Hesabı siler. Uygulama mağazaları (App Store, Google Play) uygulama içinden hesap
    silmeyi zorunlu tutar.

    Kişisel bilgiler (e-posta, parola, ad, fotoğraf, biyografi) silinir ve hesap kapanır.
    Para hareketleri defteri (transactions) yasal kayıt olduğu için silinmez; bu satırlar
    artık kimliği belirsiz "Silinmiş kullanıcı"ya bağlıdır.
    """
    if user.password_hash and not (password and await verify_password(password, user.password_hash)):
        raise UnauthorizedError("Şifre hatalı.", code="invalid_credentials")

    # Takipleri iki yönde de kaldır (karşı tarafların sayaçları düzelsin).
    follows = (await db.execute(
        select(Follow.follower_id, Follow.followee_id)
        .where(or_(Follow.follower_id == user.id, Follow.followee_id == user.id))
    )).all()
    for follower_id, followee_id in follows:
        await user_service.set_follow(db, follower_id, followee_id, follow=False)

    # Kişinin açtığı odalar kapanır.
    await db.execute(update(Room).where(Room.host_id == user.id).values(is_active=False, is_live=False))

    user.username = f"deleted_{user.id}"
    user.email = None
    user.password_hash = None
    user.display_name = "Silinmiş kullanıcı"
    user.avatar_url = None
    user.cover_url = None
    user.bio = ""
    user.age = None
    user.city = None
    user.is_active = False
    await _revoke_all(db, user.id)   # commit eder
    audit("account_deleted", deleted_user_id=user.id)
