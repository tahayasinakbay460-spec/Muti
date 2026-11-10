"""
Özel mesaj tabloları: conversations (iki kişi arasındaki sohbet), messages (tek tek mesajlar).
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BigIntPk, utcnow


class Conversation(Base):
    """
    İki kullanıcı arasındaki sohbet.

    İki kişiyi hep aynı sırada saklarız: küçük id `user_low_id`, büyük id
    `user_high_id`. Böylece (5, 9) ile (9, 5) aynı satır olur ve iki kişi arasında
    yanlışlıkla iki ayrı sohbet açılamaz.

    Mesaj listesi ekranı çok sık açılır. Her açılışta "son mesaj neydi, kaç okunmamış
    var" diye messages tablosunu taramamak için bu bilgileri burada hazır tutuyoruz.
    """
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("user_low_id", "user_high_id"),)

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    user_low_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user_high_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Her iki taraf için okunmamış mesaj sayısı.
    unread_low: Mapped[int] = mapped_column(Integer, default=0)
    unread_high: Mapped[int] = mapped_column(Integer, default=0)

    # Son mesajın kopyası (liste ekranı için).
    last_message_text: Mapped[str | None] = mapped_column(String(1000))
    last_message_sender_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Mesaj türleri:
#   text  → düz yazı
#   voice → sesli mesaj (ses dosyası diskte, bkz. services/media_storage.py)
#   gift  → sohbette gönderilen hediye (para hareketi transactions defterinde)
#   call  → biten / cevapsız aramanın sohbetteki izi ("📞 Sesli arama · 3 dk")
#   image → fotoğraf (dosya diskte; yalnızca sohbetin iki üyesine verilir)
MESSAGE_KINDS = ("text", "voice", "gift", "call", "image")


class Message(Base):
    __tablename__ = "messages"
    # "Bu sohbetin son 50 mesajı" sorgusunu hızlandırır.
    __table_args__ = (Index("ix_messages_conversation_id_id", "conversation_id", "id"),)

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # Yazılı mesajda metnin kendisi; diğer türlerde boş kalır (önizleme yazısı sohbet satırında).
    text: Mapped[str] = mapped_column(String(1000))
    kind: Mapped[str] = mapped_column(String(8), default="text", server_default="text")
    # voice: depodaki dosyanın adı. Dışarıya hiçbir zaman doğrudan açılmaz; yalnızca sohbetin
    # iki üyesine, yetki kontrolünden sonra verilir.
    media_path: Mapped[str | None] = mapped_column(String(200))
    # voice: kaydın süresi; call: konuşulan dakika.
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    gift_id: Mapped[int | None] = mapped_column(ForeignKey("gifts.id", ondelete="SET NULL"))
    quantity: Mapped[int | None] = mapped_column(Integer)
    call_id: Mapped[int | None] = mapped_column(ForeignKey("calls.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RoomMessage(Base):
    """
    Oda sohbetindeki mesajların kalıcı kaydı. Odadaki canlı akış (son 50 mesaj) bellekte
    durur (realtime/state.py); bu tablo yönetim panelinin geçmişe bakabilmesi içindir.
    Odada silinen mesaj burada silinmez, `deleted_at` ile işaretlenir (şikâyet incelemesinde kanıt).

    DEMO KISAYOLU: Kayıtlar süresiz tutuluyor ve yönetici hepsini okuyabiliyor. Canlıda
    saklama süresi (ör. 30 gün sonra silme) ve gizlilik metninde açık bilgilendirme gerekir (KVKK).
    """
    __tablename__ = "room_messages"
    __table_args__ = (Index("ix_room_messages_room_id_id", "room_id", "id"),)

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    # Odadaki istemcilerin mesajı tanıdığı rastgele kimlik (silme işlemi bununla gelir).
    public_id: Mapped[str] = mapped_column(String(32), index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
