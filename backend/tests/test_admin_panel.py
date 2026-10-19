"""
Masaüstü yönetim paneli testleri: finans, işlemler, mesaj okuma (denetim kaydıyla), oda sohbet
geçmişi, katalog düzenleme, VIP verme, duyuru.
"""
import logging

from tests.conftest import API
from tests.test_admin import admin  # noqa: F401  (fixture)
from tests.test_api import me, new_guest, receive_until, wait_until_registered


def test_admin_panel_requires_admin(client, guest):
    for path in ("/admin/finance", "/admin/transactions", "/admin/conversations", "/admin/catalog/gifts"):
        assert client.get(f"{API}{path}", headers=guest).status_code == 403


def test_finance_series_and_transactions(client, admin):  # noqa: F811
    buyer = new_guest(client)
    buyer_id = me(client, buyer)["id"]
    client.post(f"{API}/wallet/purchase", headers=buyer, json={"package_id": 2})          # 1.650 coin
    client.post(f"{API}/gifts/send", headers=buyer, json={"receiver_id": 2001, "gift_id": 6})  # 299

    finance = client.get(f"{API}/admin/finance", headers=admin, params={"days": 7}).json()
    assert len(finance["days"]) == 7
    today = finance["days"][-1]
    assert today["coins_sold"] >= 1650 and today["gift_coins"] >= 299 and today["new_users"] >= 1
    assert finance["totals"]["purchase"] >= 1650 and finance["top_spenders"]

    mine = client.get(f"{API}/admin/transactions", headers=admin, params={"user_id": buyer_id}).json()
    assert [t["type"] for t in mine][:2] == ["gift_sent", "purchase"]
    assert all(t["user"]["id"] == buyer_id for t in mine)
    purchases = client.get(f"{API}/admin/transactions", headers=admin, params={"type": "purchase", "limit": 5}).json()
    assert purchases and all(t["type"] == "purchase" for t in purchases)
    older = client.get(f"{API}/admin/transactions", headers=admin, params={"before_id": purchases[0]["id"], "limit": 5}).json()
    assert all(t["id"] < purchases[0]["id"] for t in older)


def test_admin_reads_private_and_room_messages_and_it_is_audited(client, admin, caplog):  # noqa: F811
    caplog.set_level(logging.INFO, logger="muti")
    a, b = new_guest(client), new_guest(client)
    a_id, b_id = me(client, a)["id"], me(client, b)["id"]
    conversation_id = client.post(f"{API}/conversations", headers=a, json={"user_id": b_id}).json()["id"]
    client.post(f"{API}/conversations/{conversation_id}/messages", headers=a, json={"text": "Gizli mesaj"})

    conversations = client.get(f"{API}/admin/conversations", headers=admin, params={"user_id": a_id}).json()
    assert conversations[0]["id"] == conversation_id and conversations[0]["message_count"] == 1
    messages = client.get(f"{API}/admin/conversations/{conversation_id}/messages", headers=admin).json()
    assert [(m["sender"]["id"], m["text"]) for m in messages] == [(a_id, "Gizli mesaj")]
    assert any(r.getMessage() == "admin_viewed_conversation" and r.fields["conversation_id"] == conversation_id
               for r in caplog.records)

    # Oda sohbeti artık kalıcı: odadan silinen mesaj da panelde "silindi" olarak görünür.
    room = client.post(f"{API}/rooms", headers=a, json={"title": "Kayıtlı Sohbet"}).json()
    token = a["Authorization"].removeprefix("Bearer ")
    with client.websocket_connect(f"/ws/rooms/{room['id']}?token={token}") as socket:
        receive_until(socket, "chat:history")
        socket.send_json({"event": "chat:message", "payload": {"text": "ilk"}})
        first = receive_until(socket, "chat:message")
        socket.send_json({"event": "chat:message", "payload": {"text": "ikinci"}})
        receive_until(socket, "chat:message")
        client.delete(f"{API}/rooms/{room['id']}/messages/{first['id']}", headers=a)
        receive_until(socket, "chat:message_deleted")
    log = client.get(f"{API}/admin/rooms/{room['id']}/messages", headers=admin).json()
    assert [(m["text"], m["deleted_at"] is not None) for m in log] == [("ilk", True), ("ikinci", False)]
    assert client.get(f"{API}/admin/rooms/999999/messages", headers=admin).status_code == 404


def test_catalog_editing_changes_what_users_see(client, admin, guest):  # noqa: F811
    gifts = client.get(f"{API}/admin/catalog/gifts", headers=admin).json()
    rose = next(g for g in gifts if g["name"] == "Gül")
    updated = client.patch(f"{API}/admin/catalog/gifts/{rose['id']}", headers=admin, json={"price": 15}).json()
    assert updated["price"] == 15
    assert next(g for g in client.get(f"{API}/gifts", headers=guest).json() if g["id"] == rose["id"])["price"] == 15
    client.patch(f"{API}/admin/catalog/gifts/{rose['id']}", headers=admin, json={"is_active": False})
    assert rose["id"] not in [g["id"] for g in client.get(f"{API}/gifts", headers=guest).json()]
    client.patch(f"{API}/admin/catalog/gifts/{rose['id']}", headers=admin, json={"is_active": True, "price": 10})
    assert client.patch(f"{API}/admin/catalog/gifts/{rose['id']}", headers=admin, json={"price": 0}).status_code == 422

    packages = client.get(f"{API}/admin/catalog/packages", headers=admin).json()
    first = packages[0]
    changed = client.patch(f"{API}/admin/catalog/packages/{first['id']}", headers=admin, json={"bonus": 99}).json()
    assert changed["bonus"] == 99
    client.patch(f"{API}/admin/catalog/packages/{first['id']}", headers=admin, json={"bonus": first["bonus"]})


def test_grant_vip_and_broadcast(client, admin):  # noqa: F811
    user = new_guest(client)
    user_id = me(client, user)["id"]
    granted = client.post(f"{API}/admin/users/{user_id}/vip", headers=admin, json={"level": 2, "days": 7}).json()
    assert granted["user"]["vip_level"] == 2 and me(client, user)["entry_effect"]["style"] == "entry-crown"
    assert me(client, user)["coin_balance"] == 500   # para hareketi yok
    assert client.post(f"{API}/admin/users/{user_id}/vip", headers=admin, json={"level": 4, "days": 7}).status_code == 422

    token = user["Authorization"].removeprefix("Bearer ")
    with client.websocket_connect(f"/ws/me?token={token}") as socket:
        wait_until_registered(socket)
        sent = client.post(f"{API}/admin/broadcast", headers=admin, json={"text": "Bakım bu gece 03:00'te"}).json()
        assert sent["sent"] > 10
        pushed = receive_until(socket, "notification:new")
        assert pushed["text"] == "📢 Bakım bu gece 03:00'te"


def test_user_list_sorting(client, admin):  # noqa: F811
    richest = client.get(f"{API}/admin/users", headers=admin, params={"sort": "richest"}).json()
    coins = [u["coin_balance"] for u in richest]
    assert coins == sorted(coins, reverse=True)
    reported = client.get(f"{API}/admin/users", headers=admin, params={"sort": "reported"}).json()
    counts = [u["reports_against"] for u in reported]
    assert counts == sorted(counts, reverse=True)
