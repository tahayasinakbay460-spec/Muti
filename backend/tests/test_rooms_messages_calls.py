"""
Odalar (ülke, canlı, son girilenler), sohbet mesaj türleri (sesli mesaj, hediye) ve ücretli birebir arama testleri.
"""
from app.core.config import settings
from app.services import call_service
from tests.conftest import API, auth_headers
from tests.test_api import me, new_guest, receive_until, wait_until_registered


def token_of(headers: dict) -> str:
    return headers["Authorization"].removeprefix("Bearer ")


def open_chat(client, headers, other_id) -> int:
    return client.post(f"{API}/conversations", headers=headers, json={"user_id": other_id}).json()["id"]


def coins(client, headers) -> int:
    return me(client, headers)["coin_balance"]


# ── Odalar ────────────────────────────────────────────────────────────────────

def test_country_on_register_profile_and_room_filter(client, muti):
    response = client.post(f"{API}/auth/register", json={
        "username": "ulkeli_uye", "email": "ulkeli@example.com", "password": "gizli123", "country": "de",
    })
    assert response.status_code == 201, response.text
    headers = auth_headers(response.json())
    assert me(client, headers)["country"] == "DE"
    assert client.patch(f"{API}/users/me", headers=headers, json={"country": "tr"}).json()["country"] == "TR"
    assert client.patch(f"{API}/users/me", headers=headers, json={"country": "TUR"}).status_code == 422

    countries = {c["country"]: c["room_count"] for c in client.get(f"{API}/rooms/countries", headers=muti).json()}
    assert countries["TR"] >= 1 and countries["DE"] >= 1 and countries["AZ"] >= 1
    german = client.get(f"{API}/rooms", headers=muti, params={"country": "de"}).json()
    assert german and all(r["host"]["country"] == "DE" for r in german)
    assert client.get(f"{API}/rooms", headers=muti, params={"country": "XYZ"}).status_code == 422


def test_live_tab_lists_only_rooms_with_someone_on_mic(client, guest):
    room = client.post(f"{API}/rooms", headers=guest, json={"title": "Canlı deneme"}).json()
    live_ids = lambda: {r["id"] for r in client.get(f"{API}/rooms", headers=guest, params={"category": "live", "limit": 50}).json()}  # noqa: E731
    assert room["id"] in live_ids()          # açan kişi ilk koltuğa oturdu
    client.delete(f"{API}/rooms/{room['id']}/seats/me", headers=guest)
    assert room["id"] not in live_ids()      # mikrofonda kimse kalmadı


def test_recent_rooms_after_joining(client, guest):
    with client.websocket_connect(f"/ws/rooms/107340?token={token_of(guest)}") as socket:
        receive_until(socket, "chat:history")
    recent = client.get(f"{API}/rooms/recent", headers=guest).json()
    assert recent[0]["id"] == 107340


# ── Sesli mesaj ve sohbette hediye ────────────────────────────────────────────

def test_voice_message_upload_and_private_download(client, guest):
    other, stranger = new_guest(client), new_guest(client)
    chat_id = open_chat(client, guest, me(client, other)["id"])
    audio = b"\x1aE\xdf\xa3" + b"0" * 2000   # webm başlığıyla başlayan sahte ses

    sent = client.post(
        f"{API}/conversations/{chat_id}/voice", headers={**guest, "Content-Type": "audio/webm;codecs=opus"},
        params={"duration": 4}, content=audio,
    )
    assert sent.status_code == 201, sent.text
    message = sent.json()
    assert message["kind"] == "voice" and message["duration_seconds"] == 4 and message["media_url"]

    for headers in (guest, other):
        file = client.get(f"{API}{message['media_url']}", headers=headers)
        assert file.status_code == 200 and file.content == audio
        assert file.headers["content-type"].startswith("audio/webm")
    # Sohbette olmayan kişi dosyayı alamaz
    assert client.get(f"{API}{message['media_url']}", headers=stranger).status_code == 404
    # Sohbet listesinde önizleme
    summary = next(c for c in client.get(f"{API}/conversations", headers=other).json() if c["id"] == chat_id)
    assert summary["last_message"]["text"] == "🎤 Sesli mesaj"

    bad_type = client.post(f"{API}/conversations/{chat_id}/voice", headers={**guest, "Content-Type": "text/plain"},
                           params={"duration": 4}, content=audio)
    assert bad_type.json()["code"] == "unsupported_audio"
    too_long = client.post(f"{API}/conversations/{chat_id}/voice", headers={**guest, "Content-Type": "audio/webm"},
                           params={"duration": settings.voice_message_max_seconds + 1}, content=audio)
    assert too_long.json()["code"] == "audio_too_long"
    too_big = client.post(f"{API}/conversations/{chat_id}/voice", headers={**guest, "Content-Type": "audio/webm"},
                          params={"duration": 4}, content=b"0" * (settings.voice_message_max_bytes + 1))
    assert too_big.json()["code"] == "audio_too_large"


def test_gift_in_conversation_is_paid_once_and_shown_in_chat(client, guest):
    other = new_guest(client)
    other_id = me(client, other)["id"]
    chat_id = open_chat(client, guest, other_id)
    gift = min(client.get(f"{API}/gifts", headers=guest).json(), key=lambda g: g["price"])
    before = coins(client, guest)
    headers = {**guest, "Idempotency-Key": "dm-gift-key-1"}

    first = client.post(f"{API}/conversations/{chat_id}/gift", headers=headers, json={"gift_id": gift["id"], "quantity": 2})
    assert first.status_code == 200, first.text
    assert first.json()["message"]["kind"] == "gift" and first.json()["message"]["gift"]["id"] == gift["id"]
    # Aynı anahtar ikinci kez: para da mesaj da tekrarlanmaz
    again = client.post(f"{API}/conversations/{chat_id}/gift", headers=headers, json={"gift_id": gift["id"], "quantity": 2})
    assert again.status_code == 200 and again.json()["message"] is None

    assert coins(client, guest) == before - gift["price"] * 2 + first.json()["lucky_win"]
    messages = client.get(f"{API}/conversations/{chat_id}", headers=other).json()["messages"]
    assert [m["kind"] for m in messages] == ["gift"]
    assert messages[0]["quantity"] == 2 and not messages[0]["from_me"]


# ── Arama ─────────────────────────────────────────────────────────────────────

def test_call_needs_callee_online_and_enough_coins(client, guest, monkeypatch):
    other = new_guest(client)
    other_id = me(client, other)["id"]
    offline = client.post(f"{API}/calls", headers=guest, json={"callee_id": other_id, "kind": "voice"})
    assert offline.json()["code"] == "callee_offline"
    monkeypatch.setattr(settings, "call_voice_price_per_minute", 100_000)
    with client.websocket_connect(f"/ws/me?token={token_of(other)}") as socket:
        wait_until_registered(socket)
        poor = client.post(f"{API}/calls", headers=guest, json={"callee_id": other_id, "kind": "voice"})
        assert poor.status_code == 402
    assert client.get(f"{API}/calls/prices", headers=guest).json()["voice_per_minute"] == 100_000


def test_call_accept_charge_signal_and_hang_up(client, guest):
    caller, callee = guest, new_guest(client)
    caller_id, callee_id = me(client, caller)["id"], me(client, callee)["id"]
    price = settings.call_voice_price_per_minute
    before = coins(client, caller)
    with client.websocket_connect(f"/ws/me?token={token_of(caller)}") as caller_ws, \
            client.websocket_connect(f"/ws/me?token={token_of(callee)}") as callee_ws:
        wait_until_registered(caller_ws)
        wait_until_registered(callee_ws)

        call = client.post(f"{API}/calls", headers=caller, json={"callee_id": callee_id, "kind": "voice"}).json()
        assert call["status"] == "ringing" and call["is_caller"]
        incoming = receive_until(callee_ws, "call:incoming")
        assert incoming["id"] == call["id"] and incoming["peer"]["id"] == caller_id and incoming["coins_spent"] is None
        # Aynı anda ikinci arama olmaz
        busy = client.post(f"{API}/calls", headers=callee, json={"callee_id": caller_id})
        assert busy.json()["code"] == "call_busy"
        # Arayan kendi aramasını açamaz
        assert client.post(f"{API}/calls/{call['id']}/accept", headers=caller).json()["code"] == "not_callee"

        voice = client.post(f"{API}/calls/{call['id']}/accept", headers=callee)
        assert voice.status_code == 200 and voice.json()["provider"] == "mesh"
        # İlk dakika peşin kesilir, sonra arayana "açıldı" haberi gider
        charged = receive_until(caller_ws, "call:charged")
        assert charged["billed_minutes"] == 1 and charged["coin_balance"] == before - price
        accepted = receive_until(caller_ws, "call:accepted")
        assert accepted["call"]["status"] == "active" and accepted["voice"]["can_publish"]
        assert client.get(f"{API}/calls/{call['id']}/join", headers=caller).status_code == 200

        # Mesh bağlantı mesajı yalnızca karşı tarafa gider
        caller_ws.send_json({"event": "call:signal", "payload": {
            "call_id": call["id"], "description": {"type": "offer", "sdp": "v=0"},
        }})
        signal = receive_until(callee_ws, "call:signal")
        assert signal["from"] == caller_id and signal["description"]["type"] == "offer"

        ended = client.post(f"{API}/calls/{call['id']}/end", headers=callee).json()
        assert ended["status"] == "ended"
        assert receive_until(caller_ws, "call:ended")["reason"] == "hangup"

    assert coins(client, caller) == before - price
    chat_id = open_chat(client, caller, callee_id)
    last = client.get(f"{API}/conversations/{chat_id}", headers=callee).json()["messages"][-1]
    assert last["kind"] == "call" and last["call_kind"] == "voice" and last["call_status"] == "ended"


def test_call_declined_and_missed(client, guest, monkeypatch):
    caller, callee = guest, new_guest(client)
    callee_id = me(client, callee)["id"]
    with client.websocket_connect(f"/ws/me?token={token_of(caller)}") as caller_ws, \
            client.websocket_connect(f"/ws/me?token={token_of(callee)}") as callee_ws:
        wait_until_registered(caller_ws)
        wait_until_registered(callee_ws)
        call = client.post(f"{API}/calls", headers=caller, json={"callee_id": callee_id, "kind": "video"}).json()
        assert client.post(f"{API}/calls/{call['id']}/decline", headers=callee).status_code == 204
        assert receive_until(caller_ws, "call:ended")["status"] == "declined"

        monkeypatch.setattr(settings, "call_ring_seconds", 0.2)
        call = client.post(f"{API}/calls", headers=caller, json={"callee_id": callee_id, "kind": "voice"}).json()
        assert receive_until(caller_ws, "call:ended")["status"] == "missed"
        assert client.get(f"{API}/calls/{call['id']}", headers=caller).json()["status"] == "missed"
        # Başkası aramayı göremez
        assert client.get(f"{API}/calls/{call['id']}", headers=new_guest(client)).status_code == 404


def test_call_ends_when_caller_runs_out_of_coins(client, guest, monkeypatch):
    caller, callee = guest, new_guest(client)
    callee_id = me(client, callee)["id"]
    balance = coins(client, caller)
    price = balance // 2 - 10           # iki dakika yeter, üçüncüsü yetmez
    monkeypatch.setattr(settings, "call_voice_price_per_minute", price)
    monkeypatch.setattr(call_service, "MINUTE_SECONDS", 0.2)
    diamonds_before = me(client, callee)["diamond_balance"]
    with client.websocket_connect(f"/ws/me?token={token_of(caller)}") as caller_ws, \
            client.websocket_connect(f"/ws/me?token={token_of(callee)}") as callee_ws:
        wait_until_registered(caller_ws)
        wait_until_registered(callee_ws)
        call = client.post(f"{API}/calls", headers=caller, json={"callee_id": callee_id}).json()
        client.post(f"{API}/calls/{call['id']}/accept", headers=callee)
        receive_until(caller_ws, "call:charged")
        second = receive_until(caller_ws, "call:charged")
        assert second["billed_minutes"] == 2 and second["low_balance"]
        ended = receive_until(caller_ws, "call:ended")
        assert ended["reason"] == "insufficient_balance" and ended["billed_minutes"] == 2

    assert coins(client, caller) == balance - 2 * price
    share = price * settings.call_receiver_share_percent // 100
    assert me(client, callee)["diamond_balance"] == diamonds_before + 2 * share
