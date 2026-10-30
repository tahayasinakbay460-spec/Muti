"""
/api/v1/diagnostics/voice — tarayıcının bildirdiği ses sorunları (bkz. diagnostics_service).
"""
from fastapi import APIRouter, Request, status

from app.core.deps import CurrentUserId
from app.schemas.diagnostics import VoiceDiagnosticRequest
from app.services import diagnostics_service

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.post("/voice", status_code=status.HTTP_204_NO_CONTENT)
async def report_voice_event(body: VoiceDiagnosticRequest, request: Request, user_id: CurrentUserId) -> None:
    """Yalnızca kayda yazar; hiçbir veriyi değiştirmez."""
    diagnostics_service.record_voice_event(user_id, body, request.headers.get("user-agent", ""))
