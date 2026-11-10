"""
Yayıncı başvuruları: host_applications.

YAYINCI NEDİR? Sesli oda açmak ve hediye almak herkese açıktır. "Yayıncı" ise bizim onayladığımız
kişidir: profilinde yayıncı rozeti olur, ajansa katılabilir; ileride kameralı canlı yayın ve
elmasını paraya çevirme yalnızca yayıncılara açılacak.

Kim yayıncı olur? Başvuru yapar (doğum tarihi, 18 yaş üstü onayı, kısa tanıtım), yönetim panelinde
moderatör inceler, onaylar ya da gerekçesiyle reddeder. Onaylanınca kullanıcıda `is_host` açılır.

DEMO KISAYOLU: Yaş yalnızca beyana dayanıyor. Canlıda (özellikle kameralı yayından ve para
çekiminden önce) kimlik doğrulama hizmeti gerekir.
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BigIntPk, utcnow

# pending → incelemede · approved → onaylandı · rejected → reddedildi
HOST_APPLICATION_STATUSES = ("pending", "approved", "rejected")


class HostApplication(Base):
    __tablename__ = "host_applications"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    birth_date: Mapped[date] = mapped_column(Date)
    intro: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    review_note: Mapped[str | None] = mapped_column(String(300))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
