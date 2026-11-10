"""
Ajans (yayıncı ajansı) tabloları.

AJANS NEDİR? Sesli sohbet uygulamalarında yayıncıların (hediye alan, odası kalabalık kişiler)
çoğu bir ajansa bağlıdır. Ajans yayıncılarını bulur, yönetir, onlara hedef koyar; uygulama da
ajansa, yayıncılarının kazancından komisyon öder. Ajansları uygulama yöneticisi kurar (iş ortağı
olduğu için herkes açamaz); ajans sahibi yayıncıları davet eder.

DEMO KISAYOLU: Komisyon yalnızca hesaplanıp gösteriliyor. Gerçek ödeme (ay sonu hesaplaşma,
fatura, banka transferi) elmasların paraya çevrilmesiyle birlikte yazılacak.
"""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BigIntPk, utcnow


class Agency(Base):
    __tablename__ = "agencies"
    __table_args__ = (CheckConstraint("commission_percent BETWEEN 0 AND 50", name="agency_commission_range"),)

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)   # bir kişi tek ajansın sahibi
    # Yayıncıların hediyelerden kazandığı elmasın yüzde kaçı ajansa komisyon olarak hesaplanır.
    commission_percent: Mapped[int] = mapped_column(Integer, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgencyMember(Base):
    """
    Yayıncının ajans üyeliği ya da bekleyen daveti. Birincil anahtar user_id: bir yayıncı aynı
    anda tek ajansa bağlı olabilir (ya da tek bekleyen davet).
    status: invited (davet bekliyor) | active (üye)
    """
    __tablename__ = "agency_members"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    agency_id: Mapped[int] = mapped_column(ForeignKey("agencies.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="invited")
    # Ajansın bu yayıncıya koyduğu aylık elmas hedefi (0 = hedef yok).
    monthly_target: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgencySettlement(Base):
    """
    Ajansın bir ayki komisyon hesaplaşması. Komisyon BİZİM payımızdan ödenir: yayıncının kazancı
    düşmez; ajans sahibine, yayıncılarının o ay hediyelerden kazandığı elmasın yüzde komisyonu kadar
    elmas eklenir. Her ajans her ay için tek satır (unique): aynı ay iki kez ödenemez.
    """
    __tablename__ = "agency_settlements"
    __table_args__ = (UniqueConstraint("agency_id", "month"),)

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    agency_id: Mapped[int] = mapped_column(ForeignKey("agencies.id", ondelete="CASCADE"), index=True)
    month: Mapped[str] = mapped_column(String(7))           # "2026-10"
    host_diamonds: Mapped[int] = mapped_column(BigInteger)  # yayıncıların o ayki toplam elması
    commission_percent: Mapped[int] = mapped_column(Integer)
    commission_diamonds: Mapped[int] = mapped_column(BigInteger)
    member_count: Mapped[int] = mapped_column(Integer)
    settled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
