"""
Mağaza tabloları: store_items (satılan kozmetikler), user_items (kimin neye sahip olduğu).

Kozmetik = yalnızca görünüşü değiştiren eşya: avatar çerçevesi, odaya giriş efekti,
sohbet balonu. Oyunda avantaj sağlamaz; kullanıcı kendini göstermek için alır.
Satışlar süreli yapılır (7 / 30 gün): süre dolunca eşya görünmez olur ama satır silinmez,
tekrar alınırsa aynı satırın süresi uzatılır.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BigIntPk, utcnow

# Eşya türleri. Her türden aynı anda yalnızca BİR eşya takılı (kullanımda) olabilir.
STORE_ITEM_KINDS = ("frame", "entry_effect", "chat_bubble")
# Satış süreleri (gün). Fiyat her süre için ayrı tutulur.
STORE_DURATIONS = (7, 30)


class StoreItem(Base):
    __tablename__ = "store_items"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(40))
    # Frontend'in bu eşyayı nasıl çizeceği: CSS sınıfı adı (ör. "frame-gold", "entry-rocket").
    style: Mapped[str] = mapped_column(String(40))
    emoji: Mapped[str] = mapped_column(String(16), default="")
    price_7d: Mapped[int] = mapped_column(Integer)
    price_30d: Mapped[int] = mapped_column(Integer)
    # 0 değilse yalnızca en az bu VIP seviyesindekiler satın alabilir (VIP'e özel eşya).
    vip_level_required: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UserItem(Base):
    """Bir kullanıcının sahip olduğu eşya. Bir kullanıcı bir eşyaya tek satırla sahip olur."""
    __tablename__ = "user_items"
    __table_args__ = (
        UniqueConstraint("user_id", "item_id"),
        # "Bu kişilerin takılı eşyaları" sorgusu her kullanıcı listesinde çalışır; hızlı olmalı.
        Index("ix_user_items_user_id_equipped", "user_id", "is_equipped"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    item_id: Mapped[int] = mapped_column(ForeignKey("store_items.id"))
    # Bu andan sonra eşya geçersiz. Süre dolan eşya takılı kalsa bile gösterilmez.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_equipped: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
