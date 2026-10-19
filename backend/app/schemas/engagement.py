"""
Bağlılık sistemleri JSON şemaları: günlük giriş, görevler, aile, CP, sıralamalar, etkinlikler.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.user import UserOut


# ── Günlük giriş ve görevler ──────────────────────────────────────────────────

class CheckInStatus(BaseModel):
    day: int                  # bugün alınacak (ya da alınmış) gün, 1-7
    claimed_today: bool
    rewards: list[int]        # 7 günün coin ödülleri


class CheckInResult(BaseModel):
    day: int
    coins: int
    coin_balance: int


class TaskOut(BaseModel):
    id: str
    title: str
    target: int
    progress: int
    coins: int
    claimed: bool


class TaskClaimResult(BaseModel):
    task_id: str
    coins: int
    coin_balance: int


# ── Aile ──────────────────────────────────────────────────────────────────────

def _strip(value):
    return value.strip() if isinstance(value, str) else value


class FamilyCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=24)
    badge: str = Field(min_length=1, max_length=16)
    slogan: str = Field(default="", max_length=120)

    _strip_text = field_validator("name", "badge", "slogan", mode="before")(_strip)


class FamilyUpdateRequest(BaseModel):
    slogan: str | None = Field(default=None, max_length=120)
    badge: str | None = Field(default=None, min_length=1, max_length=16)

    _strip_text = field_validator("slogan", "badge", mode="before")(_strip)


class FamilyOut(BaseModel):
    id: int
    name: str
    badge: str
    slogan: str
    owner_id: int
    member_count: int
    max_members: int
    week_coins: int           # üyelerin bu hafta gönderdiği hediyelerin coin toplamı
    level: int                # toplam hediye değerine göre aile seviyesi
    my_role: Literal["owner", "admin", "member"] | None = None   # isteği atan kişinin rolü


class FamilyMemberOut(BaseModel):
    user: UserOut
    role: Literal["owner", "admin", "member"]
    week_coins: int


class FamilyDetail(FamilyOut):
    members: list[FamilyMemberOut]


class FamilyMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)

    _strip_text = field_validator("text", mode="before")(_strip)


class FamilyMessageOut(BaseModel):
    id: int
    sender: UserOut
    text: str
    created_at: datetime


class FamilyRoleRequest(BaseModel):
    role: Literal["admin", "member"]


# ── CP ────────────────────────────────────────────────────────────────────────

class CoupleOut(BaseModel):
    partner: UserOut
    status: Literal["pending", "active"]
    requested_by_me: bool
    since: datetime           # teklif ya da kabul anı
    cp_coins: int             # ikisinin birbirine gönderdiği hediyelerin coin toplamı


class CoupleStatus(BaseModel):
    active: CoupleOut | None
    incoming: list[CoupleOut]   # bana gelen, bekleyen teklifler
    outgoing: list[CoupleOut]   # benim gönderdiğim, bekleyen teklifler
    proposal_price: int


# ── Sıralamalar ───────────────────────────────────────────────────────────────

LeaderboardKind = Literal["rich", "charm", "rooms", "families"]
LeaderboardPeriod = Literal["day", "week", "month"]


class LeaderboardEntry(BaseModel):
    rank: int
    score: int
    # Türüne göre biri dolu: kişi (rich/charm), oda, aile
    user: UserOut | None = None
    room: dict | None = None
    family: dict | None = None


class Leaderboard(BaseModel):
    kind: LeaderboardKind
    period: LeaderboardPeriod
    entries: list[LeaderboardEntry]
    me: LeaderboardEntry | None = None   # kişi sıralamalarında isteği atanın sırası (listede yoksa da)


# ── Etkinlikler ───────────────────────────────────────────────────────────────

class EventOut(BaseModel):
    id: int
    title: str
    description: str
    emoji: str
    metric: Literal["gifts_sent", "gifts_received"]
    starts_at: datetime
    ends_at: datetime
    rewards: list[int]
    status: Literal["upcoming", "active", "ended"]


class EventDetail(EventOut):
    entries: list[LeaderboardEntry]
    me: LeaderboardEntry | None = None
