"""
Özel mesajlar (iki kişi arası sohbet).

Mesaj REST ile gönderilir (POST). Kaydedildikten sonra karşı tarafa kişiye özel
WebSocket'ten (/ws/me) `message:new` olayı itilir; böylece sohbet açıksa mesaj anında
görünür, değilse bildirim çıkar. Uygulama kapalıyken bildirim (push notification)
mobil aşamanın işi.
"""
from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal, utcnow
from app.core.errors import AppError, NotFoundError
from app.core.timefmt import as_utc, clock_label
from app.models import Conversation, Message, RoomMessage
from app.realtime import events
from app.realtime.hub import user_hub
from app.schemas.message import ConversationDetail, ConversationSummary, MessageOut
from app.services import engagement_service, user_service


# ── Küçük yardımcılar ─────────────────────────────────────────────────────────

def _other_user_id(conversation: Conversation, me: int) -> int:
    """Sohbetteki karşı tarafın id'si."""
    return conversation.user_high_id if conversation.user_low_id == me else conversation.user_low_id


def _my_unread(conversation: Conversation, me: int) -> int:
    return conversation.unread_low if conversation.user_low_id == me else conversation.unread_high


def _message_out(sender_id: int, text: str, created_at: datetime, me: int, message_id: int | None = None) -> MessageOut:
    return MessageOut(
        id=message_id, from_me=sender_id == me, text=text,
        created_at=as_utc(created_at), time=clock_label(created_at),
    )


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
        messages=[_message_out(m.sender_id, m.text, m.created_at, me, m.id) for m in messages],
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


async def send_message(db: AsyncSession, me: int, conversation_id: int, text: str) -> MessageOut:
    conversation = await _get_conversation(db, me, conversation_id)
    await user_service.require_not_blocked(db, me, _other_user_id(conversation, me))
    now = utcnow()

    message = Message(conversation_id=conversation.id, sender_id=me, text=text, created_at=now)
    db.add(message)

    # Sohbet satırındaki "son mesaj" kopyasını güncelle ve karşı tarafın okunmamış
    # sayacını artır. Sayaç yine "şu anki değere +1" şeklinde, veritabanında artıyor.
    other_unread = Conversation.unread_high if conversation.user_low_id == me else Conversation.unread_low
    await db.execute(
        update(Conversation).where(Conversation.id == conversation.id).values({
            "last_message_text": text,
            "last_message_sender_id": me,
            "last_message_at": now,
            other_unread.key: other_unread + 1,
        })
    )
    await db.commit()

    # Anlık bildirim: karşı tarafa ve (başka sekmede/cihazda açık olabilir diye) bana.
    # Her iki taraf `from_me` alanını kendi gözünden görür.
    other_id = _other_user_id(conversation, me)
    sender = await user_service.present_user(db, await user_service.get_user(db, me), viewer_id=None)
    for receiver_id in (other_id, me):
        await user_hub.publish(receiver_id, events.MESSAGE_NEW, {
            "conversation_id": conversation.id,
            "sender": sender.model_dump(mode="json"),
            "message": _message_out(me, text, now, receiver_id, message.id).model_dump(mode="json"),
        })
    return _message_out(me, text, now, me, message.id)


async def mark_read(db: AsyncSession, me: int, conversation_id: int) -> None:
    """Sohbet ekranı açıkken gelen mesajı okundu say (sayaç sıfırlanır)."""
    conversation = await _get_conversation(db, me, conversation_id)
    await _reset_my_unread(db, conversation, me)


async def total_unread(db: AsyncSession, me: int) -> int:
    """Bütün sohbetlerimdeki okunmamış mesaj toplamı (alt çubuktaki "Mesajlar" rozeti)."""
    low = select(func.coalesce(func.sum(Conversation.unread_low), 0)).where(Conversation.user_low_id == me)
    high = select(func.coalesce(func.sum(Conversation.unread_high), 0)).where(Conversation.user_high_id == me)
    return (await db.scalar(low)) + (await db.scalar(high))


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

