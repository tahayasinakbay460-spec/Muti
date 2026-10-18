"""
Oda tablosu.

DİKKAT: Burada yalnızca odanın KALICI bilgileri durur (adı, sahibi, kategorisi).
"Şu an hangi koltukta kim oturuyor, kaç kişi dinliyor" gibi saniyede defalarca
değişen CANLI bilgiler veritabanında değil, realtime/state.py içindeki hızlı
depoda (ileride Redis) tutulur.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BigIntPk, utcnow

# Geçerli oda kategorileri (frontend'deki ROOM_CATEGORIES ile aynı; "for_you" bir
# kategori değil, "hepsini göster" anlamına gelen filtredir).
ROOM_CATEGORIES = ("chat", "music", "game", "new_people")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    title: Mapped[str] = mapped_column(String(60))
    category: Mapped[str] = mapped_column(String(32), index=True)
    cover_url: Mapped[str | None] = mapped_column(String(500))
    announcement: Mapped[str] = mapped_column(String(300), default="")
    # Odanın sahibi (host).
    host_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Odada kaç koltuk (mikrofon yeri) var.
    seat_count: Mapped[int] = mapped_column(Integer, default=8)
    # "CANLI" rozeti.
    is_live: Mapped[bool] = mapped_column(Boolean, default=True)
    # false: oda kapatılmış, listelerde görünmez (satırı silmiyoruz, geçmiş kalsın).
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
