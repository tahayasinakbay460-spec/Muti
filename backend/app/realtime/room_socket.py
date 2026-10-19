"""
Oda WebSocket'i: bir kullanıcı odadayken sunucuyla arasındaki canlı hat.

Adres:  ws://sunucu/ws/rooms/{room_id}?token=<access_token>

HTTP ile farkı: HTTP'de istemci sorar, sunucu cevaplar ve hat kapanır. WebSocket'te
hat açık kalır; sunucu istediği an istemciye mesaj itebilir. Sohbet, hediye
animasyonu ve oyun hamleleri bu yüzden buradan akar.

Bu dosyadaki akış:
  1. Bağlanan kişinin token'ını doğrula, odayı kontrol et.
  2. Kişiyi odanın yayın listesine ekle, herkese "X katıldı" de.
  3. Kişiden mesaj geldikçe işle (sohbet, zar).
  4. Bağlantı kopunca listeden çıkar, koltuğunu boşalt.

TEMEL KURAL — SUNUCU OTORİTEDİR: İstemciden gelen veriye güvenilmez. Mesajı kimin
yazdığını token'dan biz biliriz, zarı biz atarız, hediyeyi yalnızca gerçekten
parası düşülmüşse biz yayınlarız.
"""
import json
import secrets
import time
from collections import deque
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.database import SessionLocal
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.models import Room, User
from app.realtime import events
from app.realtime.games import roulette
from app.realtime.hub import room_hub
from app.realtime.state import room_state
from app.services import room_service, user_service
from app.voice import voice_provider

router = APIRouter()

# Tek bir mesajın en büyük boyutu (karakter). Daha büyüğü işlenmeden reddedilir.
# Sesli görüşme teklifleri (SDP) birkaç bin karakter tuttuğu için sınır buna göre.
MAX_MESSAGE_SIZE = 16000


class RateLimiter:
    """
    Hız sınırı: `period` saniye içinde en fazla `limit` işlem.
    Biri odayı mesaj yağmuruna tutmasın (spam) diye her bağlantıya bir tane verilir.
    """

    def __init__(self, limit: int, period: float) -> None:
        self.limit = limit
        self.period = period
        self._moments: deque[float] = deque()   # son işlemlerin zamanları

    def allow(self) -> bool:
        now = time.monotonic()
        # Süresi geçmiş kayıtları baştan at.
        while self._moments and now - self._moments[0] > self.period:
            self._moments.popleft()
        if len(self._moments) >= self.limit:
            return False
        self._moments.append(now)
        return True


async def _send_error(websocket: WebSocket, code: str, detail: str) -> None:
    """Hatayı yalnızca hatayı yapan kişiye bildirir (odaya yayınlanmaz)."""
    await websocket.send_text(json.dumps({"event": events.ERROR, "payload": {"code": code, "detail": detail}}))


async def _publish_listener_count(room_id: int) -> None:
    counts = await room_state.listener_counts([room_id])
    await room_hub.publish(room_id, events.ROOM_LISTENER_COUNT, {"listener_count": counts[room_id]})


async def _relay_voice_signal(room_id: int, sender_id: int, signal: events.VoiceSignalIn) -> None:
    """
    Ses bağlantı mesajını karşı tarafa iletir. Yalnızca odadaki iki kişi arasında ve
    ikisinden en az biri koltuktaysa. Koltukta olmayan iki dinleyici arasında ses kanalı
    açılamaz; yoksa dinleyiciler koltuk kuralını atlayıp kendi aralarında konuşabilirdi.
    """
    if signal.to == sender_id or not await room_state.is_in_room(room_id, signal.to):
        return
    seated = {seat.user_id for seat in (await room_state.get_seats([room_id]))[room_id]}
    if sender_id not in seated and signal.to not in seated:
        return
    await room_hub.send_to_user(room_id, signal.to, events.VOICE_SIGNAL, {
        "from": sender_id,
        "description": signal.description.model_dump() if signal.description else None,
        "candidate": signal.candidate.model_dump() if signal.candidate else None,
    })


@router.websocket("/ws/rooms/{room_id}")
async def room_socket(websocket: WebSocket, room_id: int, token: str = "") -> None:
    # Önce bağlantıyı kabul ediyoruz ki reddederken istemciye anlamlı bir kod gönderebilelim.
    await websocket.accept()

    # ── 1. Kimlik ve oda kontrolü ─────────────────────────────────────────────
    try:
        user_id = decode_access_token(token)
    except AppError:
        await websocket.close(code=events.CLOSE_UNAUTHORIZED)
        return

    # Veritabanı oturumunu yalnızca bu kısa kontrol için açıp hemen kapatıyoruz.
    # Bağlantı saatlerce açık kalabilir; o süre boyunca bir veritabanı bağlantısını
    # meşgul etseydik birkaç bin kullanıcıda havuz tükenirdi.
    async with SessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None or not user.is_active:
            await websocket.close(code=events.CLOSE_UNAUTHORIZED)
            return
        room = await db.get(Room, room_id)
        if room is None or not room.is_active:
            await websocket.close(code=events.CLOSE_ROOM_NOT_FOUND)
            return
        if await room_state.is_banned(room.id, user_id):
            await websocket.close(code=events.CLOSE_BANNED)
            return
        await room_state.ensure_room(room.id, room.seat_count)
        # Bu kişinin yayınlarda kullanılacak görünen bilgisi (bir kez hazırlanır).
        user_payload = (await user_service.present_user(db, user, viewer_id=None)).model_dump(mode="json")

    # ── 2. Odaya katıl ────────────────────────────────────────────────────────
    room_hub.add(room_id, websocket, user_id)
    is_first_connection = await room_state.add_listener(room_id, user_id)
    chat_limiter = RateLimiter(limit=5, period=5)    # 5 saniyede en fazla 5 mesaj
    dice_limiter = RateLimiter(limit=1, period=1.5)  # 1.5 saniyede en fazla 1 zar
    game_limiter = RateLimiter(limit=5, period=5)    # rulet: 5 saniyede en fazla 5 işlem
    # Ses bağlantısı kurulurken her karşı taraf için onlarca küçük mesaj gider; sınır geniş.
    voice_limiter = RateLimiter(limit=300, period=10)

    try:
        # Yeni gelen kişi sohbetin ortasına düşmesin: son mesajları yalnızca ona gönder.
        await websocket.send_text(json.dumps(
            {"event": events.CHAT_HISTORY, "payload": {"messages": await room_state.recent_chat(room_id)}},
            ensure_ascii=False, default=str,
        ))
        if is_first_connection:
            await room_hub.publish(room_id, events.ROOM_USER_JOINED, {"user": user_payload})
        await _publish_listener_count(room_id)

        # ── 3. Mesajları dinle ────────────────────────────────────────────────
        while True:
            raw = await websocket.receive_text()
            await room_state.touch_presence(user_id)

            if len(raw) > MAX_MESSAGE_SIZE:
                await _send_error(websocket, "message_too_large", "Mesaj çok uzun.")
                continue
            try:
                message = json.loads(raw)
                event = message["event"]
                payload = message.get("payload") or {}
            except (ValueError, KeyError, TypeError, AttributeError):
                await _send_error(websocket, "invalid_message", "Mesaj biçimi hatalı.")
                continue

            if event == events.CHAT_MESSAGE:
                if not chat_limiter.allow():
                    await _send_error(websocket, "rate_limited", "Çok hızlı yazıyorsun, biraz yavaşla.")
                    continue
                try:
                    chat = events.ChatMessageIn.model_validate(payload)
                except ValidationError:
                    await _send_error(websocket, "invalid_message", "Mesaj boş veya çok uzun.")
                    continue
                muted = (await room_state.chat_mute_remaining(room_id, [user_id])).get(user_id)
                if muted:
                    minutes = max(1, round(muted / 60))
                    await _send_error(websocket, "chat_muted", f"Sohbette susturuldun ({minutes} dk).")
                    continue
                # `user` alanını istemciden değil, token'dan bildiğimiz kişiden dolduruyoruz.
                # `id`: mesajı sonradan silebilmek için; tahmin edilemez olsun diye rastgele.
                chat_message = {
                    "id": secrets.token_hex(8), "user": user_payload, "text": chat.text,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                await room_state.append_chat(room_id, chat_message)
                await room_hub.publish(room_id, events.CHAT_MESSAGE, chat_message)

            elif event == events.GAME_DICE_ROLLED:
                if not dice_limiter.allow():
                    continue
                # Zarı SUNUCU atar. İstemcinin gönderdiği değerlere bakmıyoruz; yoksa
                # herkes kendine hep 6-6 gönderirdi. `secrets` tahmin edilemez sayı üretir.
                values = [secrets.randbelow(6) + 1, secrets.randbelow(6) + 1]
                await room_hub.publish(room_id, events.GAME_DICE_ROLLED, {"user": user_payload, "values": values})

            elif event in (events.GAME_ROULETTE_START, events.GAME_ROULETTE_BET):
                if not game_limiter.allow():
                    continue
                try:
                    if event == events.GAME_ROULETTE_START:
                        await roulette.start(room_id, user_payload)
                    else:
                        await roulette.bet(room_id, user_id, user_payload, str(payload.get("color", "")))
                except AppError as error:
                    await _send_error(websocket, error.code, error.detail)

            elif event == events.VOICE_SIGNAL and voice_provider.relays_signals:
                if not voice_limiter.allow():
                    continue
                try:
                    signal = events.VoiceSignalIn.model_validate(payload)
                except ValidationError:
                    await _send_error(websocket, "invalid_signal", "Ses bağlantı mesajı hatalı.")
                    continue
                await _relay_voice_signal(room_id, user_id, signal)

            elif event == events.GIFT_SENT:
                # Bilerek yok sayılıyor. Hediye yayını yalnızca POST /gifts/send başarılı
                # olunca sunucu tarafından yapılır (bkz. gift_service.send_gift). İstemciden
                # geleni yayınlasaydık herkes para ödemeden sahte hediye animasyonu gösterebilirdi.
                continue

            else:
                await _send_error(websocket, "unknown_event", "Bilinmeyen olay.")

    except WebSocketDisconnect:
        pass   # Kullanıcı odadan çıktı ya da bağlantısı koptu; normal bir durum.
    except RuntimeError:
        pass   # Bağlantıyı sunucu kapattı (ör. kişi odadan atıldı); okumaya devam edilemez.
    finally:
        # ── 4. Temizlik (ne olursa olsun çalışır) ─────────────────────────────
        room_hub.remove(room_id, websocket)
        fully_left = await room_state.remove_listener(room_id, user_id)
        # Kişinin odada başka açık bağlantısı kalmadıysa koltuğunu da boşalt.
        if fully_left and await room_state.leave_seat(room_id, user_id):
            async with SessionLocal() as db:
                room = await db.get(Room, room_id)
                if room is not None:
                    await room_service.publish_seats(db, room)
        if fully_left:
            await room_hub.publish(room_id, events.ROOM_USER_LEFT, {"user_id": user_id})
        await _publish_listener_count(room_id)
