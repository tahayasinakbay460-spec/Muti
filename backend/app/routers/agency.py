"""
Ajans uçları: /api/v1/agencies/... (ajans sahibi ve yayıncılar). Ajansı yönetici kurar (/admin/agencies).
"""
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUserId, DbSession
from app.schemas.admin import AgencyDashboard, AgencyOut, AgencyTargetRequest, MyAgency
from app.services import agency_service

router = APIRouter(prefix="/agencies", tags=["agencies"])


@router.get("", response_model=list[AgencyOut])
async def list_agencies(_user_id: CurrentUserId, db: DbSession, query: Annotated[str, Query(max_length=40)] = ""):
    """Başvurulabilecek ajanslar; ada ya da ajans numarasına göre aranır."""
    return await agency_service.list_public(db, query)


@router.get("/me", response_model=MyAgency)
async def get_my_agency(user_id: CurrentUserId, db: DbSession):
    """Sahibiysen ajans paneli, üyeysen ajansın ve bu ayki kazancın, davet varsa davet."""
    return await agency_service.my_agency(db, user_id)


@router.post("/me/invite/accept", response_model=MyAgency)
async def accept_invite(user_id: CurrentUserId, db: DbSession):
    return await agency_service.answer_invite(db, user_id, accept=True)


@router.post("/me/invite/decline", response_model=MyAgency)
async def decline_invite(user_id: CurrentUserId, db: DbSession):
    return await agency_service.answer_invite(db, user_id, accept=False)


@router.delete("/me/application", response_model=MyAgency)
async def withdraw_application(user_id: CurrentUserId, db: DbSession):
    """Bekleyen ajans başvurumu geri çekerim."""
    return await agency_service.withdraw_application(db, user_id)


@router.post("/me/applications/{target_id}/accept", response_model=AgencyDashboard)
async def accept_application(target_id: int, user_id: CurrentUserId, db: DbSession):
    """Ajans sahibi başvuruyu kabul eder. Reddetmek için: DELETE /me/members/{target_id}."""
    return await agency_service.accept_application(db, user_id, target_id)


@router.delete("/me/membership", response_model=MyAgency)
async def leave_agency(user_id: CurrentUserId, db: DbSession):
    return await agency_service.leave(db, user_id)


@router.post("/me/members/{target_id}", response_model=AgencyDashboard)
async def invite_host(target_id: int, user_id: CurrentUserId, db: DbSession):
    """Ajans sahibi bir yayıncıyı davet eder (yayıncı kabul edince üye olur)."""
    return await agency_service.invite(db, user_id, target_id)


@router.put("/me/members/{target_id}/target", response_model=AgencyDashboard)
async def set_member_target(target_id: int, data: AgencyTargetRequest, user_id: CurrentUserId, db: DbSession):
    return await agency_service.set_target(db, user_id, target_id, data.monthly_target)


@router.delete("/me/members/{target_id}", response_model=AgencyDashboard)
async def remove_member(target_id: int, user_id: CurrentUserId, db: DbSession):
    """Üyeyi çıkarır ya da bekleyen daveti geri çeker."""
    return await agency_service.remove_member(db, user_id, target_id)


@router.post("/{agency_id}/apply", response_model=MyAgency)
async def apply_to_agency(agency_id: int, user_id: CurrentUserId, db: DbSession):
    """Ajansa yayıncı olarak başvurur; ajans sahibi kabul edince üye olunur."""
    return await agency_service.apply(db, user_id, agency_id)
