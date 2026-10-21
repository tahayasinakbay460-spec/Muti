"""
Alembic: veritabanı şemasının "değişiklik defteri".

Her şema değişikliği (yeni tablo, yeni kolon...) `migrations/versions/` altında numaralı
bir dosyadır. `alembic upgrade head` veritabanına henüz uygulanmamış dosyaları sırayla
uygular; veriler silinmez. Canlıda sunucu her açılışta önce bunu çalıştırır (Dockerfile).

Model değiştirince yeni dosya üretmek için (backend klasöründe):
    alembic revision --autogenerate -m "add user phone"
Üretilen dosya mutlaka okunur: Alembic her değişikliği doğru tahmin edemez (ör. kolon adı değişimi).
"""
import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app import models  # noqa: F401  (tablolar Base.metadata'ya kaydolsun)
from app.core.config import settings
from app.core.database import Base

target_metadata = Base.metadata


def _configure(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite kolon değiştirmeyi doğrudan desteklemez; "batch" modu tabloyu yeniden kurar.
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run() -> None:
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as connection:
        await connection.run_sync(_configure)
    await engine.dispose()


asyncio.run(_run())
