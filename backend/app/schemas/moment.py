"""
Anılar (Instagram benzeri paylaşımlar) için JSON şemaları.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.user import UserOut


class MomentOut(BaseModel):
    id: int
    user: UserOut
    text: str
    image_url: str | None
    like_count: int
    comment_count: int = 0
    created_at: datetime
    # ── Bakan kişiye göre ─────────────────────────────────────────────────────
    is_liked: bool
    is_mine: bool


class MomentCreateRequest(BaseModel):
    text: str = Field(default="", max_length=500)
    # Yalnızca hazır listeden (GET /moments/image-options) bir adres kabul edilir; kontrol serviste.
    image_url: str | None = Field(default=None, max_length=500)

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def not_empty(self):
        # Ne yazı ne görsel olan boş bir paylaşım anlamsız.
        if not self.text and not self.image_url:
            raise ValueError("Bir şey yaz ya da bir görsel seç.")
        return self


class MomentCommentOut(BaseModel):
    id: int
    moment_id: int
    user: UserOut
    text: str
    created_at: datetime
    # Bakan kişi silebilir mi: yorumu yazan ya da anının sahibi.
    can_delete: bool


class MomentCommentCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class MomentLikeResult(BaseModel):
    is_liked: bool
    like_count: int


class MomentImageOptions(BaseModel):
    images: list[str]


MomentFeed = Literal["explore", "following"]
