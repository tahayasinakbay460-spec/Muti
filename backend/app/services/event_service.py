"""
Süreli etkinlikler (kampanyalar): başlangıç-bitiş arasında en çok hediye gönderen (ya da alan)
ilk sıralar coin ödülü kazanır.

ÖDÜL DAĞITIMI: Ayrı bir zamanlayıcı (cron) yok. Etkinlik bittikten sonra biri listeye ya da
etkinliğe ilk baktığında `finalize` çalışır. "Henüz dağıtılmadıysa dağıtıldı olarak işaretle"
adımı tek komutla yapıldığı için aynı anda gelen iki istekten yalnızca biri ödül dağıtır.
DEMO KISAYOLU: Canlıda bu iş zamanlanmış bir görevle (ör. her dakika) yapılmalı; kimse
bakmasa da ödüller zamanında verilsin.
"""
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.core.errors import NotFoundError
from app.core.logs import audit
from app.core.timefmt import as_utc
from app.models import Event
from app.schemas.engagement import EventDetail, EventOut
from app.services import leaderboard_service, notification_service, wallet_service


def _status(event: Event) -> str:
    now = utcnow()
    if as_utc(event.starts_at) > now:
        return "upcoming"
    return "active" if as_utc(event.ends_at) > now else "ended"


def _out(event: Event) -> EventOut:
    return EventOut(
        id=event.id, title=event.title, description=event.description, emoji=event.emoji, metric=event.metric,
        starts_at=as_utc(event.starts_at), ends_at=as_utc(event.ends_at), rewards=list(event.rewards),
        status=_status(event),
    )


async def finalize(db: AsyncSession, event: Event) -> None:
    """Bitmiş etkinliğin ödüllerini bir kez dağıtır."""
    if _status(event) != "ended" or event.finalized_at is not None:
        return
    claimed = await db.execute(
        update(Event).where(Event.id == event.id, Event.finalized_at.is_(None)).values(finalized_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        await db.rollback()   # başka bir istek bizden önce dağıttı
        return
    winners = await leaderboard_service.user_scores(
        db, event.metric, as_utc(event.starts_at), as_utc(event.ends_at), limit=len(event.rewards),
    )
    for rank, ((user_id, _score), coins) in enumerate(zip(winners, event.rewards), 1):
        await wallet_service.change_balance(
            db, user_id=user_id, currency="coin", delta=coins, type="event_reward",
            label=f"{event.title}: {rank}. sıra ödülü",
            # Aynı etkinlikten aynı kişiye ikinci ödül yazılamaz (veritabanı da engeller).
            idempotency_key=f"event:{event.id}",
        )
    await db.commit()
    await db.refresh(event)
    audit("event_finalized", event_id=event.id, winners=[uid for uid, _ in winners[: len(event.rewards)]])
    for rank, ((user_id, _score), coins) in enumerate(zip(winners, event.rewards), 1):
        await notification_service.notify(
            db, user_id, "event_reward", f"🏆 {event.title} etkinliğinde {rank}. oldun! +{coins} coin",
        )


async def list_events(db: AsyncSession) -> list[EventOut]:
    """Süren ve yaklaşan etkinlikler önce, bitenlerden son 5'i sonra."""
    events = list(await db.scalars(select(Event).order_by(Event.ends_at.desc())))
    for event in events:
        await finalize(db, event)
    order = {"active": 0, "upcoming": 1, "ended": 2}
    outs = sorted((_out(event) for event in events), key=lambda e: (order[e.status], e.ends_at))
    ended = [e for e in outs if e.status == "ended"][:5]
    return [e for e in outs if e.status != "ended"] + ended


async def get_event(db: AsyncSession, viewer_id: int, event_id: int) -> EventDetail:
    event = await db.get(Event, event_id)
    if event is None:
        raise NotFoundError("Etkinlik bulunamadı.")
    await finalize(db, event)
    entries, me = await leaderboard_service.user_entries(
        db, viewer_id, event.metric, as_utc(event.starts_at), as_utc(event.ends_at),
    )
    return EventDetail(**_out(event).model_dump(), entries=entries, me=me)
