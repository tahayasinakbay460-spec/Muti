"""
Zaman etiketleri ("3 gün önce", "21:05").

DEMO KISAYOLU: Bu etiketleri normalde istemci üretmelidir (kullanıcının kendi saat
dilimi ve diliyle). Web demo hazır etiket beklediği için şimdilik sunucu üretiyor.
API her zaman ham `created_at` alanını da döner; mobil uygulama onu kullanmalı.
"""
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.database import utcnow


def as_utc(value: datetime) -> datetime:
    """SQLite tarihleri saat dilimi bilgisi olmadan geri verir; onları UTC kabul ederiz."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _to_display(value: datetime) -> datetime:
    return as_utc(value) + timedelta(hours=settings.display_utc_offset_hours)


def days_since(value: datetime) -> int:
    return max(0, (utcnow() - as_utc(value)).days)


def time_ago_label(value: datetime) -> str:
    """Cüzdan geçmişi için: 'Az önce', '5 dk önce', 'Dün', '3 gün önce'..."""
    seconds = (utcnow() - as_utc(value)).total_seconds()
    if seconds < 60:
        return "Az önce"
    if seconds < 3600:
        return f"{int(seconds // 60)} dk önce"
    if seconds < 86400:
        return f"{int(seconds // 3600)} saat önce"
    days = int(seconds // 86400)
    if days == 1:
        return "Dün"
    if days < 7:
        return f"{days} gün önce"
    if days < 30:
        return f"{days // 7} hafta önce"
    return _to_display(value).strftime("%d.%m.%Y")


def clock_label(value: datetime) -> str:
    """Mesajlar için: bugünse '21:05', dünse 'Dün', daha eskiyse '14.09'."""
    shown = _to_display(value)
    today = _to_display(utcnow()).date()
    if shown.date() == today:
        return shown.strftime("%H:%M")
    if shown.date() == today - timedelta(days=1):
        return "Dün"
    return shown.strftime("%d.%m")
