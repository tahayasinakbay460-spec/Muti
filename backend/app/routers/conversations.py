"""
/api/v1/conversations — özel mesajlar.
"""
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request, Response, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.deps import CurrentUserId, DbSession
from app.core.uploads import read_limited_body
from app.schemas.message import (
    ConversationDetail, ConversationGiftRequest, ConversationGiftResult, ConversationOpenRequest,
    ConversationOpenResult, ConversationSummary, MessageOut, MessageSendRequest, UnreadCount,
)
from app.services import message_service

IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", min_length=8, max_length=64)]

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(user_id: CurrentUserId, db: DbSession):
    return await message_service.list_conversations(db, user_id)


# SIRA ÖNEMLİ: sabit adres "/unread-count", "/{conversation_id}" adresinden önce tanımlanmalı.
@router.get("/unread-count", response_model=UnreadCount)
async def get_unread_count(user_id: CurrentUserId, db: DbSession):
    """Toplam okunmamış mesaj sayısı (alt çubuktaki rozet)."""
    return UnreadCount(unread_count=await message_service.total_unread(db, user_id))


@router.post("", response_model=ConversationOpenResult)
async def open_conversation(data: ConversationOpenRequest, user_id: CurrentUserId, db: DbSession):
    """Bir kişiyle sohbeti açar; daha önce açılmışsa mevcut sohbetin id'sini döner."""
    return ConversationOpenResult(id=await message_service.open_conversation(db, user_id, data.user_id))


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: int,
    user_id: CurrentUserId,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before_id: int | None = None,
):
    """Sohbetin mesajlarını döner ve okunmamışları okundu sayar."""
    return await message_service.get_conversation(db, user_id, conversation_id, limit, before_id)


@router.post("/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(conversation_id: int, user_id: CurrentUserId, db: DbSession):
    """Sohbet açıkken gelen mesajları okundu sayar."""
    await message_service.mark_read(db, user_id, conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{conversation_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def send_message(conversation_id: int, data: MessageSendRequest, user_id: CurrentUserId, db: DbSession):
    return await message_service.send_message(db, user_id, conversation_id, data.text)


@router.post("/{conversation_id}/voice", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def send_voice(
    conversation_id: int,
    request: Request,
    user_id: CurrentUserId,
    db: DbSession,
    duration: Annotated[int, Query(ge=1, le=600)],
    content_type: Annotated[str, Header()] = "",
):
    """
    Sesli mesaj gönderir. Gövde ses dosyasının kendisidir (form değil), türü `Content-Type`
    başlığında (audio/webm, audio/ogg, audio/mp4), süresi `duration` (saniye) parametresinde.
    """
    data = await read_limited_body(request, settings.voice_message_max_bytes, "Ses kaydı çok büyük.", "audio_too_large")
    return await message_service.send_voice(db, user_id, conversation_id, content_type, data, duration)


@router.post("/{conversation_id}/image", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def send_image(
    conversation_id: int, request: Request, user_id: CurrentUserId, db: DbSession,
    content_type: Annotated[str, Header()] = "",
):
    """Sohbette fotoğraf gönderir. Gövde dosyanın kendisidir; fotoğraf herkese açık adresten verilmez."""
    data = await read_limited_body(request, settings.image_max_bytes, "Fotoğraf çok büyük.", "image_too_large")
    return await message_service.send_image(db, user_id, conversation_id, content_type, data)


@router.get("/{conversation_id}/messages/{message_id}/media")
async def get_voice_file(conversation_id: int, message_id: int, user_id: CurrentUserId, db: DbSession):
    """Sesli mesajın / fotoğrafın dosyası. Yalnızca sohbetin iki üyesi alabilir; önbellek kişiye özel."""
    path, media_type = await message_service.voice_file(db, user_id, conversation_id, message_id)
    return FileResponse(path, media_type=media_type, headers={
        "Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff",
    })


@router.post("/{conversation_id}/gift", response_model=ConversationGiftResult)
async def send_gift(
    conversation_id: int, data: ConversationGiftRequest, user_id: CurrentUserId, db: DbSession,
    idempotency_key: IdempotencyKey = None,
):
    """Sohbetteki kişiye hediye gönderir; sohbete hediye mesajı düşer."""
    return await message_service.send_gift(db, user_id, conversation_id, data, idempotency_key)
