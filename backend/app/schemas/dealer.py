"""
Coin bayisi şemaları (bkz. models/dealer.py).
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.user import UserOut


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class DealerPublicOut(BaseModel):
    """Cüzdandaki "Bayiden coin al" listesi: resmi bayiler. Kullanıcı bayiye mesaj atıp anlaşır."""
    user: UserOut
    note: str = ""


class DealerSaleRequest(BaseModel):
    user_id: int
    coins: int = Field(ge=1, le=10_000_000)


class DealerSaleOut(BaseModel):
    id: int
    user: UserOut | None        # alıcı (hesabı silindiyse null)
    coins: int
    created_at: datetime


class DealerPanel(BaseModel):
    """Bayinin kendi paneli: stok, bugünkü satış ve sınırı, son satışlar."""
    status: Literal["active", "suspended"]
    stock: int
    daily_limit: int
    sold_today: int
    recent_sales: list[DealerSaleOut]


class DealerSaleResult(BaseModel):
    stock: int
    sold_today: int
    sale: DealerSaleOut


# ── Panel (yönetim) ───────────────────────────────────────────────────────────

class DealerAdminOut(BaseModel):
    user: UserOut
    status: Literal["active", "suspended"]
    stock: int
    daily_limit: int
    sold_today: int
    note: str
    total_loaded: int            # bugüne kadar yüklenen stok (coin)
    total_paid_kurus: int        # bayinin bize ödediği toplam (kuruş)
    created_at: datetime


class DealerCreateRequest(BaseModel):
    user_id: int
    daily_limit: int | None = Field(default=None, ge=1, le=1_000_000_000)   # boşsa .env varsayılanı
    note: str = Field(default="", max_length=200)

    _strip_note = field_validator("note", mode="before")(_strip)


class DealerUpdateRequest(BaseModel):
    status: Literal["active", "suspended"] | None = None
    daily_limit: int | None = Field(default=None, ge=1, le=1_000_000_000)
    note: str | None = Field(default=None, max_length=200)

    _strip_note = field_validator("note", mode="before")(_strip)


class DealerStockRequest(BaseModel):
    """Toptan stok yükleme. Eksi coin = iade/düzeltme (stoktan geri alma)."""
    coins: int = Field(ge=-100_000_000, le=100_000_000)
    paid_kurus: int = Field(default=0, ge=0, le=100_000_000_000)
    payment_ref: str = Field(min_length=3, max_length=100)   # dekont/fatura no: kayıtsız stok verilmez

    _strip_ref = field_validator("payment_ref", mode="before")(_strip)


class DealerStockOrderOut(BaseModel):
    id: int
    coins: int
    paid_kurus: int
    payment_ref: str
    created_by: UserOut | None
    created_at: datetime


class DealerAdminDetail(BaseModel):
    dealer: DealerAdminOut
    orders: list[DealerStockOrderOut]
    sales: list[DealerSaleOut]
    suggested_kurus_per_1000: int   # önerilen toptan fiyat: liste fiyatı − bayi indirimi
