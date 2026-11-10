"""
Dosya yükleme yardımcısı: isteğin gövdesini (body) sınırlı okur.

Yüklemeler form (multipart) değil, gövdenin kendisi dosyadır (sesli mesaj, fotoğraf); türü
`Content-Type` başlığındadır. Gövde parça parça okunur: sınırı aşan dosya belleğe tamamen
alınmadan reddedilir (yoksa biri 1 GB'lık istekle sunucunun belleğini doldurabilirdi).
"""
from fastapi import Request

from app.core.errors import AppError


async def read_limited_body(request: Request, max_bytes: int, too_large_message: str, code: str) -> bytes:
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > max_bytes:
            raise AppError(too_large_message, code=code)
    return bytes(data)
