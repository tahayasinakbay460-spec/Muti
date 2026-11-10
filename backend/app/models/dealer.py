"""
Coin bayileri (TopTop'taki "coin seller / top-up" satıcıları).

BAYİ NEDİR? Bizimle anlaşmalı kişi ya da ajans. Bizden toptan (indirimli) coin stoğu alır, parasını
bize havale ile öder; sonra kullanıcılara kendi fiyatıyla satar ve coin'i uygulamadan kullanıcının
ID'sine gönderir. Kullanıcı bayiye nakit, havale, kendi ülkesindeki ödeme yolları ile öder. Bu yol,
App Store / Google Play komisyonu (%15-30) olmadan satış demektir ve kartı olmayan kullanıcıya ulaşır.

PARA NASIL AKAR?
  1. Panel bayiye stok yükler: bayi bize ödediği tutarı ve dekont numarasını yazarız (DealerStockOrder),
     bayinin stoğu artar (para defterinde `dealer_stock`).
  2. Bayi uygulamadaki "Bayi paneli"nden kullanıcı ID + miktar girer: stoğu düşer (`dealer_sale`),
     kullanıcının coin'i artar (`dealer_topup`). İkisi tek transaction'da.
Bayinin stoğu ayrı bir bakiyedir: bayi kendi stoğunu hediye olarak harcayamaz, yalnızca satabilir.

KÖTÜYE KULLANIMA KARŞI
  - Günlük satış sınırı (bayi başına): çalıntı kartla alınmış stoğun bir günde dağıtılmasını sınırlar.
  - Panel bayiyi anında askıya alabilir; askıdaki bayi satış yapamaz.
  - Misafir hesaba satış yapılamaz (hesap kaybolursa coin de gider, şikâyet bize gelir).
  - Her hareket para defterinde; bütün panel işlemleri audit ve personel kaydına yazılır.
"""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BigIntPk, utcnow

DEALER_STATUSES = ("active", "suspended")


class CoinDealer(Base):
    __tablename__ = "coin_dealers"
    __table_args__ = (
        # Veritabanı kuralı: stok eksiye düşemez (asıl kontrol change_balance'taki tek komutluk UPDATE).
        CheckConstraint("stock >= 0", name="dealer_stock_non_negative"),
        CheckConstraint("daily_limit > 0", name="dealer_daily_limit_positive"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    # Satılabilir coin stoğu. YALNIZCA wallet_service.change_balance(currency="dealer_coin") değiştirir.
    stock: Mapped[int] = mapped_column(BigInteger, default=0)
    # Bir günde (yerel takvim) en fazla kaç coin satabilir.
    daily_limit: Mapped[int] = mapped_column(BigInteger)
    # Bugünkü satış toplamı ve hangi güne ait olduğu ("2026-11-10"). Gün değişince sayaç sıfırdan başlar.
    # Ayrı sütun olması sınır kontrolünü tek bir UPDATE ile yapmayı sağlar (iki eşzamanlı satış sınırı aşamaz).
    sold_today: Mapped[int] = mapped_column(BigInteger, default=0)
    sold_day: Mapped[str] = mapped_column(String(10), default="")
    note: Mapped[str] = mapped_column(String(200), default="")      # panel notu (ülke, iletişim, sözleşme no)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DealerStockOrder(Base):
    """
    Bayiye yapılan toptan satış: kaç coin verildi, karşılığında ne kadar ödendi, dekont numarası.
    Muhasebe kaydıdır; güncellenmez, silinmez. Eksi coin = iade/düzeltme (stoktan geri alma).
    """
    __tablename__ = "dealer_stock_orders"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    dealer_id: Mapped[int] = mapped_column(ForeignKey("coin_dealers.user_id", ondelete="CASCADE"), index=True)
    coins: Mapped[int] = mapped_column(BigInteger)
    # Bayinin bize ödediği tutar, kuruş olarak (float yok): 150000 = 1.500,00 TL
    paid_kurus: Mapped[int] = mapped_column(BigInteger, default=0)
    payment_ref: Mapped[str] = mapped_column(String(100), default="")   # havale dekontu / fatura no
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
