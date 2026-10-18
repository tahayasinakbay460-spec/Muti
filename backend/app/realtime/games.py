"""
Oda içi çok oyunculu oyunlar. Şimdilik: Rulet.

RULET NASIL OYNANIR?
  1. Odadaki biri turu başlatır (`game:roulette_start`). Herkese "tur başladı" yayınlanır.
  2. ROULETTE_BETTING_SECONDS saniye boyunca herkes bir renk seçer (`game:roulette_bet`):
     kırmızı, siyah ya da yeşil. Seçim süre bitene kadar değiştirilebilir.
  3. Süre bitince SUNUCU 0-36 arası bir sayı çeker; sayının rengini bilenler kazanır.
     Sonuç herkese aynı anda yayınlanır.

Coin bahsi yok: oyun sadece eğlence için. (Paralı oyun eklenirse coin hareketi
wallet_service üzerinden, tek transaction içinde yapılmalı.)

SUNUCU OTORİTEDİR: sayıyı istemci değil sunucu çeker (`secrets` ile, tahmin edilemez).
İstemcinin gönderdiği renk dışında hiçbir veriye bakılmaz.

DEMO KISAYOLU: Turlar bu sürecin belleğinde tutulur ve süre `asyncio` zamanlayıcısıyla
bitirilir. Birden fazla sunucuda tur durumu Redis'te tutulmalı ve turu yalnızca bir
sunucu bitirmeli (ör. süreli anahtar + kilit).
"""
import asyncio
import secrets
from dataclasses import dataclass, field

from app.core.errors import AppError, ConflictError
from app.realtime import events
from app.realtime.hub import room_hub

ROULETTE_COLORS = ("red", "black", "green")
# Avrupa ruleti: 0 yeşil, aşağıdakiler kırmızı, kalanlar siyah.
RED_NUMBERS = frozenset({1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36})


def roulette_color(number: int) -> str:
    if number == 0:
        return "green"
    return "red" if number in RED_NUMBERS else "black"


@dataclass
class RouletteRound:
    round_id: int
    # kullanıcı id → (seçtiği renk, yayınlarda kullanılan görünen bilgisi)
    bets: dict[int, tuple[str, dict]] = field(default_factory=dict)


class RouletteTables:
    """Her odada aynı anda en fazla bir rulet turu olur."""

    def __init__(self, betting_seconds: float = 10) -> None:
        self.betting_seconds = betting_seconds
        self._rounds: dict[int, RouletteRound] = {}
        self._next_round_id = 1
        # Çalışan zamanlayıcıları tutuyoruz; tutmazsak Python onları yarıda çöpe atabilir.
        self._timers: set[asyncio.Task] = set()

    async def start(self, room_id: int, user: dict) -> None:
        if room_id in self._rounds:
            raise ConflictError("Zaten bir rulet turu sürüyor.", code="roulette_running")
        game_round = RouletteRound(round_id=self._next_round_id)
        self._next_round_id += 1
        self._rounds[room_id] = game_round

        await room_hub.publish(room_id, events.GAME_ROULETTE_STARTED, {
            "round_id": game_round.round_id, "started_by": user, "betting_seconds": self.betting_seconds,
        })
        timer = asyncio.create_task(self._finish_later(room_id, game_round))
        self._timers.add(timer)
        timer.add_done_callback(self._timers.discard)

    async def bet(self, room_id: int, user_id: int, user: dict, color: str) -> None:
        if color not in ROULETTE_COLORS:
            raise AppError("Geçersiz renk.", code="invalid_color")
        game_round = self._rounds.get(room_id)
        if game_round is None:
            raise ConflictError("Şu an süren bir rulet turu yok.", code="no_active_round")
        game_round.bets[user_id] = (color, user)
        await room_hub.publish(room_id, events.GAME_ROULETTE_BET_PLACED, {
            "round_id": game_round.round_id, "user": user, "color": color,
        })

    async def _finish_later(self, room_id: int, game_round: RouletteRound) -> None:
        await asyncio.sleep(self.betting_seconds)
        # Turu önce listeden çıkarıyoruz: bu andan sonra gelen seçimler reddedilir.
        self._rounds.pop(room_id, None)
        number = secrets.randbelow(37)
        color = roulette_color(number)
        winners = [user for chosen, user in game_round.bets.values() if chosen == color]
        await room_hub.publish(room_id, events.GAME_ROULETTE_RESULT, {
            "round_id": game_round.round_id, "number": number, "color": color,
            "winners": winners, "player_count": len(game_round.bets),
        })


# Uygulamanın kullandığı tek rulet masası yöneticisi.
roulette = RouletteTables()
