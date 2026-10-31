"""
Kısa kopmalar: koltuk bekletme, dönene güncel koltuklar, aynı hesapla tek cihaz, ses izni.

Bağlantıyı 1006 koduyla kapatmak ağ kopmasını taklit eder; 1000 "kendim çıktım" demektir.
"""
import time

import pytest

from app.realtime import room_socket
from tests.conftest import API
from tests.test_api import me, new_guest, receive_until

GRACE_SECONDS = 0.15
NETWORK_DROP = 1006


def token(headers: dict) -> str:
    return headers["Authorization"].removeprefix("Bearer ")


def seat_user(client, room_id: int, headers: dict, index: int = 1) -> int | None:
    return client.get(f"{API}/rooms/{room_id}", headers=headers).json()["seats"][index]["user_id"]


def wait_for_seat(client, room_id: int, headers: dict, expected: int | None) -> None:
    deadline = time.monotonic() + 3
    while seat_user(client, room_id, headers) != expected:
        assert time.monotonic() < deadline, "koltuk beklenen duruma gelmedi"
        time.sleep(0.02)


def wait_for_pending(room: dict) -> None:
    """Sunucu kopmayı işleyip bekleme süresini başlatana kadar bekler."""
    deadline = time.monotonic() + 3
    while (room["id"], room["member_id"]) not in room_socket._pending_departures:
        assert time.monotonic() < deadline, "bekleme başlamadı"
        time.sleep(0.01)


@pytest.fixture
def seated_room(client, guest, monkeypatch):
    """Oda sahibi + 1 numaralı koltukta oturan üye."""
    monkeypatch.setattr(room_socket, "SEAT_GRACE_SECONDS", GRACE_SECONDS)
    room = client.post(f"{API}/rooms", headers=guest, json={"title": "Kopma"}).json()
    member = new_guest(client)
    return {"id": room["id"], "host": guest, "member": member, "member_id": me(client, member)["id"]}


def open_socket(client, room: dict, headers: dict, query: str = ""):
    return client.websocket_connect(f"/ws/rooms/{room['id']}?token={token(headers)}{query}")


def take_seat(client, room: dict) -> None:
    assert client.post(f"{API}/rooms/{room['id']}/seats/1", headers=room["member"]).status_code == 200


def test_seat_survives_short_drop_and_return_is_not_a_new_join(client, seated_room, monkeypatch):
    room = seated_room
    # Süre uzun: ayrılma görevi bu test içinde tek başına bitemesin, yalnızca geri dönüş iptal etsin
    monkeypatch.setattr(room_socket, "SEAT_GRACE_SECONDS", 30)
    with open_socket(client, room, room["host"]) as host_socket:
        receive_until(host_socket, "chat:history")
        with open_socket(client, room, room["member"]) as socket:
            receive_until(socket, "chat:history")
            take_seat(client, room)
            socket.close(code=NETWORK_DROP)
        wait_for_pending(room)

        # Dönene kadar koltuğu duruyor ve "odadan çıktı" yayını yapılmıyor.
        assert seat_user(client, room["id"], room["host"]) == room["member_id"]

        with open_socket(client, room, room["member"], "&resume=true") as returned:
            receive_until(returned, "chat:history")
            restored = receive_until(returned, "room:seats_updated")
            assert restored["seats"][1]["user_id"] == room["member_id"]

            assert (room["id"], room["member_id"]) not in room_socket._pending_departures


def test_returning_user_does_not_trigger_join_announcement(client, seated_room, monkeypatch):
    room = seated_room
    monkeypatch.setattr(room_socket, "SEAT_GRACE_SECONDS", 30)
    with open_socket(client, room, room["member"]) as first:
        receive_until(first, "chat:history")
        first.close(code=NETWORK_DROP)
    wait_for_pending(room)

    with open_socket(client, room, room["host"]) as host_socket:
        receive_until(host_socket, "chat:history")
        with open_socket(client, room, room["member"], "&resume=true") as returned:
            receive_until(returned, "chat:history")
            returned.send_json({"event": "chat:message", "payload": {"text": "döndüm"}})
            joined = []
            while True:
                message = host_socket.receive_json()
                if message["event"] == "room:user_joined":
                    joined.append(message["payload"]["user"]["id"])
                if message["event"] == "chat:message":
                    break
            assert room["member_id"] not in joined


def test_seat_is_released_when_user_does_not_return(client, seated_room):
    room = seated_room
    with open_socket(client, room, room["host"]) as host_socket:
        receive_until(host_socket, "chat:history")
        with open_socket(client, room, room["member"]) as socket:
            receive_until(socket, "chat:history")
            take_seat(client, room)
            socket.close(code=NETWORK_DROP)
        wait_for_seat(client, room["id"], room["host"], None)
        assert receive_until(host_socket, "room:user_left")["user_id"] == room["member_id"]


def test_leaving_on_purpose_frees_seat_at_once(client, seated_room, monkeypatch):
    room = seated_room
    monkeypatch.setattr(room_socket, "SEAT_GRACE_SECONDS", 30)
    with open_socket(client, room, room["member"]) as socket:
        receive_until(socket, "chat:history")
        take_seat(client, room)
    wait_for_seat(client, room["id"], room["host"], None)
    assert (room["id"], room["member_id"]) not in room_socket._pending_departures


def test_resume_sends_current_seats_but_first_join_does_not(client, seated_room):
    room = seated_room
    take_seat(client, room)
    with open_socket(client, room, room["host"]) as socket:
        receive_until(socket, "chat:history")
        socket.send_json({"event": "chat:message", "payload": {"text": "işaret"}})
        events = []
        while not events or events[-1] != "chat:message":
            events.append(socket.receive_json()["event"])
        assert "room:seats_updated" not in events

    with open_socket(client, room, room["host"], "&resume=true") as socket:
        receive_until(socket, "chat:history")
        assert receive_until(socket, "room:seats_updated")["seats"][1]["user_id"] == room["member_id"]


def test_second_device_replaces_first_and_keeps_the_seat(client, seated_room):
    room = seated_room
    with open_socket(client, room, room["member"]) as old_device:
        receive_until(old_device, "chat:history")
        take_seat(client, room)
        with open_socket(client, room, room["member"]) as new_device:
            receive_until(new_device, "chat:history")
            closed = receive_until_close(old_device)
            assert closed["code"] == 4409
            assert seat_user(client, room["id"], room["host"]) == room["member_id"]
            new_device.send_json({"event": "chat:message", "payload": {"text": "yeni cihaz"}})
            assert receive_until(new_device, "chat:message")["text"] == "yeni cihaz"


def receive_until_close(socket) -> dict:
    while True:
        message = socket.receive()
        if message["type"] == "websocket.close":
            return message


def test_kicked_user_is_gone_without_grace(client, seated_room, monkeypatch):
    room = seated_room
    monkeypatch.setattr(room_socket, "SEAT_GRACE_SECONDS", 30)
    with open_socket(client, room, room["member"]) as socket:
        receive_until(socket, "chat:history")
        take_seat(client, room)
        kicked = client.post(f"{API}/rooms/{room['id']}/kicks/{room['member_id']}", headers=room["host"])
        assert kicked.status_code == 204
        assert receive_until_close(socket)["code"] == 4403
    assert (room["id"], room["member_id"]) not in room_socket._pending_departures


def test_voice_access_requires_being_in_the_room(client, seated_room, monkeypatch):
    room = seated_room
    voice = f"{API}/rooms/{room['id']}/voice"
    denied = client.get(voice, headers=room["member"])
    assert denied.status_code == 403 and denied.json()["code"] == "not_in_room"

    # Kopma sırasında koltuktaki kişi konuşma iznini yenileyebilmeli.
    monkeypatch.setattr(room_socket, "SEAT_GRACE_SECONDS", 30)
    with open_socket(client, room, room["member"]) as socket:
        receive_until(socket, "chat:history")
        assert client.get(voice, headers=room["member"]).json()["can_publish"] is False
        take_seat(client, room)
        socket.close(code=NETWORK_DROP)
    wait_for_pending(room)
    assert client.get(voice, headers=room["member"]).json()["can_publish"] is True


def test_pending_departures_are_cancelled_on_shutdown(client, seated_room, monkeypatch):
    room = seated_room
    monkeypatch.setattr(room_socket, "SEAT_GRACE_SECONDS", 30)
    with open_socket(client, room, room["member"]) as socket:
        receive_until(socket, "chat:history")
        socket.close(code=NETWORK_DROP)
    wait_for_pending(room)
    client.portal.call(_cancel_on_loop)
    assert not room_socket._pending_departures


async def _cancel_on_loop() -> None:
    # Görev iptali, görevin çalıştığı olay döngüsünde yapılmalı.
    room_socket.cancel_pending_departures()
