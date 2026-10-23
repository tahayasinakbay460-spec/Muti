"""
Testlerin ortak hazırlığı.

Testler gerçek veritabanına (app.db) dokunmaz: her test çalıştırmasında geçici bir
klasörde tertemiz bir SQLite dosyası açılır, örnek veri ona yüklenir.

Çalıştırmak için (backend klasöründe):
    python -m pytest
"""
import os
import tempfile
from pathlib import Path

import pytest

# DİKKAT: Bu satırlar `app` import edilmeden ÖNCE çalışmalı; ayarlar import anında okunur.
_test_dir = Path(tempfile.mkdtemp(prefix="muti_tests_"))
# TEST_DATABASE_URL verilirse (CI'daki PostgreSQL işi) testler o veritabanında koşar.
os.environ["DATABASE_URL"] = (
    os.environ.get("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{(_test_dir / 'test.db').as_posix()}"
)
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256"
os.environ["ENVIRONMENT"] = "development"
os.environ["DEMO_MODE"] = "true"
# Geliştiricinin kendi .env ayarı (ör. VOICE_PROVIDER=agora) testleri değiştirmesin
os.environ["VOICE_PROVIDER"] = "mesh"
# Testler saniyede onlarca kez giriş yapar; hız sınırı ayrı testte (test_launch.py) denenir.
os.environ["AUTH_ATTEMPTS_PER_MINUTE"] = "100000"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

API = "/api/v1"


@pytest.fixture(scope="session")
def client():
    """Uygulamayı bir kez başlatır (tablolar + örnek veri) ve bütün testlere verir."""
    with TestClient(app) as test_client:
        yield test_client


def auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def muti(client) -> dict:
    """Örnek ana kullanıcı (12450 coin) olarak giriş yapar; Authorization başlığını döner."""
    response = client.post(f"{API}/auth/login", json={"username": "muti", "password": "demo1234"})
    assert response.status_code == 200, response.text
    return auth_headers(response.json())


@pytest.fixture
def guest(client) -> dict:
    """Her test için yepyeni bir misafir hesap (500 coin hoş geldin bonusu ile)."""
    response = client.post(f"{API}/auth/guest")
    assert response.status_code == 201, response.text
    return auth_headers(response.json())
