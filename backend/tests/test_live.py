"""
Kameralı canlı yayın testleri: kim açabilir, izleyici bilgisi, görüntü sinyali, panelden kapatma.
"""
from contextlib import ExitStack

from tests.conftest import API
from tests.test_activities import join, new_room
from tests.test_admin import make_host, staff_headers
from tests.test_api import me, new_guest, receive_until
from tests.test_social import register


def test_live_camera_flow(client):
    host, viewer, outsider = register(client, "kamera_yayinci"), new_guest(client), new_guest(client)
    host_id, viewer_id = me(client, host)["id"], me(client, viewer)["id"]
    room = new_room(client, host, "Kameralı oda")
    rooms = f"{API}/rooms/{room['id']}"

    # Onaylı yayıncı değilse açamaz
    assert client.post(f"{rooms}/camera", headers=host).json()["code"] == "host_required"
    make_host(client, host)

    with ExitStack() as stack:
        host_socket = join(stack, client, room["id"], host)
        viewer_socket = join(stack, client, room["id"], viewer)
        # Koltukta değilse sesi gitmez: önce koltuk (oda sahibi girişte otomatik oturur, kaldırıyoruz)
        client.delete(f"{rooms}/seats/me", headers=host)
        assert client.post(f"{rooms}/camera", headers=host).json()["code"] == "seat_required"
        assert client.post(f"{rooms}/camera", headers=viewer).json()["code"] == "not_room_owner"
        client.post(f"{rooms}/seats/0", headers=host)

        started = client.post(f"{rooms}/camera", headers=host)
        assert started.status_code == 200 and started.json()["user_id"] == host_id
        assert receive_until(viewer_socket, "room:camera_updated")["camera"]["user_id"] == host_id
        assert client.get(rooms, headers=viewer).json()["camera_user_id"] == host_id
        assert client.get(f"{rooms}/activities", headers=viewer).json()["camera"]["user_id"] == host_id
        live = client.get(f"{API}/rooms", headers=viewer, params={"category": "live"}).json()
        assert live[0]["id"] == room["id"]   # kameralı oda Canlı'da en üstte

        # Görüntü kanalı: yalnızca yayıncı gönderebilir, odada olmayan bağlanamaz
        viewer_info = client.get(f"{rooms}/camera/join", headers=viewer).json()
        assert (viewer_info["can_publish"], viewer_info["streamer_id"]) == (False, host_id)
        assert client.get(f"{rooms}/camera/join", headers=host).json()["can_publish"] is True
        assert client.get(f"{rooms}/camera/join", headers=outsider).json()["code"] == "not_in_room"

        # Mesh: izleyicinin teklifi yayıncıya iletilir
        viewer_socket.send_json({"event": "live:signal", "payload": {
            "to": host_id, "description": {"type": "offer", "sdp": "v=0"}}})
        relayed = receive_until(host_socket, "live:signal")
        assert relayed["from"] == viewer_id and relayed["description"]["type"] == "offer"

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

        # Yayıncı yeniden açıp kendisi kapatabilir
        client.post(f"{rooms}/camera", headers=host)
        assert client.delete(f"{rooms}/camera", headers=host).status_code == 204
        assert client.get(rooms, headers=viewer).json()["camera_user_id"] is None
