"""
Kullanıcı işlemleri: profil getirme, takip etme, öneriler.

SERVİS NEDİR? İş kurallarının yazıldığı katman. Router "istek geldi" der ve servisi
çağırır; servis kuralları uygular, veritabanıyla konuşur ve sonucu döner.
Aynı servis fonksiyonunu hem HTTP endpoint'i hem WebSocket hem test çağırabilir.
"""
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError
from app.core.timefmt import as_utc, days_since
from app.models import Follow, User
from app.realtime.state import room_state
from app.schemas.user import UserOut


async def get_user(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise NotFoundError("Kullanıcı bulunamadı.")
    return user


# ── Kullanıcıyı JSON'a hazırlama ──────────────────────────────────────────────

async def present_users(db: AsyncSession, users: list[User], viewer_id: int | None) -> list[UserOut]:
    """
    Kullanıcı satırlarını dışarıya gösterilecek hale (UserOut) çevirir.

    `viewer_id` = isteği atan kişi. "Takip ediyor muyum?" gibi alanlar ona göre dolar.
    None verilirse (herkese giden yayınlarda) bu kişisel alanlar boş/false kalır.

    ÖNEMLİ: Liste halinde çalışır. 20 kullanıcı için 20 ayrı "takip ediyor muyum"
    sorgusu atmak yerine TEK sorgu atar. (Tek tek sormaya "N+1 problemi" denir ve
    kalabalık sistemleri en çok yavaşlatan hatalardan biridir.)
    """
    if not users:
        return []
    user_ids = [user.id for user in users]

    following_ids: set[int] = set()
    if viewer_id is not None:
        rows = await db.scalars(
            select(Follow.followee_id).where(Follow.follower_id == viewer_id, Follow.followee_id.in_(user_ids))
        )
        following_ids = set(rows)

    online_ids = await room_state.online_user_ids(user_ids)

    result = []
    for user in users:
        is_me = user.id == viewer_id
        result.append(UserOut(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            age=user.age,
            city=user.city,
            avatar_url=user.avatar_url,
            cover_url=user.cover_url,
            bio=user.bio,
            vip_level=user.vip_level,
            level=user.level,
            is_verified=user.is_verified,
            is_guest=user.is_guest,
            is_online=user.id in online_ids,
            joined_days=days_since(user.created_at),
            created_at=as_utc(user.created_at),
            followers_count=user.followers_count,
            following_count=user.following_count,
            friends_count=user.friends_count,
            visitors_count=user.visitors_count,
            is_me=is_me,
            is_following=user.id in following_ids,
            # Bakiyeyi yalnızca sahibine gösteriyoruz.
            coin_balance=user.coin_balance if is_me else None,
            diamond_balance=user.diamond_balance if is_me else None,
        ))
    return result


async def present_user(db: AsyncSession, user: User, viewer_id: int | None) -> UserOut:
    return (await present_users(db, [user], viewer_id))[0]


async def load_users_out(db: AsyncSession, user_ids: set[int], viewer_id: int | None) -> dict[int, UserOut]:
    """Verilen id'lerdeki kullanıcıları tek sorguyla getirir: { id: UserOut }."""
    if not user_ids:
        return {}
    users = list(await db.scalars(select(User).where(User.id.in_(user_ids))))
    return {out.id: out for out in await present_users(db, users, viewer_id)}


# ── Takip ─────────────────────────────────────────────────────────────────────

async def toggle_follow(db: AsyncSession, viewer_id: int, target_id: int) -> bool:
    """
    Takip ediyorsa bırakır, etmiyorsa takip eder. Yeni durumu döner (True = takipte).
    """
    if viewer_id == target_id:
        raise AppError("Kendini takip edemezsin.", code="cannot_follow_self")
    await get_user(db, target_id)

    # Önce silmeyi dene: bir satır silindiyse zaten takip ediyormuş → artık etmiyor.
    deleted = await db.execute(
        delete(Follow).where(Follow.follower_id == viewer_id, Follow.followee_id == target_id)
    )
    if deleted.rowcount:
        now_following, delta = False, -1
    else:
        db.add(Follow(follower_id=viewer_id, followee_id=target_id))
        try:
            await db.flush()
        except IntegrityError:
            # Aynı anda gelen ikinci bir istek (çift tıklama) satırı bizden önce eklemiş.
            # Sayaçları iki kez artırmamak için burada duruyoruz.
            await db.rollback()
            return True
        now_following, delta = True, 1

    # Sayaçları "oku, +1 yap, yaz" şeklinde DEĞİL, veritabanına "şu anki değere ekle"
    # diyerek güncelliyoruz. Böylece aynı anda gelen iki istek birbirini ezmez.
    await db.execute(
        update(User).where(User.id == target_id).values(followers_count=User.followers_count + delta)
    )
    await db.execute(
        update(User).where(User.id == viewer_id).values(following_count=User.following_count + delta)
    )

    # Karşı taraf da beni takip ediyorsa bu bir "arkadaşlık"tır; iki tarafın sayacı değişir.
    follows_back = await db.scalar(
        select(Follow.follower_id).where(Follow.follower_id == target_id, Follow.followee_id == viewer_id)
    )
    if follows_back is not None:
        await db.execute(
            update(User).where(User.id.in_([viewer_id, target_id])).values(friends_count=User.friends_count + delta)
        )

    await db.commit()
    return now_following


async def list_suggested(db: AsyncSession, viewer_id: int, limit: int = 8) -> list[UserOut]:
    """
    Keşfet ekranındaki "tanıyor olabileceğin kişiler".
    DEMO KISAYOLU: En çok takipçisi olan, henüz takip etmediğim kişiler.
    Gerçek öneri sistemi (ortak arkadaş, ilgi alanı) sonraki aşamanın işi.
    """
    already_following = select(Follow.followee_id).where(Follow.follower_id == viewer_id)
    users = await db.scalars(
        select(User)
        .where(User.id != viewer_id, User.is_active, ~User.is_guest, User.id.not_in(already_following))
        .order_by(User.followers_count.desc())
        .limit(limit)
    )
    return await present_users(db, list(users), viewer_id)
