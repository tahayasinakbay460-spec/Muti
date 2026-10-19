"""
Bağlılık sistemleri uçları:
  /api/v1/rewards/checkin   — günlük giriş ödülü
  /api/v1/tasks             — günlük görevler
  /api/v1/families          — aile (klan) ve aile sohbeti
  /api/v1/couples           — CP (çift)
  /api/v1/leaderboards      — sıralamalar (zengin, çekici, oda, aile × gün, hafta, ay)
  /api/v1/events            — süreli etkinlikler
"""
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.core.deps import CurrentUserId, DbSession
from app.schemas.engagement import (
    CheckInResult, CheckInStatus, CoupleStatus, EventDetail, EventOut, FamilyCreateRequest, FamilyDetail,
    FamilyMessageIn, FamilyMessageOut, FamilyOut, FamilyRoleRequest, FamilyUpdateRequest, Leaderboard,
    LeaderboardKind, LeaderboardPeriod, TaskClaimResult, TaskOut,
)
from app.services import (
    couple_service, engagement_service, event_service, family_service, leaderboard_service,
)

router = APIRouter(tags=["engagement"])


# ── Günlük giriş ve görevler ──────────────────────────────────────────────────

@router.get("/rewards/checkin", response_model=CheckInStatus)
async def get_checkin(user_id: CurrentUserId, db: DbSession):
    return await engagement_service.checkin_status(db, user_id)


@router.post("/rewards/checkin", response_model=CheckInResult)
async def claim_checkin(user_id: CurrentUserId, db: DbSession):
    """Günde bir kez. Art arda gelinen gün arttıkça ödül büyür (7 günlük döngü)."""
    return await engagement_service.claim_checkin(db, user_id)


@router.get("/tasks", response_model=list[TaskOut])
async def list_tasks(user_id: CurrentUserId, db: DbSession):
    return await engagement_service.list_tasks(db, user_id)


@router.post("/tasks/{task_id}/claim", response_model=TaskClaimResult)
async def claim_task(task_id: str, user_id: CurrentUserId, db: DbSession):
    return await engagement_service.claim_task(db, user_id, task_id)


# ── Aile ──────────────────────────────────────────────────────────────────────
# SIRA ÖNEMLİ: "/families/me" adresi "/families/{family_id}" adresinden önce tanımlanmalı.

@router.get("/families", response_model=list[FamilyOut])
async def list_families(user_id: CurrentUserId, db: DbSession, query: Annotated[str, Query(max_length=24)] = ""):
    return await family_service.list_families(db, user_id, query)


@router.post("/families", response_model=FamilyDetail, status_code=status.HTTP_201_CREATED)
async def create_family(data: FamilyCreateRequest, user_id: CurrentUserId, db: DbSession):
    """Aile kurar (coin karşılığı). Zaten bir ailedeysen 409 `already_in_family`."""
    return await family_service.create_family(db, user_id, data)


@router.get("/families/me", response_model=FamilyDetail | None)
async def get_my_family(user_id: CurrentUserId, db: DbSession):
    family_id = await family_service.my_family_id(db, user_id)
    return await family_service.get_detail(db, user_id, family_id) if family_id else None


@router.delete("/families/me/membership", status_code=status.HTTP_204_NO_CONTENT)
async def leave_family(user_id: CurrentUserId, db: DbSession):
    await family_service.leave_family(db, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/families/{family_id}", response_model=FamilyDetail)
async def get_family(family_id: int, user_id: CurrentUserId, db: DbSession):
    return await family_service.get_detail(db, user_id, family_id)


@router.patch("/families/{family_id}", response_model=FamilyDetail)
async def update_family(family_id: int, data: FamilyUpdateRequest, user_id: CurrentUserId, db: DbSession):
    return await family_service.update_family(db, user_id, family_id, data)


@router.delete("/families/{family_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disband_family(family_id: int, user_id: CurrentUserId, db: DbSession):
    """Aileyi dağıtır (yalnızca kurucu)."""
    await family_service.disband_family(db, user_id, family_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/families/{family_id}/join", response_model=FamilyDetail)
async def join_family(family_id: int, user_id: CurrentUserId, db: DbSession):
    return await family_service.join_family(db, user_id, family_id)


@router.delete("/families/{family_id}/members/{target_id}", response_model=FamilyDetail)
async def kick_family_member(family_id: int, target_id: int, user_id: CurrentUserId, db: DbSession):
    return await family_service.kick_member(db, user_id, family_id, target_id)


@router.put("/families/{family_id}/members/{target_id}/role", response_model=FamilyDetail)
async def set_family_role(family_id: int, target_id: int, data: FamilyRoleRequest, user_id: CurrentUserId, db: DbSession):
    return await family_service.set_role(db, user_id, family_id, target_id, data.role)


@router.get("/families/{family_id}/messages", response_model=list[FamilyMessageOut])
async def list_family_messages(family_id: int, user_id: CurrentUserId, db: DbSession, before_id: int | None = None):
    return await family_service.list_messages(db, user_id, family_id, before_id)


@router.post("/families/{family_id}/messages", response_model=FamilyMessageOut, status_code=status.HTTP_201_CREATED)
async def send_family_message(family_id: int, data: FamilyMessageIn, user_id: CurrentUserId, db: DbSession):
    """Mesaj, uygulamada olan üyelere `/ws/me` üzerinden `family:message` olayıyla anında gider."""
    return await family_service.send_message(db, user_id, family_id, data.text)


# ── CP ────────────────────────────────────────────────────────────────────────

@router.get("/couples/me", response_model=CoupleStatus)
async def get_couple_status(user_id: CurrentUserId, db: DbSession):
    return await couple_service.get_status(db, user_id)


@router.delete("/couples/me", response_model=CoupleStatus)
async def break_up(user_id: CurrentUserId, db: DbSession):
    return await couple_service.break_up(db, user_id)


@router.post("/couples/{target_id}", response_model=CoupleStatus)
async def propose(target_id: int, user_id: CurrentUserId, db: DbSession):
    """CP teklif eder (yüzük bedeli düşer; reddedilirse iade edilir)."""
    return await couple_service.propose(db, user_id, target_id)


@router.post("/couples/{partner_id}/accept", response_model=CoupleStatus)
async def accept_proposal(partner_id: int, user_id: CurrentUserId, db: DbSession):
    return await couple_service.accept(db, user_id, partner_id)


@router.delete("/couples/{partner_id}/request", response_model=CoupleStatus)
async def decline_or_withdraw(partner_id: int, user_id: CurrentUserId, db: DbSession):
    """Gelen teklifi reddeder ya da gönderdiğin teklifi geri çeker."""
    return await couple_service.decline(db, user_id, partner_id)


# ── Sıralamalar ve etkinlikler ────────────────────────────────────────────────

@router.get("/leaderboards", response_model=Leaderboard)
async def get_leaderboard(
    user_id: CurrentUserId, db: DbSession, kind: LeaderboardKind = "rich", period: LeaderboardPeriod = "week",
):
    return await leaderboard_service.get_leaderboard(db, user_id, kind, period)


@router.get("/events", response_model=list[EventOut])
async def list_events(_user_id: CurrentUserId, db: DbSession):
    return await event_service.list_events(db)


@router.get("/events/{event_id}", response_model=EventDetail)
async def get_event(event_id: int, user_id: CurrentUserId, db: DbSession):
    return await event_service.get_event(db, user_id, event_id)
