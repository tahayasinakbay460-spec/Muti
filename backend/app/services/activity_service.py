"""
Oda içi etkinlikler: PK (takım hediye yarışı), birlikte izleme (YouTube), karaoke sırası.

PK NASIL İŞLER?
  Oda sahibi ya da yönetici süreli bir PK başlatır. Koltuklar ikiye ayrılır: ilk yarısı
  kırmızı, ikinci yarısı mavi takım. PK süresince bir takımdaki koltukta oturan birine gönderilen
  hediyenin coin değeri o takımın puanına eklenir (gift_service çağırır). Süre dolunca kazanan
  ve en çok destek olan (MVP) herkese duyurulur.

BİRLİKTE İZLEME: Video oynatılmaz, yalnızca "hangi video, hangi saniyede" bilgisi paylaşılır.
Her tarayıcı videoyu YouTube'dan kendisi açar ve sunucunun söylediği saniyeye gider. Böylece
sunucumuz video trafiği taşımaz (binlerce izleyicide bile yük yok).

DEMO KISAYOLU: Bu durumlar sürecin belleğinde. Birden fazla sunucuda Redis'te tutulmalı ve PK'yi
bitirme işini tek bir sunucu yapmalı (süreli kilit). Rulet ve hazine sandığı ile aynı not.
"""
import asyncio
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.logs import audit
from app.realtime import events
from app.realtime.hub import room_hub
from app.realtime.state import room_state
from app.schemas.activity import KaraokeOut, MediaOut, PkContributor, PkOut
from app.services import room_service, user_service

# ── PK ────────────────────────────────────────────────────────────────────────


@dataclass
class Pk:
    pk_id: str
    ends_at: datetime
    red_seats: list[int]
    blue_seats: list[int]
    red: int = 0
    blue: int = 0
    # gönderen id → (kullanıcı bilgisi, toplam coin): MVP'yi bulmak için
    supporters: dict[int, tuple[dict, int]] = field(default_factory=dict)
    status: str = "running"
    winner: str | None = None


_pks: dict[int, Pk] = {}
_timers: set[asyncio.Task] = set()


def _schedule(coroutine) -> None:
    task = asyncio.create_task(coroutine)
    _timers.add(task)                     # tutulmazsa Python görevi yarıda çöpe atabilir
    task.add_done_callback(_timers.discard)


def _pk_out(pk: Pk) -> PkOut:
    mvp = None
    if pk.supporters:
        user, coins = max(pk.supporters.values(), key=lambda item: item[1])
        mvp = PkContributor(user=user, coins=coins)
    return PkOut(
        pk_id=pk.pk_id, status=pk.status, ends_at=pk.ends_at, red=pk.red, blue=pk.blue,
        red_seats=pk.red_seats, blue_seats=pk.blue_seats, winner=pk.winner, mvp=mvp,
    )


async def start_pk(db: AsyncSession, actor_id: int, room_id: int, minutes: int) -> PkOut:
    room = await room_service.get_room_row(db, room_id)
    await room_service.require_moderator(db, room, actor_id)
    current = _pks.get(room_id)
    if current and current.status == "running":
        raise ConflictError("Bu odada zaten bir PK sürüyor.", code="pk_running")
    half = room.seat_count // 2
    pk = Pk(
        pk_id=secrets.token_hex(6), ends_at=utcnow() + timedelta(minutes=minutes),
        red_seats=list(range(half)), blue_seats=list(range(half, room.seat_count)),
    )
    _pks[room_id] = pk
    _schedule(_finish_later(room_id, pk.pk_id, minutes * 60))
    audit("room_pk_started", room_id=room_id, minutes=minutes)
    out = _pk_out(pk)
    await room_hub.publish(room_id, events.ROOM_PK_UPDATED, {"pk": out.model_dump(mode="json")})
    return out


async def _finish_later(room_id: int, pk_id: str, seconds: float) -> None:
    await asyncio.sleep(seconds)
    await _finish(room_id, pk_id)


async def _finish(room_id: int, pk_id: str) -> None:
    """PK'yi sonuçlandırır. Erken bitirilmiş ya da yerine yenisi başlamışsa dokunmaz."""
    pk = _pks.get(room_id)
    if pk is None or pk.pk_id != pk_id or pk.status != "running":
        return
    pk.status = "ended"
    pk.winner = "red" if pk.red > pk.blue else "blue" if pk.blue > pk.red else "draw"
    await room_hub.publish(room_id, events.ROOM_PK_UPDATED, {"pk": _pk_out(pk).model_dump(mode="json")})


async def stop_pk(db: AsyncSession, actor_id: int, room_id: int) -> PkOut:
    """PK'yi süresinden önce bitirir (sonuç o anki puanlara göre)."""
    room = await room_service.get_room_row(db, room_id)
    await room_service.require_moderator(db, room, actor_id)
    pk = _pks.get(room_id)
    if pk is None or pk.status != "running":
        raise AppError("Süren bir PK yok.", code="no_pk")
    await _finish(room_id, pk.pk_id)
    audit("room_pk_stopped", room_id=room_id)
    return _pk_out(pk)


async def add_gift(room_id: int, receiver_id: int, sender: dict, coins: int) -> None:
    """Odada gönderilen hediye PK süresinde bir takımdaki koltuğa gittiyse puanı ekler."""
    pk = _pks.get(room_id)
    if pk is None or pk.status != "running" or coins <= 0:
        return
    seat = await room_state.seat_index_of(room_id, receiver_id)
    if seat is None:
        return
    if seat in pk.red_seats:
        pk.red += coins
    elif seat in pk.blue_seats:
        pk.blue += coins
    else:
        return
    _user, total = pk.supporters.get(sender["id"], (sender, 0))
    pk.supporters[sender["id"]] = (sender, total + coins)
    await room_hub.publish(room_id, events.ROOM_PK_UPDATED, {"pk": _pk_out(pk).model_dump(mode="json")})


# ── Birlikte izleme ───────────────────────────────────────────────────────────

# youtube.com/watch?v=ID, youtu.be/ID, youtube.com/shorts/ID, youtube.com/embed/ID — ID 11 karakter.
_YOUTUBE = re.compile(
    r"^(?:https?://)?(?:www\.|m\.)?(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})(?:[?&#].*)?$"
)


@dataclass
class Media:
    video_id: str
    set_by: dict
    started_at: datetime | None = None
    paused: bool = False
    position: float = 0.0


_media: dict[int, Media] = {}


def parse_youtube_id(url: str) -> str:
    """
    Bağlantıdan YouTube video kimliğini çıkarır. Başka bir adres kabul edilmez: sayfalara
    rastgele bir site gömülemesin (güvenlik).
    """
    match = _YOUTUBE.match(url.strip())
    if not match:
        raise AppError("Geçerli bir YouTube bağlantısı gir.", code="invalid_video_url")
    return match.group(1)


def _media_out(media: Media) -> MediaOut:
    return MediaOut(
        video_id=media.video_id, started_at=media.started_at, paused=media.paused,
        position=media.position, set_by=media.set_by, server_time=utcnow(),
    )


async def _publish_media(room_id: int) -> None:
    media = _media.get(room_id)
    await room_hub.publish(room_id, events.ROOM_MEDIA_UPDATED, {
        "media": _media_out(media).model_dump(mode="json") if media else None,
    })


async def set_media(db: AsyncSession, actor_id: int, room_id: int, url: str) -> MediaOut:
    room = await room_service.get_room_row(db, room_id)
    await room_service.require_moderator(db, room, actor_id)
    video_id = parse_youtube_id(url)
    actor = (await user_service.present_user(db, await user_service.get_user(db, actor_id), viewer_id=None)).model_dump(mode="json")
    _media[room_id] = Media(video_id=video_id, set_by=actor, started_at=utcnow())
    audit("room_media_set", room_id=room_id, video_id=video_id)
    await _publish_media(room_id)
    return _media_out(_media[room_id])


async def control_media(db: AsyncSession, actor_id: int, room_id: int, action: str, position: float | None) -> MediaOut:
    room = await room_service.get_room_row(db, room_id)
    await room_service.require_moderator(db, room, actor_id)
    media = _media.get(room_id)
    if media is None:
        raise NotFoundError("Odada açık bir video yok.")
    now = utcnow()
    current = media.position if media.paused or media.started_at is None else (now - media.started_at).total_seconds()
    if action == "pause":
        media.paused, media.position = True, position if position is not None else current
    elif action == "play":
        # Zaten oynuyorsa hiçbir şey yapma (kaldığı eski saniyeye geri sarmasın).
        if media.paused:
            media.paused = False
            media.started_at = now - timedelta(seconds=media.position)
    else:   # seek
        target = position or 0.0
        media.position = target
        if not media.paused:
            media.started_at = now - timedelta(seconds=target)
    await _publish_media(room_id)
    return _media_out(media)


async def stop_media(db: AsyncSession, actor_id: int, room_id: int) -> None:
    room = await room_service.get_room_row(db, room_id)
    await room_service.require_moderator(db, room, actor_id)
    if _media.pop(room_id, None) is not None:
        await _publish_media(room_id)


# ── Karaoke sırası ────────────────────────────────────────────────────────────

@dataclass
class Karaoke:
    singer: dict | None = None
    queue: list[dict] = field(default_factory=list)


_karaoke: dict[int, Karaoke] = {}
KARAOKE_QUEUE_LIMIT = 20


def _karaoke_out(room_id: int) -> KaraokeOut:
    karaoke = _karaoke.get(room_id) or Karaoke()
    return KaraokeOut(singer=karaoke.singer, queue=list(karaoke.queue))


async def _publish_karaoke(room_id: int) -> KaraokeOut:
    out = _karaoke_out(room_id)
    await room_hub.publish(room_id, events.ROOM_KARAOKE_UPDATED, {"karaoke": out.model_dump(mode="json")})
    return out


async def join_karaoke(db: AsyncSession, user_id: int, room_id: int) -> KaraokeOut:
    await room_service.get_room_row(db, room_id)
    if not await room_state.is_in_room(room_id, user_id):
        raise AppError("Sıraya girmek için odada olmalısın.", code="not_in_room")
    karaoke = _karaoke.setdefault(room_id, Karaoke())
    if any(u["id"] == user_id for u in karaoke.queue) or (karaoke.singer and karaoke.singer["id"] == user_id):
        raise ConflictError("Zaten sıradasın.", code="already_in_queue")
    if len(karaoke.queue) >= KARAOKE_QUEUE_LIMIT:
        raise ConflictError("Karaoke sırası dolu.", code="karaoke_queue_full")
    user = (await user_service.present_user(db, await user_service.get_user(db, user_id), viewer_id=None)).model_dump(mode="json")
    karaoke.queue.append(user)
    return await _publish_karaoke(room_id)


async def leave_karaoke(user_id: int, room_id: int) -> KaraokeOut:
    karaoke = _karaoke.get(room_id)
    if karaoke:
        karaoke.queue = [u for u in karaoke.queue if u["id"] != user_id]
        if karaoke.singer and karaoke.singer["id"] == user_id:
            karaoke.singer = None
    return await _publish_karaoke(room_id)


async def next_singer(db: AsyncSession, actor_id: int, room_id: int) -> KaraokeOut:
    """Sıradaki kişiyi şarkıcı yapar (oda sahibi / yönetici)."""
    room = await room_service.get_room_row(db, room_id)
    await room_service.require_moderator(db, room, actor_id)
    karaoke = _karaoke.setdefault(room_id, Karaoke())
    karaoke.singer = karaoke.queue.pop(0) if karaoke.queue else None
    return await _publish_karaoke(room_id)


# ── Odaya girişte tek seferlik durum ──────────────────────────────────────────

def snapshot(room_id: int) -> dict:
    pk = _pks.get(room_id)
    media = _media.get(room_id)
    return {
        "pk": _pk_out(pk) if pk else None,
        "media": _media_out(media) if media else None,
        "karaoke": _karaoke_out(room_id),
    }


def drop_room(room_id: int) -> None:
    """Oda kapanınca bütün etkinlik durumunu unut."""
    for store in (_pks, _media, _karaoke):
        store.pop(room_id, None)
