"""
Yönetim paneli personelinin işlem kaydı: staff_actions.

Ekranda "kim, ne zaman, kime, ne yaptı" sorusunun cevabı. Dosyaya yazılan audit kaydından
farkı: panelden aranabilir ve listelenebilir. Satırlar değiştirilmez ve silinmez.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BigIntPk, utcnow


class StaffAction(Base):
    __tablename__ = "staff_actions"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    # İşlemi yapan personel. Hesabı silinse bile kayıt kalır (SET NULL).
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    # Ör. "user_banned", "balance_adjusted", "staff_role_changed"
    action: Mapped[str] = mapped_column(String(40), index=True)
    # Neye yapıldı: "user" | "room" | "report" | "gift" | "package" | "agency" | "all"
    target_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    # İnsan için kısa açıklama (gerekçe, tutar, yeni rol...). Parola/token asla yazılmaz.
    detail: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
