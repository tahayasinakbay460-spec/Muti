import logging

from app.services import diagnostics_service

REPORT = {"room_id": 5, "provider": "agora", "event": "mic_failed", "detail": "create_track NotAllowedError"}


def voice_records(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.getMessage() == "voice_client_event"]


def test_voice_event_is_written_to_server_log(client, guest, caplog):
    caplog.set_level(logging.INFO, logger="app")
    response = client.post(
        "/api/v1/diagnostics/voice", json=REPORT,
        headers={**guest, "User-Agent": "test-browser"},
    )
    assert response.status_code == 204
    fields = voice_records(caplog)[-1].fields
    assert fields["event"] == "mic_failed"
    assert fields["detail"] == REPORT["detail"]
    assert fields["user_agent"] == "test-browser"


def test_mic_flow_events_are_accepted(client, guest):
    for event in ("mic_published", "mic_flowing", "mic_silent"):
        body = {**REPORT, "event": event}
        assert client.post("/api/v1/diagnostics/voice", json=body, headers=guest).status_code == 204


def test_voice_event_requires_login(client):
    assert client.post("/api/v1/diagnostics/voice", json=REPORT).status_code == 401


def test_unknown_voice_event_is_rejected(client, guest):
    body = {**REPORT, "event": "anything"}
    assert client.post("/api/v1/diagnostics/voice", json=body, headers=guest).status_code == 422


def test_one_user_cannot_flood_the_log(client, guest, caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="app")
    monkeypatch.setattr(diagnostics_service, "EVENTS_PER_MINUTE", 2)
    monkeypatch.setattr(diagnostics_service, "_limiters", {})
    for _ in range(4):
        response = client.post("/api/v1/diagnostics/voice", json=REPORT, headers=guest)
        assert response.status_code == 204
    assert len(voice_records(caplog)) == 2
