"""
İki kişilik oda oyunları (düello): Dört Bağla ve Taş-Kağıt-Makas.

AKIŞ: Biri masa açar (`game:duel_create`) → başka biri oturur (`game:duel_join`) → oyuncular sırayla
hamle yapar (`game:duel_move`). Her değişiklikte masanın tamamı odadaki herkese yayınlanır
(`game:duel_updated`): oyuncular da izleyiciler de aynı tahtayı görür.

SUNUCU OTORİTEDİR: Hamlenin geçerli olup olmadığına, sıranın kimde olduğuna ve kazananı sunucu
karar verir. Taş-Kağıt-Makas'ta seçimler iki oyuncu da seçene kadar kimseye (rakibe de)
gösterilmez; yoksa ikinci seçen rakibin seçimini görüp kazanırdı.

SÜRE: Hamle sırası gelen oyuncu MOVE_SECONDS içinde oynamazsa hükmen kaybeder; rakip gelmeyen masa
WAIT_SECONDS sonra kapanır. Oyuncu odadan çıkarsa da hükmen kaybeder.

DEMO KISAYOLU: Masalar sürecin belleğinde (bkz. games.py notu).
"""
import asyncio
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.core.database import utcnow
from app.core.errors import AppError, ConflictError, NotFoundError
from app.realtime import events
from app.realtime.hub import room_hub
from app.schemas.activity import DuelOut

ROWS, COLUMNS = 6, 7
RPS_CHOICES = ("rock", "paper", "scissors")
RPS_BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}   # anahtar, değeri yener
RPS_WINS_NEEDED = 2          # 3 turdan 2'sini alan kazanır
MAX_TABLES_PER_ROOM = 3
MOVE_SECONDS = 45
WAIT_SECONDS = 120
FINISHED_VISIBLE_SECONDS = 20   # biten masa bu kadar ekranda kalır, sonra kapanır


@dataclass
class Table:
    table_id: str
    game: str
    players: list[dict]
    status: str = "waiting"
    turn: int = 0
    board: list[list[int]] = field(default_factory=lambda: [[0] * COLUMNS for _ in range(ROWS)])
    scores: list[int] = field(default_factory=lambda: [0, 0])
    choices: list[str | None] = field(default_factory=lambda: [None, None])
    last_round: dict | None = None
    winner: int | None = None
    reason: str | None = None
    deadline: datetime | None = None
    # Her yeni bekleme süresi yeni bir "nesil": eski zamanlayıcı uyanınca güncel değilse hiçbir şey yapmaz.
    generation: int = 0

    def out(self) -> DuelOut:
        common = dict(
            table_id=self.table_id, game=self.game, status=self.status, players=self.players,
            winner=self.winner, reason=self.reason, deadline=self.deadline,
        )
        if self.game == "connect4":
            return DuelOut(**common, turn=self.turn, board=self.board)
        # Seçimin kendisi değil, yalnızca "seçti mi" bilgisi gider.
        return DuelOut(**common, scores=self.scores, chosen=[c is not None for c in self.choices],
                       last_round=self.last_round)


def connect4_winner(board: list[list[int]], row: int, column: int) -> bool:
    """Son atılan taş (row, column) dört taşlık bir çizgi tamamladı mı? Dört yöne bakılır."""
    piece = board[row][column]
    for d_row, d_col in ((0, 1), (1, 0), (1, 1), (1, -1)):
        count = 1
        for sign in (1, -1):
            r, c = row + d_row * sign, column + d_col * sign
            while 0 <= r < ROWS and 0 <= c < COLUMNS and board[r][c] == piece:
                count += 1
                r, c = r + d_row * sign, c + d_col * sign
        if count >= 4:
            return True
    return False


class Duels:
    def __init__(self) -> None:
        self._tables: dict[int, dict[str, Table]] = {}
        self._timers: set[asyncio.Task] = set()
        # Testlerde süreler kısaltılabilsin diye örnek değişkeni
        self.move_seconds = MOVE_SECONDS
        self.wait_seconds = WAIT_SECONDS
        self.finished_seconds = FINISHED_VISIBLE_SECONDS

    def list_tables(self, room_id: int) -> list[DuelOut]:
        return [table.out() for table in self._tables.get(room_id, {}).values()]

    def _get(self, room_id: int, table_id: str) -> Table:
        table = self._tables.get(room_id, {}).get(table_id)
        if table is None:
            raise NotFoundError("Masa bulunamadı.")
        return table

    async def _publish(self, room_id: int, table: Table) -> None:
        await room_hub.publish(room_id, events.GAME_DUEL_UPDATED, {"table": table.out().model_dump(mode="json")})

    def _arm(self, room_id: int, table: Table, seconds: float) -> None:
        """Yeni bir süre başlatır; eski süre sayacı geçersiz olur."""
        table.generation += 1
        table.deadline = utcnow() + timedelta(seconds=seconds)
        task = asyncio.create_task(self._expire(room_id, table.table_id, table.generation, seconds))
        self._timers.add(task)
        task.add_done_callback(self._timers.discard)

    async def _expire(self, room_id: int, table_id: str, generation: int, seconds: float) -> None:
        await asyncio.sleep(seconds)
        table = self._tables.get(room_id, {}).get(table_id)
        if table is None or table.generation != generation:
            return
        if table.status == "waiting" or table.status == "finished":
            await self._close(room_id, table_id)
        elif table.game == "connect4":
            await self._finish(room_id, table, winner=1 - table.turn, reason="forfeit")
        else:
            # Taş-Kağıt-Makas: seçim yapmayan kaybeder; ikisi de yapmadıysa berabere.
            missing = [i for i, choice in enumerate(table.choices) if choice is None]
            await self._finish(room_id, table, winner=None if len(missing) == 2 else 1 - missing[0], reason="forfeit")

    async def _close(self, room_id: int, table_id: str) -> None:
        tables = self._tables.get(room_id, {})
        if tables.pop(table_id, None) is not None:
            await room_hub.publish(room_id, events.GAME_DUEL_CLOSED, {"table_id": table_id})
        if not tables:
            self._tables.pop(room_id, None)

    async def _finish(self, room_id: int, table: Table, winner: int | None, reason: str) -> None:
        table.status, table.winner, table.reason = "finished", winner, reason
        self._arm(room_id, table, self.finished_seconds)
        await self._publish(room_id, table)

    async def create(self, room_id: int, user: dict, game: str) -> DuelOut:
        if game not in ("connect4", "rps"):
            raise AppError("Bilinmeyen oyun.", code="invalid_game")
        tables = self._tables.setdefault(room_id, {})
        if any(user["id"] in [p["id"] for p in t.players] and t.status != "finished" for t in tables.values()):
            raise ConflictError("Zaten bir masadasın.", code="already_at_table")
        if len([t for t in tables.values() if t.status != "finished"]) >= MAX_TABLES_PER_ROOM:
            raise ConflictError("Bu odada en fazla 3 masa açılabilir.", code="too_many_tables")
        table = Table(table_id=secrets.token_hex(5), game=game, players=[user])
        tables[table.table_id] = table
        self._arm(room_id, table, self.wait_seconds)
        await self._publish(room_id, table)
        return table.out()

    async def join(self, room_id: int, user: dict, table_id: str) -> DuelOut:
        table = self._get(room_id, table_id)
        if table.status != "waiting":
            raise ConflictError("Bu masa dolu.", code="table_full")
        if table.players[0]["id"] == user["id"]:
            raise ConflictError("Kendi masana rakip olamazsın.", code="cannot_join_own")
        table.players.append(user)
        table.status = "playing"
        # Dört Bağla'da ilk hamleyi kimin yapacağını yazı-tura belirler.
        table.turn = secrets.randbelow(2)
        self._arm(room_id, table, self.move_seconds)
        await self._publish(room_id, table)
        return table.out()

    async def move(self, room_id: int, user_id: int, table_id: str, move) -> DuelOut:
        table = self._get(room_id, table_id)
        if table.status != "playing":
            raise ConflictError("Oyun sürmüyor.", code="game_not_running")
        ids = [p["id"] for p in table.players]
        if user_id not in ids:
            raise AppError("Bu masada oyuncu değilsin.", code="not_a_player")
        seat = ids.index(user_id)
        if table.game == "connect4":
            await self._connect4_move(room_id, table, seat, move)
        else:
            await self._rps_move(room_id, table, seat, move)
        return table.out()

    async def _connect4_move(self, room_id: int, table: Table, seat: int, column) -> None:
        if seat != table.turn:
            raise AppError("Sıra sende değil.", code="not_your_turn")
        if not isinstance(column, int) or not 0 <= column < COLUMNS:
            raise AppError("Geçersiz sütun.", code="invalid_move")
        # Taş, sütundaki en alttaki boş hücreye düşer.
        row = next((r for r in range(ROWS - 1, -1, -1) if table.board[r][column] == 0), None)
        if row is None:
            raise AppError("Bu sütun dolu.", code="column_full")
        table.board[row][column] = seat + 1
        if connect4_winner(table.board, row, column):
            await self._finish(room_id, table, winner=seat, reason="win")
        elif all(table.board[0][c] != 0 for c in range(COLUMNS)):
            await self._finish(room_id, table, winner=None, reason="draw")
        else:
            table.turn = 1 - seat
            self._arm(room_id, table, self.move_seconds)
            await self._publish(room_id, table)

    async def _rps_move(self, room_id: int, table: Table, seat: int, choice) -> None:
        if choice not in RPS_CHOICES:
            raise AppError("Geçersiz seçim.", code="invalid_move")
        if table.choices[seat] is not None:
            raise ConflictError("Bu turda seçimini yaptın.", code="already_chosen")
        table.choices[seat] = choice
        if None in table.choices:
            await self._publish(room_id, table)   # rakip yalnızca "seçti" bilgisini görür
            return
        first, second = table.choices
        round_winner = None if first == second else (0 if RPS_BEATS[first] == second else 1)
        if round_winner is not None:
            table.scores[round_winner] += 1
        table.last_round = {"choices": [first, second], "winner": round_winner}
        table.choices = [None, None]
        if max(table.scores) >= RPS_WINS_NEEDED:
            await self._finish(room_id, table, winner=table.scores.index(max(table.scores)), reason="win")
        else:
            self._arm(room_id, table, self.move_seconds)
            await self._publish(room_id, table)

    async def leave(self, room_id: int, user_id: int, table_id: str | None = None) -> None:
        """Oyuncu masadan ya da odadan çıktı: oyun sürüyorsa hükmen kaybeder, bekliyorsa masa kapanır."""
        for table in list(self._tables.get(room_id, {}).values()):
            if table_id is not None and table.table_id != table_id:
                continue
            ids = [p["id"] for p in table.players]
            if user_id not in ids:
                continue
            if table.status == "playing":
                await self._finish(room_id, table, winner=1 - ids.index(user_id), reason="forfeit")
            elif table.status == "waiting":
                await self._close(room_id, table.table_id)

    def drop_room(self, room_id: int) -> None:
        self._tables.pop(room_id, None)


# Uygulamanın kullandığı tek düello yöneticisi.
duels = Duels()
