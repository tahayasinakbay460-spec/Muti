"""
Özel mesajlar (iki kişi arası sohbet).

Mesaj REST ile gönderilir (POST). Kaydedildikten sonra karşı tarafa kişiye özel
WebSocket'ten (/ws/me) `message:new` olayı itilir; böylece sohbet açıksa mesaj anında
görünür, değilse bildirim çıkar. Uygulama kapalıyken bildirim (push notification)
mobil aşamanın işi.
"""
from datetime import datetime

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal, utcnow
from app.core.errors import AppError, NotFoundError
from app.core.logs import audit
from app.core.timefmt import as_utc, clock_label
from app.models import Call, Conversation, Gift, Message, RoomMessage
from app.realtime import events
from app.realtime.hub import user_hub
from app.schemas.economy import GiftOut, GiftSendRequest
from app.schemas.message import (
    ConversationDetail, ConversationGiftRequest, ConversationGiftResult, ConversationSummary, MessageOut,
)
from app.services import engagement_service, gift_service, media_service, user_service, wallet_service
from app.services.media_storage import media_storage

# Sesli mesajda kabul edilen ses biçimleri → dosya uzantısı. Tarayıcılar MediaRecorder ile
# çoğunlukla webm (Chrome, Firefox) ya da mp4 (Safari) üretir.
VOICE_CONTENT_TYPES = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a"}
EXTENSION_MEDIA_TYPES = {
    **{ext: content_type for content_type, ext in VOICE_CONTENT_TYPES.items()},
    "jpg": "image/jpeg", "png": "image/png", "webp": "image/webp",
}


# ── Küçük yardımcılar ─────────────────────────────────────────────────────────

def _other_user_id(conversation: Conversation, me: int) -> int:
    """Sohbetteki karşı tarafın id'si."""
    return conversation.user_high_id if conversation.user_low_id == me else conversation.user_low_id


def _my_unread(conversation: Conversation, me: int) -> int:
    return conversation.unread_low if conversation.user_low_id == me else conversation.unread_high


def _message_out(sender_id: int, text: str, created_at: datetime, me: int, message_id: int | None = None) -> MessageOut:
    """Sohbet listesindeki "son mesaj" satırı: yalnızca önizleme yazısı."""
    return MessageOut(
        id=message_id, from_me=sender_id == me, text=text,
        created_at=as_utc(created_at), time=clock_label(created_at),
    )


def _present(message: Message, me: int, gifts: dict[int, Gift], calls: dict[int, Call]) -> MessageOut:
    """Bir mesaj satırını, bakan kişinin (`me`) gözünden JSON'a hazırlar."""
    out = _message_out(message.sender_id, message.text, message.created_at, me, message.id)
    out.kind = message.kind
    out.duration_seconds = message.duration_seconds
    if message.kind in ("voice", "image"):
        out.media_url = f"/conversations/{message.conversation_id}/messages/{message.id}/media"
    elif message.kind == "gift":
        gift = gifts.get(message.gift_id)
        out.gift = GiftOut.model_validate(gift) if gift else None
        out.quantity = message.quantity
    elif message.kind == "call":
        call = calls.get(message.call_id)
        if call is not None:
            out.call_kind = call.kind
            out.call_status = call.status if call.status in ("ended", "missed", "declined") else "ended"
    return out


async def _present_many(db: AsyncSession, messages: list[Message], me: int) -> list[MessageOut]:
    """Mesaj listesi: hediye ve arama bilgileri, kaç mesaj olursa olsun ikişer sorguyla gelir."""
    gift_ids = {m.gift_id for m in messages if m.gift_id}
    call_ids = {m.call_id for m in messages if m.call_id}
    gifts = {g.id: g for g in await db.scalars(select(Gift).where(Gift.id.in_(gift_ids)))} if gift_ids else {}
    calls = {c.id: c for c in await db.scalars(select(Call).where(Call.id.in_(call_ids)))} if call_ids else {}
    return [_present(m, me, gifts, calls) for m in messages]


async def _get_conversation(db: AsyncSession, me: int, conversation_id: int) -> Conversation:
    conversation = await db.get(Conversation, conversation_id)
    # Sohbet var ama ben üyesi değilsem de "bulunamadı" diyoruz. "Yetkin yok" deseydik
    # başkasına ait bir sohbetin var olduğunu ele vermiş olurduk.
    if conversation is None or me not in (conversation.user_low_id, conversation.user_high_id):
        raise NotFoundError("Sohbet bulunamadı.")
    return conversation


async def _reset_my_unread(db: AsyncSession, conversation: Conversation, me: int) -> None:
    unread_column = "unread_low" if conversation.user_low_id == me else "unread_high"
    await db.execute(update(Conversation).where(Conversation.id == conversation.id).values({unread_column: 0}))
    await db.commit()


# ── İşlemler ──────────────────────────────────────────────────────────────────

async def list_conversations(db: AsyncSession, me: int, limit: int = 50) -> list[ConversationSummary]:
    """Benim sohbetlerim, en son yazışılan en üstte."""
    conversations = list(await db.scalars(
        select(Conversation)
        .where(or_(Conversation.user_low_id == me, Conversation.user_high_id == me))
        # Hiç mesajı olmayan yeni sohbetler için oluşturulma zamanına göre sırala.
        .order_by(func.coalesce(Conversation.last_message_at, Conversation.created_at).desc())
        .limit(limit)
    ))
    users = await user_service.load_users_out(db, {_other_user_id(c, me) for c in conversations}, me)

    return [
        ConversationSummary(
            id=c.id,
            user_id=_other_user_id(c, me),
            user=users[_other_user_id(c, me)],
            unread_count=_my_unread(c, me),
            last_message=(
                _message_out(c.last_message_sender_id, c.last_message_text, c.last_message_at, me)
                if c.last_message_at else None
            ),
        )
        for c in conversations if _other_user_id(c, me) in users
    ]


async def get_conversation(
    db: AsyncSession, me: int, conversation_id: int, limit: int = 50, before_id: int | None = None,
) -> ConversationDetail:
    """
    Sohbeti açar: son `limit` mesajı döner ve okunmamış sayacımı sıfırlar.
    Daha eski mesajlar için `before_id` (ekrandaki en eski mesajın id'si) gönderilir.
    """
    conversation = await _get_conversation(db, me, conversation_id)

    statement = (
        select(Message).where(Message.conversation_id == conversation.id).order_by(Message.id.desc()).limit(limit)
    )
    if before_id is not None:
        statement = statement.where(Message.id < before_id)
    # Veritabanından yeniden eskiye çektik (son mesajları almak için); ekranda
    # eskiden yeniye görünmesi gerektiğinden ters çeviriyoruz.
    messages = list(await db.scalars(statement))[::-1]

    # Sohbeti açtım → benim tarafımdaki okunmamış sayacı sıfırla.
    await _reset_my_unread(db, conversation, me)

    other_id = _other_user_id(conversation, me)
    other = await user_service.present_user(db, await user_service.get_user(db, other_id), me)
    return ConversationDetail(
        id=conversation.id,
        user_id=other_id,
        user=other,
        unread_count=0,
        messages=await _present_many(db, messages, me),
    )


async def open_conversation(db: AsyncSession, me: int, other_id: int) -> int:
    """Bu kişiyle sohbetim varsa onun id'sini döner, yoksa yeni bir sohbet açar."""
    if other_id == me:
        raise AppError("Kendine mesaj gönderemezsin.", code="cannot_message_self")
    await user_service.get_user(db, other_id)
    await user_service.require_not_blocked(db, me, other_id)

    low, high = min(me, other_id), max(me, other_id)
    find = select(Conversation.id).where(Conversation.user_low_id == low, Conversation.user_high_id == high)

    existing_id = await db.scalar(find)
    if existing_id is not None:
        return existing_id

    conversation = Conversation(user_low_id=low, user_high_id=high)
    db.add(conversation)
    try:
        await db.commit()
    except IntegrityError:
        # Karşı taraf tam aynı anda bana sohbet açmış; onunkini kullan.
        await db.rollback()
        return await db.scalar(find)
    return conversation.id


async def _store_message(db: AsyncSession, conversation: Conversation, me: int, *, preview: str, **fields) -> Message:
    """
    Her türden mesajın ortak yolu: satırı yazar, sohbet satırındaki "son mesaj" kopyasını ve karşı
    tarafın okunmamış sayacını günceller, commit eder, sonra iki tarafa `message:new` yayınlar.
    `preview`: sohbet listesinde görünen kısa yazı (yazılı mesajda metnin kendisi).
    """
    now = utcnow()
    message = Message(conversation_id=conversation.id, sender_id=me, created_at=now, **fields)
    db.add(message)

    # Sayaç "şu anki değere +1" şeklinde, veritabanında artıyor (aynı anda iki mesajda kayıp olmaz).
    other_unread = Conversation.unread_high if conversation.user_low_id == me else Conversation.unread_low
    await db.execute(
        update(Conversation).where(Conversation.id == conversation.id).values({
            "last_message_text": preview[:1000],
            "last_message_sender_id": me,
            "last_message_at": now,
            other_unread.key: other_unread + 1,
        })
    )
    await db.commit()

    # Anlık bildirim: karşı tarafa ve (başka sekmede/cihazda açık olabilir diye) bana.
    # Her iki taraf `from_me` alanını kendi gözünden görür. Yayın commit'ten SONRA.
    sender = await user_service.present_user(db, await user_service.get_user(db, me), viewer_id=None)
    for receiver_id in (_other_user_id(conversation, me), me):
        presented = (await _present_many(db, [message], receiver_id))[0]
        await user_hub.publish(receiver_id, events.MESSAGE_NEW, {
            "conversation_id": conversation.id,
            "sender": sender.model_dump(mode="json"),
            "message": presented.model_dump(mode="json"),
        })
    return message


async def send_message(db: AsyncSession, me: int, conversation_id: int, text: str) -> MessageOut:
    conversation = await _get_conversation(db, me, conversation_id)
    await user_service.require_not_blocked(db, me, _other_user_id(conversation, me))
    message = await _store_message(db, conversation, me, preview=text, text=text, kind="text")
    return (await _present_many(db, [message], me))[0]


# ── Sesli mesaj ───────────────────────────────────────────────────────────────

async def send_voice(
    db: AsyncSession, me: int, conversation_id: int, content_type: str, data: bytes, duration_seconds: int,
) -> MessageOut:
    """
    Sesli mesaj: ses dosyası diske, mesaj satırı veritabanına yazılır.
    Sınırlar sunucuda: tür, boyut, süre. (Süreyi istemci söyler, üst sınırı biz koyarız.
    Dosyanın gerçek süresini ölçmek sesi çözümlemeyi gerektirir; boyut sınırı kaba bir güvencedir.)
    """
    conversation = await _get_conversation(db, me, conversation_id)
    await user_service.require_not_blocked(db, me, _other_user_id(conversation, me))
    extension = VOICE_CONTENT_TYPES.get(content_type.split(";")[0].strip().lower())
    if extension is None:
        raise AppError("Bu ses biçimi desteklenmiyor.", code="unsupported_audio")
    if not data:
        raise AppError("Ses kaydı boş.", code="empty_audio")
    if len(data) > settings.voice_message_max_bytes:
        raise AppError("Ses kaydı çok büyük.", code="audio_too_large")
    if not 1 <= duration_seconds <= settings.voice_message_max_seconds:
        raise AppError(f"Sesli mesaj en fazla {settings.voice_message_max_seconds} saniye olabilir.", code="audio_too_long")

    key = await media_storage.save("voice", extension, data)
    try:
        message = await _store_message(
            db, conversation, me, preview="🎤 Sesli mesaj", text="🎤 Sesli mesaj", kind="voice",
            media_path=key, duration_seconds=duration_seconds,
        )
    except Exception:
        # Mesaj yazılamadıysa sahipsiz dosya diskte kalmasın.
        await db.rollback()
        await media_storage.delete(key)
        raise
    return (await _present_many(db, [message], me))[0]


async def send_image(db: AsyncSession, me: int, conversation_id: int, content_type: str, data: bytes) -> MessageOut:
    """Sohbette fotoğraf. Doğrulama ve saklama media_service'te (tür, boyut, sihirli bayt, sıklık)."""
    conversation = await _get_conversation(db, me, conversation_id)
    await user_service.require_not_blocked(db, me, _other_user_id(conversation, me))
    user = await user_service.get_user(db, me)
    upload = await media_service.store_image(db, user, "chat", content_type, data)
    message = await _store_message(
        db, conversation, me, preview="📷 Fotoğraf", text="📷 Fotoğraf", kind="image", media_path=upload.key,
    )
    return (await _present_many(db, [message], me))[0]


async def voice_file(db: AsyncSession, me: int, conversation_id: int, message_id: int) -> tuple[str, str]:
    """Sesli mesaj ya da sohbet fotoğrafının yolu ve türü. Yalnızca sohbetin iki üyesi alabilir."""
    conversation = await _get_conversation(db, me, conversation_id)
    message = await db.get(Message, message_id)
    if message is None or message.conversation_id != conversation.id or not message.media_path:
        raise NotFoundError("Kayıt bulunamadı.")
    path = media_storage.local_path(message.media_path)
    if not path.is_file():
        raise NotFoundError("Kayıt bulunamadı.")
    return str(path), EXTENSION_MEDIA_TYPES[path.suffix.lstrip(".")]


# ── Sohbette hediye ───────────────────────────────────────────────────────────

async def send_gift(
    db: AsyncSession, me: int, conversation_id: int, data: ConversationGiftRequest, idempotency_key: str | None,
) -> ConversationGiftResult:
    """
    Sohbetteki kişiye hediye: para kuralları odadaki hediyeyle aynıdır (gift_service.send_gift,
    oda yok). Para işi bittikten sonra sohbete hediye mesajı düşer.
    Aynı Idempotency-Key ikinci kez gelirse para da mesaj da tekrarlanmaz.
    """
    conversation = await _get_conversation(db, me, conversation_id)
    other_id = _other_user_id(conversation, me)
    is_replay = await wallet_service.find_by_idempotency_key(db, me, idempotency_key) is not None
    result = await gift_service.send_gift(
        db, me, GiftSendRequest(receiver_id=other_id, gift_id=data.gift_id, quantity=data.quantity), idempotency_key,
    )
    message_out = None
    if not is_replay:
        preview = f"🎁 {result.gift.name} x{result.quantity}"
        message = await _store_message(
            db, conversation, me, preview=preview, text=preview,
            kind="gift", gift_id=result.gift.id, quantity=result.quantity,
        )
        message_out = (await _present_many(db, [message], me))[0]
        audit("conversation_gift_sent", conversation_id=conversation.id, gift_id=result.gift.id, quantity=result.quantity)
    return ConversationGiftResult(
        coin_balance=result.coin_balance, message=message_out,
        lucky_win=result.lucky_win, lucky_multiplier=result.lucky_multiplier,
    )


# ── Arama izi ─────────────────────────────────────────────────────────────────

CALL_LABELS = {"voice": "Sesli arama", "video": "Görüntülü arama"}


async def add_call_message(db: AsyncSession, call: Call) -> None:
    """
    Arama bitince ikisinin sohbetine iz bırakır ("📞 Sesli arama · 3 dk", "Cevapsız arama").
    Mesajın göndereni arayandır. Sohbet yoksa açılır.
    """
    conversation_id = await open_conversation(db, call.caller_id, call.callee_id)
    conversation = await db.get(Conversation, conversation_id)
    label = CALL_LABELS[call.kind]
    if call.status == "ended":
        preview = f"📞 {label} · {max(1, call.billed_minutes)} dk"
    elif call.status == "declined":
        preview = f"📞 {label} reddedildi"
    else:
        preview = f"📞 Cevapsız {label.lower()}"
    seconds = None
    if call.started_at and call.ended_at:
        seconds = int((as_utc(call.ended_at) - as_utc(call.started_at)).total_seconds())
    await _store_message(
        db, conversation, call.caller_id, preview=preview, text=preview, kind="call",
        call_id=call.id, duration_seconds=seconds,
    )


async def mark_read(db: AsyncSession, me: int, conversation_id: int) -> None:
    """Sohbet ekranı açıkken gelen mesajı okundu say (sayaç sıfırlanır)."""
    conversation = await _get_conversation(db, me, conversation_id)
    await _reset_my_unread(db, conversation, me)


async def total_unread(db: AsyncSession, me: int) -> int:
    """Bütün sohbetlerimdeki okunmamış mesaj toplamı (alt çubuktaki "Mesajlar" rozeti)."""
    # Tek sorgu: ben "low" taraftaysam low sayacı, değilsem high sayacı. (Kişi kendisiyle sohbet açamaz.)
    mine = case((Conversation.user_low_id == me, Conversation.unread_low), else_=Conversation.unread_high)
    return await db.scalar(
        select(func.coalesce(func.sum(mine), 0))
        .where(or_(Conversation.user_low_id == me, Conversation.user_high_id == me))
    )


# ── Oda sohbeti kaydı ─────────────────────────────────────────────────────────

async def save_room_message(room_id: int, user_id: int, public_id: str, text: str) -> None:
    """
    Oda sohbetine yazılan mesajı kalıcı olarak kaydeder ve günlük görev sayacını artırır;
    ikisi tek veritabanı işleminde. WebSocket'in açık veritabanı oturumu olmadığı için kendi
    oturumunu açar. DEMO KISAYOLU: her mesaj bir yazım; kalabalık odalarda toplu yazım (kuyruk) gerekir.
    """
    async with SessionLocal() as db:
        db.add(RoomMessage(room_id=room_id, user_id=user_id, public_id=public_id, text=text))
        await engagement_service.record(db, user_id, engagement_service.METRIC_CHAT_MESSAGE)
        await db.commit()

