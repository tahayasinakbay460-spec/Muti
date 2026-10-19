"""
Bağlılık (kullanıcıyı geri getiren) tabloları: günlük giriş ödülü, görev sayaçları,
alınmış görev ödülleri, süreli etkinlikler.
"""
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BigIntPk, utcnow


class DailyCheckIn(Base):
    """Günlük giriş ödülü alındı kaydı. Bir kullanıcı bir günde yalnızca bir satır yazabilir."""
    __tablename__ = "daily_checkins"
    __table_args__ = (UniqueConstraint("user_id", "day"),)

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)            # kullanıcının yerel takvimine göre
    # Art arda kaçıncı gün (1-7); 7'den sonra 1'e döner, bir gün atlanırsa 1'den başlar.
    streak_day: Mapped[int] = mapped_column(Integer)
    coins: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TaskCounter(Base):
    """
    Görev sayacı: "bu kullanıcı bugün şu işi kaç kez yaptı" (ör. gift_sent = 2).
    Görevler (services/engagement_service.py TASKS) bu sayaçlara bakarak ilerler.
    DEMO KISAYOLU: Her sohbet mesajında bir veritabanı yazımı olur. Canlıda sayaçlar Redis'te
    (INCR, gün sonunda kendiliğinden silinen anahtar) tutulmalı.
    """
    __tablename__ = "task_counters"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    metric: Mapped[str] = mapped_column(String(32), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class TaskClaim(Base):
    """Alınmış görev ödülü. Birincil anahtar sayesinde bir görevin ödülü günde bir kez alınır."""
    __tablename__ = "task_claims"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    coins: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Etkinlikte sıralamanın neye göre yapıldığı.
EVENT_METRICS = ("gifts_sent", "gifts_received")


class Event(Base):
    """
    Süreli etkinlik (kampanya): ör. "Hafta Sonu Hediye Yarışı". Başlangıç ile bitiş arasında
    en çok hediye gönderen (ya da alan) ilk sıralar ödül kazanır. Ödüller etkinlik bitince bir
    kez dağıtılır (bkz. services/event_service.py finalize).
    """
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    title: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(500), default="")
    emoji: Mapped[str] = mapped_column(String(16), default="🎉")
    metric: Mapped[str] = mapped_column(String(32))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Sıraya göre coin ödülü: [1., 2., 3. ...]
    rewards: Mapped[list] = mapped_column(JSON, default=list)
    # Ödüller dağıtıldıysa dağıtım anı. Boşsa henüz dağıtılmadı.
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
