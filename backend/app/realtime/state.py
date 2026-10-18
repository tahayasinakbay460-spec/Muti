"""
Canlı oda durumu deposu: koltuklar, dinleyiciler, kim çevrimiçi.

NEDEN VERİTABANINDA DEĞİL?
Bu bilgiler saniyede defalarca değişir ve oda kapanınca anlamını yitirir. Bunları
her seferinde diske (veritabanına) yazmak hem yavaş hem gereksizdir. Hızlı bir
bellek deposunda tutulur.

İKİ PARÇA VAR:
  1. RoomStateStore        → "sözleşme": deponun hangi işlemleri sunduğunu söyler.
  2. InMemoryRoomStateStore → o sözleşmenin şimdiki uygulaması: Python sözlükleri.

DEMO KISAYOLU: InMemory sürümü yalnızca TEK sunucu süreciyle doğru çalışır ve sunucu
yeniden başlayınca her şey sıfırlanır. Canlıda aynı sözleşmeyi uygulayan bir
RedisRoomStateStore yazılacak ve en alttaki `room_state = ...` satırı değişecek.
Kodun geri kalanı yalnızca sözleşmeyi bildiği için başka hiçbir yere dokunulmaz.
"""
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace

from app.core.errors import ConflictError, NotFoundError

# Bir kullanıcı son isteğinden bu kadar saniye sonrasına kadar "çevrimiçi" sayılır.
ONLINE_WINDOW_SECONDS = 300


@dataclass
class Seat:
    index: int
    user_id: int | None = None
    is_muted: bool = False
    is_locked: bool = False


class RoomStateStore(ABC):
    """Sözleşme. Metodlar `async`, çünkü Redis sürümünde her biri bir ağ çağrısı olacak."""

    # ── Koltuklar ─────────────────────────────────────────────────────────────
    @abstractmethod
    async def ensure_room(self, room_id: int, seat_count: int) -> None:
        """Odanın koltukları depoda yoksa boş olarak oluşturur. Varsa hiçbir şey yapmaz."""

    @abstractmethod
    async def get_seats(self, room_ids: list[int]) -> dict[int, list[Seat]]:
        """Birden çok odanın koltuklarını tek seferde getirir (oda listesi için)."""

    @abstractmethod
    async def take_seat(self, room_id: int, seat_index: int, user_id: int) -> None:
        """Kullanıcıyı koltuğa oturtur. Koltuk dolu/kilitliyse hata fırlatır."""

    @abstractmethod
    async def leave_seat(self, room_id: int, user_id: int) -> bool:
        """Kullanıcıyı koltuğundan kaldırır. Gerçekten oturuyorduysa True döner."""

    @abstractmethod
    async def toggle_mute(self, room_id: int, user_id: int) -> bool:
        """Kullanıcının mikrofonunu aç/kapa yapar. Oturmuyorsa False döner."""

    # ── Dinleyiciler ──────────────────────────────────────────────────────────
    @abstractmethod
    async def add_listener(self, room_id: int, user_id: int) -> bool:
        """Odaya bir bağlantı ekler. Kullanıcının bu odadaki İLK bağlantısıysa True döner."""

    @abstractmethod
    async def remove_listener(self, room_id: int, user_id: int) -> bool:
        """Bir bağlantıyı düşer. Kullanıcının odada hiç bağlantısı kalmadıysa True döner."""

    @abstractmethod
    async def listener_counts(self, room_ids: list[int]) -> dict[int, int]:
        """Odalardaki kişi sayıları."""

    @abstractmethod
    async def room_ranks(self, room_ids: list[int]) -> dict[int, int]:
        """Odaların dinleyici sayısına göre sırası (1 = en kalabalık)."""

    # ── Çevrimiçi durumu ──────────────────────────────────────────────────────
    @abstractmethod
    async def touch_presence(self, user_id: int) -> None:
        """Kullanıcının "az önce buradaydı" damgasını yeniler."""

    @abstractmethod
    async def online_user_ids(self, user_ids: list[int]) -> set[int]:
        """Verilen kullanıcılardan şu an çevrimiçi olanlar."""


class InMemoryRoomStateStore(RoomStateStore):
    """
    Bellek içi uygulama.

    Kilit (lock) kullanmıyoruz çünkü Python'un async yapısında bir fonksiyon,
    içinde `await` olmadığı sürece kesintiye uğramaz. Aşağıdaki metodların
    gövdesinde `await` yok → "iki kişi aynı anda aynı koltuğa oturdu" olamaz.
    (Redis sürümünde aynı garantiyi Lua script veya HSETNX verecek.)
    """

    def __init__(self) -> None:
        self._seats: dict[int, list[Seat]] = {}
        # oda → { kullanıcı → açık bağlantı sayısı }. Aynı kişi iki sekmeden
        # bağlanabilir; onu iki kişi saymamak için bağlantıları kişi başına tutuyoruz.
        self._listeners: dict[int, dict[int, int]] = {}
        self._last_seen: dict[int, float] = {}
        # Yalnızca demo verisi için (bkz. demo/seed.py): hazır odalar boş görünmesin.
        self.demo_listener_base: dict[int, int] = {}
        self.demo_always_online: set[int] = set()

    def demo_set_seat(self, room_id: int, index: int, user_id: int | None = None,
                      is_muted: bool = False, is_locked: bool = False) -> None:
        """Yalnızca demo verisi için: bir koltuğu kontrolsüz, doğrudan ayarlar."""
        self._seats[room_id][index] = Seat(index=index, user_id=user_id, is_muted=is_muted, is_locked=is_locked)

    # ── Koltuklar ─────────────────────────────────────────────────────────────
    async def ensure_room(self, room_id: int, seat_count: int) -> None:
        if room_id not in self._seats:
            self._seats[room_id] = [Seat(index=i) for i in range(seat_count)]

    async def get_seats(self, room_ids: list[int]) -> dict[int, list[Seat]]:
        # Kopyasını veriyoruz ki dışarıdaki kod depodaki asıl veriyi yanlışlıkla değiştirmesin.
        return {rid: [replace(seat) for seat in self._seats.get(rid, [])] for rid in room_ids}

    async def take_seat(self, room_id: int, seat_index: int, user_id: int) -> None:
        seats = self._seats.get(room_id, [])
        if not 0 <= seat_index < len(seats):
            raise NotFoundError("Koltuk bulunamadı.", code="seat_not_found")
        target = seats[seat_index]
        if target.is_locked:
            raise ConflictError("Bu koltuk kilitli.", code="seat_locked")
        if target.user_id is not None and target.user_id != user_id:
            raise ConflictError("Bu koltuk dolu.", code="seat_taken")
        # Bir kişi aynı anda tek koltukta oturabilir: önce eski koltuğunu boşalt.
        for seat in seats:
            if seat.user_id == user_id:
                seat.user_id = None
        target.user_id = user_id
        target.is_muted = False

    async def leave_seat(self, room_id: int, user_id: int) -> bool:
        for seat in self._seats.get(room_id, []):
            if seat.user_id == user_id:
                seat.user_id = None
                seat.is_muted = False
                return True
        return False

    async def toggle_mute(self, room_id: int, user_id: int) -> bool:
        for seat in self._seats.get(room_id, []):
            if seat.user_id == user_id:
                seat.is_muted = not seat.is_muted
                return True
        return False

    # ── Dinleyiciler ──────────────────────────────────────────────────────────
    async def add_listener(self, room_id: int, user_id: int) -> bool:
        connections = self._listeners.setdefault(room_id, {})
        connections[user_id] = connections.get(user_id, 0) + 1
        return connections[user_id] == 1

    async def remove_listener(self, room_id: int, user_id: int) -> bool:
        connections = self._listeners.get(room_id, {})
        remaining = connections.get(user_id, 0) - 1
        if remaining > 0:
            connections[user_id] = remaining
            return False
        connections.pop(user_id, None)
        return True

    def _count(self, room_id: int) -> int:
        return len(self._listeners.get(room_id, {})) + self.demo_listener_base.get(room_id, 0)

    async def listener_counts(self, room_ids: list[int]) -> dict[int, int]:
        return {rid: self._count(rid) for rid in room_ids}

    async def room_ranks(self, room_ids: list[int]) -> dict[int, int]:
        # DEMO KISAYOLU: her çağrıda bütün odaları sıralıyoruz. Oda sayısı büyüyünce
        # pahalı olur; Redis'te bu iş sorted set ile (ZREVRANK) tek adımdır.
        ordered = sorted(self._seats, key=self._count, reverse=True)
        position = {rid: index + 1 for index, rid in enumerate(ordered)}
        return {rid: position.get(rid, len(ordered) + 1) for rid in room_ids}

    # ── Çevrimiçi durumu ──────────────────────────────────────────────────────
    async def touch_presence(self, user_id: int) -> None:
        # DEMO KISAYOLU: bu sözlük hiç küçülmez. Redis'te süreli anahtar (SETEX) kendisi silinir.
        self._last_seen[user_id] = time.monotonic()

    async def online_user_ids(self, user_ids: list[int]) -> set[int]:
        threshold = time.monotonic() - ONLINE_WINDOW_SECONDS
        return {
            uid for uid in user_ids
            if uid in self.demo_always_online or self._last_seen.get(uid, 0) > threshold
        }


# Uygulamanın kullandığı tek depo. Redis'e geçerken yalnızca bu satır değişir.
room_state: RoomStateStore = InMemoryRoomStateStore()
