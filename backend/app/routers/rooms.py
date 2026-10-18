"""
/api/v1/rooms — oda listesi, oda oluşturma, oda takibi, koltuk ve mikrofon işlemleri, moderasyon.
"""
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.core.deps import CurrentUserId, DbSession
from app.schemas.room import RoomCreateRequest, RoomFollowResult, RoomOut
from app.services import moderation_service, room_service

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


# SIRA ÖNEMLİ: "/followed" sabit adresi "/{room_id}" adresinden önce tanımlanmalı.
@router.get("/followed", response_model=list[RoomOut])
async def list_followed_rooms(user_id: CurrentUserId, db: DbSession):
    """Takip ettiğim odalar (ana sayfadaki "Takip" sekmesi)."""
    return await room_service.list_followed_rooms(db, user_id)


@router.get("/{room_id}", response_model=RoomOut)
async def get_room(room_id: int, user_id: CurrentUserId, db: DbSession):
    return await room_service.get_room(db, user_id, room_id)


@router.post("/{room_id}/follow", response_model=RoomFollowResult)
async def toggle_room_follow(room_id: int, user_id: CurrentUserId, db: DbSession):
    """Odayı takip ediyorsan bırakır, etmiyorsan takip eder."""
    return RoomFollowResult(is_following=await room_service.toggle_room_follow(db, user_id, room_id))


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


# ── Moderasyon ────────────────────────────────────────────────────────────────
# Yetki kontrolleri moderation_service içinde yapılır (oda sahibi / yönetici).

@router.put("/{room_id}/admins/{target_id}", response_model=RoomOut)
async def add_admin(room_id: int, target_id: int, user_id: CurrentUserId, db: DbSession):
    """Kişiyi oda yöneticisi yapar. Yalnızca oda sahibi."""
    return await moderation_service.set_admin(db, user_id, room_id, target_id, make_admin=True)


@router.delete("/{room_id}/admins/{target_id}", response_model=RoomOut)
async def remove_admin(room_id: int, target_id: int, user_id: CurrentUserId, db: DbSession):
    """Kişinin yöneticiliğini alır. Yalnızca oda sahibi."""
    return await moderation_service.set_admin(db, user_id, room_id, target_id, make_admin=False)


@router.put("/{room_id}/seats/{seat_index}/lock", response_model=RoomOut)
async def lock_seat(room_id: int, seat_index: int, user_id: CurrentUserId, db: DbSession):
    """Koltuğu kilitler; doluysa oturan kişi indirilir."""
    return await moderation_service.set_seat_lock(db, user_id, room_id, seat_index, locked=True)


@router.delete("/{room_id}/seats/{seat_index}/lock", response_model=RoomOut)
async def unlock_seat(room_id: int, seat_index: int, user_id: CurrentUserId, db: DbSession):
    return await moderation_service.set_seat_lock(db, user_id, room_id, seat_index, locked=False)


@router.delete("/{room_id}/seats/{seat_index}/user", response_model=RoomOut)
async def remove_from_seat(room_id: int, seat_index: int, user_id: CurrentUserId, db: DbSession):
    """Koltuktaki kişiyi indirir; kişi dinleyici olarak odada kalır."""
    return await moderation_service.remove_from_seat(db, user_id, room_id, seat_index)


@router.post("/{room_id}/kicks/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def kick_from_room(room_id: int, target_id: int, user_id: CurrentUserId, db: DbSession):
    """Kişiyi odadan atar; bir süre (10 dk) geri giremez."""
    await moderation_service.kick_from_room(db, user_id, room_id, target_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
