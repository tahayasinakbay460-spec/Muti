"""
Sıralamalar: zenginler (en çok hediye gönderen), çekiciler (en çok hediye alan), odalar,
aileler; günlük / haftalık / aylık. Etkinlik sıralaması da aynı hesabı kullanır.

Puanlar para defterinden (transactions) hesaplanır: ayrı sayaç yok, defterle hiç çelişmez.
DEMO KISAYOLU: Her istekte defter toplanıyor. Kalabalıkta her hediyede Redis sorted set'e
(ZINCRBY) puan eklenir, sıralama oradan okunur.
"""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timefmt import period_start
from app.models import Family, FamilyMember, Room, Transaction
from app.schemas.engagement import Leaderboard, LeaderboardEntry
from app.services import user_service

LIMIT = 30


async def user_scores(
    db: AsyncSession, metric: str, since: datetime, until: datetime | None = None, limit: int | None = LIMIT,
) -> list[tuple[int, int]]:
    """
    [(kullanıcı id, puan)] büyükten küçüğe. metric: "gifts_sent" (coin) ya da "gifts_received" (elmas).
    `limit=None` herkesi döner (kişinin kendi sırasını bulmak için).
    """
    if metric == "gifts_sent":
        score, kind = func.sum(-Transaction.amount), "gift_sent"
    else:
        score, kind = func.sum(Transaction.amount), "gift_received"
    statement = (
        select(Transaction.user_id, score.label("score"))
        .where(Transaction.type == kind, Transaction.created_at >= since)
        .group_by(Transaction.user_id)
        # Eşitlikte önce o puana ilk ulaşan değil, küçük id üstte: sıra her istekte aynı kalsın.
        .order_by(score.desc(), Transaction.user_id)
    )
    if until is not None:
        statement = statement.where(Transaction.created_at < until)
    if limit is not None:
        statement = statement.limit(limit)
    return [(row.user_id, row.score) for row in await db.execute(statement)]


async def user_entries(
    db: AsyncSession, viewer_id: int, metric: str, since: datetime, until: datetime | None = None,
) -> tuple[list[LeaderboardEntry], LeaderboardEntry | None]:
    """Kişi sıralaması ve isteği atanın kendi sırası (ilk 30'da olmasa da)."""
    everyone = await user_scores(db, metric, since, until, limit=None)
    top = everyone[:LIMIT]
    mine = next(((rank, score) for rank, (uid, score) in enumerate(everyone, 1) if uid == viewer_id), None)
    users = await user_service.load_users_out(db, {uid for uid, _ in top} | {viewer_id}, viewer_id)
    entries = [
        LeaderboardEntry(rank=rank, score=score, user=users[uid])
        for rank, (uid, score) in enumerate(top, 1) if uid in users
    ]
    me = LeaderboardEntry(rank=mine[0], score=mine[1], user=users.get(viewer_id)) if mine else None
    return entries, me


async def get_leaderboard(db: AsyncSession, viewer_id: int, kind: str, period: str) -> Leaderboard:
    since = period_start(period)
    me = None
    if kind in ("rich", "charm"):
        entries, me = await user_entries(db, viewer_id, "gifts_sent" if kind == "rich" else "gifts_received", since)

    elif kind == "rooms":
        score = func.sum(-Transaction.amount)
        rows = (await db.execute(
            select(Room.id, Room.title, Room.cover_url, score.label("score"))
            .join(Transaction, Transaction.room_id == Room.id)
            .where(Transaction.type == "gift_sent", Transaction.created_at >= since, Room.is_active)
            .group_by(Room.id, Room.title, Room.cover_url).order_by(score.desc(), Room.id).limit(LIMIT)
        )).all()
        entries = [
            LeaderboardEntry(rank=rank, score=row.score, room={"id": row.id, "title": row.title, "cover_url": row.cover_url})
            for rank, row in enumerate(rows, 1)
        ]

    else:   # families: şu anki üyelerin bu dönemde gönderdiği hediyeler
        score = func.sum(-Transaction.amount)
        rows = (await db.execute(
            select(Family.id, Family.name, Family.badge, Family.member_count, score.label("score"))
            .join(FamilyMember, FamilyMember.family_id == Family.id)
            .join(Transaction, Transaction.user_id == FamilyMember.user_id)
            .where(Transaction.type == "gift_sent", Transaction.created_at >= since)
            .group_by(Family.id, Family.name, Family.badge, Family.member_count)
            .order_by(score.desc(), Family.id).limit(LIMIT)
        )).all()
        entries = [
            LeaderboardEntry(rank=rank, score=row.score, family={
                "id": row.id, "name": row.name, "badge": row.badge, "member_count": row.member_count,
            })
            for rank, row in enumerate(rows, 1)
        ]

    return Leaderboard(kind=kind, period=period, entries=entries, me=me)
