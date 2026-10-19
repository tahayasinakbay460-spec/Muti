"""
Sosyal güvenlik ve bildirim tabloları: user_blocks, reports, notifications.
"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BigIntPk, utcnow


class UserBlock(Base):
    """
    Kim kimi engelledi. Bir satır = "blocker, blocked'u engelledi".
    Engelleme iki yönlü etki eder: iki taraf birbirine mesaj atamaz, birbirini takip edemez.
    """
    __tablename__ = "user_blocks"

    blocker_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    blocked_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Şikâyet edilebilecek şeyler ve şikâyet sebepleri (arayüzdeki seçeneklerle aynı).
REPORT_TARGET_TYPES = ("user", "room")
REPORT_REASONS = ("spam", "harassment", "inappropriate", "underage", "fraud", "other")


class Report(Base):
    """
    Kullanıcı şikâyetleri. Uygulama mağazaları (App Store, Google Play) sohbet
    uygulamalarında şikâyet ve engelleme özelliğini zorunlu tutar.
    Satırları uygulama yöneticileri yönetim panelinden inceler (bkz. services/admin_service.py).
    """
    __tablename__ = "reports"
    __table_args__ = (
        # Yönetim paneli "açık şikâyetler, en yeni en üstte" diye listeleyecek.
        Index("ix_reports_status_id", "status", "id"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(16))      # user | room
    target_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(32))
    details: Mapped[str] = mapped_column(String(500), default="")
    # open → incelenmeyi bekliyor; resolved / dismissed → yönetici karar verdi.
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # ── Karar (yönetici inceledikten sonra dolar) ─────────────────────────────
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # dismiss (asılsız) | ban_user (kullanıcı banlandı) | close_room (oda kapatıldı)
    action: Mapped[str | None] = mapped_column(String(16))
    resolution_note: Mapped[str] = mapped_column(String(300), default="")


class Notification(Base):
    """
    Bildirim merkezi. Bir satır = bir kişiye giden bir bildirim.
    Türler: follow (seni takip etti), gift_received (hediye aldın), level_up (seviye atladın),
    room_role (bir odada yönetici/VIP yapıldın).
    """
    __tablename__ = "notifications"
    __table_args__ = (
        # "Bu kişinin bildirimleri, en yeni en üstte" sorgusu.
        Index("ix_notifications_user_id_id", "user_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(32))
    # Bildirimi tetikleyen kişi (takip eden, hediye gönderen). Sistem bildiriminde boş.
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # Ekranda gösterilecek metin; bildirimi üretirken bir kez yazılır.
    text: Mapped[str] = mapped_column(String(200))
    # Bildirime dokununca nereye gidileceği gibi ek bilgiler ({"room_id": 5}).
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
