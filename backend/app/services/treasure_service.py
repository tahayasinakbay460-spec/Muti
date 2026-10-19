"""
Hazine sandığı: odada gönderilen hediyeler sandığı doldurur; dolunca sandık açılır ve
odadaki herkes kısa bir süre içinde sandıktan bir kez rastgele coin kapabilir.

NASIL İŞLER?
  1. Odada her hediye gönderildiğinde coin değeri sandığın ilerlemesine eklenir
     (`add_gift_coins`). Herkese `room:chest_updated` ile yeni ilerleme yayınlanır.
  2. İlerleme hedefe (settings.chest_target_coins) ulaşınca sandık AÇILIR: hedefin
     belli bir yüzdesi (settings.chest_reward_percent) dağıtılacak coin olur.
  3. Açık kaldığı süre boyunca odadakiler `POST /rooms/{id}/chest/claim` ile kapar.
     Kaç coin çıkacağını SUNUCU çeker. Her kişi bir sandıktan bir kez alır.
  4. Coin bitince ya da süre dolunca sandık kapanır ve sıfırdan dolmaya başlar.

AYNI ANDA İKİ KİŞİ SON COİNİ KAPARSA? Sandığın durumu bu süreçte tek iş parçacığında
(asyncio) değişir: "kalan coinden düş" adımı araya başka iş girmeden yapılır, veritabanı
yazımından ÖNCE. Yazım başarısız olursa ayrılan coin sandığa geri konur.

DEMO KISAYOLU: Sandıklar bu sürecin belleğinde. Birden fazla sunucuda Redis'te tutulmalı,
"kalan coinden düş" adımı Redis'in tek komutluk (atomik) işlemiyle (DECRBY / Lua) yapılmalı.
"""
import asyncio
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import utcnow
from app.core.errors import AppError, ConflictError, ForbiddenError
from app.realtime import events
from app.realtime.hub import room_hub
from app.realtime.state import room_state
from app.schemas.store import ChestClaimResult, ChestOut
from app.services import user_service, wallet_service


@dataclass
class Chest:
    # Rastgele kimlik: sunucu yeniden başlasa bile eski bir sandıkla karışmaz
    # (ödülün idempotency anahtarı bu kimlikten üretilir).
    chest_id: str = field(default_factory=lambda: secrets.token_hex(6))
    progress: int = 0
    status: str = "filling"           # filling | open
    reward_pool: int = 0              # açıldığında dağıtılacak toplam coin
    coins_left: int = 0
    ends_at: datetime | None = None
    claimed_ids: set[int] = field(default_factory=set)


_chests: dict[int, Chest] = {}
# Kapanma zamanlayıcıları; tutulmazsa Python onları yarıda çöpe atabilir.
_timers: set[asyncio.Task] = set()


def _chest(room_id: int) -> Chest:
    return _chests.setdefault(room_id, Chest())


def _present(chest: Chest, viewer_id: int | None = None) -> ChestOut:
    is_open = chest.status == "open"
    return ChestOut(
        chest_id=chest.chest_id, status=chest.status, progress=chest.progress,
        target=settings.chest_target_coins,
        ends_at=chest.ends_at if is_open else None,
        coins_left=chest.coins_left if is_open else 0,
        claimed_by_me=viewer_id in chest.claimed_ids,
    )


async def _publish(room_id: int, chest: Chest) -> None:
    # Yayın herkese aynı gider; "ben aldım mı?" bilgisini her istemci kendisi tutar.
    await room_hub.publish(room_id, events.ROOM_CHEST_UPDATED, {"chest": _present(chest).model_dump(mode="json")})


def get_chest(room_id: int, viewer_id: int) -> ChestOut:
    return _present(_chest(room_id), viewer_id)


async def add_gift_coins(room_id: int, coins: int) -> None:
    """Odada gönderilen bir hediyenin coin değerini sandığa ekler; hedefe ulaştıysa sandığı açar."""
    chest = _chest(room_id)
    if chest.status == "open" or coins <= 0:
        # Açık sandık kapanmadan yeni dolum başlamaz; o sırada gelen hediyeler sayılmaz.
        return
    chest.progress = min(chest.progress + coins, settings.chest_target_coins)
    if chest.progress >= settings.chest_target_coins:
        chest.status = "open"
        chest.reward_pool = chest.coins_left = settings.chest_target_coins * settings.chest_reward_percent // 100
        chest.ends_at = utcnow() + timedelta(seconds=settings.chest_open_seconds)
        timer = asyncio.create_task(_close_later(room_id, chest.chest_id, settings.chest_open_seconds))
        _timers.add(timer)
        timer.add_done_callback(_timers.discard)
    await _publish(room_id, chest)


async def _close_later(room_id: int, chest_id: str, seconds: float) -> None:
    await asyncio.sleep(seconds)
    await _close(room_id, chest_id)


async def _close(room_id: int, chest_id: str) -> None:
    """Sandığı kapatır ve yerine boş bir sandık koyar. Başka bir sandık geldiyse dokunmaz."""
    chest = _chests.get(room_id)
    if chest is None or chest.chest_id != chest_id:
        return
    _chests[room_id] = Chest()
    await _publish(room_id, _chests[room_id])


def _draw_amount(chest: Chest) -> int:
    """Kişinin kapacağı coin: havuzun %5'i ile %15'i arası, kalan coini aşmaz."""
    low = max(1, chest.reward_pool * 5 // 100)
    spread = max(1, chest.reward_pool * 10 // 100)
    return min(chest.coins_left, low + secrets.randbelow(spread + 1))


async def claim(db: AsyncSession, room_id: int, user_id: int) -> ChestClaimResult:
    chest = _chest(room_id)
    if chest.status != "open" or chest.coins_left <= 0 or (chest.ends_at and chest.ends_at <= utcnow()):
        raise AppError("Sandık şu an açık değil.", code="chest_closed")
    if user_id in chest.claimed_ids:
        raise ConflictError("Bu sandıktan zaten aldın.", code="chest_already_claimed")
    if not await room_state.is_in_room(room_id, user_id):
        raise ForbiddenError("Sandıktan almak için odada olmalısın.", code="not_in_room")

    # Ayırma: aşağıdaki satırlar arasında `await` yok, yani başka bir istek araya giremez.
    amount = _draw_amount(chest)
    chest.coins_left -= amount
    chest.claimed_ids.add(user_id)

    try:
        balance = await wallet_service.change_balance(
            db, user_id=user_id, currency="coin", delta=amount, type="chest_reward",
            label="Hazine sandığı", room_id=room_id,
            # Aynı sandıktan ikinci kez ödül yazılamaz (veritabanı da engeller).
            idempotency_key=f"chest:{chest.chest_id}",
        )
        await db.commit()
    except Exception as error:
        await db.rollback()
        # Yazılamadı: ayrılan coini sandığa geri koy.
        if _chests.get(room_id) is chest:
            chest.coins_left += amount
            chest.claimed_ids.discard(user_id)
        if isinstance(error, IntegrityError):
            raise ConflictError("Bu sandıktan zaten aldın.", code="chest_already_claimed") from error
        raise

    user = await user_service.present_user(db, await user_service.get_user(db, user_id), viewer_id=None)
    await room_hub.publish(room_id, events.ROOM_CHEST_CLAIMED, {
        "user": user.model_dump(mode="json"), "coins": amount, "coins_left": chest.coins_left,
    })
    if chest.coins_left <= 0:
        await _close(room_id, chest.chest_id)
    return ChestClaimResult(coins=amount, coin_balance=balance)


def drop_room(room_id: int) -> None:
    """Oda kapanınca sandığını da unut."""
    _chests.pop(room_id, None)
