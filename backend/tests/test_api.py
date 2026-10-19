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


def test_profile_update_changes_only_sent_fields(client, guest):
    before = me(client, guest)
    response = client.patch(f"{API}/users/me", headers=guest, json={
        "display_name": "  Yeni Ad  ", "bio": "Merhaba", "city": "İzmir", "avatar_url": "assets/avatars/w3.jpg",
    })
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["display_name"] == "Yeni Ad" and updated["bio"] == "Merhaba" and updated["city"] == "İzmir"
    assert updated["avatar_url"] == "assets/avatars/w3.jpg"
    # Gönderilmeyen alanlar olduğu gibi kalır.
    assert updated["age"] == before["age"] and updated["cover_url"] == before["cover_url"]
    assert me(client, guest)["display_name"] == "Yeni Ad"

    # Boş görünen ad, listede olmayan görsel ve sınır dışı yaş reddedilir.
    assert client.patch(f"{API}/users/me", headers=guest, json={"display_name": "   "}).status_code == 422
    bad_avatar = client.patch(f"{API}/users/me", headers=guest, json={"avatar_url": "https://evil.example/x.jpg"})
    assert bad_avatar.json()["code"] == "invalid_avatar"
    assert client.patch(f"{API}/users/me", headers=guest, json={"age": 7}).status_code == 422

    options = client.get(f"{API}/users/me/media-options", headers=guest).json()
    assert "assets/avatars/w3.jpg" in options["avatars"] and options["covers"]


def test_room_follow_toggle_and_followed_list(client, guest):
    assert client.get(f"{API}/rooms/followed", headers=guest).json() == []
    assert client.post(f"{API}/rooms/104211/follow", headers=guest).json() == {"is_following": True}
    assert client.get(f"{API}/rooms/104211", headers=guest).json()["is_following"] is True
    assert [room["id"] for room in client.get(f"{API}/rooms/followed", headers=guest).json()] == [104211]

    assert client.post(f"{API}/rooms/104211/follow", headers=guest).json() == {"is_following": False}
    assert client.get(f"{API}/rooms/followed", headers=guest).json() == []
    assert client.post(f"{API}/rooms/999999/follow", headers=guest).status_code == 404


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


# ── Moderasyon ────────────────────────────────────────────────────────────────

def new_guest(client) -> dict:
    return auth_headers(client.post(f"{API}/auth/guest").json())


def test_moderation_roles_and_seat_rules(client, guest):
    host = guest
    room = client.post(f"{API}/rooms", headers=host, json={"title": "Moderasyon"}).json()
    rooms = f"{API}/rooms/{room['id']}"
    helper, member = new_guest(client), new_guest(client)
    helper_id, member_id, host_id = me(client, helper)["id"], me(client, member)["id"], room["host_id"]

    # Sıradan dinleyici yönetim işlemi yapamaz, rol de veremez.
    assert client.put(f"{rooms}/seats/3/lock", headers=member).json()["code"] == "not_room_moderator"
    assert client.put(f"{rooms}/roles/{member_id}", headers=helper, json={"role": "vip"}).json()["code"] == "not_room_moderator"

    # Oda sahibi yönetici atar. Yönetici VIP verebilir ama yönetici atayamaz.
    assert client.put(f"{rooms}/roles/{helper_id}", headers=host, json={"role": "admin"}).json()["admin_ids"] == [helper_id]
    assert client.put(f"{rooms}/roles/{member_id}", headers=helper, json={"role": "admin"}).json()["code"] == "not_room_host"
    assert client.put(f"{rooms}/roles/{member_id}", headers=helper, json={"role": "vip"}).json()["vip_ids"] == [member_id]
    assert client.put(f"{rooms}/roles/{member_id}", headers=helper, json={"role": "listener"}).json()["vip_ids"] == []

    # Yönetici, dinleyiciyi koltuktan indirebilir ama oda sahibini indiremez.
    client.post(f"{rooms}/seats/2", headers=member)
    assert client.delete(f"{rooms}/seats/2/user", headers=helper).json()["seats"][2]["user_id"] is None
    assert client.delete(f"{rooms}/seats/0/user", headers=helper).json()["code"] == "target_outranks_you"

    # Kilitli koltuğa oturulamaz; dolu koltuk kilitlenince oturan kişi iner.
    client.post(f"{rooms}/seats/4", headers=member)
    locked = client.put(f"{rooms}/seats/4/lock", headers=helper).json()
    assert locked["seats"][4]["is_locked"] and locked["seats"][4]["user_id"] is None
    assert client.post(f"{rooms}/seats/4", headers=member).json()["code"] == "seat_locked"
    assert client.delete(f"{rooms}/seats/4/lock", headers=helper).json()["seats"][4]["is_locked"] is False

    # Yöneticilik geri alınınca yetki de gider.
    assert client.put(f"{rooms}/roles/{helper_id}", headers=host, json={"role": "listener"}).json()["admin_ids"] == []
    assert client.put(f"{rooms}/seats/5/lock", headers=helper).json()["code"] == "not_room_moderator"
    assert client.post(f"{rooms}/kicks/{host_id}", headers=helper).status_code == 403


def test_kicked_user_is_disconnected_and_banned(client, guest):
    host = guest
    room = client.post(f"{API}/rooms", headers=host, json={"title": "Atma Testi"}).json()
    member = new_guest(client)
    member_id = me(client, member)["id"]
    token = member["Authorization"].removeprefix("Bearer ")

    with client.websocket_connect(f"/ws/rooms/{room['id']}?token={token}") as socket:
        receive_until(socket, "room:listener_count")
        client.post(f"{API}/rooms/{room['id']}/seats/1", headers=member)
        assert client.post(f"{API}/rooms/{room['id']}/kicks/{member_id}", headers=host).status_code == 204
        assert receive_until(socket, "room:user_kicked")["user"]["id"] == member_id
        closed = socket.receive()
        assert closed["type"] == "websocket.close" and closed["code"] == 4403

    # Yasak süresince ne bağlanabilir ne de koltuğa oturabilir; koltuğu da boşalmıştır.
    with client.websocket_connect(f"/ws/rooms/{room['id']}?token={token}") as socket:
        assert socket.receive()["code"] == 4403
    assert client.post(f"{API}/rooms/{room['id']}/seats/1", headers=member).json()["code"] == "room_banned"
    assert client.get(f"{API}/rooms/{room['id']}", headers=host).json()["seats"][1]["user_id"] is None


def test_mic_block_chat_mute_and_message_delete(client, guest):
    host = guest
    room = client.post(f"{API}/rooms", headers=host, json={"title": "Susturma"}).json()
    rooms = f"{API}/rooms/{room['id']}"
    member = new_guest(client)
    member_id = me(client, member)["id"]
    token = member["Authorization"].removeprefix("Bearer ")

    with client.websocket_connect(f"/ws/rooms/{room['id']}?token={token}") as socket:
        assert receive_until(socket, "chat:history")["messages"] == []

        # Mikrofon engeli: kişi sessiz oturur ve kendisi açamaz; engel kalkınca açabilir.
        client.post(f"{rooms}/seats/1", headers=member)
        blocked = client.put(f"{rooms}/mic-blocks/{member_id}", headers=host).json()
        assert blocked["seats"][1]["is_muted"] and blocked["seats"][1]["is_mic_blocked"]
        assert client.post(f"{rooms}/seats/me/mute", headers=member).json()["code"] == "mic_blocked"
        # Koltuktan kalkıp yeniden otursa bile engel sürer.
        client.delete(f"{rooms}/seats/me", headers=member)
        assert client.post(f"{rooms}/seats/2", headers=member).json()["seats"][2]["is_muted"] is True
        client.delete(f"{rooms}/mic-blocks/{member_id}", headers=host)
        assert client.post(f"{rooms}/seats/me/mute", headers=member).json()["seats"][2]["is_muted"] is False
        # Dinleyici başkasının mikrofonunu engelleyemez.
        assert client.put(f"{rooms}/mic-blocks/{room['host_id']}", headers=member).status_code == 403

        # Mesajın kimliği var; kişi kendi mesajını silebilir.
        socket.send_json({"event": "chat:message", "payload": {"text": "silinecek"}})
        message = receive_until(socket, "chat:message")
        assert message["id"] and message["created_at"]
        assert client.delete(f"{rooms}/messages/{message['id']}", headers=member).status_code == 204
        assert receive_until(socket, "chat:message_deleted")["message_id"] == message["id"]
        assert client.delete(f"{rooms}/messages/{message['id']}", headers=member).json()["code"] == "message_not_found"

        # Susturulan kişi yazamaz; oda sahibi onun mesajını da silebilir.
        socket.send_json({"event": "chat:message", "payload": {"text": "kaba söz"}})
        rude = receive_until(socket, "chat:message")
        assert client.put(f"{rooms}/chat-mutes/{member_id}", headers=host, json={"minutes": 5}).status_code == 204
        assert receive_until(socket, "room:chat_muted")["seconds"] == 300
        socket.send_json({"event": "chat:message", "payload": {"text": "yine"}})
        assert receive_until(socket, "error")["code"] == "chat_muted"
        assert client.delete(f"{rooms}/messages/{rude['id']}", headers=host).status_code == 204
        # Geçersiz süre reddedilir; susturma kaldırılınca yazabilir.
        assert client.put(f"{rooms}/chat-mutes/{member_id}", headers=host, json={"minutes": 7}).status_code == 422
        client.delete(f"{rooms}/chat-mutes/{member_id}", headers=host)
        socket.send_json({"event": "chat:message", "payload": {"text": "özür dilerim"}})
        assert receive_until(socket, "chat:message")["text"] == "özür dilerim"

    # Odaya yeni giren son mesajları görür; silinen mesajlar listede yoktur.
    host_token = host["Authorization"].removeprefix("Bearer ")
    with client.websocket_connect(f"/ws/rooms/{room['id']}?token={host_token}") as socket:
        history = receive_until(socket, "chat:history")["messages"]
        assert [m["text"] for m in history] == ["özür dilerim"]


def test_member_list_and_seat_invites(client, guest):
    host = guest
    room = client.post(f"{API}/rooms", headers=host, json={"title": "Davetli Koltuk"}).json()
    rooms = f"{API}/rooms/{room['id']}"
    member, vip = new_guest(client), new_guest(client)
    member_id, vip_id = me(client, member)["id"], me(client, vip)["id"]
    token = member["Authorization"].removeprefix("Bearer ")

    # Koltuklar davetle açılır; VIP kendisi oturabilir, sıradan dinleyici oturamaz.
    assert client.patch(rooms, headers=host, json={"free_seating": False}).json()["free_seating"] is False
    client.put(f"{rooms}/roles/{vip_id}", headers=host, json={"role": "vip"})
    assert client.post(f"{rooms}/seats/3", headers=vip).json()["seats"][3]["user_id"] == vip_id
    assert client.post(f"{rooms}/seats/1", headers=member).json()["code"] == "seat_requires_invite"

    # Odada olmayan kişi davet edilemez.
    assert client.post(f"{rooms}/seat-invites/{member_id}", headers=host).json()["code"] == "not_in_room"

    with client.websocket_connect(f"/ws/rooms/{room['id']}?token={token}") as socket:
        receive_until(socket, "room:listener_count")
        members = client.get(f"{rooms}/members", headers=member).json()
        assert [(m["user"]["id"], m["role"]) for m in members] == [(member_id, "listener")]

        # Davet yalnızca davet edilene gider ve bir kez kullanılır.
        assert client.post(f"{rooms}/seat-invites/{member_id}", headers=vip).json()["code"] == "not_room_moderator"
        assert client.post(f"{rooms}/seat-invites/{member_id}", headers=host).status_code == 204
        assert receive_until(socket, "room:seat_invite")["by"]["id"] == room["host_id"]
        # Dolu koltuğu denemek daveti harcamaz.
        assert client.post(f"{rooms}/seats/3", headers=member).json()["code"] == "seat_taken"
        assert client.post(f"{rooms}/seats/1", headers=member).json()["seats"][1]["user_id"] == member_id
        client.delete(f"{rooms}/seats/me", headers=member)
        assert client.post(f"{rooms}/seats/1", headers=member).json()["code"] == "seat_requires_invite"


def test_room_settings_and_closing(client, guest):
    host = guest
    room = client.post(f"{API}/rooms", headers=host, json={"title": "Ayarlar"}).json()
    rooms = f"{API}/rooms/{room['id']}"
    member = new_guest(client)
    token = member["Authorization"].removeprefix("Bearer ")

    with client.websocket_connect(f"/ws/rooms/{room['id']}?token={token}") as socket:
        receive_until(socket, "room:listener_count")
        # Dinleyici ayar değiştiremez; geçersiz kapak reddedilir; null gönderilen alan değişmez.
        assert client.patch(rooms, headers=member, json={"title": "X"}).status_code == 403
        assert client.patch(rooms, headers=host, json={"cover_url": "http://kotu.site/a.jpg"}).json()["code"] == "invalid_cover"
        updated = client.patch(rooms, headers=host, json={
            "title": " Yeni Ad ", "announcement": "Kurallar: saygı", "cover_url": "assets/covers/night.jpg", "category": None,
        }).json()
        assert updated["title"] == "Yeni Ad" and updated["category"] == "chat"
        assert receive_until(socket, "room:updated")["announcement"] == "Kurallar: saygı"

        # Odayı yalnızca sahibi kapatır; içerideki herkes çıkarılır.
        assert client.delete(rooms, headers=member).status_code == 403
        assert client.delete(rooms, headers=host).status_code == 204
        receive_until(socket, "room:closed")
        closed = socket.receive()
        assert closed["type"] == "websocket.close" and closed["code"] == 4404

    assert client.get(rooms, headers=host).status_code == 404
    assert room["id"] not in [r["id"] for r in client.get(f"{API}/rooms", headers=host).json()]


# ── Kişiye özel kanal (özel mesaj bildirimi) ──────────────────────────────────

def test_private_message_is_pushed_to_receiver(client, guest):
    sender, receiver = guest, new_guest(client)
    sender_id, receiver_id = me(client, sender)["id"], me(client, receiver)["id"]
    token = receiver["Authorization"].removeprefix("Bearer ")

    with client.websocket_connect(f"/ws/me?token={token}") as socket:
        conversation_id = client.post(f"{API}/conversations", headers=sender, json={"user_id": receiver_id}).json()["id"]
        client.post(f"{API}/conversations/{conversation_id}/messages", headers=sender, json={"text": " Merhaba "})

        pushed = receive_until(socket, "message:new")
        assert pushed["conversation_id"] == conversation_id and pushed["sender"]["id"] == sender_id
        # Alıcı mesajı kendi gözünden görür: "benden değil".
        assert pushed["message"]["text"] == "Merhaba" and pushed["message"]["from_me"] is False

        # Sunucu ping dışında bir şey kabul etmez.
        socket.send_json({"event": "chat:message", "payload": {"text": "x"}})
        assert receive_until(socket, "error")["code"] == "unknown_event"

    assert client.get(f"{API}/conversations/unread-count", headers=receiver).json() == {"unread_count": 1}
    assert client.post(f"{API}/conversations/{conversation_id}/read", headers=receiver).status_code == 204
    assert client.get(f"{API}/conversations/unread-count", headers=receiver).json() == {"unread_count": 0}
    # Başkasının sohbetini okundu sayamaz.
    assert client.post(f"{API}/conversations/{conversation_id}/read", headers=new_guest(client)).status_code == 404


def test_user_socket_rejects_bad_token(client):
    with client.websocket_connect("/ws/me?token=bozuk") as socket:
        assert socket.receive()["code"] == 4401


# ── Oda içi oyun: Rulet ───────────────────────────────────────────────────────

def test_roulette_round_is_run_by_server(client, guest, monkeypatch):
    from app.realtime.games import roulette, roulette_color

    assert [roulette_color(n) for n in (0, 1, 2, 36)] == ["green", "red", "black", "red"]
    monkeypatch.setattr(roulette, "betting_seconds", 0.3)   # testte 10 sn beklemeyelim

    room = client.post(f"{API}/rooms", headers=guest, json={"title": "Rulet Masası"}).json()
    token = guest["Authorization"].removeprefix("Bearer ")
    my_id = me(client, guest)["id"]

    with client.websocket_connect(f"/ws/rooms/{room['id']}?token={token}") as socket:
        socket.send_json({"event": "game:roulette_bet", "payload": {"color": "red"}})
        assert receive_until(socket, "error")["code"] == "no_active_round"

        socket.send_json({"event": "game:roulette_start", "payload": {}})
        started = receive_until(socket, "game:roulette_started")
        assert started["started_by"]["id"] == my_id and started["betting_seconds"] == 0.3

        socket.send_json({"event": "game:roulette_start", "payload": {}})
        assert receive_until(socket, "error")["code"] == "roulette_running"
        socket.send_json({"event": "game:roulette_bet", "payload": {"color": "mor"}})
        assert receive_until(socket, "error")["code"] == "invalid_color"

        socket.send_json({"event": "game:roulette_bet", "payload": {"color": "red"}})
        assert receive_until(socket, "game:roulette_bet_placed")["color"] == "red"

        result = receive_until(socket, "game:roulette_result")
        assert 0 <= result["number"] <= 36 and result["color"] == roulette_color(result["number"])
        assert result["player_count"] == 1
        # Kazananı istemci değil sunucu belirler: kırmızı geldiyse kazandım, gelmediyse kaybettim.
        assert [w["id"] for w in result["winners"]] == ([my_id] if result["color"] == "red" else [])


# ── Sesli görüşme (WebRTC) ────────────────────────────────────────────────────

def test_voice_join_info_and_signal_relay(client, guest):
    host = guest
    room = client.post(f"{API}/rooms", headers=host, json={"title": "Sesli"}).json()
    rooms = f"{API}/rooms/{room['id']}"
    listener, other = new_guest(client), new_guest(client)
    host_id, listener_id, other_id = room["host_id"], me(client, listener)["id"], me(client, other)["id"]
    token = lambda headers: headers["Authorization"].removeprefix("Bearer ")

    # Varsayılan sağlayıcı mesh: ICE sunucuları gelir; konuşma izni yalnızca koltuktakinde.
    info = client.get(f"{rooms}/voice", headers=host).json()
    assert info["provider"] == "mesh" and info["can_publish"] is True and info["ice_servers"]
    assert client.get(f"{rooms}/voice", headers=listener).json()["can_publish"] is False

    with client.websocket_connect(f"/ws/rooms/{room['id']}?token={token(host)}") as host_socket, \
            client.websocket_connect(f"/ws/rooms/{room['id']}?token={token(listener)}") as listener_socket, \
            client.websocket_connect(f"/ws/rooms/{room['id']}?token={token(other)}") as other_socket:
        receive_until(listener_socket, "room:listener_count")

        # Dinleyici → koltuktaki oda sahibi: iletilir, gönderen sunucu tarafından yazılır.
        offer = {"type": "offer", "sdp": "v=0 test"}
        listener_socket.send_json({"event": "voice:signal", "payload": {"to": host_id, "description": offer}})
        relayed = receive_until(host_socket, "voice:signal")
        assert relayed["from"] == listener_id and relayed["description"] == offer

        # İki dinleyici arasında ses kanalı açılamaz: mesaj iletilmez.
        listener_socket.send_json({"event": "voice:signal", "payload": {"to": other_id, "candidate": {"candidate": "x"}}})
        other_socket.send_json({"event": "chat:message", "payload": {"text": "işaret"}})
        assert receive_until(other_socket, "chat:message")["text"] == "işaret"   # araya voice:signal girmedi

        # Biçimi bozuk mesaj reddedilir.
        listener_socket.send_json({"event": "voice:signal", "payload": {"to": host_id, "description": {"type": "hack"}}})
        assert receive_until(listener_socket, "error")["code"] == "invalid_signal"


def test_turn_credentials_and_livekit_token():
    import base64
    import hashlib
    import hmac

    import jwt

    from app.voice.ice import turn_credentials
    from app.voice.livekit import LiveKitVoiceProvider

    # coturn "use-auth-secret": kullanıcı adı = bitiş zamanı:kullanıcı, parola = HMAC-SHA1.
    username, credential = turn_credentials(42, "gizli", 3600, now=1000)
    assert username == "4600:42"
    assert credential == base64.b64encode(hmac.new(b"gizli", b"4600:42", hashlib.sha1).digest()).decode()

    # LiveKit token'ı: doğru oda ve konuşma izni, LiveKit'in beklediği alan adlarıyla.
    import asyncio
    provider = LiveKitVoiceProvider("wss://ses.ornek.com", "APIkey", "s" * 32)
    info = asyncio.run(provider.join_info(7, 42, "Ayşe", can_publish=False))
    claims = jwt.decode(info.token, "s" * 32, algorithms=["HS256"])
    assert info.url == "wss://ses.ornek.com" and provider.api_url == "https://ses.ornek.com"
    assert claims["iss"] == "APIkey" and claims["sub"] == "42" and claims["name"] == "Ayşe"
    assert claims["video"] == {
        "room": "room-7", "roomJoin": True, "canPublish": False, "canSubscribe": True, "canPublishData": False,
    }
