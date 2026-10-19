"""
Kullanıcı işlemleri: profil getirme, takip etme, arama, öneriler, engelleme kontrolü.

SERVİS NEDİR? İş kurallarının yazıldığı katman. Router "istek geldi" der ve servisi
çağırır; servis kuralları uygular, veritabanıyla konuşur ve sonucu döner.
Aynı servis fonksiyonunu hem HTTP endpoint'i hem WebSocket hem test çağırabilir.
"""
from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.database import utcnow
from app.core.timefmt import as_utc, days_since
from app.demo import content
from app.models import Follow, User, UserBlock
from app.realtime.state import room_state
from app.schemas.user import ProfileUpdateRequest, UserOut
from app.services import level_service, notification_service, store_service


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

    blocked_ids: set[int] = set()
    if viewer_id is not None:
        blocked_ids = set(await db.scalars(
            select(UserBlock.blocked_id).where(UserBlock.blocker_id == viewer_id, UserBlock.blocked_id.in_(user_ids))
        ))

    cosmetics = await store_service.equipped_cosmetics(db, user_ids)
    now = utcnow()

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
            vip_level=user.active_vip_level(now),
            level=user.level,
            experience=user.experience,
            next_level_experience=level_service.experience_for(user.level + 1),
            is_verified=user.is_verified,
            is_guest=user.is_guest,
            is_online=user.id in online_ids,
            **cosmetics.get(user.id, {}),
            joined_days=days_since(user.created_at),
            created_at=as_utc(user.created_at),
            followers_count=user.followers_count,
            following_count=user.following_count,
            friends_count=user.friends_count,
            visitors_count=user.visitors_count,
            is_me=is_me,
            is_following=user.id in following_ids,
            is_blocked=user.id in blocked_ids,
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


# ── Engelleme kontrolü ────────────────────────────────────────────────────────

async def is_blocked_between(db: AsyncSession, user_a: int, user_b: int) -> bool:
    """İki kişiden biri diğerini engellemiş mi? (Engelleme iki yönlü etki eder.)"""
    return await db.scalar(
        select(UserBlock.blocker_id).where(or_(
            (UserBlock.blocker_id == user_a) & (UserBlock.blocked_id == user_b),
            (UserBlock.blocker_id == user_b) & (UserBlock.blocked_id == user_a),
        )).limit(1)
    ) is not None


async def require_not_blocked(db: AsyncSession, user_a: int, user_b: int) -> None:
    if await is_blocked_between(db, user_a, user_b):
        # Kimin kimi engellediğini söylemiyoruz.
        raise ForbiddenError("Bu kişiyle etkileşim kuramazsın.", code="user_blocked")


# ── Takip ─────────────────────────────────────────────────────────────────────

async def set_follow(db: AsyncSession, follower_id: int, followee_id: int, follow: bool) -> bool:
    """
    Takip satırını ekler ya da siler ve sayaçları günceller. Commit ETMEZ (engelleme
    gibi başka işlemlerle aynı transaction'da kullanılabilsin diye).
    Gerçekten bir değişiklik olduysa True döner.
    """
    if follow:
        db.add(Follow(follower_id=follower_id, followee_id=followee_id))
        try:
            await db.flush()
        except IntegrityError:
            # Aynı anda gelen ikinci bir istek (çift tıklama) satırı bizden önce eklemiş.
            # Sayaçları iki kez artırmamak için burada duruyoruz.
            await db.rollback()
            return False
        delta = 1
    else:
        deleted = await db.execute(
            delete(Follow).where(Follow.follower_id == follower_id, Follow.followee_id == followee_id)
        )
        if not deleted.rowcount:
            return False
        delta = -1

    # Sayaçları "oku, +1 yap, yaz" şeklinde DEĞİL, veritabanına "şu anki değere ekle"
    # diyerek güncelliyoruz. Böylece aynı anda gelen iki istek birbirini ezmez.
    await db.execute(
        update(User).where(User.id == followee_id).values(followers_count=User.followers_count + delta)
    )
    await db.execute(
        update(User).where(User.id == follower_id).values(following_count=User.following_count + delta)
    )

    # Karşı taraf da takip ediyorsa bu bir "arkadaşlık"tır; iki tarafın sayacı değişir.
    follows_back = await db.scalar(
        select(Follow.follower_id).where(Follow.follower_id == followee_id, Follow.followee_id == follower_id)
    )
    if follows_back is not None:
        await db.execute(
            update(User).where(User.id.in_([follower_id, followee_id])).values(friends_count=User.friends_count + delta)
        )
    return True


async def toggle_follow(db: AsyncSession, viewer_id: int, target_id: int) -> bool:
    """
    Takip ediyorsa bırakır, etmiyorsa takip eder. Yeni durumu döner (True = takipte).
    """
    if viewer_id == target_id:
        raise AppError("Kendini takip edemezsin.", code="cannot_follow_self")
    await get_user(db, target_id)

    # Önce bırakmayı dene: bir satır silindiyse zaten takip ediyormuş → artık etmiyor.
    if await set_follow(db, viewer_id, target_id, follow=False):
        await db.commit()
        return False

    await require_not_blocked(db, viewer_id, target_id)
    if not await set_follow(db, viewer_id, target_id, follow=True):
        return True
    await db.commit()

    viewer = await get_user(db, viewer_id)
    await notification_service.notify(
        db, target_id, "follow", f"{viewer.display_name} seni takip etmeye başladı.",
        actor_id=viewer_id, data={"user_id": viewer_id},
    )
    return True


# ── Arama ─────────────────────────────────────────────────────────────────────

async def search_users(db: AsyncSession, viewer_id: int, query: str, limit: int = 30) -> list[UserOut]:
    """
    Kullanıcı arama: ada, kullanıcı adına ya da ID numarasına göre.
    Engellediklerim ve beni engelleyenler sonuçlarda görünmez.
    """
    text = query.strip().lstrip("@")
    if not text:
        return []
    # Kullanıcının yazdığı % ve _ SQL'de joker anlamına gelir; düz karakter sayılsın diye kaçırıyoruz.
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    conditions = [User.username.ilike(pattern, escape="\\"), User.display_name.ilike(pattern, escape="\\")]
    if text.isdigit():
        conditions.append(User.id == int(text))

    blocked = select(UserBlock.blocked_id).where(UserBlock.blocker_id == viewer_id)
    blocked_me = select(UserBlock.blocker_id).where(UserBlock.blocked_id == viewer_id)
    users = await db.scalars(
        select(User)
        .where(or_(*conditions), User.is_active, User.id != viewer_id,
               User.id.not_in(blocked), User.id.not_in(blocked_me))
        .order_by(User.followers_count.desc())
        .limit(limit)
    )
    return await present_users(db, list(users), viewer_id)


# ── Profil düzenleme ──────────────────────────────────────────────────────────

async def update_profile(db: AsyncSession, user: User, data: ProfileUpdateRequest) -> UserOut:
    """
    Kullanıcının kendi profilini günceller. Yalnızca istekte gönderilen alanlar değişir.

    `model_fields_set` = istemcinin JSON'da gerçekten yazdığı alanlar. Böylece
    "alanı hiç göndermedi" (dokunma) ile "null gönderdi" (temizle) birbirinden ayrılır.
    """
    changes = {field: getattr(data, field) for field in data.model_fields_set}

    if "display_name" in changes and not changes["display_name"]:
        raise AppError("Görünen ad boş olamaz.", code="invalid_display_name")
    if "bio" in changes and changes["bio"] is None:
        changes["bio"] = ""
    if "city" in changes and not changes["city"]:
        changes["city"] = None
    # Görseller yalnızca hazır listeden seçilebilir (bkz. demo/content.py).
    if changes.get("avatar_url") is not None and changes["avatar_url"] not in content.AVATAR_CHOICES:
        raise AppError("Bu avatar seçilemez.", code="invalid_avatar")
    if changes.get("cover_url") is not None and changes["cover_url"] not in content.COVER_CHOICES:
        raise AppError("Bu kapak seçilemez.", code="invalid_cover")

    for field, value in changes.items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return await present_user(db, user, viewer_id=user.id)


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
