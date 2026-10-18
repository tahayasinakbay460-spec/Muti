"""
Uçtan uca API testleri: gerçek HTTP/WebSocket istekleri atılır, cevaplar kontrol edilir.
Her test, bozulursa kullanıcıya zarar verecek bir davranışı korur.
"""
from concurrent.futures import ThreadPoolExecutor

from tests.conftest import API, auth_headers


def me(client, headers) -> dict:
    return client.get(f"{API}/users/me", headers=headers).json()


# ── Kimlik ────────────────────────────────────────────────────────────────────

def test_requests_without_token_are_rejected(client):
    response = client.get(f"{API}/users/me")
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_register_login_and_duplicate_username(client):
    payload = {"username": "Yeni_Uye", "email": "yeni@example.com", "password": "gizli123"}
    registered = client.post(f"{API}/auth/register", json=payload)
    assert registered.status_code == 201
    user = registered.json()["user"]
    assert user["username"] == "yeni_uye" and user["display_name"] == "Yeni_Uye"
    assert user["coin_balance"] == 500   # hoş geldin bonusu

    assert client.post(f"{API}/auth/register", json=payload).json()["code"] == "username_taken"

    assert client.post(f"{API}/auth/login", json={"username": "yeni_uye", "password": "gizli123"}).status_code == 200
    wrong = client.post(f"{API}/auth/login", json={"username": "yeni_uye", "password": "yanlis"})
    assert wrong.status_code == 401 and wrong.json()["code"] == "invalid_credentials"


def test_validation_error_has_our_format(client):
    response = client.post(f"{API}/auth/register", json={"username": "ab", "email": "x", "password": "1"})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert isinstance(response.json()["detail"], str)


def test_refresh_token_works_once_and_reuse_closes_all_sessions(client):
    tokens = client.post(f"{API}/auth/guest").json()

    renewed = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert renewed.status_code == 200
    assert client.get(f"{API}/users/me", headers=auth_headers(renewed.json())).status_code == 200

    # Eski refresh token ikinci kez kullanılamaz...
    reused = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reused.status_code == 401
    # ...ve bu bir çalınma belirtisi sayıldığı için yeni verilen token da iptal edilmiştir.
    after = client.post(f"{API}/auth/refresh", json={"refresh_token": renewed.json()["refresh_token"]})
    assert after.status_code == 401


# ── Ekonomi ───────────────────────────────────────────────────────────────────

def test_gift_moves_money_and_writes_history(client, guest):
    before = me(client, guest)["coin_balance"]
    sent = client.post(f"{API}/gifts/send", headers=guest, json={"receiver_id": 2001, "gift_id": 5, "quantity": 2})
    assert sent.status_code == 200, sent.text
    assert sent.json()["coin_balance"] == before - 198          # Pasta 99 x 2
    assert me(client, guest)["coin_balance"] == before - 198

    history = client.get(f"{API}/wallet/transactions", headers=guest).json()
    assert history[0]["type"] == "gift_sent" and history[0]["amount"] == -198


def test_gift_with_insufficient_balance_changes_nothing(client, guest):
    before = me(client, guest)["coin_balance"]
    response = client.post(f"{API}/gifts/send", headers=guest, json={"receiver_id": 2001, "gift_id": 12})
    assert response.status_code == 402 and response.json()["code"] == "insufficient_balance"
    assert me(client, guest)["coin_balance"] == before


def test_same_idempotency_key_charges_only_once(client, guest):
    before = me(client, guest)["coin_balance"]
    headers = {**guest, "Idempotency-Key": "tap-0001-abcdef"}
    body = {"receiver_id": 2001, "gift_id": 1, "quantity": 3}

    first = client.post(f"{API}/gifts/send", headers=headers, json=body)
    second = client.post(f"{API}/gifts/send", headers=headers, json=body)
    assert first.status_code == second.status_code == 200
    assert first.json()["coin_balance"] == second.json()["coin_balance"] == before - 30
    assert me(client, guest)["coin_balance"] == before - 30


def test_concurrent_gifts_cannot_overspend(client, guest):
    """500 coinle aynı anda 12 tane 99'luk hediye: tam 5'i geçmeli, bakiye eksiye düşmemeli."""
    body = {"receiver_id": 2001, "gift_id": 5, "quantity": 1}
    with ThreadPoolExecutor(max_workers=12) as pool:
        statuses = list(pool.map(
            lambda _: client.post(f"{API}/gifts/send", headers=guest, json=body).status_code, range(12),
        ))
    assert statuses.count(200) == 5 and statuses.count(402) == 7
    assert me(client, guest)["coin_balance"] == 500 - 5 * 99


def test_purchase_adds_coins(client, guest):
    before = me(client, guest)["coin_balance"]
    bought = client.post(f"{API}/wallet/purchase", headers=guest, json={"package_id": 2})
    assert bought.status_code == 200
    assert bought.json() == {"coin_balance": before + 1650, "added": 1650}   # 1500 + 150 bonus


# ── Odalar ────────────────────────────────────────────────────────────────────

def test_room_list_and_seat_rules(client, guest):
    rooms = client.get(f"{API}/rooms?category=music", headers=guest).json()
    assert rooms and all(room["category"] == "music" for room in rooms)

    room = client.get(f"{API}/rooms/104211", headers=guest).json()
    assert room["host"]["id"] == 2015 and len(room["seats"]) == 8

    seats = f"{API}/rooms/104211/seats"
    assert client.post(f"{seats}/0", headers=guest).json()["code"] == "seat_taken"
    assert client.post(f"{seats}/7", headers=guest).json()["code"] == "seat_locked"

    my_id = me(client, guest)["id"]
    seated = client.post(f"{seats}/3", headers=guest).json()
    assert seated["seats"][3]["user_id"] == my_id

    # Başka koltuğa geçince eskisi boşalır (aynı anda tek koltuk).
    moved = client.post(f"{seats}/5", headers=guest).json()
    assert moved["seats"][3]["user_id"] is None and moved["seats"][5]["user_id"] == my_id

    assert client.post(f"{seats}/me/mute", headers=guest).json()["seats"][5]["is_muted"] is True
    assert client.delete(f"{seats}/me", headers=guest).json()["seats"][5]["user_id"] is None


def test_create_room_seats_host(client, guest):
    created = client.post(f"{API}/rooms", headers=guest, json={"title": "  Test Odam  ", "category": "game"})
    assert created.status_code == 201
    room = created.json()
    assert room["title"] == "Test Odam" and room["seats"][0]["user_id"] == room["host_id"]


# ── Sosyal ────────────────────────────────────────────────────────────────────

def test_follow_toggle_updates_counter(client, guest):
    before = client.get(f"{API}/users/2002", headers=guest).json()
    assert client.post(f"{API}/users/2002/follow", headers=guest).json() == {"is_following": True}
    after = client.get(f"{API}/users/2002", headers=guest).json()
    assert after["is_following"] and after["followers_count"] == before["followers_count"] + 1
    assert after["coin_balance"] is None   # başkasının bakiyesi görünmez
    assert client.post(f"{API}/users/2002/follow", headers=guest).json() == {"is_following": False}


def test_conversation_flow_and_privacy(client, muti, guest):
    listed = client.get(f"{API}/conversations", headers=muti).json()
    assert len(listed) == 4 and listed[0]["user"]["username"] == "merve" and listed[0]["unread_count"] == 2

    opened = client.get(f"{API}/conversations/{listed[0]['id']}", headers=muti).json()
    assert [m["from_me"] for m in opened["messages"]] == [False, True, False]
    assert client.get(f"{API}/conversations", headers=muti).json()[0]["unread_count"] == 0

    # Başkasının sohbeti okunamaz.
    assert client.get(f"{API}/conversations/{listed[0]['id']}", headers=guest).status_code == 404

    conversation_id = client.post(f"{API}/conversations", headers=guest, json={"user_id": 2002}).json()["id"]
    assert client.post(f"{API}/conversations", headers=guest, json={"user_id": 2002}).json()["id"] == conversation_id
    sent = client.post(f"{API}/conversations/{conversation_id}/messages", headers=guest, json={"text": "Selam!"})
    assert sent.status_code == 201 and sent.json()["from_me"] is True


def test_public_lists_load(client, muti):
    for path in ("/banners", "/gifts", "/wallet/packages", "/users/suggested", "/users/2001/profile"):
        assert client.get(f"{API}{path}", headers=muti).status_code == 200, path
    gifters = client.get(f"{API}/leaderboards/gifters", headers=muti).json()
    assert [g["user"]["id"] for g in gifters] == [2001, 2012, 2015, 2003, 2010]


# ── WebSocket ─────────────────────────────────────────────────────────────────

def receive_until(socket, event: str) -> dict:
    """İstenen olay gelene kadar diğer olayları atlar."""
    for _ in range(20):
        message = socket.receive_json()
        if message["event"] == event:
            return message["payload"]
    raise AssertionError(f"{event} gelmedi")


def test_room_socket_chat_dice_and_gift(client, guest):
    token = guest["Authorization"].removeprefix("Bearer ")
    my_id = me(client, guest)["id"]

    with client.websocket_connect(f"/ws/rooms/107340?token={token}") as socket:
        assert receive_until(socket, "room:user_joined")["user"]["id"] == my_id
        assert receive_until(socket, "room:listener_count")["listener_count"] == 22   # 21 örnek + ben

        # Başkasının adına yazmaya çalışsam da mesaj benim adımla yayınlanır.
        socket.send_json({"event": "chat:message", "payload": {"user": {"id": 2001}, "text": " Selam "}})
        chat = receive_until(socket, "chat:message")
        assert chat["user"]["id"] == my_id and chat["text"] == "Selam"

        # Zarı sunucu atar: gönderdiğim 9-9 yok sayılır.
        socket.send_json({"event": "game:dice_rolled", "payload": {"values": [9, 9]}})
        assert all(1 <= value <= 6 for value in receive_until(socket, "game:dice_rolled")["values"])

        # Gerçek hediye odaya yayınlanır.
        client.post(f"{API}/gifts/send", headers=guest, json={"receiver_id": 2010, "gift_id": 1, "room_id": 107340})
        gift = receive_until(socket, "gift:sent")
        assert gift["sender"]["id"] == my_id and gift["receiver"]["id"] == 2010 and gift["gift"]["name"] == "Gül"


def test_room_socket_rejects_bad_token(client):
    with client.websocket_connect("/ws/rooms/107340?token=bozuk") as socket:
        closed = socket.receive()
        assert closed["type"] == "websocket.close" and closed["code"] == 4401
