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
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(_test_dir / 'test.db').as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256"
os.environ["ENVIRONMENT"] = "development"
os.environ["DEMO_MODE"] = "true"

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
