"""
Uygulama geneli yönetim paneli: /api/v1/admin/...

Her uç iki şey ister (bkz. core/deps.py Staff):
  - Panel oturumu: `POST /admin/session` ile şifre girilerek alınan `X-Staff-Token`.
  - Rolün o işleme yetkisi (bkz. core/permissions.py). `recent_auth=True` olan kritik işlemlerde
    şifrenin son birkaç dakikada girilmiş olması da gerekir.
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import CurrentStaff, CurrentUser, DbSession, Staff, require_recent_auth
from app.core.errors import ForbiddenError
from app.core.ratelimit import limit_auth_attempts
from app.schemas.admin import (
    AdminConversationOut, AdminMessageOut, AdminReportOut, AdminRoomOut, AdminStats, AdminTransactionOut, AdminUserOut,
    AgencyCreateRequest, AgencyOut, BalanceAdjustRequest, BalanceAdjustResult, BanRequest, BroadcastRequest,
    BroadcastResult, CatalogGiftOut, CatalogGiftUpdate, CatalogPackageOut, CatalogPackageUpdate, FinanceSummary,
    GrantVipRequest, ReportResolveRequest, StaffActionOut, StaffMemberOut, StaffRoleUpdate, StaffSessionOut,
    StaffSessionRequest,
)
from app.services import admin_service, agency_service, staff_service

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Panel oturumu ─────────────────────────────────────────────────────────────

@router.post("/session", response_model=StaffSessionOut, dependencies=[Depends(limit_auth_attempts)])
async def start_session(data: StaffSessionRequest, user: CurrentUser):
    """Şifreyi yeniden doğrular, panel token'ı verir. Kritik işlemden önce de çağrılır."""
    return await staff_service.start_session(user, data.password)


@router.get("/session", response_model=StaffSessionOut)
async def get_session(staff: CurrentStaff):
    """Açık panel oturumunun rolü ve yetkileri (sayfa yenilenince menüyü çizmek için)."""
    return staff_service.session_out(staff.user, staff.auth_time)


# ── Özet ve şikâyetler ────────────────────────────────────────────────────────

@router.get("/stats", response_model=AdminStats)
async def get_stats(_staff: Staff("dashboard.view"), db: DbSession):
    return await admin_service.get_stats(db)


@router.get("/reports", response_model=list[AdminReportOut])
async def list_reports(
    _staff: Staff("reports.manage"), db: DbSession,
    status_filter: Annotated[Literal["open", "closed"], Query(alias="status")] = "open",
):
    return await admin_service.list_reports(db, status_filter)


@router.post("/reports/{report_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
async def resolve_report(report_id: int, data: ReportResolveRequest, staff: Staff("reports.manage"), db: DbSession):
    """Aynı hedef hakkındaki bütün açık şikâyetler aynı kararla kapanır."""
    # Şikâyetten ban/oda kapatma, doğrudan yapılanla aynı yetkiyi ister.
    needed = {"ban_user": "users.ban", "close_room": "rooms.manage"}.get(data.action)
    if needed and not staff.can(needed):
        raise ForbiddenError("Rolünün bu karara yetkisi yok.", code="permission_denied")
    if data.action == "ban_user":
        require_recent_auth(staff)
    await admin_service.resolve_report(db, staff.user.id, report_id, data.action, data.note)


# ── Kullanıcılar ──────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[AdminUserOut])
async def search_users(
    _staff: Staff("users.view"), db: DbSession, query: Annotated[str, Query(max_length=60)] = "",
    sort: Literal["newest", "richest", "reported"] = "newest",
):
    """Ad, kullanıcı adı, e-posta ya da ID ile arar; banlı kullanıcılar da listelenir."""
    return await admin_service.search_users(db, query, sort)


@router.get("/users/{user_id}", response_model=AdminUserOut)
async def get_user(user_id: int, _staff: Staff("users.view"), db: DbSession):
    return await admin_service.get_user_detail(db, user_id)


@router.post("/users/{user_id}/ban", response_model=AdminUserOut)
async def ban_user(user_id: int, data: BanRequest, staff: Staff("users.ban", recent_auth=True), db: DbSession):
    """Anında etkili: oturumlar kapanır, açık bağlantılar kesilir."""
    return await admin_service.ban_user(db, staff.user.id, user_id, data.reason)


@router.delete("/users/{user_id}/ban", response_model=AdminUserOut)
async def unban_user(user_id: int, staff: Staff("users.ban", recent_auth=True), db: DbSession):
    return await admin_service.unban_user(db, staff.user.id, user_id)


@router.post("/users/{user_id}/balance", response_model=BalanceAdjustResult)
async def adjust_balance(
    user_id: int, data: BalanceAdjustRequest, staff: Staff("users.balance", recent_auth=True), db: DbSession,
):
    """Bakiye düzeltmesi (+ ekler, - düşer). Para defterine `admin_adjustment` olarak yazılır."""
    return await admin_service.adjust_balance(db, staff.user.id, user_id, data.currency, data.amount, data.reason)


@router.post("/users/{user_id}/vip", response_model=AdminUserOut)
async def grant_vip(user_id: int, data: GrantVipRequest, staff: Staff("users.vip", recent_auth=True), db: DbSession):
    """Ücretsiz VIP verir (üyelik eşyalarıyla); para hareketi yok."""
    return await admin_service.grant_vip(db, staff.user.id, user_id, data.level, data.days)


# ── Odalar ve mesajlar ────────────────────────────────────────────────────────

@router.get("/rooms", response_model=list[AdminRoomOut])
async def list_rooms(_staff: Staff("rooms.manage"), db: DbSession):
    return await admin_service.list_rooms(db)


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def close_room(room_id: int, staff: Staff("rooms.manage"), db: DbSession):
    await admin_service.close_room(db, staff.user.id, room_id, reason="admin_panel")


@router.get("/conversations", response_model=list[AdminConversationOut])
async def list_conversations(
    _staff: Staff("messages.read"), db: DbSession, user_id: int | None = None, before_id: int | None = None,
):
    """DEMO: personel bütün özel sohbetleri görebiliyor (bkz. admin_service notu)."""
    return await admin_service.list_conversations(db, user_id, before_id)


@router.get("/conversations/{conversation_id}/messages", response_model=list[AdminMessageOut])
async def get_conversation_messages(conversation_id: int, staff: Staff("messages.read"), db: DbSession):
    """Her görüntüleme denetim kaydına ve personel işlem kaydına yazılır."""
    return await admin_service.conversation_messages(db, staff.user.id, conversation_id)


@router.get("/rooms/{room_id}/messages", response_model=list[AdminMessageOut])
async def get_room_messages(room_id: int, staff: Staff("messages.read"), db: DbSession, before_id: int | None = None):
    """Oda sohbet geçmişi (odadan silinenler de, `deleted_at` dolu). Görüntüleme kayda yazılır."""
    return await admin_service.room_messages(db, staff.user.id, room_id, before_id)


# ── Finans ────────────────────────────────────────────────────────────────────

@router.get("/finance", response_model=FinanceSummary)
async def get_finance(_staff: Staff("finance.view"), db: DbSession, days: Annotated[int, Query(ge=1, le=90)] = 14):
    """Son günlerin coin satışı, hediye, VIP, mağaza ve yeni kullanıcı serileri; en iyiler."""
    return await admin_service.finance_summary(db, days)


@router.get("/transactions", response_model=list[AdminTransactionOut])
async def list_transactions(
    _staff: Staff("finance.view"), db: DbSession, type: str | None = None, user_id: int | None = None,
    before_id: int | None = None, limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    return await admin_service.list_transactions(db, type, user_id, before_id, limit)


# ── Katalog, ajans, duyuru ────────────────────────────────────────────────────

@router.get("/catalog/gifts", response_model=list[CatalogGiftOut])
async def list_catalog_gifts(_staff: Staff("catalog.manage"), db: DbSession):
    return await admin_service.list_catalog_gifts(db)


@router.patch("/catalog/gifts/{gift_id}", response_model=CatalogGiftOut)
async def update_gift(gift_id: int, data: CatalogGiftUpdate, staff: Staff("catalog.manage", recent_auth=True), db: DbSession):
    return await admin_service.update_gift(db, staff.user.id, gift_id, data)


@router.get("/catalog/packages", response_model=list[CatalogPackageOut])
async def list_catalog_packages(_staff: Staff("catalog.manage"), db: DbSession):
    return await admin_service.list_catalog_packages(db)


@router.patch("/catalog/packages/{package_id}", response_model=CatalogPackageOut)
async def update_package(
    package_id: int, data: CatalogPackageUpdate, staff: Staff("catalog.manage", recent_auth=True), db: DbSession,
):
    return await admin_service.update_package(db, staff.user.id, package_id, data)


@router.get("/agencies", response_model=list[AgencyOut])
async def list_agencies(_staff: Staff("agencies.manage"), db: DbSession):
    return await agency_service.list_agencies(db)


@router.post("/agencies", response_model=AgencyOut, status_code=status.HTTP_201_CREATED)
async def create_agency(data: AgencyCreateRequest, staff: Staff("agencies.manage"), db: DbSession):
    return await admin_service.create_agency(db, staff.user.id, data.name, data.owner_id, data.commission_percent)


@router.post("/broadcast", response_model=BroadcastResult)
async def broadcast(data: BroadcastRequest, staff: Staff("broadcast.send", recent_auth=True), db: DbSession):
    """Bütün aktif kullanıcılara sistem bildirimi."""
    return await admin_service.broadcast(db, staff.user.id, data.text)


# ── Personel ──────────────────────────────────────────────────────────────────

@router.get("/staff", response_model=list[StaffMemberOut])
async def list_staff(_staff: Staff("staff.manage"), db: DbSession):
    return await staff_service.list_staff(db)


@router.put("/staff/{user_id}", response_model=StaffMemberOut | None)
async def set_staff_role(
    user_id: int, data: StaffRoleUpdate, staff: Staff("staff.manage", recent_auth=True), db: DbSession,
):
    """Rol verir ya da değiştirir; `role: null` panel erişimini kaldırır (yanıt null)."""
    return await staff_service.set_role(db, staff.user, user_id, data.role)


@router.get("/staff/actions", response_model=list[StaffActionOut])
async def list_staff_actions(
    _staff: Staff("staff.audit"), db: DbSession, actor_id: int | None = None, before_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Personel işlem kaydı: kim, ne zaman, kime, ne yaptı (yeniden eskiye)."""
    return await staff_service.list_actions(db, actor_id, before_id, limit)
