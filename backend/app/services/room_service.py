"""
Odalar: listeleme, oluşturma, koltuğa oturma/kalkma, mikrofon.

Bir odanın bilgisi iki yerden gelir ve burada birleştirilir:
  - kalıcı bilgiler (ad, sahip, kategori)      → veritabanı (models/room.py)
  - canlı bilgiler (koltuklar, dinleyici sayısı) → canlı durum deposu (realtime/state.py)
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models import Room
from app.realtime import events
from app.realtime.hub import room_hub
from app.realtime.state import room_state
from app.schemas.room import RoomCreateRequest, RoomOut, SeatOut
from app.services import user_service

# DEMO KISAYOLU: Yeni odaların kapağı frontend'in kendi klasöründeki sabit bir görsel.
# Görsel yükleme (upload) eklenince oda sahibi kendi kapağını seçecek.
DEFAULT_COVER_URL = "assets/covers/sky.jpg"


async def _get_room_row(db: AsyncSession, room_id: int) -> Room:
    room = await db.get(Room, room_id)
    if room is None or not room.is_active:
        raise NotFoundError("Oda bulunamadı.")
    # Koltukları canlı depoda yoksa oluştur (ör. sunucu yeniden başladıktan sonra).
    await room_state.ensure_room(room.id, room.seat_count)
    return room


async def present_rooms(db: AsyncSession, rooms: list[Room], viewer_id: int | None) -> list[RoomOut]:
    """
    Oda satırlarını canlı bilgilerle birleştirip JSON'a hazırlar.
    Kaç oda olursa olsun kullanıcılar için TEK veritabanı sorgusu atılır.
    """
    if not rooms:
        return []
    room_ids = [room.id for room in rooms]
    for room in rooms:
        await room_state.ensure_room(room.id, room.seat_count)

    seats_by_room = await room_state.get_seats(room_ids)
    listener_counts = await room_state.listener_counts(room_ids)
    ranks = await room_state.room_ranks(room_ids)

    # Ekranda görünecek herkesin id'sini topla: oda sahipleri + koltukta oturanlar.
    user_ids = {room.host_id for room in rooms}
    for seats in seats_by_room.values():
        user_ids.update(seat.user_id for seat in seats if seat.user_id is not None)
    users = await user_service.load_users_out(db, user_ids, viewer_id)

    return [
        RoomOut(
            id=room.id,
            title=room.title,
            category=room.category,
            cover_url=room.cover_url,
            is_live=room.is_live,
            listener_count=listener_counts[room.id],
            host_id=room.host_id,
            hourly_rank=ranks[room.id],
            announcement=room.announcement,
            host=users[room.host_id],
            seats=[
                SeatOut(
                    index=seat.index, user_id=seat.user_id, is_muted=seat.is_muted,
                    is_locked=seat.is_locked, user=users.get(seat.user_id),
                )
                for seat in seats_by_room[room.id]
            ],
        )
        for room in rooms
    ]


async def list_rooms(
    db: AsyncSession, viewer_id: int, category: str = "", query: str = "", limit: int = 30, offset: int = 0,
) -> list[RoomOut]:
    statement = select(Room).where(Room.is_active)
    # "for_you" gerçek bir kategori değil, "hepsi" demek.
    if category and category != "for_you":
        statement = statement.where(Room.category == category)
    if query.strip():
        # Kullanıcının yazdığı % ve _ işaretleri SQL'de "joker" anlamına gelir;
        # onları düz karakter sayılsın diye kaçırıyoruz.
        escaped = query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(Room.title.ilike(f"%{escaped}%", escape="\\"))
    statement = statement.order_by(Room.id.desc()).limit(limit).offset(offset)

    rooms = await present_rooms(db, list(await db.scalars(statement)), viewer_id)
    # DEMO KISAYOLU: Yalnızca bu sayfadaki odaları kalabalıktan tenhaya sıralıyoruz.
    # Canlıda "en popüler odalar" sıralaması Redis'ten gelecek, sayfa ona göre çekilecek.
    rooms.sort(key=lambda room: room.listener_count, reverse=True)
    return rooms


async def get_room(db: AsyncSession, viewer_id: int, room_id: int) -> RoomOut:
    room = await _get_room_row(db, room_id)
    return (await present_rooms(db, [room], viewer_id))[0]


async def create_room(db: AsyncSession, host_id: int, data: RoomCreateRequest) -> RoomOut:
    room = Room(
        title=data.title,
        category=data.category,
        cover_url=DEFAULT_COVER_URL,
        announcement="Odaya hoş geldin!",
        host_id=host_id,
    )
    db.add(room)
    await db.commit()

    # Oda sahibi otomatik olarak 0 numaralı koltuğa oturur.
    await room_state.ensure_room(room.id, room.seat_count)
    await room_state.take_seat(room.id, 0, host_id)
    return (await present_rooms(db, [room], host_id))[0]


# ── Koltuk işlemleri ──────────────────────────────────────────────────────────
# Üçü de aynı kalıbı izler: odayı doğrula → canlı depoda değişikliği yap →
# odadaki herkese yeni koltuk düzenini yayınla → isteği atana odanın son halini dön.

async def take_seat(db: AsyncSession, user_id: int, room_id: int, seat_index: int) -> RoomOut:
    room = await _get_room_row(db, room_id)
    await room_state.take_seat(room.id, seat_index, user_id)
    await publish_seats(db, room)
    return (await present_rooms(db, [room], user_id))[0]


async def leave_seat(db: AsyncSession, user_id: int, room_id: int) -> RoomOut:
    room = await _get_room_row(db, room_id)
    if await room_state.leave_seat(room.id, user_id):
        await publish_seats(db, room)
    return (await present_rooms(db, [room], user_id))[0]


async def toggle_mute(db: AsyncSession, user_id: int, room_id: int) -> RoomOut:
    room = await _get_room_row(db, room_id)
    if not await room_state.toggle_mute(room.id, user_id):
        raise ConflictError("Önce bir koltuğa oturmalısın.", code="not_seated")
    await publish_seats(db, room)
    return (await present_rooms(db, [room], user_id))[0]


async def publish_seats(db: AsyncSession, room: Room) -> None:
    """
    Koltukların son halini odadaki herkese yayınlar.
    Yayın herkese aynı gittiği için kişiye özel alanlar (is_me, is_following) boştur;
    istemci "bu ben miyim" kontrolünü kullanıcı id'si ile kendisi yapar.
    """
    snapshot = (await present_rooms(db, [room], viewer_id=None))[0]
    await room_hub.publish(room.id, events.ROOM_SEATS_UPDATED, {
        "seats": [seat.model_dump(mode="json") for seat in snapshot.seats],
    })
