"""
Özel mesaj JSON şemaları.
"""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.user import UserOut


class MessageOut(BaseModel):
    id: int | None = None
    from_me: bool             # mesajı isteği atan kişi mi yazdı? (baloncuk sağda mı solda mı)
    text: str
    created_at: datetime
    time: str                 # "21:05" (DEMO: mobil istemci created_at'ten kendisi üretmeli)


class ConversationSummary(BaseModel):
    """Mesajlar listesindeki tek satır."""
    id: int
    user_id: int              # karşıdaki kişi
    user: UserOut
    unread_count: int
    last_message: MessageOut | None


class ConversationDetail(BaseModel):
    """Açılmış bir sohbet: karşıdaki kişi + mesajlar (eskiden yeniye)."""
    id: int
    user_id: int
    user: UserOut
    unread_count: int
    messages: list[MessageOut]


class ConversationOpenRequest(BaseModel):
    user_id: int


class ConversationOpenResult(BaseModel):
    id: int


class UnreadCount(BaseModel):
    unread_count: int


class MessageSendRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value
