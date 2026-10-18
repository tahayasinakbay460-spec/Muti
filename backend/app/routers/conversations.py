"""
/api/v1/conversations — özel mesajlar.
"""
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUserId, DbSession
from app.schemas.message import (
    ConversationDetail, ConversationOpenRequest, ConversationOpenResult,
    ConversationSummary, MessageOut, MessageSendRequest,
)
from app.services import message_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(user_id: CurrentUserId, db: DbSession):
    return await message_service.list_conversations(db, user_id)


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


@router.post("/{conversation_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def send_message(conversation_id: int, data: MessageSendRequest, user_id: CurrentUserId, db: DbSession):
    return await message_service.send_message(db, user_id, conversation_id, data.text)
