"""
Oda yönetimi (moderasyon): roller, koltuklar, susturma, mesaj silme, odadan atma,
koltuğa davet, oda ayarları ve odayı kapatma.

ROLLER (yüksekten alçağa; tanımları room_service içinde):
  - host     → odanın sahibi (rooms.host_id). Her şeyi yapabilir, yönetici atar, odayı kapatır.
  - admin    → oda sahibinin atadığı yönetici.
  - vip      → odanın ayrıcalıklı üyesi; yönetim yetkisi yok.
  - listener → diğer herkes. Koltukta oturan "konuşmacı" da yetki bakımından listener'dır.

TEMEL KURAL: Bir işlem ancak kendinden ALT rütbedeki birine yapılabilir.
Yönetici, oda sahibine ya da başka bir yöneticiye dokunamaz.
Bütün yetki kontrolleri burada, sunucuda yapılır; istemcinin "ben yöneticiyim" demesine bakılmaz.
"""
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.demo.content import COVER_CHOICES
from app.models import Room, RoomMember
from app.realtime import events
from app.realtime.hub import room_hub
from app.realtime.state import room_state
from app.schemas.room import RoomMemberOut, RoomOut, RoomUpdateRequest
from app.services import notification_service, room_service, treasure_service, user_service
from app.services.room_service import ADMIN, HOST, LISTENER, ROLE_RANK
from app.voice import voice_provider

# Odadan atılan kişi bu kadar süre (saniye) odaya geri giremez.
KICK_BAN_SECONDS = 10 * 60
# Dinleyici listesinde en fazla bu kadar kişi gösterilir.
MEMBER_LIST_LIMIT = 200


async def _require_moderator(db: AsyncSession, room: Room, actor_id: int) -> str:
    """İşlemi yapan kişi oda sahibi ya da yönetici değilse hata fırlatır; rolünü döner."""
    role = await room_service.get_role(db, room, actor_id)
    if ROLE_RANK[role] < ROLE_RANK[ADMIN]:
        raise ForbiddenError("Bu işlem için oda yöneticisi olmalısın.", code="not_room_moderator")
    return role


async def _require_outranks(db: AsyncSession, room: Room, actor_id: int, actor_role: str, target_id: int) -> str:
    """İşlemi yapan kişi hedeften üst rütbede değilse hata fırlatır; hedefin rolünü döner."""
    if target_id == actor_id:
        raise AppError("Bu işlemi kendine yapamazsın.", code="cannot_target_self")
    target_role = await room_service.get_role(db, room, target_id)
    if ROLE_RANK[actor_role] <= ROLE_RANK[target_role]:
        raise ForbiddenError("Bu kişi üzerinde yetkin yok.", code="target_outranks_you")
    return target_role


async def _moderate(db: AsyncSession, room_id: int, actor_id: int, target_id: int) -> Room:
    """En sık kalıp: odayı bul, işlemi yapan yönetici mi ve hedeften üstün mü bak."""
    room = await room_service.get_room_row(db, room_id)
    actor_role = await _require_moderator(db, room, actor_id)
    await _require_outranks(db, room, actor_id, actor_role, target_id)
    await user_service.get_user(db, target_id)
    return room


async def _snapshot(db: AsyncSession, room: Room, viewer_id: int) -> RoomOut:
    return (await room_service.present_rooms(db, [room], viewer_id))[0]


async def _user_payload(db: AsyncSession, user_id: int) -> dict:
    user = await user_service.get_user(db, user_id)
    return (await user_service.present_user(db, user, viewer_id=None)).model_dump(mode="json")


# ── Dinleyici listesi (odadaki herkes görebilir) ──────────────────────────────

async def list_members(db: AsyncSession, viewer_id: int, room_id: int) -> list[RoomMemberOut]:
    """
    Odada şu an bulunan kişiler: önce oda sahibi ve yöneticiler, sonra koltuktakiler,
    sonra en son gelen dinleyiciler.
    """
    room = await room_service.get_room_row(db, room_id)
    user_ids = (await room_state.listener_ids(room.id))[-MEMBER_LIST_LIMIT:]
    if not user_ids:
        return []

    users = await user_service.load_users_out(db, set(user_ids), viewer_id)
    roles = await room_service.get_roles(db, room, user_ids)
    seats = (await room_state.get_seats([room.id]))[room.id]
    seat_of = {seat.user_id: seat.index for seat in seats if seat.user_id is not None}
    mic_blocked = (await room_state.mic_blocked_ids([room.id]))[room.id]
    chat_muted = await room_state.chat_mute_remaining(room.id, user_ids)

    arrival = {uid: index for index, uid in enumerate(user_ids)}
    ordered = sorted(
        (uid for uid in user_ids if uid in users),
        key=lambda uid: (-ROLE_RANK[roles[uid]], uid not in seat_of, -arrival[uid]),
    )
    return [
        RoomMemberOut(
            user=users[uid], role=roles[uid], seat_index=seat_of.get(uid),
            is_mic_blocked=uid in mic_blocked, chat_muted_seconds=chat_muted.get(uid, 0),
        )
        for uid in ordered
    ]


# ── Roller ────────────────────────────────────────────────────────────────────

async def set_role(db: AsyncSession, actor_id: int, room_id: int, target_id: int, role: str) -> RoomOut:
    """
    Kişinin odadaki rolünü değiştirir ("listener" = özel rolü geri al).
    Yönetici atamak ya da yöneticiliği almak yalnızca oda sahibinin işidir.
    VIP vermek/almak oda sahibi ve yöneticilerin işidir.
    """
    room = await room_service.get_room_row(db, room_id)
    if target_id == room.host_id:
        raise AppError("Oda sahibi zaten tam yetkili.", code="cannot_target_self")
    actor_role = await _require_moderator(db, room, actor_id)
    current = await _require_outranks(db, room, actor_id, actor_role, target_id)
    if ADMIN in (role, current) and actor_role != HOST:
        raise ForbiddenError("Yönetici atamayı yalnızca oda sahibi yapabilir.", code="not_room_host")
    await user_service.get_user(db, target_id)

    if role != current:
        await db.execute(delete(RoomMember).where(RoomMember.room_id == room.id, RoomMember.user_id == target_id))
        if role != LISTENER:
            db.add(RoomMember(room_id=room.id, user_id=target_id, role=role))
        await db.commit()

    snapshot = await _snapshot(db, room, actor_id)
    await room_hub.publish(room.id, events.ROOM_ROLES_UPDATED, {
        "admin_ids": snapshot.admin_ids, "vip_ids": snapshot.vip_ids,
    })
    if role != current and role != LISTENER:
        await notification_service.notify(
            db, target_id, "room_role",
            f"“{room.title}” odasında {'yönetici' if role == ADMIN else 'VIP'} yapıldın.",
            actor_id=actor_id, data={"room_id": room.id},
        )
    return snapshot


# ── Koltuk işlemleri ──────────────────────────────────────────────────────────

async def set_seat_lock(db: AsyncSession, actor_id: int, room_id: int, seat_index: int, locked: bool) -> RoomOut:
    """Koltuğu kilitler/açar. Doluysa ve yetki yetiyorsa önce oturan kişi indirilir."""
    room = await room_service.get_room_row(db, room_id)
    actor_role = await _require_moderator(db, room, actor_id)

    if locked:
        seats = (await room_state.get_seats([room.id]))[room.id]
        if not 0 <= seat_index < len(seats):
            raise NotFoundError("Koltuk bulunamadı.", code="seat_not_found")
        occupant = seats[seat_index].user_id
        if occupant is not None:
            await _require_outranks(db, room, actor_id, actor_role, occupant)
            await room_state.clear_seat(room.id, seat_index)
    await room_state.set_seat_locked(room.id, seat_index, locked)

    await room_service.publish_seats(db, room)
    return await _snapshot(db, room, actor_id)


async def remove_from_seat(db: AsyncSession, actor_id: int, room_id: int, seat_index: int) -> RoomOut:
    """Koltuktaki kişiyi indirir; kişi dinleyici olarak odada kalır."""
    room = await room_service.get_room_row(db, room_id)
    actor_role = await _require_moderator(db, room, actor_id)

    seats = (await room_state.get_seats([room.id]))[room.id]
    if not 0 <= seat_index < len(seats) or seats[seat_index].user_id is None:
        raise ConflictError("Bu koltuk zaten boş.", code="seat_empty")
    await _require_outranks(db, room, actor_id, actor_role, seats[seat_index].user_id)
    await room_state.clear_seat(room.id, seat_index)

    await room_service.publish_seats(db, room)
    return await _snapshot(db, room, actor_id)


async def invite_to_seat(db: AsyncSession, actor_id: int, room_id: int, target_id: int) -> None:
    """
    Odadaki bir dinleyiciyi koltuğa davet eder. Davet yalnızca o kişiye gider; kişi
    SEAT_INVITE_SECONDS içinde boş bir koltuğa oturabilir (koltuklar davetle açılsa bile).
    """
    room = await room_service.get_room_row(db, room_id)
    await _require_moderator(db, room, actor_id)
    if target_id == actor_id:
        raise AppError("Bu işlemi kendine yapamazsın.", code="cannot_target_self")
    if not await room_state.is_in_room(room.id, target_id):
        raise ConflictError("Bu kişi şu an odada değil.", code="not_in_room")
    if await room_state.seat_index_of(room.id, target_id) is not None:
        raise ConflictError("Bu kişi zaten koltukta.", code="already_seated")

    await room_state.grant_seat_invite(room.id, target_id, room_service.SEAT_INVITE_SECONDS)
    await room_hub.send_to_user(room.id, target_id, events.ROOM_SEAT_INVITE, {
        "by": await _user_payload(db, actor_id), "expires_in": room_service.SEAT_INVITE_SECONDS,
    })


# ── Mikrofon ve sohbet ────────────────────────────────────────────────────────

async def set_mic_blocked(db: AsyncSession, actor_id: int, room_id: int, target_id: int, blocked: bool) -> RoomOut:
    """
    Kişinin mikrofonunu kapatır ve kendisinin açmasını engeller (ya da engeli kaldırır).

    NOT: Engeli sunucu koltuk durumunda tutar ve herkese yayınlar; ses istemcisi buna
    uyar. Sesi sunucu tarafında da kesmek SFU'lu ses sağlayıcısıyla mümkündür
    (bkz. app/voice/).
    """
    room = await _moderate(db, room_id, actor_id, target_id)
    await room_state.set_mic_blocked(room.id, target_id, blocked)
    await room_service.publish_seats(db, room)
    return await _snapshot(db, room, actor_id)


async def set_chat_mute(db: AsyncSession, actor_id: int, room_id: int, target_id: int, minutes: int | None) -> None:
    """Kişiyi `minutes` dakika sohbete yazamaz yapar. None: susturmayı kaldırır."""
    room = await _moderate(db, room_id, actor_id, target_id)
    seconds = minutes * 60 if minutes else None
    await room_state.mute_chat(room.id, target_id, seconds)
    await room_hub.publish(room.id, events.ROOM_CHAT_MUTED, {
        "user": await _user_payload(db, target_id), "seconds": seconds or 0,
    })


async def delete_chat_message(db: AsyncSession, actor_id: int, room_id: int, message_id: str) -> None:
    """
    Sohbetteki bir mesajı herkesin ekranından kaldırır.
    Kişi kendi mesajını silebilir; başkasınınkini ancak ondan üst rütbedeki yönetici silebilir.
    """
    room = await room_service.get_room_row(db, room_id)
    message = next((m for m in await room_state.recent_chat(room.id) if m["id"] == message_id), None)
    if message is None:
        raise NotFoundError("Mesaj bulunamadı.", code="message_not_found")
    author_id = message["user"]["id"]
    if author_id != actor_id:
        actor_role = await _require_moderator(db, room, actor_id)
        await _require_outranks(db, room, actor_id, actor_role, author_id)

    await room_state.remove_chat(room.id, message_id)
    await room_hub.publish(room.id, events.CHAT_MESSAGE_DELETED, {"message_id": message_id})


# ── Odadan atma ───────────────────────────────────────────────────────────────

async def kick_from_room(db: AsyncSession, actor_id: int, room_id: int, target_id: int) -> None:
    """
    Kişiyi odadan atar: koltuğu boşalır, bağlantıları kapatılır ve KICK_BAN_SECONDS
    boyunca odaya geri giremez.
    """
    room = await _moderate(db, room_id, actor_id, target_id)

    await room_state.ban_from_room(room.id, target_id, KICK_BAN_SECONDS)
    if await room_state.leave_seat(room.id, target_id):
        await room_service.publish_seats(db, room)

    # Önce odaya duyur (atılan kişinin ekranı da bu mesajı alıp odadan çıkar), sonra bağlantısını kapat.
    await room_hub.publish(room.id, events.ROOM_USER_KICKED, {"user": await _user_payload(db, target_id)})
    await room_hub.disconnect_user(room.id, target_id, events.CLOSE_BANNED)
    await voice_provider.remove_participant(room.id, target_id)


# ── Oda ayarları ve odayı kapatma ─────────────────────────────────────────────

async def update_room(db: AsyncSession, actor_id: int, room_id: int, data: RoomUpdateRequest) -> RoomOut:
    """Oda adı, kategori, duyuru, kapak ve koltuk kuralı. Oda sahibi ve yöneticiler değiştirir."""
    room = await room_service.get_room_row(db, room_id)
    await _require_moderator(db, room, actor_id)

    changes = data.model_dump(exclude_unset=True)
    # `null` gönderilen alanları yok say: bu alanların hiçbiri boş bırakılamaz.
    changes = {field: value for field, value in changes.items() if value is not None}
    if "cover_url" in changes and changes["cover_url"] not in COVER_CHOICES:
        raise AppError("Bu kapak seçilemez.", code="invalid_cover")
    for field, value in changes.items():
        setattr(room, field, value)
    await db.commit()

    await room_hub.publish(room.id, events.ROOM_UPDATED, {
        "title": room.title, "category": room.category, "cover_url": room.cover_url,
        "announcement": room.announcement, "free_seating": room.free_seating,
    })
    return await _snapshot(db, room, actor_id)


async def close_room(db: AsyncSession, actor_id: int, room_id: int) -> None:
    """
    Odayı kapatır (yalnızca oda sahibi). Satır silinmez, `is_active = false` olur:
    hediye geçmişi gibi kayıtlar bu odaya bağlı kalmaya devam eder.
    """
    room = await room_service.get_room_row(db, room_id)
    if actor_id != room.host_id:
        raise ForbiddenError("Odayı yalnızca oda sahibi kapatabilir.", code="not_room_host")
    room.is_active = False
    room.is_live = False
    await db.commit()

    await room_hub.publish(room.id, events.ROOM_CLOSED, {})
    await room_hub.disconnect_room(room.id, events.CLOSE_ROOM_NOT_FOUND)
    await room_state.drop_room(room.id)
    treasure_service.drop_room(room.id)
    await voice_provider.close_room(room.id)
