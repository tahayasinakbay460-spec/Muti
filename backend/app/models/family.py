"""
Aile (klan) ve CP (çift) tabloları.

AİLE: Kullanıcıların kurduğu topluluk. Bir kullanıcı aynı anda tek bir ailede olabilir.
Ailenin rozeti profilde ve sohbette görünür; üyelerin gönderdiği hediyeler aile sıralamasını
belirler; ailenin kendi sohbeti vardır.

CP (couple / çift): İki kullanıcının profilde birbirine bağlanması. Biri teklif eder, diğeri
kabul eder. Bir kullanıcının aynı anda tek CP'si olabilir.
"""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BigIntPk, utcnow

FAMILY_ROLES = ("owner", "admin", "member")


class Family(Base):
    __tablename__ = "families"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    name: Mapped[str] = mapped_column(String(24), unique=True)
    badge: Mapped[str] = mapped_column(String(16))           # rozet emojisi, ör. "🦁"
    slogan: Mapped[str] = mapped_column(String(120), default="")
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # Hazır hesaplanmış sayaç (her listede üyeleri saymamak için); üye girip çıktıkça +1/-1.
    member_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FamilyMember(Base):
    """Üyelik. Birincil anahtar user_id: bir kullanıcı en fazla bir ailede olabilir."""
    __tablename__ = "family_members"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FamilyMessage(Base):
    """Aile sohbetindeki mesaj."""
    __tablename__ = "family_messages"
    __table_args__ = (Index("ix_family_messages_family_id_id", "family_id", "id"),)

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Couple(Base):
    """
    CP teklifi ya da ilişkisi. İki kullanıcı arasında tek satır olur (küçük id önce yazılır).
    status: pending (teklif bekliyor) | active (kabul edildi). Ayrılınca satır silinir.
    Kimin kiminle CP olduğu ayrıca User.cp_partner_id'de tutulur (hızlı okuma ve "aynı anda
    tek CP" kuralının atomik kontrolü için).
    """
    __tablename__ = "couples"
    __table_args__ = (
        UniqueConstraint("user_low_id", "user_high_id"),
        CheckConstraint("user_low_id < user_high_id", name="couple_ordered_pair"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    user_low_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    user_high_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
