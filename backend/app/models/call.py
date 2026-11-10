"""
Birebir sesli / görüntülü arama kaydı: calls.

Arama ücretlidir: ARAYAN dakika başı coin öder, ARANAN payını elmas olarak kazanır
(fiyatlar .env: CALL_VOICE_PRICE_PER_MINUTE, CALL_VIDEO_PRICE_PER_MINUTE). Para hareketlerinin
kendisi her zaman `transactions` defterindedir; buradaki `billed_minutes` ve `coins_spent`
yalnızca ekranda göstermek için hazır tutulan özetlerdir.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BigIntPk, utcnow

CALL_KINDS = ("voice", "video")
# ringing  → aranan kişinin ekranında çalıyor
# active   → açıldı, dakika sayılıyor
# ended    → konuşuldu ve kapandı
# missed   → çaldı, kimse açmadı / arayan vazgeçti
# declined → aranan reddetti
CALL_STATUSES = ("ringing", "active", "ended", "missed", "declined")


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    caller_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    callee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(12), default="ringing")
    # Aramanın başladığı andaki dakika fiyatı: fiyat sonradan değişse de bu arama eski fiyattan sürer.
    price_per_minute: Mapped[int] = mapped_column(Integer)
    billed_minutes: Mapped[int] = mapped_column(Integer, default=0)
    coins_spent: Mapped[int] = mapped_column(Integer, default=0)
    # Neden bitti: hangup | declined | missed | insufficient_balance | disconnected
    end_reason: Mapped[str | None] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
