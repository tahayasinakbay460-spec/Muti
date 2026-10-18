"""
WebSocket olay (event) adları ve istemciden gelen verilerin şemaları.

Adlar `alan:eylem` biçimindedir ve frontend'deki js/realtime.js ile birebir aynıdır.
Adları kodun içine elle yazmak yerine buradaki sabitleri kullanırız; böylece yazım
hatası olursa program daha çalışmadan fark edilir.
"""
from pydantic import BaseModel, Field, field_validator

# ── Sunucudan istemciye giden olaylar ─────────────────────────────────────────
CHAT_MESSAGE = "chat:message"                  # { user, text }
GIFT_SENT = "gift:sent"                        # { sender, receiver, gift, quantity }
GAME_DICE_ROLLED = "game:dice_rolled"          # { user, values: [zar1, zar2] }
GAME_ROULETTE_STARTED = "game:roulette_started"      # { round_id, started_by, betting_seconds }
GAME_ROULETTE_BET_PLACED = "game:roulette_bet_placed"  # { round_id, user, color }
GAME_ROULETTE_RESULT = "game:roulette_result"        # { round_id, number, color, winners, player_count }
ROOM_USER_JOINED = "room:user_joined"          # { user }
ROOM_LISTENER_COUNT = "room:listener_count"    # { listener_count }
ROOM_SEATS_UPDATED = "room:seats_updated"      # { seats: [...] }
ROOM_ROLES_UPDATED = "room:roles_updated"      # { admin_ids: [...] }
ROOM_USER_KICKED = "room:user_kicked"          # { user }  (atılan kişinin bağlantısı ardından kapanır)
ERROR = "error"                                # { code, detail }  (yalnızca hatayı yapan kişiye)

# Kişiye özel kanal (/ws/me)
MESSAGE_NEW = "message:new"                    # { conversation_id, sender, message }
PING = "ping"                                  # istemci → sunucu: "hâlâ buradayım" (çevrimiçi durumu)

# ── WebSocket kapanış kodları ─────────────────────────────────────────────────
# 4000-4999 arası uygulamalara ayrılmıştır. İstemci koda bakıp ne yapacağına karar verir.
CLOSE_UNAUTHORIZED = 4401    # token yok/geçersiz → token yenile ya da giriş yap
CLOSE_BANNED = 4403          # odadan atıldı, yasak süresi dolmadı → odaya girme
CLOSE_ROOM_NOT_FOUND = 4404  # oda yok ya da kapatılmış

# room:speaking (kim konuşuyor) henüz yok: gerçek ses (WebRTC) eklenince gelecek.


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
