"""
Kameralı canlı yayın: oda sahibi (onaylı yayıncı) kamerasını açar, odadakiler izler.

NASIL ÇALIŞIR?
  - Sesli oda aynen çalışır: yayıncı koltuktadır, sesi oda ses kanalından gider; sohbet, hediye,
    PK, oyunlar hep aynı oda kanalında.
  - Görüntü AYRI bir kanaldan gider (bkz. voice/base.py `live_join_info`): Agora'da "live-<oda id>"
    kanalı, mesh'te yayıncının tarayıcısından her izleyiciye doğrudan bağlantı.
  - "Bu odada kim kamera açık?" bilgisinin sahibi SUNUCUDUR. İzleyici, yalnızca sunucunun söylediği
    yayıncının görüntüsünü çizer; başka biri değiştirilmiş bir uygulamayla görüntü gönderse bile
    ekranda görünmez (sesteki koltuk kuralının aynısı).

KİM AÇABİLİR? Yalnızca odanın sahibi ve yalnızca onaylı yayıncıysa (User.is_host, 18+ başvuru).
Görüntüde moderasyon yazıdan çok daha önemli olduğu için kamera herkese açılmaz.

MODERASYON: oda yöneticisi ya da yönetim paneli yayını anında kapatır (panelden kapatılınca SFU'da
görüntü bağlantısı da kesilir). Şikâyet mevcut oda şikâyetinden gelir.
DEMO KISAYOLU: otomatik görüntü denetimi (çıplaklık vb.) yok; canlıya çıkmadan önce şart
(Agora'nın içerik denetimi eklentisi ya da her X saniyede bir kare alıp denetim servisine yollamak).

DEMO KISAYOLU: durum sürecin belleğinde (PK ve birlikte izleme gibi). Birden fazla sunucuda Redis'e taşınır.
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.logs import audit
from app.realtime import events
from app.realtime.hub import room_hub
from app.realtime.state import room_state
from app.schemas.activity import LiveCameraOut
from app.services import room_service, user_service
from app.voice import VoiceJoinInfo, voice_provider


@dataclass
class Camera:
    user_id: int
    started_at: datetime


_cameras: dict[int, Camera] = {}


def camera_user_ids() -> dict[int, int]:
    """Oda id → kamerası açık yayıncının id'si (oda listesindeki 🎥 rozeti ve Canlı sıralaması için)."""
    return {room_id: camera.user_id for room_id, camera in _cameras.items()}


def camera_out(room_id: int) -> LiveCameraOut | None:
    camera = _cameras.get(room_id)
    return LiveCameraOut(user_id=camera.user_id, started_at=camera.started_at) if camera else None


async def _publish(room_id: int, reason: str = "") -> None:
    camera = camera_out(room_id)
    await room_hub.publish(room_id, events.ROOM_CAMERA_UPDATED, {
        "camera": camera.model_dump(mode="json") if camera else None, "reason": reason,
    })


async def start(db: AsyncSession, user_id: int, room_id: int) -> LiveCameraOut:
    room = await room_service.get_room_row(db, room_id)
    if room.host_id != user_id:
        raise ForbiddenError("Kamerayı yalnızca oda sahibi açabilir.", code="not_room_owner")
    user = await user_service.get_user(db, user_id)
    if not user.is_host:
        raise ForbiddenError("Kameralı yayın onaylı yayıncılara açık. Ben > Yayıncı ol ile başvurabilirsin.",
                             code="host_required")
    if await room_state.seat_index_of(room.id, user_id) is None:
        # Görüntü kanalında ses yok: yayıncı koltukta değilse izleyiciler onu duyamaz.
        raise AppError("Kamerayı açmak için önce bir koltuğa otur.", code="seat_required")
    if room.id not in _cameras:
        _cameras[room.id] = Camera(user_id=user_id, started_at=utcnow())
        audit("live_camera_started", room_id=room.id)
        await _publish(room.id)
    return camera_out(room.id)


async def _stop(room_id: int, reason: str) -> None:
    if _cameras.pop(room_id, None) is not None:
        await _publish(room_id, reason)


async def stop(db: AsyncSession, actor_id: int, room_id: int) -> None:
    """Yayıncının kendisi ya da oda yöneticisi kapatır."""
    room = await room_service.get_room_row(db, room_id)
    camera = _cameras.get(room.id)
    if camera is None:
        return
    if actor_id != camera.user_id:
        await room_service.require_moderator(db, room, actor_id)
        audit("live_camera_stopped_by_moderator", room_id=room.id, streamer_id=camera.user_id)
        await voice_provider.stop_live(room.id, camera.user_id)
    await _stop(room.id, "stopped" if actor_id == camera.user_id else "moderator")


async def stop_by_staff(room_id: int) -> int:
    """Yönetim paneli yayını kapatır. Yayın yoksa NotFound. Dönüş: yayıncının id'si (kayıt için)."""
    camera = _cameras.get(room_id)
    if camera is None:
        raise NotFoundError("Bu odada açık kamera yok.")
    await voice_provider.stop_live(room_id, camera.user_id)
    await _stop(room_id, "staff")
    return camera.user_id


async def on_departure(room_id: int, user_id: int) -> None:
    """Yayıncı odadan tamamen çıktı (bağlantı süresi de doldu): yayın biter."""
    camera = _cameras.get(room_id)
    if camera is not None and camera.user_id == user_id:
        await _stop(room_id, "left")


async def join_info(db: AsyncSession, user_id: int, room_id: int) -> VoiceJoinInfo:
    """Görüntü kanalına bağlanma bilgisi. Yalnızca odadakiler; görüntü gönderme izni yalnızca yayıncıda."""
    room = await room_service.get_room_row(db, room_id)
    camera = _cameras.get(room.id)
    if camera is None:
        raise NotFoundError("Bu odada açık kamera yok.")
    if not await room_state.is_in_room(room.id, user_id):
        raise ForbiddenError("Yayını izlemek için önce odaya girmelisin.", code="not_in_room")
    info = await voice_provider.live_join_info(room.id, user_id, is_streamer=user_id == camera.user_id)
    info.streamer_id = camera.user_id
    return info


def is_streamer(room_id: int, user_id: int) -> bool:
    camera = _cameras.get(room_id)
    return camera is not None and camera.user_id == user_id


def drop_room(room_id: int) -> None:
    _cameras.pop(room_id, None)
