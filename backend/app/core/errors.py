"""
Hata yönetimi.

Kural: API her hatada aynı biçimde JSON döner:
    { "code": "insufficient_balance", "detail": "Coin bakiyen yetersiz." }

  - code   → istemcinin (web/mobil) kod içinde kontrol ettiği sabit, İngilizce anahtar
  - detail → kullanıcıya gösterilebilecek Türkçe mesaj

Servisler `raise NotFoundError("Oda bulunamadı.")` gibi bir hata fırlatır,
aşağıdaki handler'lar bunu yukarıdaki JSON'a çevirir.
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Bizim bilerek fırlattığımız bütün hataların atası."""

    status_code = 400
    code = "bad_request"

    def __init__(self, detail: str, code: str | None = None):
        super().__init__(detail)
        self.detail = detail
        if code:
            self.code = code


class UnauthorizedError(AppError):
    """Kimlik yok ya da geçersiz (giriş yapılmamış, token bozuk/süresi dolmuş)."""
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    """Kimlik belli ama bu işlemi yapmaya yetkisi yok."""
    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    """İstek geçerli ama mevcut durumla çakışıyor (koltuk dolu, kullanıcı adı alınmış...)."""
    status_code = 409
    code = "conflict"


class InsufficientBalanceError(AppError):
    status_code = 402
    code = "insufficient_balance"

    def __init__(self):
        super().__init__("Coin bakiyen yetersiz.")


class UnavailableError(AppError):
    """Özellik bu ortamda kapalı (ör. canlıda ödeme doğrulaması olmadan satın alma)."""
    status_code = 503
    code = "unavailable"


def register_error_handlers(app: FastAPI) -> None:
    """main.py bu fonksiyonu bir kez çağırır; handler'lar uygulamaya bağlanır."""

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, error: AppError):
        return JSONResponse({"code": error.code, "detail": error.detail}, status_code=error.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_request: Request, error: RequestValidationError):
        # Gönderilen JSON şemaya uymuyorsa (eksik alan, kısa şifre...) buraya düşer.
        # `errors` listesi geliştirici içindir; kullanıcıya `detail` gösterilir.
        errors = [
            {"field": ".".join(str(part) for part in e["loc"][1:]), "message": e["msg"]}
            for e in error.errors()
        ]
        field = errors[0]["field"] if errors else ""
        detail = f"Geçersiz veya eksik alan: {field}" if field else "Gönderilen bilgiler geçersiz."
        return JSONResponse({"code": "validation_error", "detail": detail, "errors": errors}, status_code=422)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, _error: Exception):
        # Koddaki bir hata (bug). Ayrıntılı döküm kayda yazıldı (core/logs.py); kullanıcıya
        # yalnızca destek için istek numarası verilir, iç ayrıntı (dosya yolu, SQL) sızdırılmaz.
        request_id = getattr(request.state, "request_id", "-")
        return JSONResponse(
            {"code": "internal_error", "detail": f"Beklenmedik bir hata oluştu. Destek numarası: {request_id}",
             "request_id": request_id},
            status_code=500, headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_request: Request, error: StarletteHTTPException):
        # FastAPI'nin kendi ürettiği hatalar (olmayan adres → 404 gibi) da aynı biçimde dönsün.
        codes = {404: "not_found", 405: "method_not_allowed"}
        return JSONResponse(
            {"code": codes.get(error.status_code, "request_failed"), "detail": str(error.detail)},
            status_code=error.status_code,
        )
