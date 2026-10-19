"""
Oda JSON şemaları.
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.user import UserOut


class SeatOut(BaseModel):
    """Odadaki bir koltuk (mikrofon yeri)."""
    index: int                # koltuk numarası, 0'dan başlar
    user_id: int | None       # boşsa null
    is_muted: bool
    is_locked: bool
    # Yönetici bu kişinin mikrofonunu engelledi: kendisi açamaz.
    is_mic_blocked: bool = False
    user: UserOut | None      # oturan kişinin bilgisi (boşsa null)


class RoomOut(BaseModel):
    id: int
    title: str
    category: str
    cover_url: str | None
    is_live: bool
    listener_count: int       # şu an odada kaç kişi var (canlı sayı)
    host_id: int
    hourly_rank: int          # dinleyici sayısına göre sıralama
    announcement: str
    host: UserOut
    seats: list[SeatOut]
    # Odanın yöneticileri ve VIP'leri (oda sahibi bu listelerde değildir, o `host_id`).
    admin_ids: list[int] = []
    vip_ids: list[int] = []
    # false: koltuklara kendiliğinden yalnızca oda sahibi, yönetici ve VIP oturur;
    # diğerleri bir yöneticinin davetiyle oturur.
    free_seating: bool = True
    # Bakan kişiye göre değişir: isteği atan kişi bu odayı takip ediyor mu?
    # Herkese giden yayınlarda (viewer yok) her zaman false'tur.
    is_following: bool = False


class RoomMemberOut(BaseModel):
    """Odada şu an bulunan bir kişi (dinleyici listesi)."""
    user: UserOut
    role: Literal["host", "admin", "vip", "listener"]
    seat_index: int | None        # koltukta değilse null
    is_mic_blocked: bool
    chat_muted_seconds: int       # sohbette susturulmuşsa kalan süre (saniye), değilse 0


class RoomFollowResult(BaseModel):
    is_following: bool


class RoomCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=60)
    category: Literal["chat", "music", "game", "new_people"] = "chat"

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value):
        # "   " gibi yalnızca boşluktan oluşan adlar min_length kontrolüne takılsın.
        return value.strip() if isinstance(value, str) else value


class RoomUpdateRequest(BaseModel):
    """
    Oda ayarları. PATCH isteğidir: yalnızca gönderilen alanlar değişir.
    Kapak yalnızca hazır listeden seçilebilir (kontrol serviste).
    """
    title: str | None = Field(default=None, min_length=1, max_length=60)
    category: Literal["chat", "music", "game", "new_people"] | None = None
    announcement: str | None = Field(default=None, max_length=300)
    cover_url: str | None = Field(default=None, max_length=500)
    free_seating: bool | None = None

    @field_validator("title", "announcement", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class RoomRoleRequest(BaseModel):
    """Kişinin odadaki rolünü değiştirir. "listener" = özel rolünü geri al."""
    role: Literal["admin", "vip", "listener"]


class ChatMuteRequest(BaseModel):
    """Sohbette susturma süresi (dakika). Yalnızca bu seçenekler; arayüzdeki düğmelerle aynı."""
    minutes: Literal[5, 30, 60, 1440]
