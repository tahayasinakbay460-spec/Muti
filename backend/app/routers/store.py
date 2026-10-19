"""
Mağaza ve VIP uçları:
  /api/v1/store/items          — kozmetik eşyalar (çerçeve, giriş efekti, sohbet balonu)
  /api/v1/users/{id}/items     — bir kullanıcının sahip olduğu eşyalar (profil)
  /api/v1/vip                  — VIP üyelik durumu, satın alma, günlük ödül
"""
from typing import Literal

from fastapi import APIRouter

from app.core.deps import CurrentUser, CurrentUserId, DbSession
from app.routers.economy import IdempotencyKey
from app.schemas.store import (
    DailyRewardResult, EquipRequest, OwnedItemOut, StoreItemOut, StorePurchaseRequest, StorePurchaseResult,
    VipPurchaseRequest, VipPurchaseResult, VipStatus,
)
from app.services import store_service, user_service, vip_service

router = APIRouter(tags=["store"])


@router.get("/store/items", response_model=list[StoreItemOut])
async def list_store_items(
    user_id: CurrentUserId, db: DbSession, kind: Literal["frame", "entry_effect", "chat_bubble"] | None = None,
):
    """Mağaza eşyaları; her birinde isteği atanın sahip olup olmadığı ve takılı olup olmadığı."""
    return await store_service.list_items(db, user_id, kind)


@router.post("/store/items/{item_id}/purchase", response_model=StorePurchaseResult)
async def purchase_store_item(
    item_id: int, data: StorePurchaseRequest, user_id: CurrentUserId, db: DbSession,
    idempotency_key: IdempotencyKey = None,
):
    """Eşyayı coinle alır ve takar. Zaten sahipsen süre kalan sürenin üstüne eklenir."""
    return await store_service.purchase_item(db, user_id, item_id, data.days, idempotency_key)


@router.put("/store/items/{item_id}/equip", response_model=StoreItemOut)
async def equip_store_item(item_id: int, data: EquipRequest, user_id: CurrentUserId, db: DbSession):
    """Sahip olunan eşyayı takar ya da çıkarır. Aynı türden takılı olan otomatik çıkar."""
    return await store_service.set_equipped(db, user_id, item_id, data.equipped)


@router.get("/users/{target_id}/items", response_model=list[OwnedItemOut])
async def list_user_items(target_id: int, _user_id: CurrentUserId, db: DbSession):
    await user_service.get_user(db, target_id)
    return await store_service.list_owned(db, target_id)


@router.get("/vip", response_model=VipStatus)
async def get_vip_status(user: CurrentUser, db: DbSession):
    return await vip_service.get_status(db, user)


@router.post("/vip/purchase", response_model=VipPurchaseResult)
async def purchase_vip(data: VipPurchaseRequest, user: CurrentUser, db: DbSession, idempotency_key: IdempotencyKey = None):
    """30 günlük VIP üyelik (DEMO: coinle). Aynı seviye süreyi uzatır, üst seviye hemen başlar."""
    return await vip_service.purchase(db, user, data.level, idempotency_key)


@router.post("/vip/daily-reward", response_model=DailyRewardResult)
async def claim_vip_daily_reward(user: CurrentUser, db: DbSession):
    """VIP günlük coin ödülü; günde bir kez."""
    return await vip_service.claim_daily_reward(db, user)
