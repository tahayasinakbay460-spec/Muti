"""
CP (çift): iki kullanıcının profilde birbirine bağlanması.

AKIŞ: Teklif eden yüzük bedelini (PROPOSAL_PRICE) öder → karşı taraf kabul eder ya da reddeder.
Reddedilir ya da teklif geri çekilirse bedel iade edilir. Kabul edilince ikisi CP olur;
ikisinden biri ayrılabilir (bedel iade edilmez).

"AYNI ANDA TEK CP" KURALI: Kabul anında iki kullanıcının `cp_partner_id` alanı "boşsa doldur"
komutuyla yazılır (para kuralındaki atomik güncelleme yöntemi). Biri aynı anda iki teklifi
kabul etmeye çalışsa bile yalnızca biri başarılı olur.
"""
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.logs import audit
from app.core.timefmt import as_utc
from app.models import Couple, Transaction, User
from app.realtime import events
from app.realtime.hub import user_hub
from app.schemas.engagement import CoupleOut, CoupleStatus
from app.services import notification_service, user_service, wallet_service

PROPOSAL_PRICE = 520   # coin ("yüzük")


def _pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


async def _notify_changed(*user_ids: int) -> None:
    """İki tarafın ekranı da güncellensin (kişiye özel kanal)."""
    for user_id in user_ids:
        await user_hub.publish(user_id, events.COUPLE_UPDATED, {})


async def _cp_coins(db: AsyncSession, a: int, b: int) -> int:
    """İkisinin birbirine gönderdiği hediyelerin coin toplamı (CP'nin "sevgi puanı")."""
    between = or_(
        and_(Transaction.user_id == a, Transaction.counterparty_id == b),
        and_(Transaction.user_id == b, Transaction.counterparty_id == a),
    )
    return await db.scalar(
        select(func.coalesce(func.sum(-Transaction.amount), 0)).where(Transaction.type == "gift_sent", between)
    )


async def _present(db: AsyncSession, couple: Couple, viewer_id: int) -> CoupleOut:
    partner_id = couple.user_high_id if couple.user_low_id == viewer_id else couple.user_low_id
    partner = await user_service.present_user(db, await user_service.get_user(db, partner_id), viewer_id)
    return CoupleOut(
        partner=partner, status=couple.status, requested_by_me=couple.requested_by == viewer_id,
        since=as_utc(couple.accepted_at or couple.created_at), cp_coins=await _cp_coins(db, viewer_id, partner_id),
    )


async def get_status(db: AsyncSession, user_id: int) -> CoupleStatus:
    rows = list(await db.scalars(
        select(Couple).where(or_(Couple.user_low_id == user_id, Couple.user_high_id == user_id)).order_by(Couple.id.desc())
    ))
    active = next((row for row in rows if row.status == "active"), None)
    pending = [row for row in rows if row.status == "pending"]
    return CoupleStatus(
        active=await _present(db, active, user_id) if active else None,
        incoming=[await _present(db, row, user_id) for row in pending if row.requested_by != user_id],
        outgoing=[await _present(db, row, user_id) for row in pending if row.requested_by == user_id],
        proposal_price=PROPOSAL_PRICE,
    )


async def _refund(db: AsyncSession, couple: Couple, reason: str) -> None:
    await wallet_service.change_balance(
        db, user_id=couple.requested_by, currency="coin", delta=PROPOSAL_PRICE, type="cp_refund",
        label=f"CP teklifi iadesi ({reason})",
    )


async def propose(db: AsyncSession, user_id: int, target_id: int) -> CoupleStatus:
    if target_id == user_id:
        raise AppError("Kendine CP teklif edemezsin.", code="cannot_propose_self")
    me = await user_service.get_user(db, user_id)
    target = await user_service.get_user(db, target_id)
    await user_service.require_not_blocked(db, user_id, target_id)
    if me.cp_partner_id or target.cp_partner_id:
        raise ConflictError("İkinizden birinin zaten CP'si var.", code="cp_taken")

    low, high = _pair(user_id, target_id)
    try:
        await wallet_service.change_balance(
            db, user_id=user_id, currency="coin", delta=-PROPOSAL_PRICE, type="cp_proposal",
            label=f"CP teklifi → {target.display_name}", counterparty_id=target_id,
        )
        # (user_low_id, user_high_id) benzersiz: aynı ikili için ikinci teklif yazılamaz.
        db.add(Couple(user_low_id=low, user_high_id=high, requested_by=user_id, status="pending"))
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise ConflictError("Aranızda zaten bir teklif var.", code="cp_request_exists") from error
    except Exception:
        await db.rollback()
        raise

    audit("cp_proposed", target_id=target_id, price=PROPOSAL_PRICE)
    await notification_service.notify(
        db, target_id, "cp_proposal", f"💍 {me.display_name} sana CP teklif etti!",
        actor_id=user_id, data={"user_id": user_id},
    )
    await _notify_changed(target_id)
    return await get_status(db, user_id)


async def _get_pending(db: AsyncSession, user_id: int, partner_id: int) -> Couple:
    low, high = _pair(user_id, partner_id)
    couple = await db.scalar(
        select(Couple).where(Couple.user_low_id == low, Couple.user_high_id == high, Couple.status == "pending")
    )
    if couple is None:
        raise NotFoundError("Bekleyen bir CP teklifi yok.")
    return couple


async def accept(db: AsyncSession, user_id: int, partner_id: int) -> CoupleStatus:
    couple = await _get_pending(db, user_id, partner_id)
    if couple.requested_by == user_id:
        raise AppError("Kendi teklifini kabul edemezsin.", code="cannot_accept_own")

    # İki satırı küçük id'den büyüğe güncelliyoruz (kilit sırası; bkz. gift_service).
    for me, other in sorted([(user_id, partner_id), (partner_id, user_id)]):
        taken = await db.execute(
            update(User).where(User.id == me, User.cp_partner_id.is_(None)).values(cp_partner_id=other)
            .execution_options(synchronize_session=False)
        )
        if taken.rowcount != 1:
            await db.rollback()
            raise ConflictError("İkinizden birinin zaten CP'si var.", code="cp_taken")
    couple.status = "active"
    couple.accepted_at = utcnow()

    # Artık ikisi de CP: ikisini içeren diğer bekleyen teklifler iadeyle kapanır.
    others = list(await db.scalars(
        select(Couple).where(
            Couple.status == "pending", Couple.id != couple.id,
            or_(Couple.user_low_id.in_([user_id, partner_id]), Couple.user_high_id.in_([user_id, partner_id])),
        )
    ))
    refunded_ids = {other.requested_by for other in others}
    for other in others:
        await _refund(db, other, "karşı taraf başka biriyle CP oldu")
        await db.delete(other)
    await db.commit()
    # Kullanıcı satırları doğrudan UPDATE ile değişti; bellekteki eski kopyalar yeniden okunsun.
    db.expire_all()

    audit("cp_accepted", partner_id=partner_id, closed_pending=len(others))
    me = await user_service.get_user(db, user_id)
    await notification_service.notify(
        db, partner_id, "cp_accepted", f"💞 {me.display_name} CP teklifini kabul etti!", actor_id=user_id,
        data={"user_id": user_id},
    )
    await _notify_changed(partner_id, *refunded_ids)
    return await get_status(db, user_id)


async def decline(db: AsyncSession, user_id: int, partner_id: int) -> CoupleStatus:
    """Gelen teklifi reddeder ya da gönderdiği teklifi geri çeker. Bedel teklif edene iade edilir."""
    couple = await _get_pending(db, user_id, partner_id)
    withdrawn = couple.requested_by == user_id
    await _refund(db, couple, "geri çekildi" if withdrawn else "reddedildi")
    await db.delete(couple)
    await db.commit()
    audit("cp_withdrawn" if withdrawn else "cp_declined", partner_id=partner_id)
    await _notify_changed(partner_id)
    return await get_status(db, user_id)


async def break_up(db: AsyncSession, user_id: int) -> CoupleStatus:
    me = await user_service.get_user(db, user_id)
    partner_id, my_name = me.cp_partner_id, me.display_name
    if partner_id is None:
        raise AppError("CP'n yok.", code="no_cp")
    low, high = _pair(user_id, partner_id)
    await db.execute(
        update(User).where(User.id.in_([user_id, partner_id])).values(cp_partner_id=None)
        .execution_options(synchronize_session=False)
    )
    await db.execute(delete(Couple).where(Couple.user_low_id == low, Couple.user_high_id == high))
    await db.commit()
    db.expire_all()
    audit("cp_broken", partner_id=partner_id)
    await notification_service.notify(db, partner_id, "cp_broken", f"{my_name} CP ilişkisini sonlandırdı.")
    await _notify_changed(partner_id)
    return await get_status(db, user_id)
