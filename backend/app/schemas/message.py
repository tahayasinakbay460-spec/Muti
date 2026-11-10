"""
Özel mesaj JSON şemaları.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.economy import GiftOut
from app.schemas.user import UserOut


class MessageOut(BaseModel):
    id: int | None = None
    from_me: bool             # mesajı isteği atan kişi mi yazdı? (baloncuk sağda mı solda mı)
    # text: yazı | voice: sesli mesaj | gift: hediye | call: arama izi (bkz. models/message.py)
    kind: Literal["text", "voice", "gift", "call", "image"] = "text"
    # Yazılı mesajda metin; diğer türlerde kısa önizleme ("🎤 Sesli mesaj") — eski istemciler de bir şey göstersin.
    text: str
    created_at: datetime
    time: str                 # "21:05" (DEMO: mobil istemci created_at'ten kendisi üretmeli)
    # voice / image: dosyanın API adresi (/api/v1 sonrası). Token ister; herkese açık bir bağlantı değildir.
    media_url: str | None = None
    duration_seconds: int | None = None   # voice: kayıt süresi, call: konuşma süresi
    gift: GiftOut | None = None
    quantity: int | None = None
    call_kind: Literal["voice", "video"] | None = None
    call_status: Literal["ended", "missed", "declined"] | None = None


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


class ConversationGiftRequest(BaseModel):
    """Sohbette hediye: alıcı sohbetin karşı tarafıdır, istemci seçemez."""
    gift_id: int
    quantity: int = Field(default=1, ge=1, le=999)


class ConversationGiftResult(BaseModel):
    coin_balance: int         # gönderenin işlemden sonraki bakiyesi
    message: MessageOut | None   # aynı istek tekrarlandıysa (idempotency) yeni mesaj açılmaz: null
    lucky_win: int = 0
    lucky_multiplier: int = 0


class MessageSendRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value
