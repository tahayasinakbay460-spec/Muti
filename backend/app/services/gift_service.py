"""
Hediyeler: katalog, hediye gönderme, en çok hediye gönderenler.
"""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, NotFoundError
from app.models import Gift, Room, Transaction, User
from app.realtime import events
from app.realtime.hub import room_hub
from app.schemas.economy import GiftOut, GiftSendRequest, GiftSendResult
from app.schemas.user import TopGifter
from app.services import user_service, wallet_service


async def list_gifts(db: AsyncSession) -> list[GiftOut]:
    gifts = await db.scalars(select(Gift).where(Gift.is_active).order_by(Gift.price))
    return [GiftOut.model_validate(gift) for gift in gifts]


async def _build_result(
    db: AsyncSession, sender_id: int, gift: Gift, receiver: User, quantity: int, coin_balance: int,
) -> GiftSendResult:
    return GiftSendResult(
        coin_balance=coin_balance,
        gift=GiftOut.model_validate(gift),
        receiver=await user_service.present_user(db, receiver, viewer_id=sender_id),
        quantity=quantity,
    )


async def _replay(db: AsyncSession, sender_id: int, previous: Transaction) -> GiftSendResult:
    """Aynı idempotency anahtarı tekrar geldi: işlemi yeniden yapma, ilk sonucu dön."""
    gift = await db.get(Gift, previous.gift_id)
    receiver = await db.get(User, previous.counterparty_id)
    balance = await wallet_service.get_coin_balance(db, sender_id)
    return await _build_result(db, sender_id, gift, receiver, previous.quantity, balance)


async def send_gift(
    db: AsyncSession, sender_id: int, data: GiftSendRequest, idempotency_key: str | None,
) -> GiftSendResult:
    """
    Hediye gönderir: gönderenden coin düşer, alana elmas eklenir, odaya animasyon yayınlanır.

    Fiyatı ve toplam tutarı HER ZAMAN sunucu hesaplar. İstemci yalnızca "şu hediyeden
    şu kadar" der; istemciden gelen bir fiyata asla güvenilmez.
    """
    previous = await wallet_service.find_by_idempotency_key(db, sender_id, idempotency_key)
    if previous:
        return await _replay(db, sender_id, previous)

    if data.receiver_id == sender_id:
        raise AppError("Kendine hediye gönderemezsin.", code="cannot_gift_self")

    gift = await db.get(Gift, data.gift_id)
    if gift is None or not gift.is_active:
        raise NotFoundError("Hediye bulunamadı.")
    receiver = await user_service.get_user(db, data.receiver_id)
    if data.room_id is not None and await db.get(Room, data.room_id) is None:
        raise NotFoundError("Oda bulunamadı.")

    total_coins = gift.price * data.quantity
    # Alıcının kazancı. `//` tamsayı bölmesidir: küsurat çıkmaz, float kullanılmaz.
    receiver_diamonds = total_coins * settings.gift_receiver_share_percent // 100

    async def debit_sender() -> int:
        return await wallet_service.change_balance(
            db, user_id=sender_id, currency="coin", delta=-total_coins, type="gift_sent",
            label=f"Hediye: {gift.name} x{data.quantity} → {receiver.display_name}",
            counterparty_id=receiver.id, gift_id=gift.id, room_id=data.room_id,
            quantity=data.quantity, idempotency_key=idempotency_key,
        )

    async def credit_receiver() -> None:
        if receiver_diamonds > 0:
            await wallet_service.change_balance(
                db, user_id=receiver.id, currency="diamond", delta=receiver_diamonds, type="gift_received",
                label=f"Hediye alındı: {gift.name} x{data.quantity}",
                counterparty_id=sender_id, gift_id=gift.id, room_id=data.room_id, quantity=data.quantity,
            )

    try:
        # KİLİT SIRASI: İki satırı (gönderen, alan) her zaman küçük id'den büyüğe doğru
        # güncelliyoruz. Neden? Ali ile Veli aynı anda birbirine hediye gönderirse ve
        # her işlem "önce kendi satırım" deseydi; biri Ali'yi kilitleyip Veli'yi,
        # diğeri Veli'yi kilitleyip Ali'yi beklerdi → sonsuz bekleme (deadlock).
        # Herkes aynı sırayı izleyince bu olamaz.
        if sender_id < receiver.id:
            coin_balance = await debit_sender()
            await credit_receiver()
        else:
            await credit_receiver()
            coin_balance = await debit_sender()
        # İki adım da başarılı → ikisini birlikte kalıcı yap.
        await db.commit()
    except IntegrityError:
        # Aynı anahtarla eşzamanlı ikinci istek: bizimkini geri al, ilk sonucu dön.
        await db.rollback()
        previous = await wallet_service.find_by_idempotency_key(db, sender_id, idempotency_key)
        if previous is None:
            raise
        return await _replay(db, sender_id, previous)
    except Exception:
        # Yetersiz bakiye dahil herhangi bir hata: yarım kalan her şeyi geri al.
        await db.rollback()
        raise

    result = await _build_result(db, sender_id, gift, receiver, data.quantity, coin_balance)

    # Para işi bitti; şimdi odadakilere animasyonu göster. Yayını commit'ten SONRA
    # yapıyoruz ki gerçekleşmemiş bir hediyenin animasyonu hiç görünmesin.
    if data.room_id is not None:
        people = await user_service.load_users_out(db, {sender_id, receiver.id}, viewer_id=None)
        await room_hub.publish(data.room_id, events.GIFT_SENT, {
            "sender": people[sender_id].model_dump(mode="json"),
            "receiver": people[receiver.id].model_dump(mode="json"),
            "gift": result.gift.model_dump(),
            "quantity": data.quantity,
        })
    return result


async def list_top_gifters(db: AsyncSession, viewer_id: int, limit: int = 5) -> list[TopGifter]:
    """
    En çok coin değerinde hediye gönderenler.

    DEMO KISAYOLU: Her istekte bütün hediye hareketleri toplanıyor. Tablo büyüyünce
    yavaşlar; canlıda sıralama Redis sorted set'te tutulur ve her hediyede +tutar yapılır.
    """
    total = func.sum(-Transaction.amount).label("total")   # amount eksi olduğu için işaretini çeviriyoruz
    rows = (await db.execute(
        select(Transaction.user_id, total)
        .where(Transaction.type == "gift_sent")
        .group_by(Transaction.user_id)
        .order_by(total.desc())
        .limit(limit)
    )).all()

    users = await user_service.load_users_out(db, {row.user_id for row in rows}, viewer_id)
    return [
        TopGifter(rank=index + 1, user=users[row.user_id], total_coins=row.total)
        for index, row in enumerate(rows) if row.user_id in users
    ]
