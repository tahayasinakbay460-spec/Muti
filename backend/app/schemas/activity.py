"""
Oda içi etkinlikler JSON şemaları: PK (takım hediye yarışı), birlikte izleme, karaoke sırası,
iki kişilik oyun masaları (düello).
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PkTeam = Literal["red", "blue"]


class PkStartRequest(BaseModel):
    minutes: Literal[1, 3, 5, 10]


class PkContributor(BaseModel):
    user: dict                # yayınlarda kullanılan kullanıcı bilgisi (UserOut JSON'u)
    coins: int


class PkOut(BaseModel):
    pk_id: str
    status: Literal["running", "ended"]
    ends_at: datetime
    red: int                  # kırmızı takıma gelen hediyelerin coin toplamı
    blue: int
    red_seats: list[int]      # koltuk numaraları (0'dan başlar)
    blue_seats: list[int]
    winner: Literal["red", "blue", "draw"] | None = None
    mvp: PkContributor | None = None   # en çok hediye gönderen destekçi


class MediaSetRequest(BaseModel):
    # Yalnızca YouTube bağlantısı kabul edilir; video kimliğini sunucu ayıklar.
    url: str = Field(min_length=5, max_length=300)


class MediaControlRequest(BaseModel):
    action: Literal["play", "pause", "seek"]
    position: float | None = Field(default=None, ge=0, le=60 * 60 * 6)   # saniye (seek ve pause için)


class MediaOut(BaseModel):
    video_id: str
    # Oynuyorsa: videonun 0. saniyesinin denk geldiği an. İstemci şu anki saniyeyi
    # "şimdi - started_at" diye hesaplar; herkes aynı saniyeyi görür.
    started_at: datetime | None
    paused: bool
    position: float           # durdurulduysa kaldığı saniye
    set_by: dict
    server_time: datetime     # istemci saat farkını düzeltsin diye sunucunun saati


class KaraokeOut(BaseModel):
    singer: dict | None       # şu an şarkı söyleyen
    queue: list[dict]         # sırada bekleyenler


DuelGame = Literal["connect4", "rps"]


class DuelOut(BaseModel):
    table_id: str
    game: DuelGame
    status: Literal["waiting", "playing", "finished"]
    players: list[dict]       # 1 ya da 2 kişi
    turn: int | None = None   # Dört Bağla: sıradaki oyuncunun sırası (0 ya da 1)
    board: list[list[int]] | None = None     # Dört Bağla: 6 satır × 7 sütun, 0 boş / 1 / 2
    scores: list[int] | None = None          # Taş-Kağıt-Makas: tur galibiyetleri
    chosen: list[bool] | None = None         # Taş-Kağıt-Makas: bu turda seçim yaptı mı (seçim gizli)
    last_round: dict | None = None           # Taş-Kağıt-Makas: son turun açıklanan seçimleri
    winner: int | None = None                # kazanan oyuncunun sırası; berabere ise None
    reason: str | None = None                # "win" | "draw" | "forfeit"
    deadline: datetime | None = None         # bu süreye kadar hamle yapılmazsa sıradaki kaybeder


class RoomActivities(BaseModel):
    """Odaya girince bir kez alınan güncel durum (sonrası WebSocket olaylarıyla güncellenir)."""
    pk: PkOut | None
    media: MediaOut | None
    karaoke: KaraokeOut
    duels: list[DuelOut]
