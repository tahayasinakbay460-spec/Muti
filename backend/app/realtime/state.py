"""
Canlı oda durumu deposu: koltuklar, dinleyiciler, oda içi kısıtlamalar (atma, sohbette
susturma, mikrofon engeli), koltuk davetleri, son sohbet mesajları, kim çevrimiçi.

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
import math
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, replace

from app.core.errors import ConflictError, NotFoundError

# Bir kullanıcı son isteğinden bu kadar saniye sonrasına kadar "çevrimiçi" sayılır.
ONLINE_WINDOW_SECONDS = 300
# Odaya yeni giren kişiye gösterilen son sohbet mesajı sayısı.
CHAT_HISTORY_SIZE = 50


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

    @abstractmethod
    async def clear_seat(self, room_id: int, seat_index: int) -> int | None:
        """Koltuktaki kişiyi kaldırır (moderasyon). Kaldırılan kişinin id'sini döner, boşsa None."""

    @abstractmethod
    async def set_seat_locked(self, room_id: int, seat_index: int, locked: bool) -> None:
        """Koltuğu kilitler/açar. Kilitlemeden önce koltuk boşaltılmış olmalı."""

    @abstractmethod
    async def seat_index_of(self, room_id: int, user_id: int) -> int | None:
        """Kullanıcı bu odada hangi koltukta oturuyor? Oturmuyorsa None."""

    # ── Mikrofon engeli (moderasyon) ──────────────────────────────────────────
    @abstractmethod
    async def set_mic_blocked(self, room_id: int, user_id: int, blocked: bool) -> None:
        """
        Engellenen kişinin mikrofonu kapanır ve kendisi açamaz. Engel kaldırılana kadar
        sürer; koltuktan kalkıp yeniden otursa bile.
        """

    @abstractmethod
    async def mic_blocked_ids(self, room_ids: list[int]) -> dict[int, set[int]]:
        """Odalarda mikrofonu engellenmiş kişiler."""

    # ── Süreli kısıtlamalar ───────────────────────────────────────────────────
    # Üçü de aynı mantıkla çalışır: (oda, kişi) için bir bitiş anı tutulur, süre dolunca
    # kendiliğinden geçersiz olur. Redis'te her biri süreli bir anahtardır (SET ... EX).
    @abstractmethod
    async def ban_from_room(self, room_id: int, user_id: int, seconds: int) -> None:
        """Kullanıcı `seconds` saniye boyunca odaya giremez."""

    @abstractmethod
    async def is_banned(self, room_id: int, user_id: int) -> bool:
        """Kullanıcının odaya girişi şu an yasaklı mı?"""

    @abstractmethod
    async def mute_chat(self, room_id: int, user_id: int, seconds: int | None) -> None:
        """Kullanıcı `seconds` saniye sohbete yazamaz. None verilirse susturma kaldırılır."""

    @abstractmethod
    async def chat_mute_remaining(self, room_id: int, user_ids: list[int]) -> dict[int, int]:
        """Susturulmuş kişilerin kalan süresi (saniye). Susturulmamışlar sonuçta yer almaz."""

    @abstractmethod
    async def grant_seat_invite(self, room_id: int, user_id: int, seconds: int) -> None:
        """Yönetici kişiyi koltuğa davet etti: kişi `seconds` içinde bir kez oturabilir."""

    @abstractmethod
    async def consume_seat_invite(self, room_id: int, user_id: int) -> bool:
        """Geçerli bir davet varsa kullanır (siler) ve True döner."""

    # ── Son sohbet mesajları ──────────────────────────────────────────────────
    @abstractmethod
    async def append_chat(self, room_id: int, message: dict) -> None:
        """Mesajı odanın son mesajlarına ekler; CHAT_HISTORY_SIZE aşılınca en eskisi düşer."""

    @abstractmethod
    async def recent_chat(self, room_id: int) -> list[dict]:
        """Odanın son mesajları, eskiden yeniye."""

    @abstractmethod
    async def remove_chat(self, room_id: int, message_id: str) -> dict | None:
        """Mesajı son mesajlardan siler ve döner. Bulunamazsa None."""

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
    async def listener_ids(self, room_id: int) -> list[int]:
        """Odaya şu an gerçekten bağlı olan kişiler (en son gelen en sonda)."""

    @abstractmethod
    async def is_in_room(self, room_id: int, user_id: int) -> bool:
        """Kullanıcının bu odaya açık bir bağlantısı var mı?"""

    @abstractmethod
    async def room_ranks(self, room_ids: list[int]) -> dict[int, int]:
        """Odaların dinleyici sayısına göre sırası (1 = en kalabalık)."""

    # ── Oda kapanınca ─────────────────────────────────────────────────────────
    @abstractmethod
    async def drop_room(self, room_id: int) -> None:
        """Kapatılan odanın bütün canlı bilgisini siler."""

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
        # (tür, oda, kullanıcı) → kısıtlamanın bittiği an. Türler: "ban", "chat_mute", "seat_invite".
        self._timed: dict[tuple[str, int, int], float] = {}
        self._mic_blocks: dict[int, set[int]] = {}
        self._chat: dict[int, deque[dict]] = {}
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
        # Mikrofonu engellenen kişi koltuğa sessiz oturur.
        target.is_muted = user_id in self._mic_blocks.get(room_id, ())

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

    def _seat_at(self, room_id: int, seat_index: int) -> Seat:
        seats = self._seats.get(room_id, [])
        if not 0 <= seat_index < len(seats):
            raise NotFoundError("Koltuk bulunamadı.", code="seat_not_found")
        return seats[seat_index]

    async def clear_seat(self, room_id: int, seat_index: int) -> int | None:
        seat = self._seat_at(room_id, seat_index)
        removed = seat.user_id
        seat.user_id = None
        seat.is_muted = False
        return removed

    async def set_seat_locked(self, room_id: int, seat_index: int, locked: bool) -> None:
        seat = self._seat_at(room_id, seat_index)
        if locked and seat.user_id is not None:
            raise ConflictError("Önce koltuktaki kişiyi indir.", code="seat_taken")
        seat.is_locked = locked

    async def seat_index_of(self, room_id: int, user_id: int) -> int | None:
        for seat in self._seats.get(room_id, []):
            if seat.user_id == user_id:
                return seat.index
        return None

    # ── Mikrofon engeli ───────────────────────────────────────────────────────
    async def set_mic_blocked(self, room_id: int, user_id: int, blocked: bool) -> None:
        blocked_ids = self._mic_blocks.setdefault(room_id, set())
        if blocked:
            blocked_ids.add(user_id)
            for seat in self._seats.get(room_id, []):
                if seat.user_id == user_id:
                    seat.is_muted = True
        else:
            blocked_ids.discard(user_id)

    async def mic_blocked_ids(self, room_ids: list[int]) -> dict[int, set[int]]:
        return {rid: set(self._mic_blocks.get(rid, ())) for rid in room_ids}

    # ── Süreli kısıtlamalar ───────────────────────────────────────────────────
    def _set_timed(self, kind: str, room_id: int, user_id: int, seconds: float | None) -> None:
        if seconds is None:
            self._timed.pop((kind, room_id, user_id), None)
        else:
            self._timed[(kind, room_id, user_id)] = time.monotonic() + seconds

    def _remaining(self, kind: str, room_id: int, user_id: int) -> float:
        """Kalan süre (saniye). Süresi dolmuşsa kaydı temizler ve 0 döner."""
        until = self._timed.get((kind, room_id, user_id))
        if until is None:
            return 0
        remaining = until - time.monotonic()
        if remaining <= 0:
            del self._timed[(kind, room_id, user_id)]
            return 0
        return remaining

    async def ban_from_room(self, room_id: int, user_id: int, seconds: int) -> None:
        self._set_timed("ban", room_id, user_id, seconds)

    async def is_banned(self, room_id: int, user_id: int) -> bool:
        return self._remaining("ban", room_id, user_id) > 0

    async def mute_chat(self, room_id: int, user_id: int, seconds: int | None) -> None:
        self._set_timed("chat_mute", room_id, user_id, seconds)

    async def chat_mute_remaining(self, room_id: int, user_ids: list[int]) -> dict[int, int]:
        remaining = {uid: self._remaining("chat_mute", room_id, uid) for uid in user_ids}
        return {uid: math.ceil(seconds) for uid, seconds in remaining.items() if seconds > 0}

    async def grant_seat_invite(self, room_id: int, user_id: int, seconds: int) -> None:
        self._set_timed("seat_invite", room_id, user_id, seconds)

    async def consume_seat_invite(self, room_id: int, user_id: int) -> bool:
        if self._remaining("seat_invite", room_id, user_id) <= 0:
            return False
        del self._timed[("seat_invite", room_id, user_id)]
        return True

    # ── Son sohbet mesajları ──────────────────────────────────────────────────
    async def append_chat(self, room_id: int, message: dict) -> None:
        # deque(maxlen=...) dolunca en eski elemanı kendisi atar. Redis'te: RPUSH + LTRIM.
        self._chat.setdefault(room_id, deque(maxlen=CHAT_HISTORY_SIZE)).append(message)

    async def recent_chat(self, room_id: int) -> list[dict]:
        return list(self._chat.get(room_id, ()))

    async def remove_chat(self, room_id: int, message_id: str) -> dict | None:
        messages = self._chat.get(room_id, deque())
        for message in messages:
            if message["id"] == message_id:
                messages.remove(message)
                return message
        return None

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

    async def listener_ids(self, room_id: int) -> list[int]:
        # Sözlük eklenme sırasını korur: en son giren en sonda.
        return list(self._listeners.get(room_id, {}))

    async def is_in_room(self, room_id: int, user_id: int) -> bool:
        return user_id in self._listeners.get(room_id, {})

    async def room_ranks(self, room_ids: list[int]) -> dict[int, int]:
        # DEMO KISAYOLU: her çağrıda bütün odaları sıralıyoruz. Oda sayısı büyüyünce
        # pahalı olur; Redis'te bu iş sorted set ile (ZREVRANK) tek adımdır.
        ordered = sorted(self._seats, key=self._count, reverse=True)
        position = {rid: index + 1 for index, rid in enumerate(ordered)}
        return {rid: position.get(rid, len(ordered) + 1) for rid in room_ids}

    # ── Oda kapanınca ─────────────────────────────────────────────────────────
    async def drop_room(self, room_id: int) -> None:
        self._seats.pop(room_id, None)
        self._listeners.pop(room_id, None)
        self._mic_blocks.pop(room_id, None)
        self._chat.pop(room_id, None)
        self.demo_listener_base.pop(room_id, None)

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
