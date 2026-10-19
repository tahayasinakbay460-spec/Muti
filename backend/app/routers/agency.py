"""
Ajans uçları: /api/v1/agencies/... (ajans sahibi ve yayıncılar). Ajansı yönetici kurar (/admin/agencies).
"""
from fastapi import APIRouter

from app.core.deps import CurrentUserId, DbSession
from app.schemas.admin import AgencyDashboard, AgencyTargetRequest, MyAgency
from app.services import agency_service

router = APIRouter(prefix="/agencies", tags=["agencies"])


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
