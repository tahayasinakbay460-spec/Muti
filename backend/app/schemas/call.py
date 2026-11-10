"""
Birebir arama JSON şemaları.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.user import UserOut


class CallStartRequest(BaseModel):
    callee_id: int
    kind: Literal["voice", "video"] = "voice"


class CallOut(BaseModel):
    id: int
    kind: Literal["voice", "video"]
    status: Literal["ringing", "active", "ended", "missed", "declined"]
    is_caller: bool           # isteği atan kişi arayan mı?
    peer: UserOut             # karşı taraf
    price_per_minute: int
    billed_minutes: int
    coins_spent: int | None   # yalnızca arayana (ödeyene) gösterilir
    started_at: datetime | None
    end_reason: str | None


class CallPrices(BaseModel):
    """Arama tuşlarının yanında ve onay penceresinde gösterilen dakika fiyatları."""
    voice_per_minute: int
    video_per_minute: int
