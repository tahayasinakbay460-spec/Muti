"""
/api/v1/rooms — oda listesi, oda oluşturma ve ayarları, oda takibi, koltuk ve mikrofon işlemleri, moderasyon.
"""
from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.core.deps import CurrentUserId, DbSession
from app.schemas.room import (
    ChatMuteRequest, RoomCreateRequest, RoomFollowResult, RoomMemberOut, RoomOut, RoomRoleRequest, RoomUpdateRequest,
)
from app.schemas.store import ChestClaimResult, ChestOut
from app.services import moderation_service, room_service, treasure_service
from app.voice import VoiceJoinInfo

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


@router.patch("/{room_id}", response_model=RoomOut)
async def update_room(room_id: int, data: RoomUpdateRequest, user_id: CurrentUserId, db: DbSession):
    """Oda ayarlarını değiştirir (ad, kategori, duyuru, kapak, koltuk kuralı). Oda sahibi ve yöneticiler."""
    return await moderation_service.update_room(db, user_id, room_id, data)


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def close_room(room_id: int, user_id: CurrentUserId, db: DbSession):
    """Odayı kapatır; içerideki herkes çıkarılır. Yalnızca oda sahibi."""
    await moderation_service.close_room(db, user_id, room_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{room_id}/members", response_model=list[RoomMemberOut])
async def list_members(room_id: int, user_id: CurrentUserId, db: DbSession):
    """Odada şu an bulunan kişiler (dinleyici listesi), rolleriyle."""
    return await moderation_service.list_members(db, user_id, room_id)


@router.get("/{room_id}/voice", response_model=VoiceJoinInfo)
async def get_voice_join(room_id: int, user_id: CurrentUserId, db: DbSession):
    """
    Odanın sesine bağlanma bilgisi. Cevabın biçimi sunucudaki ses sağlayıcısına göre
    değişir (`provider`: "mesh", "livekit" ya da "agora"); istemci buna göre bağlanır.
    """
    return await room_service.get_voice_join(db, user_id, room_id)


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

@router.put("/{room_id}/roles/{target_id}", response_model=RoomOut)
async def set_role(room_id: int, target_id: int, data: RoomRoleRequest, user_id: CurrentUserId, db: DbSession):
    """
    Kişinin odadaki rolünü değiştirir: "admin", "vip" ya da "listener" (rolü geri al).
    Yönetici yalnızca oda sahibi tarafından atanır; VIP'i yöneticiler de verebilir.
    """
    return await moderation_service.set_role(db, user_id, room_id, target_id, data.role)


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


@router.post("/{room_id}/seat-invites/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def invite_to_seat(room_id: int, target_id: int, user_id: CurrentUserId, db: DbSession):
    """Odadaki bir dinleyiciyi koltuğa davet eder (60 sn geçerli)."""
    await moderation_service.invite_to_seat(db, user_id, room_id, target_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{room_id}/mic-blocks/{target_id}", response_model=RoomOut)
async def block_mic(room_id: int, target_id: int, user_id: CurrentUserId, db: DbSession):
    """Kişinin mikrofonunu kapatır; engel kalkana kadar kendisi açamaz."""
    return await moderation_service.set_mic_blocked(db, user_id, room_id, target_id, blocked=True)


@router.delete("/{room_id}/mic-blocks/{target_id}", response_model=RoomOut)
async def unblock_mic(room_id: int, target_id: int, user_id: CurrentUserId, db: DbSession):
    return await moderation_service.set_mic_blocked(db, user_id, room_id, target_id, blocked=False)


@router.put("/{room_id}/chat-mutes/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def mute_chat(room_id: int, target_id: int, data: ChatMuteRequest, user_id: CurrentUserId, db: DbSession):
    """Kişiyi belirli bir süre sohbete yazamaz yapar."""
    await moderation_service.set_chat_mute(db, user_id, room_id, target_id, data.minutes)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{room_id}/chat-mutes/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unmute_chat(room_id: int, target_id: int, user_id: CurrentUserId, db: DbSession):
    await moderation_service.set_chat_mute(db, user_id, room_id, target_id, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{room_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_message(
    room_id: int, message_id: Annotated[str, Path(max_length=32)], user_id: CurrentUserId, db: DbSession,
):
    """Sohbetteki bir mesajı siler: kendi mesajını herkes, başkasınınkini yönetici."""
    await moderation_service.delete_chat_message(db, user_id, room_id, message_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{room_id}/chest", response_model=ChestOut)
async def get_chest(room_id: int, user_id: CurrentUserId, db: DbSession):
    """Odanın hazine sandığı: dolum durumu ya da açıksa kalan coin ve bitiş anı."""
    await room_service.get_room_row(db, room_id)
    return treasure_service.get_chest(room_id, user_id)


@router.post("/{room_id}/chest/claim", response_model=ChestClaimResult)
async def claim_chest(room_id: int, user_id: CurrentUserId, db: DbSession):
    """Açık sandıktan coin kapar (kişi başı bir kez, odada olmak gerekir). Miktarı sunucu çeker."""
    await room_service.get_room_row(db, room_id)
    return await treasure_service.claim(db, room_id, user_id)
