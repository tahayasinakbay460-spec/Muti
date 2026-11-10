"""
Birebir sesli / görüntülü arama (özel mesajlardaki 📞 ve 🎥 tuşları).

AKIŞ
  1. Arayan `POST /calls` → arama "ringing" olur, aranana `/ws/me` kanalından `call:incoming` gider.
     Aranan şu an uygulamada değilse arama hiç başlamaz (uygulama kapalıyken bildirim = push, mobil işi).
  2. Aranan açar (`/accept`) → ilk dakikanın ücreti PEŞİN düşülür, iki tarafa `call:accepted` +
     ses/görüntü bağlantı bilgisi gider. Reddeder (`/decline`) ya da süre dolarsa (`missed`) biter.
  3. Konuşma sürerken her dakikanın başında bir sonraki dakika peşin düşülür. Coin yetmezse arama
     `insufficient_balance` ile biter. Taraflardan birinin uygulaması kapandıysa `disconnected` ile biter
     (yoksa kapanmış bir aramanın parası işlemeye devam ederdi).
  4. Biri kapatır (`/end`) → `call:ended`; sohbete arama izi düşer ("📞 Sesli arama · 3 dk").

PARA
  - Arayan öder (`call_charge`), aranan payını elmas olarak kazanır (`call_income`); oranlar .env.
  - Her dakika tek transaction: arayandan düş + arananın elmasını ekle; ya ikisi ya hiçbiri.
  - Dakika başına sabit idempotency anahtarı (`call:<id>:<dakika>`): aynı dakika iki kez kesilemez.
  - Fiyat aramanın başındaki fiyattır (`Call.price_per_minute`); arada .env değişse de etkilenmez.

DEMO KISAYOLU: Çalma ve dakika zamanlayıcıları bu sürecin belleğinde (asyncio görevleri). Birden çok
sunucuda bu görevler Redis'teki bir zamanlayıcıya / kuyruk işçisine taşınır. Sunucu yeniden başlarsa
yarım kalan aramalar açılışta kapatılır (bkz. close_stale_calls).
"""
import asyncio
import logging

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal, utcnow
from app.core.errors import AppError, ConflictError, InsufficientBalanceError, NotFoundError
from app.core.logs import audit
from app.models import Call
from app.realtime import events
from app.realtime.hub import user_hub
from app.schemas.call import CallOut, CallStartRequest
from app.services import message_service, revenue_service, user_service, wallet_service
from app.voice import VoiceJoinInfo, voice_provider

logger = logging.getLogger("muti.calls")

# Bir "dakika" kaç saniye: testler kısaltır.
MINUTE_SECONDS = 60
# Arama sürerken açık olan durumlar.
OPEN_STATUSES = ("ringing", "active")

# Arama başına zamanlayıcı görevi (çalma süresi ya da dakika sayacı). DEMO: süreç belleğinde.
_timers: dict[int, asyncio.Task] = {}


def price_for(kind: str) -> int:
    return settings.call_video_price_per_minute if kind == "video" else settings.call_voice_price_per_minute


# ── Yardımcılar ───────────────────────────────────────────────────────────────

async def _present(db: AsyncSession, call: Call, viewer_id: int) -> CallOut:
    other_id = call.callee_id if call.caller_id == viewer_id else call.caller_id
    other = await user_service.present_user(db, await user_service.get_user(db, other_id), viewer_id)
    return CallOut(
        id=call.id, kind=call.kind, status=call.status, is_caller=call.caller_id == viewer_id, peer=other,
        price_per_minute=call.price_per_minute, billed_minutes=call.billed_minutes,
        # Harcanan coin yalnızca ödeyene gösterilir.
        coins_spent=call.coins_spent if call.caller_id == viewer_id else None,
        started_at=call.started_at, end_reason=call.end_reason,
    )


async def _get_my_call(db: AsyncSession, me: int, call_id: int) -> Call:
    call = await db.get(Call, call_id)
    # Başkasının aramasını "yok" sayıyoruz: var olduğunu bile ele vermeyelim.
    if call is None or me not in (call.caller_id, call.callee_id):
        raise NotFoundError("Arama bulunamadı.")
    return call


def _start_timer(call_id: int, coroutine) -> None:
    _cancel_timer(call_id)
    _timers[call_id] = asyncio.create_task(coroutine)


def _cancel_timer(call_id: int) -> None:
    task = _timers.pop(call_id, None)
    # Zamanlayıcının kendisi aramayı bitiriyorsa kendi kendini iptal etmesin.
    if task is not None and task is not asyncio.current_task():
        task.cancel()


async def _publish_both(call: Call, event: str, payload: dict) -> None:
    for user_id in (call.caller_id, call.callee_id):
        await user_hub.publish(user_id, event, {"call_id": call.id, **payload})


# ── Başlatma / açma / reddetme ────────────────────────────────────────────────

async def start_call(db: AsyncSession, me: int, data: CallStartRequest) -> CallOut:
    if data.callee_id == me:
        raise AppError("Kendini arayamazsın.", code="cannot_call_self")
    callee = await user_service.get_user(db, data.callee_id)
    await user_service.require_not_blocked(db, me, callee.id)
    price = price_for(data.kind)
    # İlk dakikayı ödeyemeyecek kişi aramayı hiç başlatamasın (karşı tarafın telefonu boşuna çalmasın).
    if await wallet_service.get_coin_balance(db, me) < price:
        raise InsufficientBalanceError()
    if not user_hub.is_connected(callee.id):
        raise ConflictError(f"{callee.display_name} şu an uygulamada değil.", code="callee_offline")
    busy = await db.scalar(
        select(Call.id).where(
            Call.status.in_(OPEN_STATUSES),
            or_(Call.caller_id.in_((me, callee.id)), Call.callee_id.in_((me, callee.id))),
        ).limit(1)
    )
    if busy is not None:
        raise ConflictError("Şu an başka bir görüşme sürüyor.", code="call_busy")

    call = Call(caller_id=me, callee_id=callee.id, kind=data.kind, status="ringing", price_per_minute=price)
    db.add(call)
    await db.commit()
    audit("call_started", call_id=call.id, callee_id=callee.id, kind=call.kind, price_per_minute=price)

    await user_hub.publish(callee.id, events.CALL_INCOMING, (await _present(db, call, callee.id)).model_dump(mode="json"))
    _start_timer(call.id, _ring_timeout(call.id))
    return await _present(db, call, me)


async def _ring_timeout(call_id: int) -> None:
    """Aranan belirli sürede açmazsa arama cevapsız kalır."""
    await asyncio.sleep(settings.call_ring_seconds)
    async with SessionLocal() as db:
        call = await db.get(Call, call_id)
        if call is not None and call.status == "ringing":
            await _finish(db, call_id, "missed", "missed")


async def accept_call(db: AsyncSession, me: int, call_id: int) -> VoiceJoinInfo:
    call = await _get_my_call(db, me, call_id)
    if call.callee_id != me:
        raise AppError("Aramayı yalnızca aranan kişi açabilir.", code="not_callee")
    # Durumu "yalnızca hâlâ çalıyorsa" değiştir: arayan tam bu anda vazgeçtiyse iki istek çakışmaz.
    changed = await db.execute(
        update(Call).where(Call.id == call.id, Call.status == "ringing").values(status="active", started_at=utcnow())
    )
    await db.commit()
    if not changed.rowcount:
        raise ConflictError("Bu arama artık çalmıyor.", code="call_not_ringing")
    _cancel_timer(call.id)
    await db.refresh(call)

    # İlk dakika peşin. Arayanın parası bu arada bittiyse arama hemen kapanır.
    if not await _charge_minute(db, call):
        await _finish(db, call_id, "ended", "insufficient_balance")
        raise ConflictError("Arayanın coini yetmediği için arama kapandı.", code="caller_insufficient_balance")

    caller = await user_service.get_user(db, call.caller_id)
    await user_hub.publish(call.caller_id, events.CALL_ACCEPTED, {
        "call": (await _present(db, call, call.caller_id)).model_dump(mode="json"),
        "voice": (await voice_provider.call_join_info(call.id, caller.id, caller.display_name)).model_dump(mode="json"),
    })
    _start_timer(call.id, _billing_loop(call.id))
    callee = await user_service.get_user(db, me)
    return await voice_provider.call_join_info(call.id, me, callee.display_name)


async def decline_call(db: AsyncSession, me: int, call_id: int) -> None:
    call = await _get_my_call(db, me, call_id)
    if call.status != "ringing":
        return
    # Aranan reddederse "declined"; arayan çalarken vazgeçerse karşı tarafta "cevapsız" görünür.
    if call.callee_id == me:
        await _finish(db, call_id, "declined", "declined")
    else:
        await _finish(db, call_id, "missed", "cancelled")


async def end_call(db: AsyncSession, me: int, call_id: int) -> CallOut:
    call = await _get_my_call(db, me, call_id)
    if call.status == "ringing":
        await decline_call(db, me, call_id)
    elif call.status == "active":
        await _finish(db, call_id, "ended", "hangup")
    await db.refresh(call)
    return await _present(db, call, me)


async def get_call(db: AsyncSession, me: int, call_id: int) -> CallOut:
    return await _present(db, await _get_my_call(db, me, call_id), me)


async def join_info(db: AsyncSession, me: int, call_id: int) -> VoiceJoinInfo:
    """Konuşma sürerken bağlantı bilgisini yeniler (ör. token süresi doldu, ağ değişti)."""
    call = await _get_my_call(db, me, call_id)
    if call.status != "active":
        raise ConflictError("Bu arama sürmüyor.", code="call_not_active")
    user = await user_service.get_user(db, me)
    return await voice_provider.call_join_info(call.id, me, user.display_name)


# ── Ücret ─────────────────────────────────────────────────────────────────────

async def _charge_minute(db: AsyncSession, call: Call) -> bool:
    """
    Bir sonraki dakikanın ücretini peşin keser. Coin yetmezse hiçbir şey değişmez ve False döner.
    Ücretsiz aramada (fiyat 0) yalnızca dakika sayılır.
    """
    # Değerleri baştan alıyoruz: geri alma (rollback) sonrası satır nesnesi "bayat" sayılır ve
    # async oturumda alanına dokunmak hata verir.
    call_id, caller_id, callee_id, kind = call.id, call.caller_id, call.callee_id, call.kind
    minute = call.billed_minutes + 1
    price = call.price_per_minute
    if price > 0:
        # Aranan ajans yayıncısıysa payı daha yüksek, ajans da komisyon hak eder (bkz. revenue_service).
        split = await revenue_service.split_income(db, callee_id, price, "call")
        income = split.host_diamonds
        key = f"call:{call_id}:{minute}"

        async def debit() -> int:
            return await wallet_service.change_balance(
                db, user_id=caller_id, currency="coin", delta=-price, type="call_charge",
                label=f"{message_service.CALL_LABELS[kind]} · {minute}. dakika",
                counterparty_id=callee_id, quantity=1, idempotency_key=key,
            )

        async def credit() -> None:
            if income > 0:
                await wallet_service.change_balance(
                    db, user_id=callee_id, currency="diamond", delta=income, type="call_income",
                    label=f"{message_service.CALL_LABELS[kind]} geliri · {minute}. dakika",
                    counterparty_id=caller_id, quantity=1,
                )

        try:
            # KİLİT SIRASI hediyedeki gibi: küçük id önce (bkz. gift_service.send_gift).
            if caller_id < callee_id:
                balance = await debit()
                await credit()
            else:
                await credit()
                balance = await debit()
            revenue_service.record_agency_share(db, split, callee_id, price, "call")
        except InsufficientBalanceError:
            await db.rollback()
            return False
        except Exception:
            await db.rollback()
            raise
    await db.execute(
        update(Call).where(Call.id == call_id)
        .values(billed_minutes=Call.billed_minutes + 1, coins_spent=Call.coins_spent + price)
    )
    await db.commit()
    await db.refresh(call)

    if price > 0:
        await user_hub.publish(call.caller_id, events.CALL_CHARGED, {
            "call_id": call.id, "billed_minutes": call.billed_minutes, "coins_spent": call.coins_spent,
            "coin_balance": balance,
            # Bir sonraki dakikayı ödeyemeyecekse önceden uyar: "Coin yükle, yoksa arama kapanacak".
            "low_balance": balance < price,
        })
    return True


async def _billing_loop(call_id: int) -> None:
    """Konuşma sürdükçe her dakikanın başında bir sonraki dakikayı keser."""
    while True:
        await asyncio.sleep(MINUTE_SECONDS)
        async with SessionLocal() as db:
            call = await db.get(Call, call_id)
            if call is None or call.status != "active":
                return
            if not (user_hub.is_connected(call.caller_id) and user_hub.is_connected(call.callee_id)):
                await _finish(db, call_id, "ended", "disconnected")
                return
            try:
                charged = await _charge_minute(db, call)
            except Exception:  # noqa: BLE001 — beklenmeyen hata: aramayı kapat, para işlemeye devam etmesin
                logger.exception("Call billing failed", extra={"fields": {"call_id": call_id}})
                charged = False
            if not charged:
                await _finish(db, call_id, "ended", "insufficient_balance")
                return


# ── Bitiş ─────────────────────────────────────────────────────────────────────

async def _finish(db: AsyncSession, call_id: int, status: str, reason: str) -> None:
    """Aramayı kapatır (yalnızca hâlâ açıksa), iki tarafa haber verir, sohbete iz bırakır."""
    changed = await db.execute(
        update(Call).where(Call.id == call_id, Call.status.in_(OPEN_STATUSES))
        .values(status=status, end_reason=reason, ended_at=utcnow())
    )
    await db.commit()
    if not changed.rowcount:
        return    # öbür taraf aynı anda kapattı; işi o yaptı
    _cancel_timer(call_id)
    call = await db.get(Call, call_id)
    await db.refresh(call)
    audit("call_ended", call_id=call.id, status=status, reason=reason,
          billed_minutes=call.billed_minutes, coins_spent=call.coins_spent)
    await _publish_both(call, events.CALL_ENDED, {
        "status": status, "reason": reason, "billed_minutes": call.billed_minutes,
    })
    await message_service.add_call_message(db, call)


async def close_stale_calls() -> None:
    """
    Sunucu açılırken çağrılır: önceki çalışmadan açık kalmış aramalar kapatılır. Zamanlayıcıları
    bellekteydi ve kayboldu; kapatmazsak bu kişiler "meşgul" görünür, kimse onları arayamazdı.
    """
    async with SessionLocal() as db:
        await db.execute(
            update(Call).where(Call.status.in_(OPEN_STATUSES))
            .values(status="ended", end_reason="server_restart", ended_at=utcnow())
        )
        await db.commit()


# ── Görüntülü / sesli bağlantı sinyali (yalnızca mesh) ────────────────────────

async def relay_signal(me: int, signal: events.CallSignalIn) -> None:
    """
    Mesh sağlayıcıda tarayıcılar birbirine doğrudan bağlanır; bağlantı mesajlarını biz taşırız.
    Yalnızca süren bir aramanın iki tarafı arasında.
    """
    async with SessionLocal() as db:
        call = await db.get(Call, signal.call_id)
        if call is None or call.status != "active" or me not in (call.caller_id, call.callee_id):
            return
    other_id = call.callee_id if call.caller_id == me else call.caller_id
    await user_hub.publish(other_id, events.CALL_SIGNAL, {
        "call_id": call.id,
        "from": me,
        "description": signal.description.model_dump() if signal.description else None,
        "candidate": signal.candidate.model_dump() if signal.candidate else None,
    })

