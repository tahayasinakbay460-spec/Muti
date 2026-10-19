"""
Bildirim merkezi: "seni takip etti", "hediye aldın", "seviye atladın" gibi bildirimler.

Bildirim iki şekilde ulaşır:
  1. Veritabanına yazılır → bildirim ekranında listelenir, okunmamışlar rozette sayılır.
  2. Kişi o an uygulamadaysa kişiye özel kanaldan (/ws/me) `notification:new` ile anında itilir.
Uygulama kapalıyken telefona bildirim (push: APNs/FCM) mobil aşamanın işi; o da buradan,
`notify` içinden tetiklenecek.

ÖNEMLİ: `notify`, çağıran taraf asıl işini (takip, hediye) commit ETTİKTEN SONRA çağrılır
ve kendi küçük transaction'ını açar. Böylece bildirim yazılamasa bile asıl işlem bozulmaz;
gerçekleşmemiş bir işlemin bildirimi de hiç gitmez.
"""
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timefmt import as_utc, time_ago_label
from app.models import Notification
from app.realtime import events
from app.realtime.hub import user_hub
from app.schemas.social import NotificationOut
from app.services import user_service


async def notify(
    db: AsyncSession, user_id: int, type: str, text: str, actor_id: int | None = None, data: dict | None = None,
) -> None:
    """Bildirim oluşturur ve kişi bağlıysa anında iletir."""
    if actor_id == user_id:
        return
    # Engellediğin birinden bildirim gelmez (ve tersi).
    if actor_id is not None and await user_service.is_blocked_between(db, user_id, actor_id):
        return
    notification = Notification(user_id=user_id, type=type, text=text, actor_id=actor_id, data=data or {})
    db.add(notification)
    await db.commit()

    out = (await _present(db, [notification], user_id))[0]
    await user_hub.publish(user_id, events.NOTIFICATION_NEW, out.model_dump(mode="json"))


async def _present(db: AsyncSession, notifications: list[Notification], viewer_id: int) -> list[NotificationOut]:
    actors = await user_service.load_users_out(
        db, {n.actor_id for n in notifications if n.actor_id is not None}, viewer_id,
    )
    return [
        NotificationOut(
            id=n.id, type=n.type, text=n.text, actor=actors.get(n.actor_id), data=n.data,
            is_read=n.is_read, created_at=as_utc(n.created_at), time_label=time_ago_label(n.created_at),
        )
        for n in notifications
    ]


async def list_notifications(
    db: AsyncSession, user_id: int, limit: int = 30, before_id: int | None = None,
) -> list[NotificationOut]:
    """Bildirimlerim, yeniden eskiye. Daha eskileri için `before_id` (bkz. wallet_service sayfalama notu)."""
    statement = (
        select(Notification).where(Notification.user_id == user_id).order_by(Notification.id.desc()).limit(limit)
    )
    if before_id is not None:
        statement = statement.where(Notification.id < before_id)
    return await _present(db, list(await db.scalars(statement)), user_id)


async def unread_count(db: AsyncSession, user_id: int) -> int:
    return await db.scalar(
        select(func.count()).select_from(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
    )


async def mark_all_read(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await db.commit()
