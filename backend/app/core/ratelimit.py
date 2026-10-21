"""
Hız sınırı (rate limit): aynı yerden kısa sürede çok fazla istek gelirse durdurur.

Neden gerekli? Giriş ucu herkese açık. Sınır olmazsa bir saldırgan saniyede yüzlerce
parola dener ya da binlerce sahte hesap açar.

Yöntem "kayan pencere" (sliding window): her IP adresi için son 60 saniyedeki
denemelerin zamanını tutarız; sayı sınırı aşarsa 429 (Too Many Requests) döneriz.

DEMO KISAYOLU: Sayaçlar sunucu belleğinde (tek süreç). Birden fazla sunucuya çıkınca
Redis'e taşınır (aynı arayüz: `hit(key)`), yoksa her sunucu ayrı sayar.
"""
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import settings
from app.core.errors import AppError
from app.core.logs import audit


class TooManyRequestsError(AppError):
    status_code = 429
    code = "too_many_requests"


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str) -> bool:
        """Denemeyi sayar. Sınır aşıldıysa False döner (o deneme sayılmaz)."""
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        # Bellek şişmesin: arada bir, süresi tamamen dolmuş anahtarları temizle.
        if len(self._hits) > 10_000:
            for stale in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
                del self._hits[stale]
        return True

    def reset(self) -> None:
        self._hits.clear()


auth_limiter = SlidingWindowLimiter(settings.auth_attempts_per_minute)


def client_ip(request: Request) -> str:
    # Sunucu bir vekil (proxy, ör. Railway) arkasındaysa gerçek adresi uvicorn
    # `--proxy-headers` ile X-Forwarded-For başlığından alıp buraya koyar.
    return request.client.host if request.client else "unknown"


async def limit_auth_attempts(request: Request) -> None:
    """Giriş/kayıt/misafir uçlarına bağlanan bağımlılık (dependency)."""
    ip = client_ip(request)
    if not auth_limiter.hit(ip):
        audit("rate_limited", ip=ip, path=request.url.path)
        raise TooManyRequestsError("Çok fazla deneme yaptın. Bir dakika sonra tekrar dene.")
