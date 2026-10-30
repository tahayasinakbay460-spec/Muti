"""
Tarayıcıdan gelen ses sorunu kayıtları.

Ses, tarayıcı ile ses sağlayıcısı arasında akar; sunucumuz bu yolu görmez. Mikrofon ya da
hoparlör hatası bu yüzden yalnızca kullanıcının tarayıcısında oluşur. Tarayıcı olayı buraya
bildirir, biz de sunucu kaydına yazarız (`voice_client_event`).
"""
import logging

from app.realtime.room_socket import RateLimiter
from app.schemas.diagnostics import VoiceDiagnosticRequest

logger = logging.getLogger(__name__)

USER_AGENT_MAX_LENGTH = 160
# Kayıtlar bir kişi tarafından şişirilemesin diye: kişi başına dakikada en fazla 60 olay
EVENTS_PER_MINUTE = 60
# DEMO KISAYOLU: sınır sayaçları bellekte, tek sürece göre. Redis'e geçince oraya taşınır.
_limiters: dict[int, RateLimiter] = {}


def record_voice_event(user_id: int, report: VoiceDiagnosticRequest, user_agent: str) -> None:
    limiter = _limiters.setdefault(user_id, RateLimiter(limit=EVENTS_PER_MINUTE, period=60))
    if not limiter.allow():
        return
    logger.warning("voice_client_event", extra={"fields": {
        "reporter_id": user_id,
        "room_id": report.room_id,
        "provider": report.provider,
        "event": report.event,
        "detail": report.detail,
        "user_agent": user_agent[:USER_AGENT_MAX_LENGTH],
    }})
