"""
Coin bayisi uçları (kullanıcı tarafı): /api/v1/dealers
  GET  /dealers           — resmi bayiler (cüzdandaki "Bayiden coin al")
  GET  /dealers/me        — bayi paneli (bayi değilse 403 `not_dealer`)
  POST /dealers/me/sales  — kullanıcıya coin gönder (Idempotency-Key ile)
Bayiyi tanımlamak ve stok yüklemek panelde: /admin/dealers (bkz. routers/admin.py).
"""
from fastapi import APIRouter

from app.core.deps import CurrentUserId, DbSession
from app.routers.economy import IdempotencyKey
from app.schemas.dealer import DealerPanel, DealerPublicOut, DealerSaleRequest, DealerSaleResult
from app.services import dealer_service

router = APIRouter(prefix="/dealers", tags=["dealers"])


@router.get("", response_model=list[DealerPublicOut])
async def list_dealers(user_id: CurrentUserId, db: DbSession):
    return await dealer_service.list_public(db, user_id)


@router.get("/me", response_model=DealerPanel)
async def get_my_panel(user_id: CurrentUserId, db: DbSession):
    return await dealer_service.my_panel(db, user_id)


@router.post("/me/sales", response_model=DealerSaleResult)
async def sell_coins(data: DealerSaleRequest, user_id: CurrentUserId, db: DbSession, idempotency_key: IdempotencyKey = None):
    """Stok ya da günlük sınır yetmezse 402 `insufficient_balance` / 409 `dealer_daily_limit`."""
    return await dealer_service.sell(db, user_id, data.user_id, data.coins, idempotency_key)
