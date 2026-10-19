"""
/api/v1/notifications — bildirim merkezi
/api/v1/reports       — şikâyet
"""
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.core.deps import CurrentUserId, DbSession
from app.schemas.social import NotificationOut, ReportRequest, UnreadCount
from app.services import notification_service, social_service

router = APIRouter(tags=["social"])


@router.get("/notifications", response_model=list[NotificationOut])
async def list_notifications(
    user_id: CurrentUserId,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    before_id: int | None = None,
):
    """Bildirimlerim, yeniden eskiye. Daha eskileri için `before_id` = listedeki son bildirimin id'si."""
    return await notification_service.list_notifications(db, user_id, limit, before_id)


@router.get("/notifications/unread-count", response_model=UnreadCount)
async def get_unread_notifications(user_id: CurrentUserId, db: DbSession):
    return UnreadCount(unread_count=await notification_service.unread_count(db, user_id))


@router.post("/notifications/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notifications_read(user_id: CurrentUserId, db: DbSession):
    """Bütün bildirimleri okundu say (bildirim ekranı açılınca)."""
    await notification_service.mark_all_read(db, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reports", status_code=status.HTTP_204_NO_CONTENT)
async def create_report(data: ReportRequest, user_id: CurrentUserId, db: DbSession):
    """Bir kullanıcıyı ya da odayı şikâyet eder; yöneticiler inceler."""
    await social_service.create_report(db, user_id, data)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
