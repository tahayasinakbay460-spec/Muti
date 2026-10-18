"""
/api/v1/rooms — oda listesi, oda oluşturma, koltuk ve mikrofon işlemleri.
"""
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUserId, DbSession
from app.schemas.room import RoomCreateRequest, RoomOut
from app.services import room_service

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("", response_model=list[RoomOut])
async def list_rooms(
    user_id: CurrentUserId,
    db: DbSession,
    category: str = "",
    query: Annotated[str, Query(max_length=60)] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Odaları listeler. `category` ile filtrelenir, `query` ile oda adında aranır."""
    return await room_service.list_rooms(db, user_id, category, query, limit, offset)


@router.post("", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
async def create_room(data: RoomCreateRequest, user_id: CurrentUserId, db: DbSession):
    """Yeni oda açar; açan kişi odanın sahibi olur ve ilk koltuğa oturur."""
    return await room_service.create_room(db, user_id, data)


@router.get("/{room_id}", response_model=RoomOut)
async def get_room(room_id: int, user_id: CurrentUserId, db: DbSession):
    return await room_service.get_room(db, user_id, room_id)


@router.post("/{room_id}/seats/{seat_index}", response_model=RoomOut)
async def take_seat(room_id: int, seat_index: int, user_id: CurrentUserId, db: DbSession):
    """Boş bir koltuğa oturur (mikrofona çıkar)."""
    return await room_service.take_seat(db, user_id, room_id, seat_index)


@router.delete("/{room_id}/seats/me", response_model=RoomOut)
async def leave_seat(room_id: int, user_id: CurrentUserId, db: DbSession):
    """Koltuktan kalkar, dinleyici olarak odada kalır."""
    return await room_service.leave_seat(db, user_id, room_id)


@router.post("/{room_id}/seats/me/mute", response_model=RoomOut)
async def toggle_mute(room_id: int, user_id: CurrentUserId, db: DbSession):
    """Kendi mikrofonunu açar/kapatır."""
    return await room_service.toggle_mute(db, user_id, room_id)
