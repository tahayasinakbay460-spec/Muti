"""
Günlük giriş ödülü ve günlük görevler.

GÜNLÜK GİRİŞ: Her gün bir kez ödül alınır. Art arda gelinen gün sayısı arttıkça ödül büyür
(7 günlük döngü); bir gün atlanırsa döngü baştan başlar.

GÖREVLER: "3 hediye gönder" gibi günlük işler. Kullanıcı bir işi yaptıkça ilgili sayaç artar
(`record`); hedefe ulaşınca ödül alınabilir. Görev tanımları kodda sabit (TASKS): yeni görev
eklemek iş kararıdır ve yeni bir sayaç gerektirebilir.
"""
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.logs import audit
from app.core.timefmt import local_today
from app.models import DailyCheckIn, TaskClaim, TaskCounter
from app.schemas.engagement import CheckInResult, CheckInStatus, TaskClaimResult, TaskOut
from app.services import wallet_service

# 7 günlük döngü: 1. gün 10 coin ... 7. gün 200 coin.
CHECKIN_REWARDS = (10, 20, 30, 50, 80, 120, 200)

# Sayaç adları: kodun neresinde artırıldıkları
METRIC_ROOM_JOIN = "room_join"         # realtime/room_socket.py — odaya giriş
METRIC_CHAT_MESSAGE = "chat_message"   # realtime/room_socket.py — oda sohbetine mesaj
METRIC_GIFT_SENT = "gift_sent"         # services/gift_service.py — hediye gönderme (adet değil, gönderim)
METRIC_FOLLOW = "follow"               # services/user_service.py — birini takip etme


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    metric: str
    target: int
    coins: int


TASKS = (
    Task("join_room", "Bir odaya katıl", METRIC_ROOM_JOIN, 1, 10),
    Task("chat_5", "Odada 5 mesaj yaz", METRIC_CHAT_MESSAGE, 5, 20),
    Task("gift_3", "3 kez hediye gönder", METRIC_GIFT_SENT, 3, 50),
    Task("follow_1", "Yeni birini takip et", METRIC_FOLLOW, 1, 10),
)
TASKS_BY_ID = {task.id: task for task in TASKS}


# ── Günlük giriş ──────────────────────────────────────────────────────────────

async def _next_streak_day(db: AsyncSession, user_id: int) -> tuple[int, bool]:
    """(bugün alınacak ya da alınmış gün numarası 1-7, bugün alındı mı)"""
    today = local_today()
    last = await db.scalar(
        select(DailyCheckIn).where(DailyCheckIn.user_id == user_id).order_by(DailyCheckIn.day.desc()).limit(1)
    )
    if last is None:
        return 1, False
    if last.day == today:
        return last.streak_day, True
    if last.day == today - timedelta(days=1):
        return last.streak_day % len(CHECKIN_REWARDS) + 1, False
    return 1, False


async def checkin_status(db: AsyncSession, user_id: int) -> CheckInStatus:
    day, claimed = await _next_streak_day(db, user_id)
    return CheckInStatus(day=day, claimed_today=claimed, rewards=list(CHECKIN_REWARDS))


async def claim_checkin(db: AsyncSession, user_id: int) -> CheckInResult:
    day, claimed = await _next_streak_day(db, user_id)
    if claimed:
        raise ConflictError("Bugünkü giriş ödülünü zaten aldın.", code="checkin_claimed")
    coins = CHECKIN_REWARDS[day - 1]
    try:
        # (user_id, day) benzersiz: aynı anda iki istek gelirse ikincisi burada reddedilir.
        db.add(DailyCheckIn(user_id=user_id, day=local_today(), streak_day=day, coins=coins))
        await db.flush()
        balance = await wallet_service.change_balance(
            db, user_id=user_id, currency="coin", delta=coins, type="daily_checkin",
            label=f"Günlük giriş ödülü ({day}. gün)",
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError("Bugünkü giriş ödülünü zaten aldın.", code="checkin_claimed")
    except Exception:
        await db.rollback()
        raise
    audit("daily_checkin", day=day, coins=coins)
    return CheckInResult(day=day, coins=coins, coin_balance=balance)


# ── Görev sayaçları ───────────────────────────────────────────────────────────

async def record(db: AsyncSession, user_id: int, metric: str, amount: int = 1) -> None:
    """
    Sayaç artırır: "varsa artır, yoksa 1 ile ekle" TEK komutla (UPSERT). Önce okuyup sonra
    yazsaydık aynı anda gelen iki işlemden biri kaybolurdu. Commit YAPMAZ: çağıranın
    transaction'ının parçasıdır (ör. hediye ile aynı anda kalıcı olur).
    """
    values = {"user_id": user_id, "metric": metric, "day": local_today(), "count": amount}
    # UPSERT yazımı veritabanına göre değişir; ikisi de aynı işi yapar.
    insert = postgres_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    statement = insert(TaskCounter).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=["user_id", "metric", "day"],
        set_={"count": TaskCounter.count + statement.excluded.count},
    )
    await db.execute(statement)


async def record_now(user_id: int, metric: str) -> None:
    """Kendi veritabanı oturumunu açıp sayacı artırır (WebSocket gibi oturumu olmayan yerler için)."""
    async with SessionLocal() as db:
        await record(db, user_id, metric)
        await db.commit()


# ── Görevler ──────────────────────────────────────────────────────────────────

async def list_tasks(db: AsyncSession, user_id: int) -> list[TaskOut]:
    today = local_today()
    counts = dict((await db.execute(
        select(TaskCounter.metric, TaskCounter.count).where(TaskCounter.user_id == user_id, TaskCounter.day == today)
    )).all())
    claimed = set(await db.scalars(
        select(TaskClaim.task_id).where(TaskClaim.user_id == user_id, TaskClaim.day == today)
    ))
    return [
        TaskOut(
            id=task.id, title=task.title, target=task.target, coins=task.coins,
            progress=min(counts.get(task.metric, 0), task.target), claimed=task.id in claimed,
        )
        for task in TASKS
    ]


async def claim_task(db: AsyncSession, user_id: int, task_id: str) -> TaskClaimResult:
    task = TASKS_BY_ID.get(task_id)
    if task is None:
        raise NotFoundError("Görev bulunamadı.")
    today = local_today()
    progress = await db.scalar(
        select(TaskCounter.count).where(
            TaskCounter.user_id == user_id, TaskCounter.metric == task.metric, TaskCounter.day == today,
        )
    ) or 0
    if progress < task.target:
        raise AppError("Görev henüz tamamlanmadı.", code="task_not_completed")
    try:
        # (user_id, task_id, day) birincil anahtar: aynı görevin ödülü günde bir kez yazılabilir.
        db.add(TaskClaim(user_id=user_id, task_id=task.id, day=today, coins=task.coins))
        await db.flush()
        balance = await wallet_service.change_balance(
            db, user_id=user_id, currency="coin", delta=task.coins, type="task_reward",
            label=f"Görev ödülü: {task.title}",
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError("Bu görevin ödülünü bugün zaten aldın.", code="task_claimed")
    except Exception:
        await db.rollback()
        raise
    audit("task_reward", task_id=task.id, coins=task.coins)
    return TaskClaimResult(task_id=task.id, coins=task.coins, coin_balance=balance)

