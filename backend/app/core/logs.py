"""
Kayıt (log) altyapısı.

LOG NEDİR, NEDEN TUTARIZ? Sunucu çalışırken olanların zaman damgalı kaydı. Bir kullanıcı
"hediye gönderemedim" dediğinde ya da gece 3'te sunucu hata verdiğinde, ne olduğunu ancak
kayıtlardan anlayabiliriz. Üç tür kayıt tutuyoruz:

  muti.access  → her HTTP isteği: yöntem, adres, sonuç kodu, süre, kim (kullanıcı id)
  muti.audit   → güvenlik ve para olayları: giriş denemesi, çalınmış token şüphesi,
                 şifre değişikliği, moderasyon, satın alma ("kim, ne zaman, ne yaptı")
  app.*        → kodun kendi kayıtları ve beklenmedik hatalar (tam hata dökümüyle)

İSTEK NUMARASI (request id): Her isteğe kısa bir numara verilir; yanıtın `X-Request-ID`
başlığında ve o isteğe ait bütün kayıtlarda aynı numara bulunur. Kullanıcı hata ekranındaki
numarayı söylerse o isteğin bütün izi tek aramayla bulunur.

ASLA KAYDA YAZILMAYANLAR: parola, access/refresh token, kart bilgisi. Kayıtlar çoğu zaman
şifrelerden daha geniş bir ekibe açıktır; sızarsa hesaplar ele geçirilmesin.

Biçim: geliştirmede okunabilir tek satır, canlıda (LOG_JSON=true) her satır bir JSON nesnesi;
log toplama servisleri (Grafana Loki, Datadog, hosting paneli) JSON'u alan alan süzebilir.
"""
import json
import logging
import re
import secrets
import sys
import time
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler

from app.core.config import settings

# Şu an işlenen isteğin numarası ve kullanıcısı. ContextVar her isteğe ayrı bir kopya tutar:
# aynı anda gelen yüzlerce istek birbirinin numarasını görmez.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)

access_logger = logging.getLogger("muti.access")
audit_logger = logging.getLogger("muti.audit")


def audit(event: str, *, log_level: int = logging.INFO, **fields) -> None:
    """
    Güvenlik/para olayı kaydı. `event` sabit bir ad (ör. "login_failed"), ayrıntılar `fields`.
    Örnek: audit("store_purchase", item_id=3, days=30, price=3000)
    """
    audit_logger.log(log_level, event, extra={"fields": fields})


_base_record_factory = logging.getLogRecordFactory()


def _record_with_context(*args, **kwargs) -> logging.LogRecord:
    """
    Her kayda, oluştuğu anda, o anki istek numarasını ve kullanıcıyı ekler. Kayıt nereye
    giderse gitsin (ekran, dosya, testlerdeki yakalayıcı) bu iki alan içinde olur.
    """
    record = _base_record_factory(*args, **kwargs)
    record.request_id = request_id_var.get()
    record.user_id = user_id_var.get()
    return record


logging.setLogRecordFactory(_record_with_context)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "user_id": getattr(record, "user_id", None),
            **getattr(record, "fields", {}),
        }
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """Geliştirme için: `12:04:31 INFO  muti.audit [a1b2c3] login_failed username=ali reason=bad_password`"""

    def format(self, record: logging.LogRecord) -> str:
        fields = " ".join(f"{key}={value}" for key, value in getattr(record, "fields", {}).items())
        user = getattr(record, "user_id", None)
        line = (
            f"{self.formatTime(record, '%H:%M:%S')} {record.levelname:<7} {record.name} "
            f"[{getattr(record, 'request_id', '-')}{f' u{user}' if user else ''}] {record.getMessage()} {fields}"
        ).rstrip()
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def setup_logging() -> None:
    """Uygulama açılırken bir kez çağrılır (app/main.py)."""
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    handlers[0].setFormatter(JsonFormatter() if settings.log_json else TextFormatter())
    if settings.log_file:
        # Dosya 10 MB'ı geçince yenisi açılır, en fazla 5 eski dosya saklanır: disk dolmaz.
        file_handler = RotatingFileHandler(settings.log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
        file_handler.setFormatter(JsonFormatter())
        handlers.append(file_handler)

    # Yalnızca kendi kayıtlarımızı (app.*, muti.*) yönetiyoruz; uvicorn kendi kayıtlarını kendisi basar.
    for name in ("app", "muti"):
        logger = logging.getLogger(name)
        logger.handlers = list(handlers)
        logger.setLevel(settings.log_level.upper())


# İstemcinin gönderdiği istek numarası yalnızca bu biçimdeyse kabul edilir; yoksa kayda
# satır sonu gibi karakterler sokup sahte kayıt satırı uydurulabilirdi (log injection).
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{8,64}")
# Yük dengeleyici bu adresi saniyede bir yoklar; kayıtları boğmasın.
_QUIET_PATHS = frozenset({"/health"})


class RequestLogMiddleware:
    """
    Her HTTP isteğine numara verir, süresini ölçer ve bitince tek satırlık erişim kaydı yazar.
    Beklenmedik bir hata olursa tam hata dökümünü kaydeder (kullanıcıya döküm gösterilmez,
    bkz. errors.py). WebSocket bağlantıları kendi kayıtlarını yazar (realtime/).

    Bu "saf ASGI" bir middleware: isteği aynı görev (task) içinde işler, böylece servislerde
    yazılan kayıtlar da aynı istek numarasını ve kullanıcıyı taşır.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else secrets.token_hex(8)
        # Hata handler'ı (errors.py) numarayı buradan okur.
        scope.setdefault("state", {})["request_id"] = request_id
        request_token = request_id_var.set(request_id)
        user_token = user_id_var.set(None)
        started = time.perf_counter()
        status = 500

        async def send_with_request_id(message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message["headers"] = [*message.get("headers", []), (b"x-request-id", request_id.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            logging.getLogger("app").exception("Unhandled error on %s %s", scope["method"], scope["path"])
            raise
        finally:
            if scope["path"] not in _QUIET_PATHS:
                # Adresin yalnızca yolu yazılır, sorgu (?...) yazılmaz: içinde kişisel veri olabilir.
                access_logger.log(
                    logging.WARNING if status >= 500 else logging.INFO,
                    "%s %s %s", scope["method"], scope["path"], status,
                    extra={"fields": {"duration_ms": round((time.perf_counter() - started) * 1000, 1)}},
                )
            request_id_var.reset(request_token)
            user_id_var.reset(user_token)
