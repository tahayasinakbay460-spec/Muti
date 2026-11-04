"""
Profil ekranının sosyal parçaları: ziyaretçiler, takipçilerim (arkadaşlık istekleri),
"Hakkında" bölümündeki sayılar ve başarı rozetleri.

ARKADAŞ NEDİR? Bizde ayrı bir "arkadaşlık isteği" tablosu yok: karşılıklı takip = arkadaş.
Beni takip eden ama benim geri takip etmediğim kişi bana "arkadaşlık isteği" göndermiş sayılır;
geri takip edince arkadaş oluruz (bkz. user_service.set_follow, friends_count).
"""
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.core.timefmt import as_utc, days_since
from app.models import FamilyMember, Follow, Moment, ProfileVisit, Room, Transaction, User, UserBlock
from app.schemas.user import Achievement, ProfileExtras, ProfileStats, UserOut, VisitorOut
from app.services import user_service

LIST_LIMIT = 100


# ── Ziyaretçiler ──────────────────────────────────────────────────────────────

async def record_visit(db: AsyncSession, visitor_id: int, visited_id: int) -> None:
    """
    Profile bakılınca çağrılır. İlk ziyarette satır eklenir ve sayaç 1 artar; tekrar bakışta
    yalnızca zaman güncellenir (aynı kişi bin kez baksa da tek ziyaretçi sayılır).
    Kendi profilime bakmam ve aramızda engel varsa sayılmaz.
    """
    if visitor_id == visited_id or await user_service.is_blocked_between(db, visitor_id, visited_id):
        return
    now = utcnow()
    touched = await db.execute(
        update(ProfileVisit)
        .where(ProfileVisit.visitor_id == visitor_id, ProfileVisit.visited_id == visited_id)
        .values(visited_at=now)
    )
    if not touched.rowcount:
        db.add(ProfileVisit(visitor_id=visitor_id, visited_id=visited_id, visited_at=now))
        try:
            await db.flush()
        except IntegrityError:
            # Aynı anda iki istek: satırı diğeri ekledi, sayaç onun işi.
            await db.rollback()
            return
        await db.execute(
            update(User).where(User.id == visited_id).values(visitors_count=User.visitors_count + 1)
        )
    await db.commit()


async def list_visitors(db: AsyncSession, user_id: int) -> list[VisitorOut]:
    """Profilime bakanlar, en son bakan en üstte."""
    rows = list(await db.execute(
        select(ProfileVisit.visitor_id, ProfileVisit.visited_at)
        .join(User, User.id == ProfileVisit.visitor_id)
        .where(ProfileVisit.visited_id == user_id, User.is_active)
        .order_by(ProfileVisit.visited_at.desc())
        .limit(LIST_LIMIT)
    ))
    users = await user_service.load_users_out(db, {visitor_id for visitor_id, _ in rows}, user_id)
    return [
        VisitorOut(user=users[visitor_id], visited_at=as_utc(visited_at))
        for visitor_id, visited_at in rows if visitor_id in users
    ]


# ── Takipçiler ────────────────────────────────────────────────────────────────

async def list_followers(db: AsyncSession, user_id: int) -> list[UserOut]:
    """
    Beni takip edenler, en yeni en üstte. Her kişide `is_following` = "ben de onu takip ediyor muyum":
    false olanlar ekranda "arkadaşlık isteği" olarak görünür.
    """
    users = await db.scalars(
        select(User)
        .join(Follow, Follow.follower_id == User.id)
        .where(Follow.followee_id == user_id, User.is_active)
        .order_by(Follow.created_at.desc())
        .limit(LIST_LIMIT)
    )
    return await user_service.present_users(db, list(users), user_id)


async def list_follow_list(db: AsyncSession, viewer_id: int, user_id: int, kind: str) -> list[UserOut]:
    """
    Profilde "Takipçi" / "Takip" sayısına dokununca açılan liste, en yeni en üstte.
      kind="followers" → bu kişiyi takip edenler
      kind="following" → bu kişinin takip ettikleri
    `is_following` bakan kişiye göredir (listeden doğrudan takip edebilsin).
    Aramızda engel varsa liste boş döner; engellediklerim listede görünmez.
    """
    await user_service.get_user(db, user_id)
    if viewer_id != user_id and await user_service.is_blocked_between(db, viewer_id, user_id):
        return []
    if kind == "followers":
        joined, matched = Follow.follower_id, Follow.followee_id
    else:
        joined, matched = Follow.followee_id, Follow.follower_id
    blocked = select(UserBlock.blocked_id).where(UserBlock.blocker_id == viewer_id).union(
        select(UserBlock.blocker_id).where(UserBlock.blocked_id == viewer_id)
    )
    users = await db.scalars(
        select(User)
        .join(Follow, joined == User.id)
        .where(matched == user_id, User.is_active, User.id.not_in(blocked))
        .order_by(Follow.created_at.desc())
        .limit(LIST_LIMIT)
    )
    return await user_service.present_users(db, list(users), viewer_id)


# ── Hakkında: sayılar ve başarılar ────────────────────────────────────────────

async def _stats(db: AsyncSession, user_id: int) -> ProfileStats:
    moments = await db.scalar(select(func.count()).select_from(Moment).where(Moment.user_id == user_id))
    rooms = await db.scalar(select(func.count()).select_from(Room).where(Room.host_id == user_id, Room.is_active))
    totals = dict((await db.execute(
        select(Transaction.type, func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.user_id == user_id, Transaction.type.in_(("gift_sent", "gift_received")))
        .group_by(Transaction.type)
    )).all())
    return ProfileStats(
        moments_count=moments or 0, rooms_count=rooms or 0,
        # gift_sent satırları eksi tutarlıdır (bakiye azaldı); ekranda artı gösteriyoruz.
        gifts_sent_coins=-int(totals.get("gift_sent", 0)),
        gifts_received_diamonds=int(totals.get("gift_received", 0)),
    )


def _number(n: int) -> str:
    """12450 → "12.450" (Türkçede binlik ayracı nokta)."""
    return f"{n:,}".replace(",", ".")


def _progress(have: int, need: int, unit: str) -> tuple[str, bool]:
    """("40 / 100 gün", False) gibi: ekranda yazı ve kazanıldı mı."""
    return f"{_number(min(have, need))} / {_number(need)} {unit}", have >= need


async def get_profile_extras(db: AsyncSession, user_id: int) -> ProfileExtras:
    """
    Başarılar veritabanındaki gerçek sayılardan hesaplanır; ayrı bir "kazanılan rozet" tablosu yok.
    Kazanılmamışlar da listede gelir: kullanıcı neyi hedefleyeceğini görsün.
    """
    user = await user_service.get_user(db, user_id)
    stats = await _stats(db, user_id)
    in_family = await db.scalar(select(FamilyMember.user_id).where(FamilyMember.user_id == user_id)) is not None
    joined = days_since(user.created_at)

    checks = [
        ("first_moment", "İlk Anı", "📸", *_progress(stats.moments_count, 1, "anı")),
        ("generous", "Cömert", "🎁", *_progress(stats.gifts_sent_coins, 10_000, "coin hediye")),
        ("rising_star", "Yükselen Yıldız", "🌟", *_progress(stats.gifts_received_diamonds, 5_000, "elmas")),
        ("popular", "Popüler", "🔥", *_progress(user.followers_count, 1_000, "takipçi")),
        ("level_20", "Deneyimli", "⚡", *_progress(user.level, 20, "seviye")),
        ("loyal", "Sadık Üye", "📅", *_progress(joined, 100, "gün")),
        ("host", "Oda Sahibi", "🎙️", *_progress(stats.rooms_count, 1, "oda")),
        ("family", "Aile Ferdi", "🛡️", "Bir aileye katıl", in_family),
        ("vip", "VIP", "👑", "VIP üye ol", user.active_vip_level() > 0),
    ]
    achievements = [
        Achievement(id=key, name=name, emoji=emoji, detail=detail, is_unlocked=unlocked)
        for key, name, emoji, detail, unlocked in checks
    ]
    # Kazanılanlar önde
    achievements.sort(key=lambda a: not a.is_unlocked)
    return ProfileExtras(stats=stats, achievements=achievements)
