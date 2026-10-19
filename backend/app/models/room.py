"""
Oda tabloları: rooms, room_follows, room_members.

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
    # true: herkes boş koltuğa kendisi oturabilir. false: yalnızca oda sahibi, yönetici ve
    # oda VIP'leri kendisi oturur; diğerleri ancak bir yöneticinin davetiyle oturabilir.
    free_seating: Mapped[bool] = mapped_column(Boolean, default=True)
    # "CANLI" rozeti.
    is_live: Mapped[bool] = mapped_column(Boolean, default=True)
    # false: oda kapatılmış, listelerde görünmez (satırı silmiyoruz, geçmiş kalsın).
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RoomFollow(Base):
    """
    Kim hangi odayı takip ediyor. Bir satır = "user, room'u takip ediyor".
    Ana sayfadaki "Takip" sekmesi bu tablodan dolar.
    """
    __tablename__ = "room_follows"

    # İkisi birlikte birincil anahtar: aynı kişi aynı odayı iki kez takip edemez.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Odaya özel roller. Oda sahibi (host) burada değildir, o `rooms.host_id` ile bilinir.
# Rolü olmayan herkes "listener" (dinleyici) sayılır ve tabloda satırı yoktur.
ROOM_MEMBER_ROLES = ("admin", "vip")


class RoomMember(Base):
    """
    Odada özel rolü olan kişiler. Bir satır = "user, bu odada şu role sahip".

      - admin → yönetici: koltuk kilitler, susturur, koltuktan indirir, odadan atar.
                Yalnızca oda sahibi atar ve geri alır.
      - vip   → odanın ayrıcalıklı üyesi: rozeti görünür, koltuklar davetle açıldığında
                bile kendisi oturabilir. Yönetim yetkisi yoktur.
                Oda sahibi ya da yöneticiler verir.
    """
    __tablename__ = "room_members"

    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
