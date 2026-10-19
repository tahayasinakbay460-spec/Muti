"""
Uygulamanın giriş noktası. Parçaları birbirine bağlar; iş mantığı burada yazılmaz.

Çalıştırmak için (backend klasöründe):
    python -m app.main
API dokümanı: http://127.0.0.1:8000/docs

KLASÖR HARİTASI — bir istek içeri girince şu yolu izler:

    routers/   → isteği karşılar, girdiyi doğrular, servisi çağırır
    services/  → iş kuralları ("bakiye yetiyor mu", "koltuk boş mu")
    models/    → veritabanı tabloları
    schemas/   → API'ye giren/çıkan JSON kalıpları
    realtime/  → WebSocket, canlı oda durumu, odaya yayın
    core/      → herkesin kullandığı altyapı (ayarlar, veritabanı, güvenlik, hatalar)
    demo/      → örnek veri ve sabit içerik (canlıya çıkmadan kaldırılacak)
"""
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.errors import register_error_handlers
from app.core.logs import RequestLogMiddleware, setup_logging
from app import models  # noqa: F401  (tablolar SQLAlchemy'ye tanıtılsın diye import ediliyor)
from app.demo import seed
from app.realtime import room_socket, user_socket
from app.realtime.state import room_state
from app.routers import activities, auth, content, conversations, economy, engagement, rooms, social, store, users


setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Sunucu açılırken bir kez çalışır; `yield` sonrası kapanırken çalışır."""
    if settings.is_production:
        # Canlıda yanlış ayarla açılmaktansa hiç açılmamak daha güvenlidir.
        if settings.demo_mode:
            raise RuntimeError("DEMO_MODE canlı ortamda açık olamaz.")
        if "*" in settings.cors_origins:
            raise RuntimeError("CORS_ORIGINS canlı ortamda '*' olamaz.")
    else:
        # DEMO KISAYOLU: Tabloları otomatik oluştur. Canlıda şema değişiklikleri
        # migration aracıyla (Alembic) kontrollü yapılacak.
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    if settings.demo_mode:
        async with SessionLocal() as db:
            await seed.seed_database(db)
        await seed.seed_live_state(room_state)

    logger.info("Server started (environment=%s, demo_mode=%s)", settings.environment, settings.demo_mode)
    yield
    logger.info("Server stopping")
    await engine.dispose()   # veritabanı bağlantılarını düzgünce kapat


app = FastAPI(title="MUTI API", version="1.0.0", lifespan=lifespan)

register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=None if settings.is_production else settings.cors_lan_origin_regex,
    # Kimlik çerezle (cookie) değil Authorization başlığıyla taşındığı için False.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    # Tarayıcıdaki kod hata ekranında istek numarasını gösterebilsin.
    expose_headers=["X-Request-ID"],
)
# Her isteği kaydeder (core/logs.py). CORS'tan sonra eklendiği için dışta kalır: CORS'un
# reddettiği istekler de kayda geçer.
app.add_middleware(RequestLogMiddleware)

# Bütün HTTP uçları /api/v1 altında. İleride uyumsuz bir değişiklik gerekirse /api/v2
# açılır; eski mobil uygulama sürümleri /api/v1 ile çalışmaya devam eder.
api_v1 = APIRouter(prefix="/api/v1")
for module in (auth, users, rooms, activities, economy, store, engagement, conversations, social, content):
    api_v1.include_router(module.router)
app.include_router(api_v1)

# WebSocket: /ws/rooms/{room_id}
app.include_router(room_socket.router)
app.include_router(user_socket.router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    """Sunucu ayakta mı? Yük dengeleyici (load balancer) bu adresi yoklar."""
    return {"status": "ok"}


if __name__ == "__main__":
    # access_log=False: istek kayıtlarını uvicorn değil RequestLogMiddleware yazar (çift satır olmasın).
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, access_log=False)
