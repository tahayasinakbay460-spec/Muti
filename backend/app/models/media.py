"""
Yüklenen fotoğrafların kaydı: media_uploads.

NEDEN AYRI BİR TABLO?
Dosyanın kendisi diskte durur (bkz. services/media_storage.py). Bu tablo "bu dosyayı kim, ne için
yükledi" bilgisini tutar. Profil, anı ya da oda kapağı yalnızca kişinin KENDİ yüklediği ve o iş için
yüklediği bir görseli kullanabilir; başkasının dosya adını bulup kendi profiline koyamaz.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BigIntPk, utcnow

# avatar / cover → profil · moment → anı · room_cover → oda kapağı · chat → özel mesaj (herkese açık değil)
MEDIA_KINDS = ("avatar", "cover", "moment", "room_cover", "chat")


class MediaUpload(Base):
    __tablename__ = "media_uploads"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    # Depodaki anahtar, ör. "images/3f9c...e1.jpg". Adı sunucu rastgele üretir.
    key: Mapped[str] = mapped_column(String(80), unique=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
