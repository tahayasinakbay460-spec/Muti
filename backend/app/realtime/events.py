"""
WebSocket olay (event) adları ve istemciden gelen verilerin şemaları.

Adlar `alan:eylem` biçimindedir ve frontend'deki js/realtime.js ile birebir aynıdır.
Adları kodun içine elle yazmak yerine buradaki sabitleri kullanırız; böylece yazım
hatası olursa program daha çalışmadan fark edilir.
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ── Sunucudan istemciye giden olaylar ─────────────────────────────────────────
CHAT_MESSAGE = "chat:message"                  # { id, user, text, created_at }
CHAT_HISTORY = "chat:history"                  # { messages: [...] }  (yalnızca odaya yeni girene)
CHAT_MESSAGE_DELETED = "chat:message_deleted"  # { message_id }
GIFT_SENT = "gift:sent"                        # { sender, receiver, gift, quantity, lucky_win, lucky_multiplier }
GAME_DICE_ROLLED = "game:dice_rolled"          # { user, values: [zar1, zar2] }
GAME_ROULETTE_STARTED = "game:roulette_started"      # { round_id, started_by, betting_seconds }
GAME_ROULETTE_BET_PLACED = "game:roulette_bet_placed"  # { round_id, user, color }
GAME_ROULETTE_RESULT = "game:roulette_result"        # { round_id, number, color, winners, player_count }
ROOM_USER_JOINED = "room:user_joined"          # { user }
ROOM_LISTENER_COUNT = "room:listener_count"    # { listener_count }
ROOM_SEATS_UPDATED = "room:seats_updated"      # { seats: [...] }
ROOM_USER_LEFT = "room:user_left"              # { user_id }  (kişinin odada hiç bağlantısı kalmadı)
ROOM_ROLES_UPDATED = "room:roles_updated"      # { admin_ids: [...], vip_ids: [...] }
ROOM_USER_KICKED = "room:user_kicked"          # { user }  (atılan kişinin bağlantısı ardından kapanır)
ROOM_CHAT_MUTED = "room:chat_muted"            # { user, seconds }  (seconds 0 → susturma kaldırıldı)
ROOM_SEAT_INVITE = "room:seat_invite"          # { by, expires_in }  (yalnızca davet edilene)
ROOM_UPDATED = "room:updated"                  # { title, category, cover_url, announcement, free_seating }
ROOM_CLOSED = "room:closed"                    # {}  (ardından herkesin bağlantısı kapanır)
ROOM_CHEST_UPDATED = "room:chest_updated"      # { chest }  (hazine sandığı doldu/açıldı/kapandı)
ROOM_CHEST_CLAIMED = "room:chest_claimed"      # { user, coins, coins_left }
ERROR = "error"                                # { code, detail }  (yalnızca hatayı yapan kişiye)

# Kişiye özel kanal (/ws/me)
MESSAGE_NEW = "message:new"                    # { conversation_id, sender, message }
NOTIFICATION_NEW = "notification:new"          # { id, type, text, actor, data, ... }  (bkz. notification_service)
PING = "ping"                                  # istemci → sunucu: "hâlâ buradayım" (çevrimiçi durumu)

# ── WebSocket kapanış kodları ─────────────────────────────────────────────────
# 4000-4999 arası uygulamalara ayrılmıştır. İstemci koda bakıp ne yapacağına karar verir.
CLOSE_UNAUTHORIZED = 4401    # token yok/geçersiz → token yenile ya da giriş yap
CLOSE_BANNED = 4403          # odadan atıldı, yasak süresi dolmadı → odaya girme
CLOSE_ROOM_NOT_FOUND = 4404  # oda yok ya da kapatılmış (oda sahibi odayı kapatınca da bu kod)

# Sesli görüşme (yalnızca mesh sağlayıcıda; bkz. app/voice/mesh.py).
# İstemci → sunucu: { to, description?, candidate? }   Sunucu → alıcı: { from, description?, candidate? }
VOICE_SIGNAL = "voice:signal"

# "Kim konuşuyor" göstergesi sunucudan gelmez: her istemci duyduğu sesin şiddetinden kendisi hesaplar.


# ── İstemciden sunucuya gelen olaylar (yukarıdakilerden farklı olanlar) ────────
GAME_ROULETTE_START = "game:roulette_start"    # {}  → turu başlat
GAME_ROULETTE_BET = "game:roulette_bet"        # { color: "red" | "black" | "green" }


# ── İstemciden sunucuya gelen veriler ─────────────────────────────────────────

class ChatMessageIn(BaseModel):
    """
    İstemci sohbet mesajı gönderirken yalnızca `text` alanına bakarız.
    İstemci `user` alanı da gönderse yok sayılır: kimin yazdığını token'dan biz biliriz.
    Yoksa herkes başkasının adına mesaj yazabilirdi.
    """
    text: str = Field(min_length=1, max_length=300)

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class SessionDescription(BaseModel):
    """WebRTC teklif/cevabı (SDP): "şu ses biçimlerini destekliyorum" yazısı."""
    type: Literal["offer", "answer"]
    sdp: str = Field(max_length=12000)


class IceCandidate(BaseModel):
    """WebRTC ağ adresi adayı: "bana şu adresten ulaşabilirsin"."""
    candidate: str = Field(max_length=500)
    sdpMid: str | None = Field(default=None, max_length=32)
    sdpMLineIndex: int | None = Field(default=None, ge=0, le=16)
    usernameFragment: str | None = Field(default=None, max_length=64)


class VoiceSignalIn(BaseModel):
    """
    Bir tarayıcının diğerine iletilmesini istediği bağlantı mesajı. Sunucu içeriğe
    karışmaz; yalnızca biçimini ve "bu iki kişi bağlanabilir mi" kuralını kontrol eder.
    """
    to: int
    description: SessionDescription | None = None
    candidate: IceCandidate | None = None
