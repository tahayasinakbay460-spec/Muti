"""
Oda yönetimi (moderasyon): yönetici atama, koltuk kilitleme, koltuktan indirme, odadan atma.

ROLLER (yüksekten alçağa):
  - host     → odanın sahibi (rooms.host_id). Her şeyi yapabilir, yönetici atar.
  - admin    → oda sahibinin atadığı yönetici (room_admins tablosu).
  - listener → diğer herkes. Koltukta oturan "konuşmacı" da yetki bakımından listener'dır.

TEMEL KURAL: Bir işlem ancak kendinden ALT rütbedeki birine yapılabilir.
Yönetici, oda sahibini ya da başka bir yöneticiyi koltuktan indiremez/atamaz.
Bütün yetki kontrolleri burada, sunucuda yapılır; istemcinin "ben yöneticiyim" demesine bakılmaz.
"""
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.models import Room, RoomAdmin
from app.realtime import events
from app.realtime.hub import room_hub
from app.realtime.state import room_state
from app.schemas.room import RoomOut
from app.services import room_service, user_service

HOST, ADMIN, LISTENER = "host", "admin", "listener"
_RANK = {HOST: 3, ADMIN: 2, LISTENER: 1}

# Odadan atılan kişi bu kadar süre (saniye) odaya geri giremez.
KICK_BAN_SECONDS = 10 * 60


async def get_role(db: AsyncSession, room: Room, user_id: int) -> str:
    if user_id == room.host_id:
        return HOST
    is_admin = await db.scalar(
        select(RoomAdmin.user_id).where(RoomAdmin.room_id == room.id, RoomAdmin.user_id == user_id)
    )
    return ADMIN if is_admin is not None else LISTENER


async def _require_moderator(db: AsyncSession, room: Room, actor_id: int) -> str:
    """İşlemi yapan kişi oda sahibi ya da yönetici değilse hata fırlatır; rolünü döner."""
    role = await get_role(db, room, actor_id)
    if role == LISTENER:
        raise ForbiddenError("Bu işlem için oda yöneticisi olmalısın.", code="not_room_moderator")
    return role


async def _require_outranks(db: AsyncSession, room: Room, actor_id: int, actor_role: str, target_id: int) -> None:
    """İşlemi yapan kişi hedeften üst rütbede değilse hata fırlatır."""
    if target_id == actor_id:
        raise AppError("Bu işlemi kendine yapamazsın.", code="cannot_target_self")
    if _RANK[actor_role] <= _RANK[await get_role(db, room, target_id)]:
        raise ForbiddenError("Bu kişi üzerinde yetkin yok.", code="target_outranks_you")


async def _snapshot(db: AsyncSession, room: Room, viewer_id: int) -> RoomOut:
    return (await room_service.present_rooms(db, [room], viewer_id))[0]


# ── Yönetici atama (yalnızca oda sahibi) ──────────────────────────────────────

async def set_admin(db: AsyncSession, actor_id: int, room_id: int, target_id: int, make_admin: bool) -> RoomOut:
    room = await room_service.get_room_row(db, room_id)
    if actor_id != room.host_id:
        raise ForbiddenError("Yönetici atamayı yalnızca oda sahibi yapabilir.", code="not_room_host")
    if target_id == room.host_id:
        raise AppError("Oda sahibi zaten tam yetkili.", code="cannot_target_self")
    await user_service.get_user(db, target_id)

    if make_admin:
        db.add(RoomAdmin(room_id=room.id, user_id=target_id))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()   # zaten yöneticiymiş; sonuç aynı
    else:
        await db.execute(delete(RoomAdmin).where(RoomAdmin.room_id == room.id, RoomAdmin.user_id == target_id))
        await db.commit()

    snapshot = await _snapshot(db, room, actor_id)
    await room_hub.publish(room.id, events.ROOM_ROLES_UPDATED, {"admin_ids": snapshot.admin_ids})
    return snapshot


# ── Koltuk işlemleri (oda sahibi ve yöneticiler) ──────────────────────────────

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


# ── Odadan atma (oda sahibi ve yöneticiler) ───────────────────────────────────

async def kick_from_room(db: AsyncSession, actor_id: int, room_id: int, target_id: int) -> None:
    """
    Kişiyi odadan atar: koltuğu boşalır, bağlantıları kapatılır ve KICK_BAN_SECONDS
    boyunca odaya geri giremez.
    """
    room = await room_service.get_room_row(db, room_id)
    actor_role = await _require_moderator(db, room, actor_id)
    await _require_outranks(db, room, actor_id, actor_role, target_id)
    target = await user_service.get_user(db, target_id)

    await room_state.ban_from_room(room.id, target_id, KICK_BAN_SECONDS)
    if await room_state.leave_seat(room.id, target_id):
        await room_service.publish_seats(db, room)

    # Önce odaya duyur (atılan kişinin ekranı da bu mesajı alıp odadan çıkar), sonra bağlantısını kapat.
    user_payload = (await user_service.present_user(db, target, viewer_id=None)).model_dump(mode="json")
    await room_hub.publish(room.id, events.ROOM_USER_KICKED, {"user": user_payload})
    await room_hub.disconnect_user(room.id, target_id, events.CLOSE_BANNED)
