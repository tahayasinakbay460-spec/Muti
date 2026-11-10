"""
Hediye ve cüzdan JSON şemaları.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.store import StoreItemBrief
from app.schemas.user import UserOut


class GiftOut(BaseModel):
    # from_attributes: bu şema doğrudan bir tablo satırından (Gift nesnesinden) üretilebilir.
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    emoji: str
    price: int
    is_lucky: bool


class GiftSendRequest(BaseModel):
    receiver_id: int
    gift_id: int
    # Üst sınır: tek istekte saçma büyük tutarları engeller.
    quantity: int = Field(default=1, ge=1, le=999)
    # Hediye bir odada gönderildiyse oda id'si (animasyon o odaya yayınlanır).
    room_id: int | None = None


class GiftSendResult(BaseModel):
    coin_balance: int         # gönderenin işlemden sonraki bakiyesi
    gift: GiftOut
    receiver: UserOut
    quantity: int
    # Şanslı hediyede gönderene geri dönen coin ve tek seferde çıkan en büyük çarpan.
    lucky_win: int = 0
    lucky_multiplier: int = 0


class CoinPackageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    coins: int
    bonus: int
    price_label: str
    is_popular: bool
    is_best_value: bool
    # Hediye paketi ise: başlığı, içindeki eşya ve süresi.
    title: str | None = None
    item: StoreItemBrief | None = None
    item_days: int = 0
    is_one_time: bool = False
    is_bought: bool = False   # tek seferlik paket bu kullanıcı tarafından alındı mı?


class PurchaseRequest(BaseModel):
    package_id: int


class PurchaseResult(BaseModel):
    coin_balance: int         # yeni bakiye
    added: int                # eklenen coin (paket + bonus)
    item: StoreItemBrief | None = None   # paketle gelen eşya


class ExchangeRequest(BaseModel):
    """Elmasları coine çevirme. Tutar tamsayı; üst sınır saçma büyük istekleri engeller."""
    diamonds: int = Field(ge=1, le=10_000_000)


class ExchangeResult(BaseModel):
    coin_balance: int
    diamond_balance: int
    coins_added: int


class Supporter(BaseModel):
    user: UserOut
    diamonds: int             # bu kişinin hediyeleriyle kazandığım toplam elmas


class RevenueRates(BaseModel):
    """
    Gelir paylaşım oranları (yüzde) ve coin fiyatı. GET /economy/rates.
    Örnek: 100 coinlik hediyede bağımsız yayıncı 50 elmas alır; ajans yayıncısı 60 elmas alır,
    ajansı da (oranı %10 ise) 10 elmas komisyon hak eder.
    """
    independent_host_percent: int
    agency_host_percent: int
    agency_commission_max_percent: int
    lucky_gift_host_percent: int
    call_host_percent: int
    call_agency_host_percent: int
    call_voice_price_per_minute: int
    call_video_price_per_minute: int
    diamond_to_coin_rate: int
    coin_price_per_1000_kurus: int   # 3000 = 1000 coin 30,00 TL (liste fiyatı)
    dealer_discount_percent: int
    withdrawals_enabled: bool


class IncomeSummary(BaseModel):
    """Yayıncı geliri: hediyelerden kazanılan elmaslar."""
    # Bu kişinin şu anki payı (hediye değerinin yüzdesi) ve bağlı olduğu ajans
    share_percent: int = 0
    agency_name: str | None = None
    diamond_balance: int
    today_diamonds: int
    week_diamonds: int
    total_diamonds: int
    # 1 elmas kaç coin eder (çevirme oranı) ve gerçek para karşılığı çekim açık mı?
    diamond_to_coin_rate: int
    withdrawals_enabled: bool
    top_supporters: list[Supporter]


class TransactionOut(BaseModel):
    id: int
    type: str
    currency: str
    label: str
    amount: int               # artı: gelen, eksi: giden
    created_at: datetime
    time_label: str           # "3 gün önce" (DEMO: mobil istemci created_at'ten kendisi üretmeli)
