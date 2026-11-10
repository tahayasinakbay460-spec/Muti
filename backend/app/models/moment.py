"""
Anılar (moments) ve profil ziyaretleri: moments, moment_likes, moment_comments, profile_visits.

ANI NEDİR? Instagram gönderisi gibi: kullanıcı kısa bir yazı ve isteğe bağlı bir görsel paylaşır,
takipçileri "Anılar" sekmesinde görür, beğenir ve yorum yazar.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BigIntPk, utcnow


class Moment(Base):
    __tablename__ = "moments"
    __table_args__ = (
        # "Bu kişinin anıları, en yeni en üstte" sorgusu (profildeki Paylaşımlar sekmesi).
        Index("ix_moments_user_id_id", "user_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(String(500), default="")
    # Kişinin yüklediği fotoğrafın adresi (bkz. services/media_service.py).
    image_url: Mapped[str | None] = mapped_column(String(500))
    # Hazır hesaplanmış beğeni sayısı: her listede moment_likes tablosunu saymamak için.
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    # Aynı mantıkla hazır yorum sayısı: akışta "12 yorumun hepsini gör" yazmak için.
    comment_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MomentLike(Base):
    """Kim hangi anıyı beğendi. İkisi birlikte birincil anahtar: aynı kişi iki kez beğenemez."""
    __tablename__ = "moment_likes"

    moment_id: Mapped[int] = mapped_column(ForeignKey("moments.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MomentComment(Base):
    """Bir anının altına yazılan yorum. Yorumu yazan ya da anının sahibi silebilir."""
    __tablename__ = "moment_comments"
    __table_args__ = (
        # "Bu anının yorumları, eskiden yeniye" sorgusu.
        Index("ix_moment_comments_moment_id_id", "moment_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    moment_id: Mapped[int] = mapped_column(ForeignKey("moments.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProfileVisit(Base):
    """
    Kim kimin profiline baktı. Kişi başına tek satır: aynı kişi tekrar bakınca yalnızca
    `visited_at` güncellenir (ziyaretçi listesi "en son bakan en üstte" sıralanır).
    """
    __tablename__ = "profile_visits"
    __table_args__ = (Index("ix_profile_visits_visited_id_visited_at", "visited_id", "visited_at"),)

    visitor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    visited_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
