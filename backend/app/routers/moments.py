"""
/api/v1/moments — Anılar (Instagram benzeri paylaşımlar): akış, paylaşma, beğenme, yorum, silme.
"""
from fastapi import APIRouter, Response, status

from app.core.deps import CurrentUser, CurrentUserId, DbSession
from app.schemas.moment import (
    MomentCommentCreateRequest, MomentCommentOut, MomentCreateRequest, MomentFeed,
    MomentLikeResult, MomentOut,
)
from app.services import moment_service

router = APIRouter(prefix="/moments", tags=["moments"])


@router.get("", response_model=list[MomentOut])
async def list_moments(user_id: CurrentUserId, db: DbSession, feed: MomentFeed = "explore", before_id: int | None = None):
    """
    Anı akışı. `feed=explore` herkesinkiler, `feed=following` takip ettiklerimin.
    Daha eskileri için `before_id` = listedeki son anının id'si.
    """
    return await moment_service.list_feed(db, user_id, feed, before_id)


@router.post("", response_model=MomentOut, status_code=status.HTTP_201_CREATED)
async def create_moment(data: MomentCreateRequest, user: CurrentUser, db: DbSession):
    return await moment_service.create_moment(db, user, data)


@router.delete("/{moment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_moment(moment_id: int, user_id: CurrentUserId, db: DbSession):
    """Yalnızca anının sahibi siler."""
    await moment_service.delete_moment(db, user_id, moment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{moment_id}/like", response_model=MomentLikeResult)
async def toggle_like(moment_id: int, user_id: CurrentUserId, db: DbSession):
    """Beğendiysen geri alır, beğenmediysen beğenir."""
    return await moment_service.toggle_like(db, user_id, moment_id)


@router.get("/{moment_id}/comments", response_model=list[MomentCommentOut])
async def list_comments(moment_id: int, user_id: CurrentUserId, db: DbSession):
    """Anının yorumları, eskiden yeniye."""
    return await moment_service.list_comments(db, user_id, moment_id)


@router.post("/{moment_id}/comments", response_model=MomentCommentOut, status_code=status.HTTP_201_CREATED)
async def add_comment(moment_id: int, data: MomentCommentCreateRequest, user: CurrentUser, db: DbSession):
    return await moment_service.add_comment(db, user, moment_id, data.text)


@router.delete("/{moment_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(moment_id: int, comment_id: int, user_id: CurrentUserId, db: DbSession):
    """Yorumu yazan ya da anının sahibi siler."""
    await moment_service.delete_comment(db, user_id, moment_id, comment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
