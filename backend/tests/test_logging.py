"""
Kayıt (log) testleri: istek numarası, erişim kaydı, güvenlik kayıtları, beklenmedik hata.
"""
import logging

import pytest
from fastapi.testclient import TestClient

from tests.conftest import API
from tests.test_api import new_guest


@pytest.fixture
def logs(caplog):
    caplog.set_level(logging.INFO, logger="muti")
    caplog.set_level(logging.INFO, logger="app")
    return caplog


def records(caplog, logger: str, message: str | None = None) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == logger and (message is None or r.getMessage() == message)]


def test_every_response_has_request_id_and_is_logged(client, logs):
    user = new_guest(client)
    response = client.get(f"{API}/users/me", headers=user)
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) >= 8

    access = [r for r in records(logs, "muti.access") if r.request_id == request_id]
    assert len(access) == 1
    assert access[0].getMessage() == "GET /api/v1/users/me 200"
    assert access[0].user_id == response.json()["id"] and access[0].fields["duration_ms"] >= 0

    # Uygun biçimdeki numara korunur (istemci kendi kaydıyla eşleştirebilsin), bozuk olan değiştirilir.
    assert client.get("/health", headers={"X-Request-ID": "mobile-abc12345"}).headers["X-Request-ID"] == "mobile-abc12345"
    # Boşluk ve işaret içeren değer (kayda sahte alan sokma denemesi) kabul edilmez.
    injected = client.get("/health", headers={"X-Request-ID": "fake level=ERROR user=admin"}).headers["X-Request-ID"]
    assert " " not in injected and "admin" not in injected


def test_failed_login_is_audited_without_password(client, logs):
    client.post(f"{API}/auth/login", json={"username": "muti", "password": "YanlisParola123"})
    client.post(f"{API}/auth/login", json={"username": "olmayan_kisi", "password": "YanlisParola123"})

    failed = records(logs, "muti.audit", "login_failed")
    assert [(r.fields["username"], r.fields["reason"]) for r in failed[-2:]] == [
        ("muti", "bad_password"), ("olmayan_kisi", "unknown_user"),
    ]
    assert all(r.levelno == logging.WARNING for r in failed)
    # Denenen parola hiçbir kayıtta geçmez.
    assert not any("YanlisParola123" in (r.getMessage() + str(getattr(r, "fields", ""))) for r in logs.records)


def test_money_and_moderation_events_are_audited(client, logs):
    user = new_guest(client)
    client.post(f"{API}/wallet/purchase", headers=user, json={"package_id": 1})
    client.post(f"{API}/store/items/1/purchase", headers=user, json={"days": 7})
    room = client.post(f"{API}/rooms", headers=user, json={"title": "Kayıt Odası"}).json()
    client.delete(f"{API}/rooms/{room['id']}", headers=user)

    events = [r.getMessage() for r in records(logs, "muti.audit")]
    for expected in ("guest_created", "coins_purchased", "store_purchase", "room_closed"):
        assert expected in events
    purchase = records(logs, "muti.audit", "store_purchase")[-1]
    assert purchase.fields == {"item_id": 1, "days": 7, "price": 300}


def test_unexpected_error_hides_details_and_logs_traceback(client, logs, monkeypatch):
    from app.main import app
    from app.services import user_service

    async def broken(*_args, **_kwargs):
        raise RuntimeError("veritabanı şifresi: gizli")

    monkeypatch.setattr(user_service, "list_suggested", broken)
    # raise_server_exceptions=False: hatayı teste fırlatma, kullanıcının göreceği cevabı döndür.
    safe_client = TestClient(app, raise_server_exceptions=False)
    response = safe_client.get(f"{API}/users/suggested", headers=new_guest(client))

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "internal_error" and body["request_id"] == response.headers["X-Request-ID"]
    assert "gizli" not in response.text   # iç ayrıntı kullanıcıya sızmaz

    errors = [r for r in records(logs, "app") if r.levelno == logging.ERROR]
    assert errors and errors[-1].exc_info and errors[-1].request_id == body["request_id"]
