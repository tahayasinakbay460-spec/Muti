"""
Sanal ekonomi uçları:
  /api/v1/gifts         — hediye kataloğu ve hediye gönderme
  /api/v1/wallet        — coin paketleri, satın alma, işlem geçmişi
  /api/v1/leaderboards  — sıralamalar
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Query

from app.core.deps import CurrentUserId, DbSession
from app.schemas.economy import (
    CoinPackageOut, ExchangeRequest, ExchangeResult, GiftOut, GiftSendRequest, GiftSendResult, IncomeSummary,
    PurchaseRequest, PurchaseResult, TransactionOut,
)
from app.schemas.user import TopGifter
from app.services import gift_service, wallet_service

router = APIRouter(tags=["economy"])

# İstemci para harcayan her dokunuş için benzersiz bir anahtar üretip bu başlıkta yollar.
# Aynı anahtar tekrar gelirse işlem ikinci kez yapılmaz (bkz. wallet_service).
# Başlık zorunlu değil ama mobil uygulama mutlaka göndermeli.
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", min_length=8, max_length=64)]


@router.get("/gifts", response_model=list[GiftOut])
async def list_gifts(_user_id: CurrentUserId, db: DbSession):
    return await gift_service.list_gifts(db)


@router.post("/gifts/send", response_model=GiftSendResult)
async def send_gift(data: GiftSendRequest, user_id: CurrentUserId, db: DbSession, idempotency_key: IdempotencyKey = None):
    """Hediye gönderir. Bakiye yetmezse 402 `insufficient_balance` döner."""
    return await gift_service.send_gift(db, user_id, data, idempotency_key)


@router.get("/wallet/packages", response_model=list[CoinPackageOut])
async def list_coin_packages(user_id: CurrentUserId, db: DbSession):
    """Coin paketleri ve hediye paketleri (coinin yanında mağaza eşyası verenler)."""
    return await wallet_service.list_packages(db, user_id)


@router.post("/wallet/purchase", response_model=PurchaseResult)
async def purchase_coins(data: PurchaseRequest, user_id: CurrentUserId, db: DbSession, idempotency_key: IdempotencyKey = None):
    """Coin paketi satın alır (DEMO: gerçek ödeme yok)."""
    return await wallet_service.purchase(db, user_id, data.package_id, idempotency_key)


@router.get("/wallet/income", response_model=IncomeSummary)
async def get_income(user_id: CurrentUserId, db: DbSession):
    """Yayıncı geliri: hediyelerden kazanılan elmaslar ve en çok destek olanlar."""
    return await wallet_service.income_summary(db, user_id)


@router.post("/wallet/exchange", response_model=ExchangeResult)
async def exchange_diamonds(data: ExchangeRequest, user_id: CurrentUserId, db: DbSession, idempotency_key: IdempotencyKey = None):
    """Elmasları coine çevirir. Elmas yetmezse 402 `insufficient_balance` döner."""
    return await wallet_service.exchange_diamonds(db, user_id, data.diamonds, idempotency_key)


@router.get("/wallet/transactions", response_model=list[TransactionOut])
async def list_transactions(
    user_id: CurrentUserId,
    db: DbSession,
    currency: Literal["coin", "diamond"] = "coin",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before_id: int | None = None,
):
    """Cüzdan geçmişi. Daha eskileri için `before_id` = listedeki son kaydın id'si."""
    return await wallet_service.list_transactions(db, user_id, currency, limit, before_id)


@router.get("/leaderboards/gifters", response_model=list[TopGifter])
async def list_top_gifters(user_id: CurrentUserId, db: DbSession):
    return await gift_service.list_top_gifters(db, user_id)
