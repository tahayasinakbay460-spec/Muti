"""
Ekonomi tabloları: gifts (hediye kataloğu), coin_packages (satılan coin paketleri),
transactions (para hareketleri defteri).
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BigIntPk, utcnow


class Gift(Base):
    """Gönderilebilen hediyeler. Fiyat coin cinsindendir."""
    __tablename__ = "gifts"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    emoji: Mapped[str] = mapped_column(String(16))
    price: Mapped[int] = mapped_column(Integer)
    # Şanslı hediye: gönderen, sunucunun çektiği çarpanla coin geri kazanabilir
    # (bkz. gift_service.draw_lucky_win). Alıcının payı normal hediyeden düşüktür.
    is_lucky: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CoinPackage(Base):
    """Cüzdan ekranında satılan coin paketleri."""
    __tablename__ = "coin_packages"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    coins: Mapped[int] = mapped_column(Integer)
    bonus: Mapped[int] = mapped_column(Integer, default=0)
    # Ekranda gösterilen fiyat yazısı ("₺29,99"). Gerçek tahsilatı mağaza (App Store /
    # Google Play) yapar; biz yalnızca etiketi gösteririz.
    price_label: Mapped[str] = mapped_column(String(20))
    is_popular: Mapped[bool] = mapped_column(Boolean, default=False)
    is_best_value: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Hediye paketi (bundle) ────────────────────────────────────────────────
    # Doluysa bu bir "paket": coinin yanında mağaza eşyası da verir (ör. 7 günlük çerçeve).
    title: Mapped[str | None] = mapped_column(String(40))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("store_items.id"))
    item_days: Mapped[int] = mapped_column(Integer, default=0)
    # Kullanıcı başına yalnızca bir kez alınabilir (ör. "Başlangıç Paketi").
    is_one_time: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Transaction(Base):
    """
    Para hareketleri defteri (ledger).

    Bir kullanıcının bakiyesi her değiştiğinde buraya BİR satır yazılır.
    Bu satırlar asla güncellenmez ve silinmez: bir hata düzeltilecekse ters yönde
    yeni bir satır eklenir. Böylece "bu bakiye nasıl oluştu?" sorusu her zaman
    cevaplanabilir.

    Bir hediye iki satır üretir: gönderen için (coin, eksi tutar) ve alan için
    (diamond, artı tutar).
    """
    __tablename__ = "transactions"
    __table_args__ = (
        # Aynı kullanıcı aynı idempotency anahtarıyla ikinci bir satır yazamaz.
        # "Çift tıklama / ağ tekrar denemesi yüzünden iki kez para düşme" bununla engellenir.
        UniqueConstraint("user_id", "idempotency_key"),
        # Cüzdan geçmişi sorgusu: "bu kullanıcının son hareketleri".
        Index("ix_transactions_user_id_id", "user_id", "id"),
        # Liderlik tablosu sorgusu: "en çok hediye gönderenler".
        Index("ix_transactions_type_created_at", "type", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    # Bakiyesi değişen kullanıcı.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # purchase | gift_sent | gift_received | reward | exchange | store_purchase | vip_purchase
    # | vip_daily | lucky_win | chest_reward
    type: Mapped[str] = mapped_column(String(32))
    # coin | diamond
    currency: Mapped[str] = mapped_column(String(16))
    # İşaretli tutar: bakiye arttıysa artı, azaldıysa eksi.
    amount: Mapped[int] = mapped_column(BigInteger)
    # Bu hareketten hemen sonraki bakiye (denetim ve hata ayıklama için).
    balance_after: Mapped[int] = mapped_column(BigInteger)
    # Kullanıcının geçmiş listesinde göreceği açıklama.
    label: Mapped[str] = mapped_column(String(200))

    # ── İlişkili kayıtlar (hareketin türüne göre bazıları boş kalır) ──────────
    counterparty_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # hediyede karşı taraf
    gift_id: Mapped[int | None] = mapped_column(ForeignKey("gifts.id"))
    package_id: Mapped[int | None] = mapped_column(ForeignKey("coin_packages.id"))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("store_items.id"))   # mağaza alımında
    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id"))
    quantity: Mapped[int | None] = mapped_column(Integer)

    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
