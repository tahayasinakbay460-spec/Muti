"""
Tam ekran kameralı canlı yayın testleri: kim açabilir, izleyici bilgisi, listeler, sinyal,
takipçi bildirimi, panelden kapatma.
"""
from contextlib import ExitStack

from tests.conftest import API
from tests.test_activities import join
from tests.test_admin import make_host, staff_headers
from tests.test_api import me, new_guest, receive_until, wait_until_registered
from tests.test_social import register


def test_live_stream_flow(client):
    host, viewer, outsider = register(client, "canli_yayinci"), new_guest(client), new_guest(client)
    host_id, viewer_id = me(client, host)["id"], me(client, viewer)["id"]
    client.post(f"{API}/users/{host_id}/follow", headers=viewer)

    # Onaylı yayıncı değilse yayın odası açamaz
    assert client.post(f"{API}/rooms/live", headers=host, json={}).json()["code"] == "host_required"
    make_host(client, host)
    room = client.post(f"{API}/rooms/live", headers=host, json={"title": "Akşam sohbeti"}).json()
    assert room["kind"] == "live" and room["title"] == "Akşam sohbeti" and room["seats"] == []
    # İkinci kez aynı oda döner (yayıncı başına tek yayın odası)
    assert client.post(f"{API}/rooms/live", headers=host, json={}).json()["id"] == room["id"]
    rooms = f"{API}/rooms/{room['id']}"
    # Yayında değilken hiçbir listede görünmez
    assert room["id"] not in [r["id"] for r in client.get(f"{API}/rooms", headers=viewer).json()]
    assert room["id"] not in [r["id"] for r in client.get(f"{API}/rooms", headers=viewer, params={"category": "live"}).json()]

    # Sesli odada kamera açılmaz
    voice_room = client.post(f"{API}/rooms", headers=host, json={"title": "Sesli oda"}).json()
    assert client.post(f"{API}/rooms/{voice_room['id']}/camera", headers=host).json()["code"] == "not_live_room"

    with ExitStack() as stack:
        # Yayın ekranına girmeden başlatılamaz
        assert client.post(f"{rooms}/camera", headers=host).json()["code"] == "not_in_room"
        host_socket = join(stack, client, room["id"], host)
        viewer_socket = join(stack, client, room["id"], viewer)
        assert client.post(f"{rooms}/camera", headers=viewer).json()["code"] == "not_room_owner"

        with client.websocket_connect(f"/ws/me?token={viewer['Authorization'].removeprefix('Bearer ')}") as inbox:
            wait_until_registered(inbox)
            started = client.post(f"{rooms}/camera", headers=host)
            assert started.status_code == 200 and started.json()["user_id"] == host_id
            # Takipçiye "canlı yayında" bildirimi gider
            note = receive_until(inbox, "notification:new")
            assert note["type"] == "live_started" and note["data"]["live_room_id"] == room["id"]

        assert receive_until(viewer_socket, "room:camera_updated")["camera"]["user_id"] == host_id
        assert client.get(rooms, headers=viewer).json()["camera_user_id"] == host_id
        live = client.get(f"{API}/rooms", headers=viewer, params={"category": "live"}).json()
        assert live[0]["id"] == room["id"]   # yayındaki kameralı yayın Canlı'da en üstte

        # Ses + görüntü kanalı: yalnızca yayıncı gönderir, yayın ekranında olmayan bağlanamaz
        viewer_info = client.get(f"{rooms}/camera/join", headers=viewer).json()
        assert (viewer_info["can_publish"], viewer_info["streamer_id"]) == (False, host_id)
        assert client.get(f"{rooms}/camera/join", headers=host).json()["can_publish"] is True
        assert client.get(f"{rooms}/camera/join", headers=outsider).json()["code"] == "not_in_room"

        # Mesh: izleyicinin teklifi yayıncıya iletilir
        viewer_socket.send_json({"event": "live:signal", "payload": {
            "to": host_id, "description": {"type": "offer", "sdp": "v=0"}}})
        relayed = receive_until(host_socket, "live:signal")
        assert relayed["from"] == viewer_id and relayed["description"]["type"] == "offer"

        # Yayında hediye: yayıncıya gider, odadakilere duyurulur
        sent = client.post(f"{API}/gifts/send", headers=viewer, json={"receiver_id": host_id, "gift_id": 1, "room_id": room["id"]})
        assert sent.status_code == 200, sent.text
        assert receive_until(host_socket, "gift:sent")["receiver"]["id"] == host_id

        # İzleyici kapatamaz; panel kapatır, odadakilere duyurulur
        assert client.delete(f"{rooms}/camera", headers=viewer).json()["code"] == "not_room_moderator"
        moderator = staff_headers(client, "moderator")
        admin_rooms = client.get(f"{API}/admin/rooms", headers=moderator).json()
        assert admin_rooms[0]["id"] == room["id"] and admin_rooms[0]["has_camera"] is True
        assert client.delete(f"{API}/admin/rooms/{room['id']}/camera", headers=moderator).status_code == 204
        stopped = receive_until(viewer_socket, "room:camera_updated")
        assert stopped["camera"] is None and stopped["reason"] == "staff"
        assert client.delete(f"{API}/admin/rooms/{room['id']}/camera", headers=moderator).status_code == 404
        assert client.get(f"{rooms}/camera/join", headers=viewer).status_code == 404

        # Yayıncı yeniden açıp kendisi bitirebilir
        client.post(f"{rooms}/camera", headers=host)
        assert client.delete(f"{rooms}/camera", headers=host).status_code == 204
        assert client.get(rooms, headers=viewer).json()["camera_user_id"] is None
