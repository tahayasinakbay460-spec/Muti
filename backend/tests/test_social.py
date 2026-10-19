"""
Arama, engelleme, şikâyet, bildirim, seviye, yayıncı geliri ve hesap ayarları testleri.
"""
from tests.conftest import API, auth_headers
from tests.test_api import me, new_guest, receive_until


def register(client, username: str) -> dict:
    response = client.post(f"{API}/auth/register", json={
        "username": username, "email": f"{username}@example.com", "password": "gizli123",
    })
    assert response.status_code == 201, response.text
    return auth_headers(response.json())


def test_user_search_by_name_username_and_id(client, muti):
    by_name = client.get(f"{API}/users/search", headers=muti, params={"query": "mer"}).json()
    assert by_name and all("mer" in (u["display_name"] + u["username"]).lower() for u in by_name)
    by_id = client.get(f"{API}/users/search", headers=muti, params={"query": "2001"}).json()
    assert [u["id"] for u in by_id] == [2001]
    # SQL joker karakterleri düz karakter sayılır: "%" her şeyi eşleştirmez.
    assert client.get(f"{API}/users/search", headers=muti, params={"query": "%"}).json() == []


def test_block_stops_messages_gifts_follows_and_hides_from_search(client, guest):
    blocker, other = guest, new_guest(client)
    blocker_id, other_id = me(client, blocker)["id"], me(client, other)["id"]
    client.post(f"{API}/users/{other_id}/follow", headers=blocker)
    client.post(f"{API}/users/{blocker_id}/follow", headers=other)
    conversation_id = client.post(f"{API}/conversations", headers=other, json={"user_id": blocker_id}).json()["id"]

    assert client.put(f"{API}/users/{other_id}/block", headers=blocker).json() == {"is_blocked": True}
    # Takipler iki yönde de kalktı, sayaçlar düzeldi.
    assert me(client, blocker)["following_count"] == 0 and me(client, blocker)["friends_count"] == 0
    assert client.get(f"{API}/users/{other_id}", headers=blocker).json()["is_blocked"] is True

    # Engellenen taraf da (kim engellediyse) mesaj, hediye ve takip yapamaz.
    sent = client.post(f"{API}/conversations/{conversation_id}/messages", headers=other, json={"text": "selam"})
    assert sent.status_code == 403 and sent.json()["code"] == "user_blocked"
    gift = client.post(f"{API}/gifts/send", headers=other, json={"receiver_id": blocker_id, "gift_id": 1})
    assert gift.json()["code"] == "user_blocked"
    assert client.post(f"{API}/users/{blocker_id}/follow", headers=other).json()["code"] == "user_blocked"
    blocker_name = me(client, blocker)["username"]
    assert client.get(f"{API}/users/search", headers=other, params={"query": blocker_name}).json() == []

    assert [u["id"] for u in client.get(f"{API}/users/me/blocks", headers=blocker).json()] == [other_id]
    assert client.delete(f"{API}/users/{other_id}/block", headers=blocker).json() == {"is_blocked": False}
    assert client.post(f"{API}/conversations/{conversation_id}/messages", headers=other, json={"text": "selam"}).status_code == 201


def test_reports_are_recorded_once(client, guest):
    payload = {"target_type": "user", "target_id": 2001, "reason": "spam", "details": " reklam "}
    assert client.post(f"{API}/reports", headers=guest, json=payload).status_code == 204
    assert client.post(f"{API}/reports", headers=guest, json=payload).status_code == 204   # tekrar: yine "alındı"
    assert client.post(f"{API}/reports", headers=guest, json={**payload, "reason": "kotu"}).status_code == 422
    my_id = me(client, guest)["id"]
    assert client.post(f"{API}/reports", headers=guest, json={**payload, "target_id": my_id}).json()["code"] == "cannot_report_self"
    assert client.post(f"{API}/reports", headers=guest, json={**payload, "target_type": "room", "target_id": 999999}).status_code == 404


def test_gift_gives_experience_level_income_and_notifications(client, guest):
    sender, receiver = guest, new_guest(client)
    receiver_id = me(client, receiver)["id"]
    token = receiver["Authorization"].removeprefix("Bearer ")

    with client.websocket_connect(f"/ws/me?token={token}") as socket:
        # Taç 299 coin: gönderen 299 XP kazanır → Lv.2 (100 XP), alan 149 elmas kazanır.
        client.post(f"{API}/gifts/send", headers=sender, json={"receiver_id": receiver_id, "gift_id": 6, "quantity": 1})
        pushed = receive_until(socket, "notification:new")
        assert pushed["type"] == "gift_received" and pushed["actor"]["id"] == me(client, sender)["id"]

    profile = me(client, sender)
    gift_price = 500 - profile["coin_balance"]
    assert profile["experience"] == gift_price and profile["level"] >= 2
    assert profile["next_level_experience"] > profile["experience"]
    sender_notes = client.get(f"{API}/notifications", headers=sender).json()
    assert sender_notes[0]["type"] == "level_up"

    # Bildirim merkezi: okunmamış sayısı, sonra hepsini okundu say.
    assert client.get(f"{API}/notifications/unread-count", headers=receiver).json() == {"unread_count": 1}
    assert client.post(f"{API}/notifications/read", headers=receiver).status_code == 204
    assert client.get(f"{API}/notifications/unread-count", headers=receiver).json() == {"unread_count": 0}

    # Yayıncı geliri: kazanılan elmaslar, en çok destek olan ve elmas → coin çevirme.
    income = client.get(f"{API}/wallet/income", headers=receiver).json()
    earned = gift_price // 2
    assert income["diamond_balance"] == income["today_diamonds"] == income["total_diamonds"] == earned
    assert income["top_supporters"][0]["diamonds"] == earned and income["withdrawals_enabled"] is False

    key = {"Idempotency-Key": "exchange-key-1"}
    first = client.post(f"{API}/wallet/exchange", headers={**receiver, **key}, json={"diamonds": 10}).json()
    again = client.post(f"{API}/wallet/exchange", headers={**receiver, **key}, json={"diamonds": 10}).json()
    assert first["diamond_balance"] == earned - 10 and first["coin_balance"] == 510 and again == first
    too_much = client.post(f"{API}/wallet/exchange", headers=receiver, json={"diamonds": 10_000})
    assert too_much.status_code == 402
    assert me(client, receiver)["diamond_balance"] == earned - 10   # yetmeyen çevirme hiçbir şeyi değiştirmedi


def test_follow_and_room_role_notifications(client, guest):
    follower, target = guest, new_guest(client)
    target_id = me(client, target)["id"]
    client.post(f"{API}/users/{target_id}/follow", headers=follower)
    room = client.post(f"{API}/rooms", headers=follower, json={"title": "Bildirim"}).json()
    client.put(f"{API}/rooms/{room['id']}/roles/{target_id}", headers=follower, json={"role": "vip"})

    notes = client.get(f"{API}/notifications", headers=target).json()
    assert [n["type"] for n in notes] == ["room_role", "follow"]
    assert notes[0]["data"] == {"room_id": room["id"]}


def test_change_password_and_delete_account(client):
    headers = register(client, "silinecek_uye")
    user_id = me(client, headers)["id"]

    bad = client.post(f"{API}/auth/change-password", headers=headers, json={"current_password": "yanlis", "new_password": "yeni123"})
    assert bad.status_code == 401
    changed = client.post(f"{API}/auth/change-password", headers=headers, json={"current_password": "gizli123", "new_password": "yeni123"})
    assert changed.status_code == 200
    headers = auth_headers(changed.json())
    assert client.post(f"{API}/auth/login", json={"username": "silinecek_uye", "password": "yeni123"}).status_code == 200

    guest = new_guest(client)
    assert client.post(f"{API}/auth/change-password", headers=guest, json={"current_password": "x", "new_password": "yeni123"}).json()["code"] == "guest_account"

    assert client.request("DELETE", f"{API}/users/me", headers=headers, json={"password": "yanlis"}).status_code == 401
    assert client.request("DELETE", f"{API}/users/me", headers=headers, json={"password": "yeni123"}).status_code == 204
    # Hesap kapandı: giriş yapılamaz, profil bulunamaz, kullanıcı adı boşa çıktı.
    assert client.post(f"{API}/auth/login", json={"username": "silinecek_uye", "password": "yeni123"}).status_code == 401
    assert client.get(f"{API}/users/{user_id}", headers=guest).status_code == 404
    assert client.get(f"{API}/users/me", headers=headers).status_code == 401
    # Misafir hesap parolasız silinebilir.
    assert client.request("DELETE", f"{API}/users/me", headers=guest, json={}).status_code == 204
