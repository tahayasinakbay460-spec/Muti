"""
Yönetim paneli ve ajans JSON şemaları.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.economy import TransactionOut
from app.schemas.user import UserOut


def _strip(value):
    return value.strip() if isinstance(value, str) else value


# ── Yönetim paneli ────────────────────────────────────────────────────────────

class AdminStats(BaseModel):
    users_total: int
    users_today: int          # bugün (yerel takvim) kayıt olan
    online_now: int
    rooms_active: int
    coins_sold_today: int     # bugün satın alınan coin (DEMO: gerçek ödeme yok)
    gift_coins_today: int     # bugün hediyeye harcanan coin
    open_reports: int
    banned_users: int


class AdminReportOut(BaseModel):
    id: int
    reporter: UserOut | None
    target_type: Literal["user", "room"]
    target_id: int
    target_label: str         # şikâyet edilen kişinin adı ya da odanın başlığı
    reason: str
    details: str
    status: str
    created_at: datetime
    action: str | None = None
    resolution_note: str = ""
    resolved_at: datetime | None = None


class ReportResolveRequest(BaseModel):
    # dismiss: asılsız; ban_user: şikâyet edilen kullanıcıyı banla; close_room: şikâyet edilen odayı kapat
    action: Literal["dismiss", "ban_user", "close_room"]
    note: str = Field(default="", max_length=300)

    _strip_note = field_validator("note", mode="before")(_strip)


class AdminUserOut(BaseModel):
    user: UserOut
    email: str | None
    is_active: bool
    is_admin: bool
    coin_balance: int
    diamond_balance: int
    reports_against: int      # bu kişi hakkında açılmış şikâyet sayısı
    recent_transactions: list[TransactionOut]


class BanRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=300)

    _strip_reason = field_validator("reason", mode="before")(_strip)


class BalanceAdjustRequest(BaseModel):
    """Yönetici düzeltmesi (ör. hatalı ödeme iadesi). Gerekçe zorunlu; para defterine yazılır."""
    currency: Literal["coin", "diamond"]
    amount: int = Field(ge=-10_000_000, le=10_000_000)
    reason: str = Field(min_length=3, max_length=200)

    _strip_reason = field_validator("reason", mode="before")(_strip)

    @field_validator("amount")
    @classmethod
    def not_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("Tutar sıfır olamaz.")
        return value


class BalanceAdjustResult(BaseModel):
    currency: str
    balance: int


class AdminRoomOut(BaseModel):
    id: int
    title: str
    host: UserOut | None
    listener_count: int
    is_live: bool
    created_at: datetime


# ── Ajans ─────────────────────────────────────────────────────────────────────

class AgencyCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    owner_id: int
    commission_percent: int = Field(default=10, ge=0, le=50)

    _strip_name = field_validator("name", mode="before")(_strip)


class AgencyOut(BaseModel):
    id: int
    name: str
    owner: UserOut
    commission_percent: int
    member_count: int


class AgencyMemberOut(BaseModel):
    user: UserOut
    status: Literal["invited", "active"]
    monthly_target: int
    month_diamonds: int       # bu ay hediyelerden kazandığı elmas
    progress_percent: int     # hedefe göre ilerleme (hedef yoksa 0)


class AgencyDashboard(BaseModel):
    agency: AgencyOut
    members: list[AgencyMemberOut]
    month_diamonds: int       # aktif üyelerin bu ay toplam kazancı
    estimated_commission: int # DEMO: yalnızca hesap, ödeme yok


class MyAgency(BaseModel):
    """Kişinin ajansla ilişkisi: sahibi mi, üyesi mi, bekleyen daveti var mı."""
    role: Literal["owner", "member"] | None
    dashboard: AgencyDashboard | None = None   # ajans sahibiyse
    agency: AgencyOut | None = None            # üyesiyse
    my_month_diamonds: int = 0
    my_target: int = 0
    invite: AgencyOut | None = None            # bekleyen davet


class AgencyTargetRequest(BaseModel):
    monthly_target: int = Field(ge=0, le=100_000_000)
