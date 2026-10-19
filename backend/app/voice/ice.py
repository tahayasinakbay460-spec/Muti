"""
ICE sunucu listesi (STUN/TURN).

TURN kimlik bilgisi neden her seferinde üretiliyor?
TURN sunucusu ses trafiğini aktardığı için bant genişliği harcar; herkese açık bir
kullanıcı adı/parola verirsek başkaları da bedavaya kullanır. Bunun yerine açık kaynak
TURN sunucusu coturn'ün "use-auth-secret" yöntemini kullanıyoruz:
    kullanıcı adı = "<bitiş zamanı>:<kullanıcı id>"
    parola        = base64( HMAC-SHA1(TURN_SECRET, kullanıcı adı) )
coturn aynı gizli anahtarla parolayı kendisi hesaplar ve süresi geçmiş adları reddeder.
Böylece parola bir saat sonra işe yaramaz ve hiçbir yerde saklanmaz. Bu yöntem pek çok
hazır TURN hizmetinde de aynıdır; sağlayıcı değişse bile bu kod değişmez.
"""
import base64
import hashlib
import hmac
import time

from app.core.config import settings
from app.voice.base import IceServer


def turn_credentials(user_id: int, secret: str, ttl_seconds: int, now: float | None = None) -> tuple[str, str]:
    expires_at = int((now if now is not None else time.time()) + ttl_seconds)
    username = f"{expires_at}:{user_id}"
    digest = hmac.new(secret.encode(), username.encode(), hashlib.sha1).digest()
    return username, base64.b64encode(digest).decode()


def ice_servers_for(user_id: int) -> list[IceServer]:
    servers = []
    if settings.voice_stun_urls:
        servers.append(IceServer(urls=settings.voice_stun_urls))
    if settings.voice_turn_urls and settings.voice_turn_secret:
        username, credential = turn_credentials(
            user_id, settings.voice_turn_secret, settings.voice_turn_ttl_seconds,
        )
        servers.append(IceServer(urls=settings.voice_turn_urls, username=username, credential=credential))
    return servers
