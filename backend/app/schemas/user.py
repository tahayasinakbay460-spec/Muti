"""
Kullanıcıyla ilgili JSON şemaları.

"Şema" = API'nin aldığı ya da döndüğü JSON'un kalıbı. Model (tablo) ile şema ayrıdır:
tabloda `password_hash` vardır ama şemada yoktur, böylece yanlışlıkla dışarı sızmaz.
"""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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
    experience: int           # deneyim puanı (bkz. services/level_service.py)
    next_level_experience: int  # bir sonraki seviye için gereken toplam deneyim
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
    is_blocked: bool = False  # isteği atan kişi bu kullanıcıyı engelledi mi?
    # Bakiye özeldir: yalnızca kişi kendi profiline bakarken dolu gelir, başkası için null.
    coin_balance: int | None = None
    diamond_balance: int | None = None


class FollowResult(BaseModel):
    is_following: bool


class ProfileUpdateRequest(BaseModel):
    """
    "Profili Düzenle" formu. PATCH isteğidir: yalnızca gönderilen alanlar değişir,
    gönderilmeyenler olduğu gibi kalır. (Servis bunu `model_fields_set` ile ayırt eder.)
    """
    display_name: str | None = Field(default=None, min_length=1, max_length=40)
    bio: str | None = Field(default=None, max_length=300)
    age: int | None = Field(default=None, ge=13, le=99)
    city: str | None = Field(default=None, max_length=60)
    # Yalnızca hazır listeden (demo/content.py) bir adres kabul edilir; kontrol serviste.
    avatar_url: str | None = Field(default=None, max_length=500)
    cover_url: str | None = Field(default=None, max_length=500)

    @field_validator("display_name", "bio", "city", mode="before")
    @classmethod
    def strip_text(cls, value):
        # Baştaki/sondaki boşlukları at; "   " gibi boş bir ad min_length kontrolüne takılsın.
        return value.strip() if isinstance(value, str) else value


class MediaOptions(BaseModel):
    """Profil düzenlemede seçilebilecek hazır avatar ve kapak görselleri."""
    avatars: list[str]
    covers: list[str]


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
