"""
Kullanıcıyla ilgili tablolar: users, follows, refresh_tokens.
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BigIntPk, utcnow


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Son savunma hattı: kodda bir hata olsa bile veritabanı eksi bakiyeye izin vermez.
        CheckConstraint("coin_balance >= 0", name="coin_balance_non_negative"),
        CheckConstraint("diamond_balance >= 0", name="diamond_balance_non_negative"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)

    # ── Giriş bilgileri ───────────────────────────────────────────────────────
    # username her zaman küçük harfle saklanır ("Ahmet" ile "ahmet" aynı kişi olsun).
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    # Misafir kullanıcıların e-postası ve parolası yoktur, o yüzden boş olabilir.
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    # Parolanın kendisi ASLA saklanmaz, yalnızca bcrypt hash'i.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    # false yapılırsa kullanıcı engellenmiş (banlı) demektir.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # ── Profil ────────────────────────────────────────────────────────────────
    display_name: Mapped[str] = mapped_column(String(40))
    age: Mapped[int | None] = mapped_column(Integer)
    city: Mapped[str | None] = mapped_column(String(60))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    cover_url: Mapped[str | None] = mapped_column(String(500))
    bio: Mapped[str] = mapped_column(String(300), default="")
    vip_level: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Cüzdan ────────────────────────────────────────────────────────────────
    # coin: gerçek parayla alınır, hediye göndermek için harcanır.
    # diamond: hediye alan kişinin kazancı.
    # Tamsayıdır (float yok): kuruş hatası olmaz. Bu iki alanı YALNIZCA
    # services/wallet_service.py değiştirir.
    coin_balance: Mapped[int] = mapped_column(BigInteger, default=0)
    diamond_balance: Mapped[int] = mapped_column(BigInteger, default=0)

    # ── Sayaçlar ──────────────────────────────────────────────────────────────
    # Bunlar "hazır hesaplanmış" sayılardır. Her profil açılışında follows tablosunu
    # saymak pahalı olur; onun yerine takip edildikçe bu sayıları +1/-1 güncelliyoruz.
    followers_count: Mapped[int] = mapped_column(Integer, default=0)
    following_count: Mapped[int] = mapped_column(Integer, default=0)
    friends_count: Mapped[int] = mapped_column(Integer, default=0)   # karşılıklı takip
    visitors_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Follow(Base):
    """Kim kimi takip ediyor. Bir satır = "follower, followee'yi takip ediyor"."""
    __tablename__ = "follows"

    # İkisi birlikte birincil anahtar: aynı kişi aynı kişiyi iki kez takip edemez.
    follower_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    followee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RefreshToken(Base):
    """Verilmiş refresh token'lar. Her cihaz/giriş için bir satır."""
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Token'ın SHA-256 hash'i (kendisi değil).
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Dolu ise token iptal edilmiştir (çıkış yapıldı ya da yenisiyle değiştirildi).
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
