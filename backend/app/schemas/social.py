"""
Bildirim, engelleme ve şikâyet JSON şemaları.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.user import UserOut


class NotificationOut(BaseModel):
    id: int
    type: str                 # follow | gift_received | level_up | room_role
    text: str
    actor: UserOut | None     # bildirimi tetikleyen kişi (sistem bildiriminde null)
    data: dict                # ör. {"room_id": 5}: dokununca nereye gidileceği
    is_read: bool
    created_at: datetime
    time_label: str           # "3 dk önce" (DEMO: mobil istemci created_at'ten kendisi üretmeli)


class UnreadCount(BaseModel):
    unread_count: int


class BlockResult(BaseModel):
    is_blocked: bool


class ReportRequest(BaseModel):
    target_type: Literal["user", "room"]
    target_id: int
    reason: Literal["spam", "harassment", "inappropriate", "underage", "fraud", "other"]
    details: str = Field(default="", max_length=500)

    @field_validator("details", mode="before")
    @classmethod
    def strip_details(cls, value):
        return value.strip() if isinstance(value, str) else value
