"""
Uygulama ayarları.

Bütün ayarlar tek bir yerde (bu dosyada) durur. Değerler `backend/.env`
dosyasından veya ortam değişkenlerinden okunur; kodun içine şifre/anahtar yazılmaz.

Kullanımı:
    from app.core.config import settings
    settings.access_token_minutes
"""
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ klasörünün tam yolu (bu dosya backend/app/core/config.py içinde)
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # .env dosyasını nereden okuyacağını söylüyoruz. Tanımadığı satırları yok sayar.
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # "development" → geliştirme kolaylıkları açık (tabloları otomatik oluşturma gibi)
    # "production"  → canlı ortam, kolaylıklar kapalı
    environment: Literal["development", "production"] = "development"

    # ── Sunucu adresi ─────────────────────────────────────────────────────────
    # "127.0.0.1" → yalnızca bu bilgisayardan erişilir (en güvenlisi).
    # "0.0.0.0"   → aynı Wi-Fi'daki cihazlar da (ör. telefon) erişebilir.
    host: str = "127.0.0.1"
    port: int = 8000

    # ── Kimlik doğrulama ──────────────────────────────────────────────────────
    # JWT'leri imzalayan gizli anahtar. Varsayılanı YOK: .env'de yoksa uygulama açılmaz.
    secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    # Access token kısa ömürlüdür: çalınsa bile en fazla bu kadar dakika işe yarar.
    access_token_minutes: int = 15
    # Refresh token uzun ömürlüdür: mobil kullanıcı her gün yeniden giriş yapmasın diye.
    refresh_token_days: int = 30

    # ── Veritabanı ────────────────────────────────────────────────────────────
    # DEMO KISAYOLU: SQLite. Canlıda "postgresql+asyncpg://..." olacak.
    database_url: str = "sqlite+aiosqlite:///./app.db"

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Tarayıcıdan API'ye istek atmasına izin verilen adresler.
    cors_origins: list[str] = ["http://127.0.0.1:5500", "http://localhost:5500"]
    # DEMO KISAYOLU: Geliştirmede ev/ofis ağındaki adreslerden (192.168.x.x, 10.x.x.x,
    # 172.16-31.x.x) açılan frontend'e de izin verilir; telefondan denemek için.
    # Canlıda kullanılmaz (bkz. main.py).
    cors_lan_origin_regex: str = (
        r"^http://(192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}):5500$"
    )

    # ── Demo ──────────────────────────────────────────────────────────────────
    # true ise: açılışta örnek veri yüklenir ve coin satın alma ödeme doğrulaması
    # olmadan çalışır. Canlıda false olmak ZORUNDA.
    demo_mode: bool = True

    # ── Ekonomi ───────────────────────────────────────────────────────────────
    # Yeni kayıt olan kullanıcıya verilen hoş geldin coini.
    signup_bonus_coins: int = 500
    # Hediyenin coin değerinin yüzde kaçı alıcıya elmas (diamond) olarak geçer.
    gift_receiver_share_percent: int = Field(default=50, ge=0, le=100)
    # Yayıncı geliri: 1 elmas çevrilince kaç coin olur.
    diamond_to_coin_rate: int = Field(default=1, ge=1)
    # Elmasların gerçek paraya çevrilip çekilmesi. Ödeme altyapısı ve kimlik doğrulama
    # (KYC) olmadan açılmaz; şimdilik kapalı.
    withdrawals_enabled: bool = False
    # Şanslı hediyede alıcının payı. Gönderen coin geri kazanabildiği için normal hediyeden düşük.
    lucky_gift_receiver_share_percent: int = Field(default=10, ge=0, le=100)

    # ── Hazine sandığı (oda içi) ──────────────────────────────────────────────
    # Odada gönderilen hediyelerin coin toplamı bu sayıya ulaşınca sandık açılır.
    chest_target_coins: int = Field(default=10_000, ge=1)
    # Açılan sandıkta dağıtılan coin: hedefin yüzde kaçı.
    chest_reward_percent: int = Field(default=10, ge=0, le=100)
    # Sandık açık kalma süresi (saniye); süre dolunca kalan coin dağıtılmaz.
    chest_open_seconds: int = Field(default=60, ge=5)

    # ── Sesli görüşme (WebRTC) ────────────────────────────────────────────────
    # "mesh":    tarayıcılar birbirine doğrudan bağlanır, ek sunucu gerekmez (küçük odalar).
    # "livekit": açık kaynak medya sunucusu (SFU); kalabalık odalar için. Bkz. app/voice/.
    voice_provider: Literal["mesh", "livekit"] = "mesh"
    # STUN: tarayıcının dışarıdan nasıl göründüğünü öğrenmesi için. Varsayılan Google'ın
    # ücretsiz sunucusu; kendi coturn sunucumuz kurulunca onun adresi yazılır.
    voice_stun_urls: list[str] = ["stun:stun.l.google.com:19302"]
    # TURN: doğrudan bağlantı kurulamayan ağlar için ses aktarıcı (ör. coturn).
    # Örnek: ["turn:turn.ornek.com:3478?transport=udp", "turns:turn.ornek.com:5349"]
    voice_turn_urls: list[str] = []
    # coturn'deki "static-auth-secret" ile aynı olmalı. Boşsa TURN kullanılmaz.
    voice_turn_secret: str = ""
    voice_turn_ttl_seconds: int = 3600
    # Yalnızca VOICE_PROVIDER=livekit iken: wss://ses.ornek.com ve API anahtar çifti.
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # ── Görüntüleme ───────────────────────────────────────────────────────────
    # DEMO KISAYOLU: "21:05" gibi saat etiketlerini sunucu üretiyor (Türkiye = UTC+3).
    # Mobil uygulamada istemci `created_at` alanını kendi saat dilimine çevirmeli.
    display_utc_offset_hours: int = 3

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
