"""
Gelir sistemleri testleri: mağaza (kozmetik), VIP üyelik, şanslı hediye, hediye paketi, hazine sandığı.
"""
import uuid

from tests.conftest import API
from tests.test_api import me, new_guest, receive_until


def rich_guest(client) -> dict:
    """En büyük coin paketini almış yeni misafir (500 + 46.800 coin)."""
    headers = new_guest(client)
    assert client.post(f"{API}/wallet/purchase", headers=headers, json={"package_id": 6}).status_code == 200
    return headers


def key() -> dict:
    return {"Idempotency-Key": uuid.uuid4().hex}


def store_item(client, headers, item_id: int) -> dict:
    return next(i for i in client.get(f"{API}/store/items", headers=headers).json() if i["id"] == item_id)


# ── Mağaza ────────────────────────────────────────────────────────────────────

def test_store_purchase_equips_and_shows_on_profile(client):
    user = rich_guest(client)
    before = me(client, user)["coin_balance"]
    frames = client.get(f"{API}/store/items", headers=user, params={"kind": "frame"}).json()
    assert frames and all(f["kind"] == "frame" and not f["is_owned"] for f in frames)

    # Aynı anahtarla iki kez gönderilen alım bir kez ücretlendirilir.
    headers = {**user, **key()}
    first = client.post(f"{API}/store/items/2/purchase", headers=headers, json={"days": 7})
    again = client.post(f"{API}/store/items/2/purchase", headers=headers, json={"days": 7})
    assert first.status_code == again.status_code == 200
    assert first.json()["coin_balance"] == again.json()["coin_balance"] == before - 500
    assert first.json()["item"]["is_owned"] and first.json()["item"]["is_equipped"]

    profile = me(client, user)
    assert profile["frame"] == "frame-neon" and profile["coin_balance"] == before - 500
    owned = client.get(f"{API}/users/{profile['id']}/items", headers=new_guest(client)).json()
    assert [i["id"] for i in owned] == [2]

    # Tekrar almak süreyi kalan sürenin üstüne ekler.
    until_7 = store_item(client, user, 2)["owned_until"]
    client.post(f"{API}/store/items/2/purchase", headers={**user, **key()}, json={"days": 30})
    assert store_item(client, user, 2)["owned_until"] > until_7

    # Aynı türden yenisi takılınca eskisi çıkar; çıkarınca çerçeve kalmaz.
    client.post(f"{API}/store/items/4/purchase", headers={**user, **key()}, json={"days": 7})
    assert me(client, user)["frame"] == "frame-ice" and not store_item(client, user, 2)["is_equipped"]
    assert client.put(f"{API}/store/items/2/equip", headers=user, json={"equipped": True}).json()["is_equipped"]
    assert me(client, user)["frame"] == "frame-neon" and not store_item(client, user, 4)["is_equipped"]
    client.put(f"{API}/store/items/2/equip", headers=user, json={"equipped": False})
    assert me(client, user)["frame"] is None


def test_store_rules(client, guest):
    # Fiyatı istemci belirleyemez; yalnızca 7 ya da 30 gün seçilebilir.
    assert client.post(f"{API}/store/items/1/purchase", headers=guest, json={"days": 1}).status_code == 422
    # 500 coinle 1500'lük eşya alınamaz; bakiye değişmez.
    poor = client.post(f"{API}/store/items/7/purchase", headers=guest, json={"days": 7})
    assert poor.status_code == 402 and me(client, guest)["coin_balance"] == 500
    # VIP'e özel eşya ve sahip olunmayan eşyayı takma.
    rich = rich_guest(client)
    vip_only = client.post(f"{API}/store/items/8/purchase", headers=rich, json={"days": 7})
    assert vip_only.status_code == 403 and vip_only.json()["code"] == "vip_required"
    not_owned = client.put(f"{API}/store/items/3/equip", headers=rich, json={"equipped": True})
    assert not_owned.status_code == 403 and not_owned.json()["code"] == "item_not_owned"
    assert client.post(f"{API}/store/items/999/purchase", headers=rich, json={"days": 7}).status_code == 404


def test_entry_effect_and_bubble_travel_with_user_in_room(client):
    user = rich_guest(client)
    client.post(f"{API}/store/items/103/purchase", headers={**user, **key()}, json={"days": 7})
    client.post(f"{API}/store/items/201/purchase", headers={**user, **key()}, json={"days": 7})
    token = user["Authorization"].removeprefix("Bearer ")

    with client.websocket_connect(f"/ws/rooms/107340?token={token}") as socket:
        joined = receive_until(socket, "room:user_joined")["user"]
        assert joined["entry_effect"] == {"name": "Roket", "style": "entry-rocket", "emoji": "🚀"}
        socket.send_json({"event": "chat:message", "payload": {"text": "Selam"}})
        assert receive_until(socket, "chat:message")["user"]["chat_bubble"] == "bubble-pink"


# ── VIP ───────────────────────────────────────────────────────────────────────

def test_vip_purchase_upgrade_items_and_daily_reward(client):
    user = rich_guest(client)
    status = client.get(f"{API}/vip", headers=user).json()
    assert status["level"] == 0 and not status["daily_reward_available"]
    assert [t["level"] for t in status["tiers"]] == [1, 2, 3]

    denied = client.post(f"{API}/vip/daily-reward", headers=user)
    assert denied.status_code == 403 and denied.json()["code"] == "vip_required"

    before = me(client, user)["coin_balance"]
    bought = client.post(f"{API}/vip/purchase", headers={**user, **key()}, json={"level": 1}).json()
    assert bought["coin_balance"] == before - 3000 and bought["status"]["level"] == 1
    profile = me(client, user)
    assert profile["vip_level"] == 1 and profile["frame"] == "frame-gold" and profile["chat_bubble"] == "bubble-neon"

    # Günlük ödül günde bir kez.
    reward = client.post(f"{API}/vip/daily-reward", headers=user)
    assert reward.status_code == 200 and reward.json()["coins"] == 60
    again = client.post(f"{API}/vip/daily-reward", headers=user)
    assert again.status_code == 409 and again.json()["code"] == "daily_reward_claimed"

    # Üst kademeye geçiş: VIP'e özel eşyalar artık alınabilir; alt kademe alınamaz.
    client.post(f"{API}/vip/purchase", headers={**user, **key()}, json={"level": 2})
    assert me(client, user)["vip_level"] == 2
    assert me(client, user)["entry_effect"]["style"] == "entry-crown"
    lower = client.post(f"{API}/vip/purchase", headers={**user, **key()}, json={"level": 1})
    assert lower.status_code == 409 and lower.json()["code"] == "vip_higher_active"
    assert client.post(f"{API}/store/items/8/purchase", headers={**user, **key()}, json={"days": 7}).status_code == 200


def test_expired_vip_is_not_shown(client):
    """Süresi dolan üyeliğin rozeti gösterilmez (seviye silinmez, `active_vip_level` 0 döner)."""
    from datetime import timedelta

    from app.core.database import utcnow
    from app.models import User

    user = User(username="x", display_name="X", vip_level=2, vip_expires_at=utcnow() - timedelta(seconds=1))
    assert user.active_vip_level() == 0
    user.vip_expires_at = utcnow() + timedelta(days=1)
    assert user.active_vip_level() == 2
    user.vip_expires_at = None   # örnek verideki süresiz üyelik
    assert user.active_vip_level() == 2


# ── Şanslı hediye ─────────────────────────────────────────────────────────────

def test_lucky_gift_pays_back_drawn_multiplier(client, guest, monkeypatch):
    from app.services import gift_service

    gifts = client.get(f"{API}/gifts", headers=guest).json()
    clover = next(g for g in gifts if g["name"] == "Şanslı Yonca")
    assert clover["is_lucky"] and not next(g for g in gifts if g["name"] == "Gül")["is_lucky"]

    receiver = new_guest(client)
    receiver_id = me(client, receiver)["id"]
    monkeypatch.setattr(gift_service, "_draw_multiplier", lambda: 10)
    sent = client.post(f"{API}/gifts/send", headers=guest,
                       json={"receiver_id": receiver_id, "gift_id": clover["id"], "quantity": 2}).json()
    # 2 × 10 coin harcandı, her adet için 10× çıktı → 200 coin geri döndü.
    assert sent["lucky_win"] == 200 and sent["lucky_multiplier"] == 10
    assert sent["coin_balance"] == 500 - 20 + 200
    # Alıcı şanslı hediyede %10 alır (normal hediyede %50).
    assert me(client, receiver)["diamond_balance"] == 2


def test_lucky_table_pays_back_less_than_spent():
    """Çarpan tablosu kullanıcıya ortalamada harcadığından az geri vermeli (yoksa bedava coin üretilir)."""
    from app.services.gift_service import LUCKY_TABLE, LUCKY_TABLE_TOTAL

    expected_return = sum(multiplier * weight for multiplier, weight in LUCKY_TABLE) / LUCKY_TABLE_TOTAL
    assert 0.5 < expected_return < 1


# ── Hediye paketi ─────────────────────────────────────────────────────────────

def test_one_time_bundle_gives_item_once(client, guest):
    packages = client.get(f"{API}/wallet/packages", headers=guest).json()
    starter = next(p for p in packages if p["title"] == "Başlangıç Paketi")
    assert starter["is_one_time"] and not starter["is_bought"] and starter["item"]["style"] == "frame-neon"
    assert packages[0]["title"] is not None   # paketler listenin başında

    bought = client.post(f"{API}/wallet/purchase", headers=guest, json={"package_id": starter["id"]}).json()
    assert bought["added"] == 900 and bought["item"]["id"] == 2
    assert me(client, guest)["frame"] == "frame-neon"

    again = client.post(f"{API}/wallet/purchase", headers=guest, json={"package_id": starter["id"]})
    assert again.status_code == 409 and again.json()["code"] == "package_already_bought"
    assert next(p for p in client.get(f"{API}/wallet/packages", headers=guest).json() if p["id"] == starter["id"])["is_bought"]


# ── Hazine sandığı ────────────────────────────────────────────────────────────

def test_treasure_chest_fills_opens_and_pays_once(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "chest_target_coins", 100)
    monkeypatch.setattr(settings, "chest_reward_percent", 50)   # sandıkta 50 coin
    host, outsider = rich_guest(client), new_guest(client)
    room = client.post(f"{API}/rooms", headers=host, json={"title": "Sandık Odası"}).json()
    token = host["Authorization"].removeprefix("Bearer ")

    with client.websocket_connect(f"/ws/rooms/{room['id']}?token={token}") as socket:
        receive_until(socket, "chat:history")   # odaya katılmış olduğumuzdan emin ol (bkz. test_api)
        closed = client.post(f"{API}/rooms/{room['id']}/chest/claim", headers=host)
        assert closed.status_code == 400 and closed.json()["code"] == "chest_closed"

        # 99 coinlik hediye sandığı doldurur ama açmaz; 10 coinlik ikincisi açar.
        gift = {"receiver_id": 2010, "room_id": room["id"]}
        client.post(f"{API}/gifts/send", headers=host, json={**gift, "gift_id": 5})
        assert receive_until(socket, "room:chest_updated")["chest"]["progress"] == 99
        client.post(f"{API}/gifts/send", headers=host, json={**gift, "gift_id": 1})
        opened = receive_until(socket, "room:chest_updated")["chest"]
        assert opened["status"] == "open" and opened["coins_left"] == 50

        # Odada olmayan alamaz; odadaki bir kez alır.
        away = client.post(f"{API}/rooms/{room['id']}/chest/claim", headers=outsider)
        assert away.status_code == 403 and away.json()["code"] == "not_in_room"
        before = me(client, host)["coin_balance"]
        claimed = client.post(f"{API}/rooms/{room['id']}/chest/claim", headers=host).json()
        assert 1 <= claimed["coins"] <= 50 and claimed["coin_balance"] == before + claimed["coins"]
        announced = receive_until(socket, "room:chest_claimed")
        assert announced["coins"] == claimed["coins"] and announced["coins_left"] == 50 - claimed["coins"]
        twice = client.post(f"{API}/rooms/{room['id']}/chest/claim", headers=host)
        assert twice.status_code == 409 and twice.json()["code"] == "chest_already_claimed"
        assert client.get(f"{API}/rooms/{room['id']}/chest", headers=host).json()["claimed_by_me"]
