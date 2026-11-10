"""
Odalar: listeleme, oluşturma, takip, koltuğa oturma/kalkma, mikrofon.

Bir odanın bilgisi iki yerden gelir ve burada birleştirilir:
  - kalıcı bilgiler (ad, sahip, kategori)      → veritabanı (models/room.py)
  - canlı bilgiler (koltuklar, dinleyici sayısı) → canlı durum deposu (realtime/state.py)
"""
from sqlalchemy import case, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal, utcnow
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.timefmt import period_start
from app.models import Room, RoomFollow, RoomMember, RoomVisit, Transaction, User
from app.realtime import events
from app.realtime.hub import room_hub
from app.realtime.state import room_state
from app.schemas.room import CountryRoomCount, MyRoomStats, RoomCreateRequest, RoomOut, SeatOut
from app.schemas.user import UserOut
from app.services import user_service
from app.voice import VoiceJoinInfo, voice_provider

# ── Oda rolleri ───────────────────────────────────────────────────────────────
# Yüksekten alçağa: host (oda sahibi) > admin (yönetici) > vip > listener (herkes).
# Koltukta oturan "konuşmacı" da yetki bakımından listener'dır.
HOST, ADMIN, VIP, LISTENER = "host", "admin", "vip", "listener"
ROLE_RANK = {HOST: 4, ADMIN: 3, VIP: 2, LISTENER: 1}

# Koltuğa davet edilen kişi bu süre içinde oturmazsa davet geçersiz olur.
SEAT_INVITE_SECONDS = 60


async def get_role(db: AsyncSession, room: Room, user_id: int) -> str:
    if user_id == room.host_id:
        return HOST
    role = await db.scalar(
        select(RoomMember.role).where(RoomMember.room_id == room.id, RoomMember.user_id == user_id)
    )
    return role or LISTENER


async def require_moderator(db: AsyncSession, room: Room, user_id: int) -> str:
    """Kişi oda sahibi ya da yönetici değilse hata fırlatır; rolünü döner. (Yetki her zaman sunucuda.)"""
    role = await get_role(db, room, user_id)
    if ROLE_RANK[role] < ROLE_RANK[ADMIN]:
        raise ForbiddenError("Bu işlem için oda yöneticisi olmalısın.", code="not_room_moderator")
    return role


async def get_roles(db: AsyncSession, room: Room, user_ids: list[int]) -> dict[int, str]:
    """Birden çok kişinin rolü, tek sorguyla (dinleyici listesi için)."""
    roles = {uid: LISTENER for uid in user_ids}
    rows = await db.execute(
        select(RoomMember.user_id, RoomMember.role)
        .where(RoomMember.room_id == room.id, RoomMember.user_id.in_(user_ids))
    )
    roles.update({uid: role for uid, role in rows})
    if room.host_id in roles:
        roles[room.host_id] = HOST
    return roles


# DEMO KISAYOLU: Yeni odaların kapağı frontend'in kendi klasöründeki sabit bir görsel.
# Görsel yükleme (upload) eklenince oda sahibi kendi kapağını seçecek.
DEFAULT_COVER_URL = "assets/covers/sky.jpg"


async def get_room_row(db: AsyncSession, room_id: int) -> Room:
    room = await db.get(Room, room_id)
    if room is None or not room.is_active:
        raise NotFoundError("Oda bulunamadı.")
    # Koltukları canlı depoda yoksa oluştur (ör. sunucu yeniden başladıktan sonra).
    await room_state.ensure_room(room.id, room.seat_count)
    return room


def _camera_user_ids() -> dict[int, int]:
    # live_service de bu dosyayı içe aktarıyor; döngü olmasın diye çağrı anında alıyoruz.
    from app.services import live_service
    return live_service.camera_user_ids()


def _running_pk_room_ids() -> set[int]:
    # activity_service bu dosyayı içe aktarıyor; döngü olmasın diye burada, çağrı anında alıyoruz.
    from app.services import activity_service
    return activity_service.running_pk_room_ids()


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

    seats_by_room = await room_state.get_seats(room_ids)# odaların koltuk durumları 
    listener_counts = await room_state.listener_counts(room_ids)#kac dinleyici var
    ranks = await room_state.room_ranks(room_ids)#oda sıralaması (canlı depoda tutuluyor, Redis'ten gelecek)
    mic_blocked = await room_state.mic_blocked_ids(room_ids)

    # Ekranda görünecek herkesin id'sini topla: oda sahipleri + koltukta oturanlar.
    user_ids = {room.host_id for room in rooms}
    for seats in seats_by_room.values():
        user_ids.update(seat.user_id for seat in seats if seat.user_id is not None)
    users = await user_service.load_users_out(db, user_ids, viewer_id)

    # Odaların yöneticileri ve VIP'leri (tek sorgu).
    member_ids: dict[tuple[int, str], list[int]] = {}
    for room_id, member_id, role in await db.execute(
        select(RoomMember.room_id, RoomMember.user_id, RoomMember.role)
        .where(RoomMember.room_id.in_(room_ids)).order_by(RoomMember.created_at)
    ):
        member_ids.setdefault((room_id, role), []).append(member_id)

    pk_room_ids = _running_pk_room_ids()
    cameras = _camera_user_ids()

    # Bakan kişinin bu odalardan hangilerini takip ettiği (tek sorgu).
    followed_ids: set[int] = set()
    if viewer_id is not None:
        followed_ids = set(await db.scalars(
            select(RoomFollow.room_id).where(RoomFollow.user_id == viewer_id, RoomFollow.room_id.in_(room_ids))
        ))

    return [
        RoomOut(
            id=room.id,
            title=room.title,
            category=room.category,
            kind=room.kind,
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
                    is_mic_blocked=seat.user_id in mic_blocked[room.id],
                )
                for seat in seats_by_room[room.id]
            ],
            admin_ids=member_ids.get((room.id, ADMIN), []),
            vip_ids=member_ids.get((room.id, VIP), []),
            free_seating=room.free_seating,
            is_following=room.id in followed_ids,
            has_pk=room.id in pk_room_ids,
            camera_user_id=cameras.get(room.id),
        )
        for room in rooms
    ]


# Odalar > Canlı sekmesinde en fazla kaç aday oda taranır (bkz. _live_room_ids).
LIVE_SCAN_LIMIT = 500


async def _live_room_ids(candidates: list[Room]) -> list[int]:
    """
    "Canlı" = şu an yayında olan kameralı yayınlar (en üstte) + koltuğunda (mikrofonda) en az bir kişi
    olan sesli odalar; her grup kalabalıktan tenhaya. Yayını kapalı kameralı yayın odası görünmez.
    Koltuklar veritabanında değil canlı depoda durduğu için filtre burada, Python'da yapılır.
    DEMO KISAYOLU: aday odaları tek tek tarıyoruz; canlıda Redis'te "mikrofonu dolu odalar"
    sıralı kümesi (sorted set) tutulur ve sayfa doğrudan oradan okunur.
    """
    if not candidates:
        return []
    candidate_ids = [room.id for room in candidates]
    seats = await room_state.get_seats(candidate_ids)
    counts = await room_state.listener_counts(candidate_ids)
    cameras = _camera_user_ids()

    def is_live(room: Room) -> bool:
        if room.kind == "live":
            return room.id in cameras
        return any(seat.user_id is not None for seat in seats.get(room.id, []))

    live = [room.id for room in candidates if is_live(room)]
    return sorted(live, key=lambda rid: (rid in cameras, counts.get(rid, 0)), reverse=True)


async def list_rooms(
    db: AsyncSession, viewer_id: int, category: str = "", query: str = "", limit: int = 30, offset: int = 0,
    country: str = "",
) -> list[RoomOut]:
    statement = select(Room).where(Room.is_active)
    # Ülke filtresi oda sahibinin ülkesine bakar ("Türkiye'deki yayıncılar"). Boşsa Genel: hepsi.
    if country:
        statement = statement.join(User, User.id == Room.host_id).where(User.country == country.upper())
    if category == "live":
        candidates = list(await db.scalars(statement.order_by(Room.id.desc()).limit(LIVE_SCAN_LIMIT)))
        for room in candidates:
            await room_state.ensure_room(room.id, room.seat_count)
        by_id = {room.id: room for room in candidates}
        page_ids = (await _live_room_ids(candidates))[offset:offset + limit]
        return await present_rooms(db, [by_id[rid] for rid in page_ids], viewer_id)
    # Kameralı yayınlar yalnızca Canlı sekmesinde (yayındayken) görünür; diğer listeler sesli odalar.
    statement = statement.where(Room.kind == "voice")
    # "for_you" gerçek bir kategori değil, "hepsi" demek. "pk" de kategori değil: PK'si süren odalar.
    if category == "pk":
        statement = statement.where(Room.id.in_(_running_pk_room_ids() or {0}))
    elif category and category != "for_you":
        statement = statement.where(Room.category == category)
    if query.strip():
        # Kullanıcının yazdığı % ve _ işaretleri SQL'de "joker" anlamına gelir;
        # onları düz karakter sayılsın diye kaçırıyoruz.
        text = query.strip()
        escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        condition = Room.title.ilike(f"%{escaped}%", escape="\\")
        # Rakamsa oda numarasıyla da ara: kullanıcılar birbirine oda ID'si söyleyerek davet eder.
        if text.isdigit():
            condition = or_(condition, Room.id == int(text))
        statement = statement.where(condition)
    statement = statement.order_by(Room.id.desc()).limit(limit).offset(offset)

    rooms = await present_rooms(db, list(await db.scalars(statement)), viewer_id)
    # DEMO KISAYOLU: Yalnızca bu sayfadaki odaları kalabalıktan tenhaya sıralıyoruz.
    # Canlıda "en popüler odalar" sıralaması Redis'ten gelecek, sayfa ona göre çekilecek.
    rooms.sort(key=lambda room: room.listener_count, reverse=True)
    return rooms


async def get_room(db: AsyncSession, viewer_id: int, room_id: int) -> RoomOut:
    room = await get_room_row(db, room_id)
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


# ── Oda takibi ────────────────────────────────────────────────────────────────

async def toggle_room_follow(db: AsyncSession, user_id: int, room_id: int) -> bool:
    """Odayı takip ediyorsa bırakır, etmiyorsa takip eder. Yeni durumu döner (True = takipte)."""
    await get_room_row(db, room_id)

    # Önce silmeyi dene: bir satır silindiyse zaten takip ediyormuş → artık etmiyor.
    deleted = await db.execute(
        delete(RoomFollow).where(RoomFollow.user_id == user_id, RoomFollow.room_id == room_id)
    )
    if deleted.rowcount:
        await db.commit()
        return False

    db.add(RoomFollow(user_id=user_id, room_id=room_id))
    try:
        await db.commit()
    except IntegrityError:
        # Aynı anda gelen ikinci istek (çift tıklama) satırı bizden önce eklemiş; sonuç yine "takipte".
        await db.rollback()
    return True


async def list_room_countries(db: AsyncSession) -> list[CountryRoomCount]:
    """Açık odası olan ülkeler, en çok odası olan en başta (Keşfet'teki bayrak çipleri)."""
    rows = await db.execute(
        select(User.country, func.count(Room.id))
        .join(User, User.id == Room.host_id)
        .where(Room.is_active, Room.kind == "voice", User.country.is_not(None))
        .group_by(User.country)
        .order_by(func.count(Room.id).desc(), User.country)
    )
    return [CountryRoomCount(country=code, room_count=count) for code, count in rows]


# ── Son girdiğim odalar ───────────────────────────────────────────────────────

RECENT_ROOMS_LIMIT = 20


async def record_visit(user_id: int, room_id: int) -> None:
    """
    Kişi odaya girince çağrılır (oda WebSocket'i). İlk girişte satır eklenir, sonrakilerde
    yalnızca zaman güncellenir. WebSocket'in açık veritabanı oturumu olmadığı için kendi
    oturumunu açar.
    """
    async with SessionLocal() as db:
        now = utcnow()
        touched = await db.execute(
            update(RoomVisit).where(RoomVisit.user_id == user_id, RoomVisit.room_id == room_id).values(visited_at=now)
        )
        if not touched.rowcount:
            db.add(RoomVisit(user_id=user_id, room_id=room_id, visited_at=now))
        try:
            await db.commit()
        except IntegrityError:
            # Aynı kişi aynı anda iki sekmeden girdi: satırı öteki ekledi, yeterli.
            await db.rollback()


async def list_recent_rooms(db: AsyncSession, user_id: int) -> list[RoomOut]:
    """En son girdiğim açık odalar, en yeni en üstte. Kendi odalarım "Odam" bölümünde, burada yok."""
    rooms = await db.scalars(
        select(Room)
        .join(RoomVisit, RoomVisit.room_id == Room.id)
        .where(RoomVisit.user_id == user_id, Room.is_active, Room.host_id != user_id)
        .order_by(RoomVisit.visited_at.desc())
        .limit(RECENT_ROOMS_LIMIT)
    )
    return await present_rooms(db, list(rooms), user_id)


async def list_followed_rooms(db: AsyncSession, user_id: int, limit: int = 50) -> list[RoomOut]:
    """Kullanıcının takip ettiği açık odalar, en son takip edilen en üstte."""
    rooms = await db.scalars(
        select(Room)
        .join(RoomFollow, RoomFollow.room_id == Room.id)
        .where(RoomFollow.user_id == user_id, Room.is_active)
        .order_by(RoomFollow.created_at.desc())
        .limit(limit)
    )
    return await present_rooms(db, list(rooms), user_id)


# ── Yayın odam (oda sahibinin istatistikleri) ─────────────────────────────────

async def list_my_rooms(db: AsyncSession, user_id: int) -> list[MyRoomStats]:
    """
    Sahibi olduğum açık odalar, her biri için takipçi ve hediye sayıları.
    Hediye bilgisi para defterinden (transactions, gift_received) toplanır: ayrı sayaç tutmuyoruz,
    böylece sayılar her zaman defterle aynıdır.
    DEMO KISAYOLU: her istekte toplanıyor; canlıda günlük özet tablosu kullanılır.
    """
    rooms = list(await db.scalars(
        select(Room).where(Room.host_id == user_id, Room.is_active, Room.kind == "voice").order_by(Room.id.desc())
    ))
    if not rooms:
        return []
    room_ids = [room.id for room in rooms]
    followers = dict((await db.execute(
        select(RoomFollow.room_id, func.count()).where(RoomFollow.room_id.in_(room_ids)).group_by(RoomFollow.room_id)
    )).all())

    received = (Transaction.type == "gift_received") & Transaction.room_id.in_(room_ids)
    # Toplam ve bu ay aynı satırlardan çıkar: iki ayrı tarama yerine tek sorgu, ay için CASE.
    month_amount = case((Transaction.created_at >= period_start("month"), Transaction.amount), else_=0)
    totals = {
        room_id: (count, diamonds, month) for room_id, count, diamonds, month in await db.execute(
            select(Transaction.room_id, func.coalesce(func.sum(Transaction.quantity), 0),
                   func.sum(Transaction.amount), func.sum(month_amount))
            .where(received).group_by(Transaction.room_id)
        )
    }

    return [
        MyRoomStats(
            room=out, follower_count=followers.get(out.id, 0),
            gift_count=int(totals.get(out.id, (0, 0, 0))[0]), gift_diamonds=int(totals.get(out.id, (0, 0, 0))[1]),
            month_gift_diamonds=int(totals.get(out.id, (0, 0, 0))[2]),
        )
        for out in await present_rooms(db, rooms, user_id)
    ]


async def list_room_followers(db: AsyncSession, user_id: int, room_id: int) -> list[UserOut]:
    """Odayı takip edenler, en yeni en üstte. Yalnızca oda sahibi ve yöneticiler görür."""
    room = await get_room_row(db, room_id)
    await require_moderator(db, room, user_id)
    users = await db.scalars(
        select(User).join(RoomFollow, RoomFollow.user_id == User.id)
        .where(RoomFollow.room_id == room_id, User.is_active)
        .order_by(RoomFollow.created_at.desc()).limit(200)
    )
    return await user_service.present_users(db, list(users), user_id)


# ── Koltuk işlemleri ──────────────────────────────────────────────────────────
# Üçü de aynı kalıbı izler: odayı doğrula → canlı depoda değişikliği yap →
# odadaki herkese yeni koltuk düzenini yayınla → isteği atana odanın son halini dön.

async def take_seat(db: AsyncSession, user_id: int, room_id: int, seat_index: int) -> RoomOut:
    room = await get_room_row(db, room_id)
    # Odadan atılan kişi yasak süresince WebSocket'e bağlanamaz; REST ile koltuğa da oturamasın.
    if await room_state.is_banned(room.id, user_id):
        raise ForbiddenError("Bu odadan çıkarıldın, bir süre giremezsin.", code="room_banned")
    # Koltuklar davetle açılıyorsa: oda sahibi, yönetici ve VIP kendisi oturur; zaten
    # koltukta olan başka koltuğa geçebilir; diğerleri geçerli bir davet ister.
    used_invite = False
    if not room.free_seating and ROLE_RANK[await get_role(db, room, user_id)] < ROLE_RANK[VIP]:
        already_seated = await room_state.seat_index_of(room.id, user_id) is not None
        if not already_seated:
            used_invite = await room_state.consume_seat_invite(room.id, user_id)
            if not used_invite:
                raise ForbiddenError("Bu odada koltuğa davetle oturulur.", code="seat_requires_invite")
    try:
        await room_state.take_seat(room.id, seat_index, user_id)
    except Exception:
        # Koltuk dolu/kilitliydi: davet boşa gitmesin, başka koltuk deneyebilsin.
        if used_invite:
            await room_state.grant_seat_invite(room.id, user_id, SEAT_INVITE_SECONDS)
        raise
    await publish_seats(db, room)
    return (await present_rooms(db, [room], user_id))[0]


async def leave_seat(db: AsyncSession, user_id: int, room_id: int) -> RoomOut:
    room = await get_room_row(db, room_id)
    if await room_state.leave_seat(room.id, user_id):
        await publish_seats(db, room)
    return (await present_rooms(db, [room], user_id))[0]


async def toggle_mute(db: AsyncSession, user_id: int, room_id: int) -> RoomOut:
    room = await get_room_row(db, room_id)
    if user_id in (await room_state.mic_blocked_ids([room.id]))[room.id]:
        raise ForbiddenError("Mikrofonun bir yönetici tarafından kapatıldı.", code="mic_blocked")
    if not await room_state.toggle_mute(room.id, user_id):
        raise ConflictError("Önce bir koltuğa oturmalısın.", code="not_seated")
    await publish_seats(db, room)
    return (await present_rooms(db, [room], user_id))[0]


async def present_seats(db: AsyncSession, room: Room) -> list[SeatOut]:
    """
    Yalnızca koltuklar, herkese aynı giden biçimde (viewer yok). `present_rooms` ile birebir
    aynı SeatOut üretir; ama oda sırası, dinleyici sayısı, yönetici listesi gibi koltuk
    yayınında kullanılmayan bilgileri hesaplamaz. Her koltuk değişiminde çalışır.
    """
    await room_state.ensure_room(room.id, room.seat_count)
    seats = (await room_state.get_seats([room.id]))[room.id]
    mic_blocked = (await room_state.mic_blocked_ids([room.id]))[room.id]
    users = await user_service.load_users_out(
        db, {seat.user_id for seat in seats if seat.user_id is not None}, None,
    )
    return [
        SeatOut(
            index=seat.index, user_id=seat.user_id, is_muted=seat.is_muted,
            is_locked=seat.is_locked, user=users.get(seat.user_id),
            is_mic_blocked=seat.user_id in mic_blocked,
        )
        for seat in seats
    ]


async def publish_seats(db: AsyncSession, room: Room) -> None:
    """
    Koltukların son halini odadaki herkese yayınlar.
    Yayın herkese aynı gittiği için kişiye özel alanlar (is_me, is_following) boştur;
    istemci "bu ben miyim" kontrolünü kullanıcı id'si ile kendisi yapar.
    """
    seats = await present_seats(db, room)
    # Önce ses sağlayıcısına kimlerin konuşabileceğini bildir (SFU'da sunucu tarafında
    # uygulanır), sonra odaya duyur: koltuğa oturan kişi mikrofonunu açmaya çalıştığında
    # izni hazır olsun.
    await voice_provider.sync_publishers(room.id, {
        seat.user_id for seat in seats if seat.user_id is not None and not seat.is_mic_blocked
    })
    await room_hub.publish(room.id, events.ROOM_SEATS_UPDATED, _seats_payload(seats))


def _seats_payload(seats: list[SeatOut]) -> dict:
    return {"seats": [seat.model_dump(mode="json") for seat in seats]}


async def seats_payload(db: AsyncSession, room: Room) -> dict:
    """Koltukların son hali, `room:seats_updated` biçiminde (tek kişiye göndermek için)."""
    return _seats_payload(await present_seats(db, room))


# ── Sesli görüşme ─────────────────────────────────────────────────────────────

async def get_voice_join(db: AsyncSession, user_id: int, room_id: int) -> VoiceJoinInfo:
    """
    Odanın sesine bağlanmak için gerekenler (bkz. app/voice/). Odada olan herkes dinleyebilir;
    konuşma izni (can_publish) yalnızca koltukta oturan ve mikrofonu engellenmemiş kişide.
    Koltuktaki kişi kısa bir kopma sırasında da yenileyebilsin: bağlantısı yok ama odadan çıkmadı.
    """
    room = await get_room_row(db, room_id)
    if await room_state.is_banned(room.id, user_id):
        raise ForbiddenError("Bu odadan çıkarıldın, bir süre giremezsin.", code="room_banned")
    user = await user_service.get_user(db, user_id)
    seated = await room_state.seat_index_of(room.id, user_id) is not None
    if not seated and not await room_state.is_in_room(room.id, user_id):
        raise ForbiddenError("Sese bağlanmak için önce odaya girmelisin.", code="not_in_room")
    blocked = user_id in (await room_state.mic_blocked_ids([room.id]))[room.id]
    return await voice_provider.join_info(room.id, user_id, user.display_name, can_publish=seated and not blocked)
