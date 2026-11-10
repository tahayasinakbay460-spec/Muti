"""
/api/v1/calls — özel mesajlardaki birebir sesli / görüntülü arama (ücretli; bkz. services/call_service.py).
"""
from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.core.deps import CurrentUserId, DbSession
from app.schemas.call import CallOut, CallPrices, CallStartRequest
from app.services import call_service
from app.voice import VoiceJoinInfo

router = APIRouter(prefix="/calls", tags=["calls"])


@router.get("/prices", response_model=CallPrices)
async def get_prices(_user_id: CurrentUserId):
    """Dakika fiyatları (onay penceresinde "Sesli arama dakikası 30 coin")."""
    return CallPrices(
        voice_per_minute=settings.call_voice_price_per_minute,
        video_per_minute=settings.call_video_price_per_minute,
    )


@router.post("", response_model=CallOut, status_code=status.HTTP_201_CREATED)
async def start_call(data: CallStartRequest, user_id: CurrentUserId, db: DbSession):
    """Aramayı başlatır; karşı tarafın ekranında çalar. Ücret, açıldığı anda başlar."""
    return await call_service.start_call(db, user_id, data)


@router.get("/{call_id}", response_model=CallOut)
async def get_call(call_id: int, user_id: CurrentUserId, db: DbSession):
    return await call_service.get_call(db, user_id, call_id)


@router.post("/{call_id}/accept", response_model=VoiceJoinInfo)
async def accept_call(call_id: int, user_id: CurrentUserId, db: DbSession):
    """Aranan kişi açar; cevapta ses/görüntü bağlantı bilgisi gelir."""
    return await call_service.accept_call(db, user_id, call_id)


@router.post("/{call_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
async def decline_call(call_id: int, user_id: CurrentUserId, db: DbSession):
    """Aranan reddeder ya da arayan çalarken vazgeçer."""
    await call_service.decline_call(db, user_id, call_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{call_id}/end", response_model=CallOut)
async def end_call(call_id: int, user_id: CurrentUserId, db: DbSession):
    """Görüşmeyi kapatır (iki taraftan biri)."""
    return await call_service.end_call(db, user_id, call_id)


@router.get("/{call_id}/join", response_model=VoiceJoinInfo)
async def join_info(call_id: int, user_id: CurrentUserId, db: DbSession):
    """Süren görüşmenin bağlantı bilgisini yeniler (ağ değişince yeniden bağlanmak için)."""
    return await call_service.join_info(db, user_id, call_id)
