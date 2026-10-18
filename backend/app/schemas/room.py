"""
Oda JSON şemaları.
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.user import UserOut


class SeatOut(BaseModel):
    """Odadaki bir koltuk (mikrofon yeri)."""
    index: int                # koltuk numarası, 0'dan başlar
    user_id: int | None       # boşsa null
    is_muted: bool
    is_locked: bool
    user: UserOut | None      # oturan kişinin bilgisi (boşsa null)


class RoomOut(BaseModel):
    id: int
    title: str
    category: str
    cover_url: str | None
    is_live: bool
    listener_count: int       # şu an odada kaç kişi var (canlı sayı)
    host_id: int
    hourly_rank: int          # dinleyici sayısına göre sıralama
    announcement: str
    host: UserOut
    seats: list[SeatOut]


class RoomCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=60)
    category: Literal["chat", "music", "game", "new_people"] = "chat"

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value):
        # "   " gibi yalnızca boşluktan oluşan adlar min_length kontrolüne takılsın.
        return value.strip() if isinstance(value, str) else value
