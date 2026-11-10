"""
Oda içi etkinlik uçları (/api/v1/rooms/{room_id}/...):
  activities       — odaya girişte güncel durum (PK, video, karaoke, oyun masaları)
  pk               — takım hediye yarışı (oda sahibi / yönetici başlatır)
  media            — birlikte izleme (YouTube)
  karaoke          — şarkı sırası
İki kişilik oyunlar (Dört Bağla, Taş-Kağıt-Makas) WebSocket üzerinden oynanır (bkz. realtime/duels.py).
"""
from fastapi import APIRouter, Response, status

from app.core.deps import CurrentUserId, DbSession
from app.realtime.duels import duels
from app.schemas.activity import (
    KaraokeOut, LiveCameraOut, MediaControlRequest, MediaOut, MediaSetRequest, PkOut, PkStartRequest, RoomActivities,
)
from app.services import activity_service, live_service, room_service
from app.voice import VoiceJoinInfo

router = APIRouter(prefix="/rooms", tags=["activities"])


@router.get("/{room_id}/activities", response_model=RoomActivities)
async def get_activities(room_id: int, _user_id: CurrentUserId, db: DbSession):
    await room_service.get_room_row(db, room_id)
    return RoomActivities(**activity_service.snapshot(room_id), duels=duels.list_tables(room_id),
                          camera=live_service.camera_out(room_id))


@router.post("/{room_id}/pk", response_model=PkOut)
async def start_pk(room_id: int, data: PkStartRequest, user_id: CurrentUserId, db: DbSession):
    """Koltukların ilk yarısı kırmızı, ikinci yarısı mavi takım. Süre: 1, 3, 5 ya da 10 dakika."""
    return await activity_service.start_pk(db, user_id, room_id, data.minutes)


@router.delete("/{room_id}/pk", response_model=PkOut)
async def stop_pk(room_id: int, user_id: CurrentUserId, db: DbSession):
    return await activity_service.stop_pk(db, user_id, room_id)


@router.put("/{room_id}/media", response_model=MediaOut)
async def set_media(room_id: int, data: MediaSetRequest, user_id: CurrentUserId, db: DbSession):
    """Odada herkesin birlikte izleyeceği YouTube videosunu açar."""
    return await activity_service.set_media(db, user_id, room_id, data.url)


@router.post("/{room_id}/media/control", response_model=MediaOut)
async def control_media(room_id: int, data: MediaControlRequest, user_id: CurrentUserId, db: DbSession):
    return await activity_service.control_media(db, user_id, room_id, data.action, data.position)


@router.delete("/{room_id}/media", status_code=status.HTTP_204_NO_CONTENT)
async def stop_media(room_id: int, user_id: CurrentUserId, db: DbSession):
    await activity_service.stop_media(db, user_id, room_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{room_id}/karaoke/queue", response_model=KaraokeOut)
async def join_karaoke(room_id: int, user_id: CurrentUserId, db: DbSession):
    return await activity_service.join_karaoke(db, user_id, room_id)


@router.delete("/{room_id}/karaoke/queue", response_model=KaraokeOut)
async def leave_karaoke(room_id: int, user_id: CurrentUserId, db: DbSession):
    await room_service.get_room_row(db, room_id)
    return await activity_service.leave_karaoke(user_id, room_id)


@router.post("/{room_id}/karaoke/next", response_model=KaraokeOut)
async def next_singer(room_id: int, user_id: CurrentUserId, db: DbSession):
    """Sıradaki kişiyi şarkıcı yapar (oda sahibi / yönetici)."""
    return await activity_service.next_singer(db, user_id, room_id)


@router.post("/{room_id}/camera", response_model=LiveCameraOut)
async def start_camera(room_id: int, user_id: CurrentUserId, db: DbSession):
    """Kameralı yayını başlatır: yalnızca oda sahibi, onaylı yayıncıysa ve koltuktaysa."""
    return await live_service.start(db, user_id, room_id)


@router.delete("/{room_id}/camera", status_code=status.HTTP_204_NO_CONTENT)
async def stop_camera(room_id: int, user_id: CurrentUserId, db: DbSession):
    """Yayıncının kendisi ya da oda yöneticisi yayını kapatır."""
    await live_service.stop(db, user_id, room_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{room_id}/camera/join", response_model=VoiceJoinInfo)
async def join_camera(room_id: int, user_id: CurrentUserId, db: DbSession):
    """Yayının görüntü kanalına bağlanma bilgisi (ses odadaki ses kanalından gelir)."""
    return await live_service.join_info(db, user_id, room_id)
