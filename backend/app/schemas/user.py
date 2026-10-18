"""
Kullanıcıyla ilgili JSON şemaları.

"Şema" = API'nin aldığı ya da döndüğü JSON'un kalıbı. Model (tablo) ile şema ayrıdır:
tabloda `password_hash` vardır ama şemada yoktur, böylece yanlışlıkla dışarı sızmaz.
"""
from datetime import datetime

from pydantic import BaseModel


class UserOut(BaseModel):
    """Bir kullanıcının dışarıya gösterilen hali."""
    id: int
    username: str
    display_name: str
    age: int | None
    city: str | None
    avatar_url: str | None
    cover_url: str | None
    bio: str
    vip_level: int
    level: int
    is_verified: bool
    is_guest: bool
    is_online: bool
    joined_days: int          # kaç gündür üye
    created_at: datetime
    followers_count: int
    following_count: int
    friends_count: int
    visitors_count: int

    # ── Bakan kişiye göre değişen alanlar ─────────────────────────────────────
    is_me: bool               # bu profil, isteği atan kişinin kendisi mi?
    is_following: bool        # isteği atan kişi bu kullanıcıyı takip ediyor mu?
    # Bakiye özeldir: yalnızca kişi kendi profiline bakarken dolu gelir, başkası için null.
    coin_balance: int | None = None
    diamond_balance: int | None = None


class FollowResult(BaseModel):
    is_following: bool


class TopGifter(BaseModel):
    rank: int
    user: UserOut
    total_coins: int


class ProfileExtras(BaseModel):
    """Profil ekranının alt bölümleri. DEMO: içerik şimdilik sabit (demo/content.py)."""
    wall_posts: list[dict]
    avatar_frames: list[dict]
    achievements: list[dict]
    recent_rewards: list[dict]
