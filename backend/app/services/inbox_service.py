"""
Mesajlar ekranındaki kısayol rozetleri: Arkadaşlık isteği, Etkinlik, Ziyaretçi.

Rozet "toplam" değil "yeni" sayısını gösterir. Eskiden etkinlik rozeti "şu an süren etkinlik
sayısı"ydı: etkinliğe bakıp çıkınca da 1 yazmaya devam ediyordu. Artık her bölüm için kişinin
o ekranı en son açtığı an (`InboxSeen.seen_at`) tutulur; rozet = o andan sonra gelenler.
Ekran hiç açılmadıysa (kayıt yok) hepsi yeni sayılır.
"""
from datetime import datetime

from sqlalchemy import and_, exists, func, select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.database import utcnow
from app.models import Event, Follow, InboxSeen, ProfileVisit, User
from app.schemas.user import InboxBadges, InboxSection


async def _seen_times(db: AsyncSession, user_id: int) -> dict[str, datetime]:
    rows = await db.execute(select(InboxSeen.section, InboxSeen.seen_at).where(InboxSeen.user_id == user_id))
    return dict(rows.all())


def _after(column, seen_at: datetime | None):
    # Hiç bakılmadıysa koşul yok (hepsi yeni); bakıldıysa yalnızca o andan sonrakiler
    return column > seen_at if seen_at is not None else true()


async def badge_counts(db: AsyncSession, user_id: int) -> InboxBadges:
    seen = await _seen_times(db, user_id)

    # Yeni arkadaşlık isteği: beni takip eden, benim geri takip etmediğim, son bakıştan sonra gelen
    back = aliased(Follow)
    requests = await db.scalar(
        select(func.count()).select_from(Follow)
        .join(User, User.id == Follow.follower_id)
        .where(
            Follow.followee_id == user_id, User.is_active,
            _after(Follow.created_at, seen.get("requests")),
            ~exists().where(and_(back.follower_id == user_id, back.followee_id == Follow.follower_id)),
        )
    )

    # Yeni ziyaret: son bakıştan sonra profilime bakan (aynı kişi tekrar bakarsa yine yeni sayılır)
    visitors = await db.scalar(
        select(func.count()).select_from(ProfileVisit)
        .join(User, User.id == ProfileVisit.visitor_id)
        .where(ProfileVisit.visited_id == user_id, User.is_active, _after(ProfileVisit.visited_at, seen.get("visitors")))
    )

    # Yeni etkinlik: şu an sürüyor ve ben son baktıktan sonra başladı
    now = utcnow()
    events = await db.scalar(
        select(func.count()).select_from(Event)
        .where(Event.starts_at <= now, Event.ends_at > now, _after(Event.starts_at, seen.get("events")))
    )
    return InboxBadges(requests=requests or 0, events=events or 0, visitors=visitors or 0)


async def mark_seen(db: AsyncSession, user_id: int, section: InboxSection) -> None:
    """Bölümün ekranı açıldı: `seen_at` = şimdi. Satır yoksa eklenir (aynı anda iki istek gelirse ikincisi günceller)."""
    now = utcnow()
    row = await db.get(InboxSeen, (user_id, section))
    if row is not None:
        row.seen_at = now
        await db.commit()
        return
    db.add(InboxSeen(user_id=user_id, section=section, seen_at=now))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        row = await db.get(InboxSeen, (user_id, section))
        row.seen_at = now
        await db.commit()
