"""
Hediye ve cüzdan JSON şemaları.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserOut


class GiftOut(BaseModel):
    # from_attributes: bu şema doğrudan bir tablo satırından (Gift nesnesinden) üretilebilir.
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    emoji: str
    price: int


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


class CoinPackageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    coins: int
    bonus: int
    price_label: str
    is_popular: bool
    is_best_value: bool


class PurchaseRequest(BaseModel):
    package_id: int


class PurchaseResult(BaseModel):
    coin_balance: int         # yeni bakiye
    added: int                # eklenen coin (paket + bonus)


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


class IncomeSummary(BaseModel):
    """Yayıncı geliri: hediyelerden kazanılan elmaslar."""
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
