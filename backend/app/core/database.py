"""
Veritabanı bağlantısı.

Burada üç şey var:
  1. engine        → veritabanına açılan bağlantı havuzu (uygulama boyunca tek tane)
  2. SessionLocal  → her istek için kısa ömürlü bir "oturum" (session) üreten fabrika
  3. Base          → bütün tablo sınıflarının (modellerin) miras aldığı ana sınıf

Neden "async"? Sunucu bir sorgunun cevabını beklerken boş durmaz, o sırada başka
kullanıcıların isteklerine bakar. Yüksek eşzamanlı kullanımda fark burada oluşur.
"""
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Integer, MetaData, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

# pool_pre_ping: havuzdaki bağlantı kopmuşsa kullanmadan önce fark edip yeniler.
engine = create_async_engine(settings.database_url, pool_pre_ping=True)

# expire_on_commit=False: commit'ten sonra nesnelerin alanlarını okumaya devam
# edebilelim diye (yoksa her okuma gizlice yeni bir sorgu atmaya çalışır).
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

if _is_sqlite:
    # SQLite varsayılan olarak foreign key kurallarını uygulamaz; her bağlantıda açıyoruz.
    # WAL modu: biri yazarken diğerleri okuyabilsin. busy_timeout: kilitliyse 5 sn bekle.
    @event.listens_for(engine.sync_engine, "connect")
    def _configure_sqlite(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


class Base(DeclarativeBase):
    # Index ve kısıt (constraint) adlarının kalıbı. Adlar tahmin edilebilir olunca
    # ileride migration (Alembic) yazmak kolaylaşır.
    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


# Birincil anahtar (id) tipi. PostgreSQL'de BIGINT (milyarlarca satıra yeter),
# SQLite'ta otomatik artan id yalnızca INTEGER ile çalıştığı için orada INTEGER.
BigIntPk = BigInteger().with_variant(Integer, "sqlite")


def utcnow() -> datetime:
    """Şu anki zaman, her zaman UTC. Sunucunun saat dilimine bağlı kalmayız."""
    return datetime.now(timezone.utc)


async def get_db() -> AsyncIterator[AsyncSession]:
    """
    Her HTTP isteği için bir veritabanı oturumu açar, istek bitince kapatır.
    Router'larda `db: DbSession` yazınca FastAPI bu fonksiyonu kendisi çağırır.
    """
    async with SessionLocal() as session:
        yield session


async def sync_id_sequences(db: AsyncSession) -> None:
    """
    PostgreSQL'de otomatik id sayaçlarını (sequence) tablodaki en büyük id'ye getirir.

    Neden? Bir satıra id elle verilirse (ör. id=1 yönetici) sayaç bunu bilmez ve bir
    sonraki yeni satıra yine 1 vermeye çalışır → "bu id zaten var" hatası. SQLite bu
    sorunu yaşamaz (her zaman en büyük id + 1 verir), orada bir şey yapılmaz.
    """
    if db.bind.dialect.name != "postgresql":
        return
    for table in Base.metadata.sorted_tables:
        column = table.columns.get("id")
        if column is None or not column.primary_key or not isinstance(column.type, Integer):
            continue
        await db.execute(text(
            f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
            f"COALESCE((SELECT MAX(id) FROM {table.name}), 0) + 1, false)"
        ))
