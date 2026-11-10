"""
Yayıncı başvurusu JSON şemaları.
"""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.user import UserOut


class HostApplyRequest(BaseModel):
    birth_date: date
    intro: str = Field(min_length=10, max_length=300)
    # Kullanıcı "18 yaşından büyüğüm ve yayıncı kurallarını kabul ediyorum" kutusunu işaretlemeli.
    accept_rules: Literal[True]

    @field_validator("intro", mode="before")
    @classmethod
    def strip_intro(cls, value):
        return value.strip() if isinstance(value, str) else value


class HostApplicationOut(BaseModel):
    id: int
    status: Literal["pending", "approved", "rejected"]
    intro: str
    review_note: str | None
    created_at: datetime
    reviewed_at: datetime | None


class HostStatus(BaseModel):
    """Kişinin yayıncılık durumu (Ben sekmesindeki "Yayıncı ol" kutusu)."""
    is_host: bool
    host_since: datetime | None
    application: HostApplicationOut | None     # en son başvurusu
    can_apply: bool                            # şu an başvurabilir mi
    reapply_after: datetime | None = None      # reddedildiyse ne zaman yeniden başvurabilir


class HostApplicationAdminOut(HostApplicationOut):
    """Panelde görünen başvuru: başvuranın bilgisi ve yaşı."""
    user: UserOut
    birth_date: date
    age: int


class HostReviewRequest(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=300)


class HostRevokeRequest(BaseModel):
    note: str = Field(default="", max_length=300)
