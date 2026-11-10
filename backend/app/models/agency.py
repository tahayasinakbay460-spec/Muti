"""
Ajans (yayıncı ajansı) tabloları.

AJANS NEDİR? Sesli sohbet uygulamalarında yayıncıların (hediye alan, odası kalabalık kişiler)
çoğu bir ajansa bağlıdır. Ajans yayıncılarını bulur, yönetir, onlara hedef koyar; uygulama da
ajansa, yayıncılarının kazancından komisyon öder. Ajansları uygulama yöneticisi kurar (iş ortağı
olduğu için herkes açamaz); ajans sahibi yayıncıları davet eder.

PARA AKIŞI: Ajans yayıncısı hediyeden bağımsız yayıncıdan yüksek pay alır; ajansın komisyonu ayrıca
BİZİM payımızdan hesaplanır (bkz. services/revenue_service.py). Her hediyede ajansın payı
`agency_earnings` tablosuna yazılır, ay sonunda panelden toplu ödenir (AgencySettlement).
DEMO KISAYOLU: Ödeme elmas olarak yapılıyor; gerçek para (fatura, banka) elmas çekimiyle gelecek.
"""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BigIntPk, utcnow


class Agency(Base):
    __tablename__ = "agencies"
    __table_args__ = (CheckConstraint("commission_percent BETWEEN 0 AND 50", name="agency_commission_range"),)

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)   # bir kişi tek ajansın sahibi
    # Yayıncılarına gelen hediyelerin (ve aramaların) coin değerinin yüzde kaçı ajansa komisyon olur.
    # Üst sınır .env AGENCY_COMMISSION_MAX_PERCENT; komisyon yayıncının payından kesilmez.
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


class AgencyEarning(Base):
    """
    Ajansın tek bir hediyeden (ya da arama dakikasından) hak ettiği komisyon. Hediye anında, hediyeyle
    AYNI transaction'da yazılır; ay sonu ödemesi bu satırların toplamıdır.

    Neden her hediyede ayrı satır? Hediye anındaki oran ve üyelik kayda geçer: ajans oranı ay ortasında
    değişse ya da yayıncı ajanstan ayrılsa bile geçmiş hesap değişmez. Yayıncı ajansa katılmadan önce
    kazandığından ajansa pay yazılmaz (satır o an yoktur). Bu satırlar güncellenmez, silinmez.
    Bakiye değiştirmez: ödeme ay sonunda `agency_commission` hareketiyle yapılır.
    """
    __tablename__ = "agency_earnings"
    __table_args__ = (Index("ix_agency_earnings_agency_id_created_at", "agency_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    agency_id: Mapped[int] = mapped_column(ForeignKey("agencies.id", ondelete="CASCADE"))
    host_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(16))            # gift | call
    coins: Mapped[int] = mapped_column(BigInteger)             # hediyenin coin değeri
    host_diamonds: Mapped[int] = mapped_column(BigInteger)     # yayıncının aldığı elmas
    commission_percent: Mapped[int] = mapped_column(Integer)   # o anki ajans oranı
    commission_diamonds: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
