"""
Uygulama geneli yönetim paneli: /api/v1/admin/... — yalnızca `is_admin` kullanıcılar (CurrentAdmin).
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response, status

from app.core.deps import CurrentAdmin, DbSession
from app.schemas.admin import (
    AdminConversationOut, AdminMessageOut, AdminReportOut, AdminRoomOut, AdminStats, AdminTransactionOut, AdminUserOut,
    AgencyCreateRequest, AgencyOut, BalanceAdjustRequest, BalanceAdjustResult, BanRequest, BroadcastRequest,
    BroadcastResult, CatalogGiftOut, CatalogGiftUpdate, CatalogPackageOut, CatalogPackageUpdate, FinanceSummary,
    GrantVipRequest, ReportResolveRequest,
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
async def search_users(
    _admin: CurrentAdmin, db: DbSession, query: Annotated[str, Query(max_length=60)] = "",
    sort: Literal["newest", "richest", "reported"] = "newest",
):
    """Ad, kullanıcı adı, e-posta ya da ID ile arar; banlı kullanıcılar da listelenir."""
    return await admin_service.search_users(db, query, sort)


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


# ── Finans, kayıtlar, katalog (masaüstü panel) ────────────────────────────────

@router.get("/finance", response_model=FinanceSummary)
async def get_finance(_admin: CurrentAdmin, db: DbSession, days: Annotated[int, Query(ge=1, le=90)] = 14):
    """Son günlerin coin satışı, hediye, VIP, mağaza ve yeni kullanıcı serileri; en iyiler."""
    return await admin_service.finance_summary(db, days)


@router.get("/transactions", response_model=list[AdminTransactionOut])
async def list_transactions(
    _admin: CurrentAdmin, db: DbSession, type: str | None = None, user_id: int | None = None,
    before_id: int | None = None, limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    return await admin_service.list_transactions(db, type, user_id, before_id, limit)


@router.get("/conversations", response_model=list[AdminConversationOut])
async def list_conversations(_admin: CurrentAdmin, db: DbSession, user_id: int | None = None, before_id: int | None = None):
    """DEMO: yönetici bütün özel sohbetleri görebiliyor (bkz. admin_service notu)."""
    return await admin_service.list_conversations(db, user_id, before_id)


@router.get("/conversations/{conversation_id}/messages", response_model=list[AdminMessageOut])
async def get_conversation_messages(conversation_id: int, _admin: CurrentAdmin, db: DbSession):
    """Her görüntüleme denetim kaydına yazılır."""
    return await admin_service.conversation_messages(db, conversation_id)


@router.get("/rooms/{room_id}/messages", response_model=list[AdminMessageOut])
async def get_room_messages(room_id: int, _admin: CurrentAdmin, db: DbSession, before_id: int | None = None):
    """Oda sohbet geçmişi (odadan silinenler de, `deleted_at` dolu). Görüntüleme kayda yazılır."""
    return await admin_service.room_messages(db, room_id, before_id)


@router.get("/catalog/gifts", response_model=list[CatalogGiftOut])
async def list_catalog_gifts(_admin: CurrentAdmin, db: DbSession):
    return await admin_service.list_catalog_gifts(db)


@router.patch("/catalog/gifts/{gift_id}", response_model=CatalogGiftOut)
async def update_gift(gift_id: int, data: CatalogGiftUpdate, _admin: CurrentAdmin, db: DbSession):
    return await admin_service.update_gift(db, gift_id, data)


@router.get("/catalog/packages", response_model=list[CatalogPackageOut])
async def list_catalog_packages(_admin: CurrentAdmin, db: DbSession):
    return await admin_service.list_catalog_packages(db)


@router.patch("/catalog/packages/{package_id}", response_model=CatalogPackageOut)
async def update_package(package_id: int, data: CatalogPackageUpdate, _admin: CurrentAdmin, db: DbSession):
    return await admin_service.update_package(db, package_id, data)


@router.post("/users/{user_id}/vip", response_model=AdminUserOut)
async def grant_vip(user_id: int, data: GrantVipRequest, _admin: CurrentAdmin, db: DbSession):
    """Ücretsiz VIP verir (üyelik eşyalarıyla); para hareketi yok."""
    return await admin_service.grant_vip(db, user_id, data.level, data.days)


@router.post("/broadcast", response_model=BroadcastResult)
async def broadcast(data: BroadcastRequest, _admin: CurrentAdmin, db: DbSession):
    """Bütün aktif kullanıcılara sistem bildirimi."""
    return await admin_service.broadcast(db, data.text)

