from typing import Literal

from pydantic import BaseModel, Field

VoiceEvent = Literal[
    "join_failed", "connection_changed", "token_expired", "mic_failed", "mic_denied_by_server",
    "mic_published", "mic_flowing", "mic_silent",
    "subscribe_failed", "speaker_not_seated", "autoplay_blocked", "socket_reconnected",
]


class VoiceDiagnosticRequest(BaseModel):
    room_id: int
    provider: Literal["mesh", "livekit", "agora"]
    event: VoiceEvent
    detail: str = Field(default="", max_length=300)
