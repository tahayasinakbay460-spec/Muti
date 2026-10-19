"""
Uygulama geneli yönetim paneli: /api/v1/admin/... — yalnızca `is_admin` kullanıcılar (CurrentAdmin).
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response, status

from app.core.deps import CurrentAdmin, DbSession
from app.schemas.admin import (
    AdminReportOut, AdminRoomOut, AdminStats, AdminUserOut, AgencyCreateRequest, AgencyOut, BalanceAdjustRequest,
    BalanceAdjustResult, BanRequest, ReportResolveRequest,
)
from app.services import admin_service, agency_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStats)
async def get_stats(_admin: CurrentAdmin, db: DbSession):
    return await admin_service.get_stats(db)


@router.get("/reports", response_model=list[AdminReportOut])
async def list_reports(_admin: CurrentAdmin, db: DbSession, status_filter: Annotated[Literal["open", "closed"], Query(alias="status")] = "open"):
    return await admin_service.list_reports(db, status_filter)


@router.post("/reports/{report_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
async def resolve_report(report_id: int, data: ReportResolveRequest, admin: CurrentAdmin, db: DbSession):
    """Aynı hedef hakkındaki bütün açık şikâyetler aynı kararla kapanır."""
    await admin_service.resolve_report(db, admin.id, report_id, data.action, data.note)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users", response_model=list[AdminUserOut])
async def search_users(_admin: CurrentAdmin, db: DbSession, query: Annotated[str, Query(max_length=60)] = ""):
    """Ad, kullanıcı adı, e-posta ya da ID ile arar; banlı kullanıcılar da listelenir."""
    return await admin_service.search_users(db, query)


@router.get("/users/{user_id}", response_model=AdminUserOut)
async def get_user(user_id: int, _admin: CurrentAdmin, db: DbSession):
    return await admin_service.get_user_detail(db, user_id)


@router.post("/users/{user_id}/ban", response_model=AdminUserOut)
async def ban_user(user_id: int, data: BanRequest, admin: CurrentAdmin, db: DbSession):
    """Anında etkili: oturumlar kapanır, açık bağlantılar kesilir."""
    return await admin_service.ban_user(db, admin.id, user_id, data.reason)


@router.delete("/users/{user_id}/ban", response_model=AdminUserOut)
async def unban_user(user_id: int, _admin: CurrentAdmin, db: DbSession):
    return await admin_service.unban_user(db, user_id)


@router.post("/users/{user_id}/balance", response_model=BalanceAdjustResult)
async def adjust_balance(user_id: int, data: BalanceAdjustRequest, _admin: CurrentAdmin, db: DbSession):
    """Bakiye düzeltmesi (+ ekler, - düşer). Para defterine `admin_adjustment` olarak yazılır."""
    return await admin_service.adjust_balance(db, user_id, data.currency, data.amount, data.reason)


@router.get("/rooms", response_model=list[AdminRoomOut])
async def list_rooms(_admin: CurrentAdmin, db: DbSession):
    return await admin_service.list_rooms(db)


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def close_room(room_id: int, _admin: CurrentAdmin, db: DbSession):
    await admin_service.close_room(db, room_id, reason="admin_panel")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/agencies", response_model=list[AgencyOut])
async def list_agencies(_admin: CurrentAdmin, db: DbSession):
    return await agency_service.list_agencies(db)


@router.post("/agencies", response_model=AgencyOut, status_code=status.HTTP_201_CREATED)
async def create_agency(data: AgencyCreateRequest, _admin: CurrentAdmin, db: DbSession):
    return await agency_service.create_agency(db, data.name, data.owner_id, data.commission_percent)
