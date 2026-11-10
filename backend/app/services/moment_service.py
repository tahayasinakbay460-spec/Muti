"""
Anılar: paylaşma, akış (Keşfet / Takip), beğenme, yorum, silme.

Akış "imleçli sayfalama" (cursor) ile gelir: istemci en son gördüğü anının id'sini
`before_id` olarak gönderir, sunucu ondan daha eskileri verir. "Sayfa 3" (offset) yerine
bunu kullanıyoruz çünkü araya yeni anı girince offset kayar ve aynı anı iki kez görünür.
"""
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError, AppError
from app.core.logs import audit
from app.core.timefmt import as_utc
from app.demo import content
from app.models import Follow, Moment, MomentComment, MomentLike, User, UserBlock
from app.schemas.moment import MomentCommentOut, MomentCreateRequest, MomentLikeResult, MomentOut
from app.services import media_service, notification_service, user_service

PAGE_SIZE = 30
COMMENT_PAGE_SIZE = 100


async def _present(db: AsyncSession, moments: list[Moment], viewer_id: int) -> list[MomentOut]:
    """Anıları JSON'a hazırlar. Yazarlar ve "beğendim mi" bilgisi tek sorguyla gelir (N+1 yok)."""
    if not moments:
        return []
    users = await user_service.load_users_out(db, {m.user_id for m in moments}, viewer_id)
    liked = set(await db.scalars(
        select(MomentLike.moment_id).where(
            MomentLike.user_id == viewer_id, MomentLike.moment_id.in_([m.id for m in moments]),
        )
    ))
    return [
        MomentOut(
            id=m.id, user=users[m.user_id], text=m.text, image_url=m.image_url, like_count=m.like_count,
            comment_count=m.comment_count, created_at=as_utc(m.created_at), is_liked=m.id in liked, is_mine=m.user_id == viewer_id,
        )
        for m in moments if m.user_id in users
    ]


def _hidden_authors(viewer_id: int):
    """Engellediğim ve beni engelleyen kişiler: anıları bana görünmez."""
    blocked = select(UserBlock.blocked_id).where(UserBlock.blocker_id == viewer_id)
    blocked_me = select(UserBlock.blocker_id).where(UserBlock.blocked_id == viewer_id)
    return blocked.union(blocked_me)


async def list_feed(db: AsyncSession, viewer_id: int, feed: str, before_id: int | None = None) -> list[MomentOut]:
    """
    explore   → herkesin anıları (Keşfet)
    following → takip ettiklerimin ve benim anılarım (Takip)
    """
    statement = (
        select(Moment).join(User, User.id == Moment.user_id)
        # Banlı / silinmiş hesapların anıları görünmez.
        .where(User.is_active, Moment.user_id.not_in(_hidden_authors(viewer_id)))
    )
    if feed == "following":
        followed = select(Follow.followee_id).where(Follow.follower_id == viewer_id)
        statement = statement.where((Moment.user_id == viewer_id) | Moment.user_id.in_(followed))
    if before_id is not None:
        statement = statement.where(Moment.id < before_id)
    moments = await db.scalars(statement.order_by(Moment.id.desc()).limit(PAGE_SIZE))
    return await _present(db, list(moments), viewer_id)


async def list_user_moments(
    db: AsyncSession, viewer_id: int, user_id: int, before_id: int | None = None,
) -> list[MomentOut]:
    """Bir kişinin anıları (profildeki Paylaşımlar sekmesi)."""
    await user_service.get_user(db, user_id)
    if viewer_id != user_id and await user_service.is_blocked_between(db, viewer_id, user_id):
        return []
    statement = select(Moment).where(Moment.user_id == user_id)
    if before_id is not None:
        statement = statement.where(Moment.id < before_id)
    moments = await db.scalars(statement.order_by(Moment.id.desc()).limit(PAGE_SIZE))
    return await _present(db, list(moments), viewer_id)


async def create_moment(db: AsyncSession, user: User, data: MomentCreateRequest) -> MomentOut:
    # Misafir hesaplar paylaşım yapamaz: kimliği belirsiz hesaplardan gelen istenmeyen içerik (spam) azalır.
    if user.is_guest:
        raise ForbiddenError("Anı paylaşmak için hesap oluştur.", code="guest_cannot_post")
    # Görsel hazır listeden ya da kişinin anı için yüklediği fotoğraftan: dışarıdan rastgele adres yazılamaz.
    if data.image_url is not None and data.image_url not in content.MOMENT_IMAGE_CHOICES \
            and not await media_service.is_own_upload(db, user.id, data.image_url, ("moment",)):
        raise AppError("Bu görsel seçilemez.", code="invalid_image")
    moment = Moment(user_id=user.id, text=data.text, image_url=data.image_url)
    db.add(moment)
    await db.commit()
    await db.refresh(moment)
    return (await _present(db, [moment], user.id))[0]


async def _get(db: AsyncSession, moment_id: int) -> Moment:
    moment = await db.get(Moment, moment_id)
    if moment is None:
        raise NotFoundError("Anı bulunamadı.")
    return moment


async def delete_moment(db: AsyncSession, user_id: int, moment_id: int) -> None:
    """Yalnızca anının sahibi siler. Beğeniler veritabanında kendiliğinden silinir (ON DELETE CASCADE)."""
    moment = await _get(db, moment_id)
    if moment.user_id != user_id:
        raise ForbiddenError("Bu anı senin değil.", code="not_moment_owner")
    # SQLite'ta yabancı anahtar silmesi her zaman açık olmayabilir; beğeni ve yorumları kendimiz siliyoruz.
    await db.execute(delete(MomentLike).where(MomentLike.moment_id == moment_id))
    await db.execute(delete(MomentComment).where(MomentComment.moment_id == moment_id))
    await db.delete(moment)
    await db.commit()
    audit("moment_deleted", moment_id=moment_id)


async def toggle_like(db: AsyncSession, user_id: int, moment_id: int) -> MomentLikeResult:
    """Beğendiyse geri alır, beğenmediyse beğenir."""
    moment = await _get(db, moment_id)
    await user_service.require_not_blocked(db, user_id, moment.user_id)

    deleted = await db.execute(
        delete(MomentLike).where(MomentLike.moment_id == moment_id, MomentLike.user_id == user_id)
    )
    if deleted.rowcount:
        is_liked, delta = False, -1
    else:
        db.add(MomentLike(moment_id=moment_id, user_id=user_id))
        try:
            await db.flush()
        except IntegrityError:
            # Çift tıklamada ikinci istek: satırı ilki eklemiş, sayacı iki kez artırmıyoruz.
            await db.rollback()
            moment = await _get(db, moment_id)
            return MomentLikeResult(is_liked=True, like_count=moment.like_count)
        is_liked, delta = True, 1

    # Sayaç "şu anki değere ekle" diye güncellenir: aynı anda gelen beğeniler birbirini ezmez.
    await db.execute(update(Moment).where(Moment.id == moment_id).values(like_count=Moment.like_count + delta))
    await db.commit()
    await db.refresh(moment)

    if is_liked:
        liker = await user_service.get_user(db, user_id)
        await notification_service.notify(
            db, moment.user_id, "moment_like", f"{liker.display_name} anını beğendi.",
            actor_id=user_id, data={"moment_id": moment_id},
        )
    return MomentLikeResult(is_liked=is_liked, like_count=moment.like_count)


# ── Yorumlar ──────────────────────────────────────────────────────────────────

async def list_comments(db: AsyncSession, viewer_id: int, moment_id: int) -> list[MomentCommentOut]:
    """Bir anının yorumları, eskiden yeniye (Instagram'daki gibi en yeni en altta)."""
    moment = await _get(db, moment_id)
    if await user_service.is_blocked_between(db, viewer_id, moment.user_id):
        return []
    comments = list(await db.scalars(
        select(MomentComment).join(User, User.id == MomentComment.user_id)
        .where(
            MomentComment.moment_id == moment_id, User.is_active,
            MomentComment.user_id.not_in(_hidden_authors(viewer_id)),
        )
        .order_by(MomentComment.id).limit(COMMENT_PAGE_SIZE)
    ))
    users = await user_service.load_users_out(db, {c.user_id for c in comments}, viewer_id)
    return [_comment_out(c, moment, users[c.user_id], viewer_id) for c in comments if c.user_id in users]


def _comment_out(comment: MomentComment, moment: Moment, user, viewer_id: int) -> MomentCommentOut:
    return MomentCommentOut(
        id=comment.id, moment_id=comment.moment_id, user=user, text=comment.text,
        created_at=as_utc(comment.created_at),
        can_delete=viewer_id in (comment.user_id, moment.user_id),
    )


async def add_comment(db: AsyncSession, user: User, moment_id: int, text: str) -> MomentCommentOut:
    if user.is_guest:
        raise ForbiddenError("Yorum yazmak için hesap oluştur.", code="guest_cannot_post")
    moment = await _get(db, moment_id)
    await user_service.require_not_blocked(db, user.id, moment.user_id)
    comment = MomentComment(moment_id=moment_id, user_id=user.id, text=text)
    db.add(comment)
    # Sayaç "şu anki değere ekle" diye artar: aynı anda gelen yorumlar birbirini ezmez.
    await db.execute(update(Moment).where(Moment.id == moment_id).values(comment_count=Moment.comment_count + 1))
    await db.commit()
    await db.refresh(comment)
    await notification_service.notify(
        db, moment.user_id, "moment_comment", f"{user.display_name} anına yorum yaptı: {text[:60]}",
        actor_id=user.id, data={"moment_id": moment_id},
    )
    author = await user_service.present_user(db, user, viewer_id=user.id)
    return _comment_out(comment, moment, author, user.id)


async def delete_comment(db: AsyncSession, user_id: int, moment_id: int, comment_id: int) -> None:
    """Yorumu yazan ya da anının sahibi siler (kendi gönderisinin altını temizleyebilsin)."""
    moment = await _get(db, moment_id)
    comment = await db.get(MomentComment, comment_id)
    if comment is None or comment.moment_id != moment_id:
        raise NotFoundError("Yorum bulunamadı.")
    if user_id not in (comment.user_id, moment.user_id):
        raise ForbiddenError("Bu yorumu silemezsin.", code="not_comment_owner")
    await db.delete(comment)
    await db.execute(
        update(Moment).where(Moment.id == moment_id, Moment.comment_count > 0)
        .values(comment_count=Moment.comment_count - 1)
    )
    await db.commit()
    audit("moment_comment_deleted", moment_id=moment_id, comment_id=comment_id, by_owner=user_id != comment.user_id)
