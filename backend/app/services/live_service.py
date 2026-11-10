"""
Kameralı canlı yayın (Bigo / TikTok canlısı gibi): tek yayıncı yüzünü göstererek yayın yapar,
izleyiciler tam ekran izler, sohbet eder, hediye gönderir.

NASIL ÇALIŞIR?
  - Her yayıncının bir "live" türünde odası vardır (Room.kind = "live"). Koltuk yok, sesli oda yok.
    Sohbet, hediye, izleyici sayısı ve atma/susturma her zamanki oda kanalından (WebSocket) gelir;
    böylece hediye, para ve moderasyon kodunun hepsi aynen kullanılır.
  - Ses ve görüntü TEK kanalda gider (Agora'da "live-<oda id>"): yayıncı mikrofon + kamera gönderir,
    izleyiciler yalnızca alır. Tek kanal olduğu için ses ile görüntü senkron kalır ve izleyici başına
    dakika bir kez sayılır (Agora her katılımcının her dakikasını faturalar).
  - "Şu an kim yayında?" bilgisinin sahibi SUNUCUDUR. İzleyici yalnızca sunucunun söylediği yayıncının
    görüntüsünü çizer; başka biri değiştirilmiş bir uygulamayla görüntü gönderse bile ekranda görünmez.

KİM YAYIN AÇABİLİR? Yalnızca onaylı yayıncılar (User.is_host, 18+ başvuru + panel onayı).
Görüntüde moderasyon yazıdan çok daha önemli olduğu için kamera herkese açılmaz.

MODERASYON: panel yayını anında kapatır (SFU'da görüntü bağlantısı da kesilir), izleyici yayını
şikâyet edebilir (oda şikâyeti).
DEMO KISAYOLU: otomatik görüntü denetimi (çıplaklık vb.) yok; canlıya çıkmadan önce şart
(Agora'nın içerik denetimi eklentisi ya da her X saniyede bir kare alıp denetim servisine yollamak).

DEMO KISAYOLU: "kim yayında" bilgisi ve bildirim bekleme süresi sürecin belleğinde. Birden fazla
sunucuda Redis'e taşınır.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.logs import audit
from app.models import Follow, Room
from app.realtime import events
from app.realtime.hub import room_hub
from app.realtime.state import room_state
from app.schemas.activity import LiveCameraOut
from app.schemas.room import RoomOut
from app.services import notification_service, room_service, user_service
from app.voice import VoiceJoinInfo, voice_provider

# Aynı yayıncı yayını kapatıp açınca takipçilerine her seferinde bildirim gitmesin.
NOTIFY_COOLDOWN = timedelta(minutes=30)
# Bir yayın başlangıcında en fazla bu kadar takipçiye bildirim (DEMO: tek istekte; canlıda kuyrukta).
NOTIFY_MAX_FOLLOWERS = 1000


@dataclass
class Camera:
    user_id: int
    started_at: datetime


_cameras: dict[int, Camera] = {}
_last_notified: dict[int, datetime] = {}   # yayıncı id → takipçilere son bildirim anı


def camera_user_ids() -> dict[int, int]:
    """Oda id → yayında olan yayıncının id'si (Canlı sekmesi sıralaması ve 🎥 rozeti için)."""
    return {room_id: camera.user_id for room_id, camera in _cameras.items()}


def camera_out(room_id: int) -> LiveCameraOut | None:
    camera = _cameras.get(room_id)
    return LiveCameraOut(user_id=camera.user_id, started_at=camera.started_at) if camera else None


async def _publish(room_id: int, reason: str = "") -> None:
    camera = camera_out(room_id)
    await room_hub.publish(room_id, events.ROOM_CAMERA_UPDATED, {
        "camera": camera.model_dump(mode="json") if camera else None, "reason": reason,
    })


async def _require_streamer(db: AsyncSession, user_id: int):
    user = await user_service.get_user(db, user_id)
    if not user.is_host:
        raise ForbiddenError("Canlı yayın onaylı yayıncılara açık. Ben > Yayıncı ol ile başvurabilirsin.",
                             code="host_required")
    return user


async def open_my_stream(db: AsyncSession, user_id: int, title: str | None) -> RoomOut:
    """
    Yayıncının canlı yayın odası: yoksa açılır, varsa (başlık verildiyse) başlığı güncellenir.
    Yayını başlatmaz; yayıncı önce kamerasını önizler, sonra `start` der.
    """
    user = await _require_streamer(db, user_id)
    room = await db.scalar(select(Room).where(Room.host_id == user_id, Room.kind == "live", Room.is_active))
    if room is None:
        # seat_count=0: canlı yayında koltuk yok (oda kanalı, sohbet ve hediye için koltuk gerekmez).
        room = Room(title=title or f"{user.display_name} canlı yayında", category="chat", kind="live",
                    cover_url=user.avatar_url or room_service.DEFAULT_COVER_URL, announcement="Yayına hoş geldin!", host_id=user_id, seat_count=0)
        db.add(room)
    elif title:
        room.title = title
    await db.commit()
    return await room_service.get_room(db, user_id, room.id)


async def _notify_followers(db: AsyncSession, user_id: int, room: Room) -> None:
    now = utcnow()
    last = _last_notified.get(user_id)
    if last and now - last < NOTIFY_COOLDOWN:
        return
    _last_notified[user_id] = now
    follower_ids = list(await db.scalars(
        select(Follow.follower_id).where(Follow.followee_id == user_id).limit(NOTIFY_MAX_FOLLOWERS)
    ))
    user = await user_service.get_user(db, user_id)
    for follower_id in follower_ids:
        await notification_service.notify(
            db, follower_id, "live_started", f"🎥 {user.display_name} canlı yayında: {room.title}",
            actor_id=user_id, data={"live_room_id": room.id},
        )


async def start(db: AsyncSession, user_id: int, room_id: int) -> LiveCameraOut:
    room = await room_service.get_room_row(db, room_id)
    if room.kind != "live":
        raise AppError("Kamera yalnızca canlı yayın odasında açılır.", code="not_live_room")
    if room.host_id != user_id:
        raise ForbiddenError("Bu yayını yalnızca sahibi başlatabilir.", code="not_room_owner")
    await _require_streamer(db, user_id)
    if not await room_state.is_in_room(room.id, user_id):
        raise ForbiddenError("Yayını başlatmak için önce yayın ekranına girmelisin.", code="not_in_room")
    if room.id not in _cameras:
        _cameras[room.id] = Camera(user_id=user_id, started_at=utcnow())
        audit("live_started", room_id=room.id)
        await _publish(room.id)
        await _notify_followers(db, user_id, room)
    return camera_out(room.id)


async def _stop(room_id: int, reason: str) -> None:
    camera = _cameras.pop(room_id, None)
    if camera is not None:
        audit("live_ended", room_id=room_id, reason=reason,
              seconds=int((utcnow() - camera.started_at).total_seconds()))
        await _publish(room_id, reason)


async def stop(db: AsyncSession, actor_id: int, room_id: int) -> None:
    """Yayıncının kendisi ya da odada yöneticilik verdiği kişi kapatır."""
    room = await room_service.get_room_row(db, room_id)
    camera = _cameras.get(room.id)
    if camera is None:
        return
    if actor_id != camera.user_id:
        await room_service.require_moderator(db, room, actor_id)
        audit("live_stopped_by_moderator", room_id=room.id, streamer_id=camera.user_id)
        await voice_provider.stop_live(room.id, camera.user_id)
    await _stop(room.id, "stopped" if actor_id == camera.user_id else "moderator")


async def stop_by_staff(room_id: int) -> int:
    """Yönetim paneli yayını kapatır. Yayın yoksa NotFound. Dönüş: yayıncının id'si (kayıt için)."""
    camera = _cameras.get(room_id)
    if camera is None:
        raise NotFoundError("Bu odada açık yayın yok.")
    await voice_provider.stop_live(room_id, camera.user_id)
    await _stop(room_id, "staff")
    return camera.user_id


async def on_departure(room_id: int, user_id: int) -> None:
    """Yayıncı yayın ekranından tamamen çıktı (kısa kopma süresi de doldu): yayın biter."""
    camera = _cameras.get(room_id)
    if camera is not None and camera.user_id == user_id:
        await _stop(room_id, "left")


async def join_info(db: AsyncSession, user_id: int, room_id: int) -> VoiceJoinInfo:
    """Yayının ses + görüntü kanalına bağlanma bilgisi. Yalnızca odadakiler; göndermek yalnızca yayıncıya."""
    room = await room_service.get_room_row(db, room_id)
    camera = _cameras.get(room.id)
    if camera is None:
        raise NotFoundError("Bu yayın şu an kapalı.")
    if not await room_state.is_in_room(room.id, user_id):
        raise ForbiddenError("Yayını izlemek için önce yayın ekranına girmelisin.", code="not_in_room")
    info = await voice_provider.live_join_info(room.id, user_id, is_streamer=user_id == camera.user_id)
    info.streamer_id = camera.user_id
    return info


def is_streamer(room_id: int, user_id: int) -> bool:
    camera = _cameras.get(room_id)
    return camera is not None and camera.user_id == user_id


def drop_room(room_id: int) -> None:
    _cameras.pop(room_id, None)
