"""
Canlıya çıkış ayarlarının testleri: hız sınırı, açık beta satın alma, yöneticinin
ortam değişkeninden oluşturulması, mesaj okuma kapısı, sayfa dosyalarının önbellek başlığı.
"""
import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import ratelimit
from app.core.config import Settings, settings
from app.core.database import SessionLocal
from app.main import NoCacheStaticFiles
from app.services import auth_service
from tests.conftest import API
from tests.test_admin import admin  # noqa: F401  (fixture)


def test_auth_attempts_are_rate_limited(client, monkeypatch):
    monkeypatch.setattr(ratelimit.auth_limiter, "limit", 3)
    ratelimit.auth_limiter.reset()
    try:
        wrong = {"username": "muti", "password": "yanlis-parola"}
        codes = [client.post(f"{API}/auth/login", json=wrong).status_code for _ in range(4)]
        assert codes == [401, 401, 401, 429]
        # Sınır IP başına: misafir girişi de aynı sayaçtan düşer.
        blocked = client.post(f"{API}/auth/guest")
        assert blocked.status_code == 429 and blocked.json()["code"] == "too_many_requests"
    finally:
        ratelimit.auth_limiter.reset()


def test_sliding_window_forgets_old_attempts(monkeypatch):
    limiter = ratelimit.SlidingWindowLimiter(limit=2, window_seconds=60)
    now = [1000.0]
    monkeypatch.setattr(ratelimit.time, "monotonic", lambda: now[0])
    assert limiter.hit("ip") and limiter.hit("ip") and not limiter.hit("ip")
    assert limiter.hit("other-ip")        # başka adres etkilenmez
    now[0] += 61                          # pencere kaydı, eski denemeler düştü
    assert limiter.hit("ip")


def test_free_coin_purchase_works_without_demo_mode(client, guest, monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", False)
    closed = client.post(f"{API}/wallet/purchase", headers=guest, json={"package_id": 1})
    assert closed.status_code == 503 and closed.json()["code"] == "purchases_unavailable"

    monkeypatch.setattr(settings, "free_coin_purchase", True)
    bought = client.post(f"{API}/wallet/purchase", headers=guest, json={"package_id": 1})
    assert bought.status_code == 200 and bought.json()["added"] > 0


def test_admin_account_is_created_from_env(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_username", "Kurucu")
    monkeypatch.setattr(settings, "admin_password", "cok-gizli-parola-123")

    async def run():
        async with SessionLocal() as db:
            await auth_service.ensure_admin_account(db)
            await auth_service.ensure_admin_account(db)   # ikinci açılışta tekrar oluşturmaz

    asyncio.run(run())
    login = client.post(f"{API}/auth/login", json={"username": "kurucu", "password": "cok-gizli-parola-123"})
    assert login.status_code == 200 and login.json()["user"]["is_admin"] is True


def test_admin_message_reading_can_be_disabled(client, admin, monkeypatch):  # noqa: F811
    assert client.get(f"{API}/admin/conversations", headers=admin).status_code == 200
    monkeypatch.setattr(settings, "admin_can_read_messages", False)
    for path in ("/admin/conversations", "/admin/conversations/1/messages", "/admin/rooms/1/messages"):
        denied = client.get(f"{API}{path}", headers=admin)
        assert denied.status_code == 403 and denied.json()["code"] == "message_access_disabled"


@pytest.mark.parametrize("given, expected", [
    ("postgresql://u:p@host:5432/db", "postgresql+asyncpg://u:p@host:5432/db"),
    ("postgres://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
    ("postgresql+asyncpg://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
    ("sqlite+aiosqlite:///./app.db", "sqlite+aiosqlite:///./app.db"),
])
def test_database_url_gets_async_driver(given, expected):
    assert Settings(secret_key="x" * 32, database_url=given).database_url == expected


def test_frontend_files_are_served_without_stale_cache(tmp_path):
    (tmp_path / "index.html").write_text("<h1>Muti</h1>", encoding="utf-8")
    site = FastAPI()
    site.mount("/", NoCacheStaticFiles(directory=tmp_path, html=True))
    with TestClient(site) as browser:
        page = browser.get("/")
        assert page.status_code == 200 and "Muti" in page.text
        assert page.headers["cache-control"] == "no-cache"
        # Dosya değişmediyse tarayıcı kısa "304 değişmedi" cevabı alır.
        again = browser.get("/", headers={"If-None-Match": page.headers["etag"]})
        assert again.status_code == 304
