"""
Mağaza, VIP üyelik ve hazine sandığı JSON şemaları.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.user import UserOut

StoreItemKind = Literal["frame", "entry_effect", "chat_bubble"]


class StoreItemBrief(BaseModel):
    """Eşyanın yalnızca görünüşü (paket içeriğinde, profilde kullanılır)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: StoreItemKind
    name: str
    style: str
    emoji: str


class StoreItemOut(StoreItemBrief):
    price_7d: int
    price_30d: int
    vip_level_required: int
    # ── İsteği atan kişiye göre ───────────────────────────────────────────────
    is_owned: bool = False            # şu an geçerli (süresi dolmamış) olarak sahip mi?
    owned_until: datetime | None = None
    is_equipped: bool = False


class OwnedItemOut(StoreItemBrief):
    """Bir kullanıcının sahip olduğu, süresi dolmamış eşya (profilde gösterilir)."""
    owned_until: datetime
    is_equipped: bool


class StorePurchaseRequest(BaseModel):
    days: Literal[7, 30]


class StorePurchaseResult(BaseModel):
    coin_balance: int
    item: StoreItemOut


class EquipRequest(BaseModel):
    # true: tak (aynı türden takılı olan çıkarılır), false: çıkar
    equipped: bool


class VipTierOut(BaseModel):
    level: int
    name: str
    price_30d: int            # coin
    daily_coins: int          # her gün alınabilen ödül
    perks: list[str]          # ekranda gösterilen ayrıcalık listesi
    items: list[StoreItemBrief]   # üyelikle birlikte verilen eşyalar


class VipStatus(BaseModel):
    level: int                # şu an geçerli seviye (0 = VIP değil)
    expires_at: datetime | None   # null + level>0 → süresiz üyelik
    daily_reward_available: bool
    tiers: list[VipTierOut]


class VipPurchaseRequest(BaseModel):
    level: Literal[1, 2, 3]


class VipPurchaseResult(BaseModel):
    coin_balance: int
    status: VipStatus


class DailyRewardResult(BaseModel):
    coins: int
    coin_balance: int


class ChestOut(BaseModel):
    """Odanın hazine sandığı. Hediyeler doldurur; dolunca herkes kapışır."""
    chest_id: str
    status: Literal["filling", "open"]
    progress: int             # şu ana kadar odada gönderilen hediyelerin coin toplamı
    target: int
    # Yalnızca açıkken dolu:
    ends_at: datetime | None = None
    coins_left: int = 0
    claimed_by_me: bool = False


class ChestClaimResult(BaseModel):
    coins: int
    coin_balance: int


class ChestClaim(BaseModel):
    """Sandıktan çıkanı odaya duyururken kullanılan biçim."""
    user: UserOut
    coins: int
