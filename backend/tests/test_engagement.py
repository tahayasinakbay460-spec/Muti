"""
Bağlılık sistemleri testleri: günlük giriş, görevler, aile, CP, sıralamalar, etkinlikler.
"""
from datetime import timedelta

from tests.conftest import API
from tests.test_api import me, new_guest, receive_until, wait_until_registered


def rich_guest(client) -> dict:
    headers = new_guest(client)
    client.post(f"{API}/wallet/purchase", headers=headers, json={"package_id": 6})   # +46.800 coin
    return headers


def token(headers: dict) -> str:
    return headers["Authorization"].removeprefix("Bearer ")


# ── Günlük giriş ──────────────────────────────────────────────────────────────

def test_daily_checkin_once_a_day_and_streak(client, monkeypatch):
    from app.core.timefmt import local_today
    from app.services import engagement_service

    user = new_guest(client)
    status = client.get(f"{API}/rewards/checkin", headers=user).json()
    assert status == {"day": 1, "claimed_today": False, "rewards": [10, 20, 30, 50, 80, 120, 200]}

    claimed = client.post(f"{API}/rewards/checkin", headers=user).json()
    assert claimed["day"] == 1 and claimed["coins"] == 10 and claimed["coin_balance"] == 510
    again = client.post(f"{API}/rewards/checkin", headers=user)
    assert again.status_code == 409 and again.json()["code"] == "checkin_claimed"

    # Ertesi gün 2. gün ödülü; bir gün atlanırsa döngü baştan başlar.
    today = local_today()
    monkeypatch.setattr(engagement_service, "local_today", lambda: today + timedelta(days=1))
    assert client.post(f"{API}/rewards/checkin", headers=user).json()["coins"] == 20
    monkeypatch.setattr(engagement_service, "local_today", lambda: today + timedelta(days=3))
    assert client.get(f"{API}/rewards/checkin", headers=user).json()["day"] == 1


# ── Görevler ──────────────────────────────────────────────────────────────────

def test_tasks_progress_and_reward_once(client):
    user = new_guest(client)
    tasks = {t["id"]: t for t in client.get(f"{API}/tasks", headers=user).json()}
    assert tasks["follow_1"]["progress"] == 0 and not tasks["follow_1"]["claimed"]

    early = client.post(f"{API}/tasks/follow_1/claim", headers=user)
    assert early.status_code == 400 and early.json()["code"] == "task_not_completed"

    client.post(f"{API}/users/2001/follow", headers=user)
    with client.websocket_connect(f"/ws/rooms/107340?token={token(user)}") as socket:
        receive_until(socket, "chat:history")
        for i in range(5):
            socket.send_json({"event": "chat:message", "payload": {"text": f"mesaj {i}"}})
            receive_until(socket, "chat:message")

    tasks = {t["id"]: t for t in client.get(f"{API}/tasks", headers=user).json()}
    assert tasks["follow_1"]["progress"] == 1 and tasks["join_room"]["progress"] == 1
    assert tasks["chat_5"]["progress"] == 5 and tasks["gift_3"]["progress"] == 0

    before = me(client, user)["coin_balance"]
    reward = client.post(f"{API}/tasks/chat_5/claim", headers=user).json()
    assert reward["coins"] == 20 and reward["coin_balance"] == before + 20
    twice = client.post(f"{API}/tasks/chat_5/claim", headers=user)
    assert twice.status_code == 409 and twice.json()["code"] == "task_claimed"
    assert client.post(f"{API}/tasks/yok/claim", headers=user).status_code == 404

    for _ in range(3):
        client.post(f"{API}/gifts/send", headers=user, json={"receiver_id": 2010, "gift_id": 1})
    assert next(t for t in client.get(f"{API}/tasks", headers=user).json() if t["id"] == "gift_3")["progress"] == 3


# ── Aile ──────────────────────────────────────────────────────────────────────

def test_family_lifecycle(client, monkeypatch):
    from app.services import family_service

    owner, member, other = rich_guest(client), new_guest(client), new_guest(client)
    member_id = me(client, member)["id"]
    before = me(client, owner)["coin_balance"]

    family = client.post(f"{API}/families", headers=owner, json={"name": "Test Ailesi", "badge": "🐺"}).json()
    assert family["my_role"] == "owner" and family["member_count"] == 1
    assert me(client, owner)["coin_balance"] == before - 2000
    assert me(client, owner)["family"] == {"id": family["id"], "name": "Test Ailesi", "badge": "🐺"}

    taken = client.post(f"{API}/families", headers=rich_guest(client), json={"name": "Test Ailesi", "badge": "🐺"})
    assert taken.status_code == 409 and taken.json()["code"] == "family_name_taken"
    again = client.post(f"{API}/families", headers=owner, json={"name": "İkinci", "badge": "🐺"})
    assert again.status_code == 409 and again.json()["code"] == "already_in_family"

    joined = client.post(f"{API}/families/{family['id']}/join", headers=member).json()
    assert joined["member_count"] == 2 and joined["my_role"] == "member"
    # Dolu aileye girilemez.
    monkeypatch.setattr(family_service, "FAMILY_MAX_MEMBERS", 2)
    full = client.post(f"{API}/families/{family['id']}/join", headers=other)
    assert full.status_code == 409 and full.json()["code"] == "family_full"
    monkeypatch.setattr(family_service, "FAMILY_MAX_MEMBERS", 50)

    # Üye yönetici yapamaz ve kimseyi çıkaramaz; kurucu ayrılamaz.
    assert client.put(f"{API}/families/{family['id']}/members/{member_id}/role", headers=member,
                      json={"role": "admin"}).status_code == 403
    assert client.delete(f"{API}/families/me/membership", headers=owner).json()["code"] == "owner_cannot_leave"

    # Aile sohbeti: yalnızca üyeler; mesaj üyelere anında gider.
    with client.websocket_connect(f"/ws/me?token={token(member)}") as socket:
        wait_until_registered(socket)
        sent = client.post(f"{API}/families/{family['id']}/messages", headers=owner, json={"text": " Hoş geldin "})
        assert sent.status_code == 201 and sent.json()["text"] == "Hoş geldin"
        pushed = receive_until(socket, "family:message")
        assert pushed["family_id"] == family["id"] and pushed["message"]["text"] == "Hoş geldin"
    assert client.get(f"{API}/families/{family['id']}/messages", headers=other).status_code == 403
    assert [m["text"] for m in client.get(f"{API}/families/{family['id']}/messages", headers=member).json()] == ["Hoş geldin"]

    # Kurucu üyeyi çıkarır; üye ailesiz kalır.
    kicked = client.delete(f"{API}/families/{family['id']}/members/{member_id}", headers=owner).json()
    assert kicked["member_count"] == 1 and me(client, member)["family"] is None

    # Dağıtılınca aile ve üyelikler silinir.
    assert client.delete(f"{API}/families/{family['id']}", headers=owner).status_code == 204
    assert client.get(f"{API}/families/me", headers=owner).json() is None
    assert client.get(f"{API}/families/{family['id']}", headers=owner).status_code == 404


def test_family_roles_settings_and_leaving(client):
    owner, admin, member = rich_guest(client), new_guest(client), new_guest(client)
    admin_id, member_id, owner_id = me(client, admin)["id"], me(client, member)["id"], me(client, owner)["id"]
    family = client.post(f"{API}/families", headers=owner, json={"name": "Roller", "badge": "🎯"}).json()
    rooms = f"{API}/families/{family['id']}"
    client.post(f"{rooms}/join", headers=admin)
    client.post(f"{rooms}/join", headers=member)
    again = client.post(f"{rooms}/join", headers=member)
    assert again.status_code == 409 and again.json()["code"] == "already_in_family"

    # Rolü yalnızca kurucu verir; yönetici slogan değiştirebilir, üye değiştiremez.
    roles = client.put(f"{rooms}/members/{admin_id}/role", headers=owner, json={"role": "admin"}).json()
    assert next(m for m in roles["members"] if m["user"]["id"] == admin_id)["role"] == "admin"
    assert client.put(f"{rooms}/members/{owner_id}/role", headers=owner, json={"role": "member"}).status_code == 404
    assert client.patch(rooms, headers=admin, json={"slogan": " Birlikte güçlüyüz "}).json()["slogan"] == "Birlikte güçlüyüz"
    assert client.patch(rooms, headers=member, json={"slogan": "x"}).status_code == 403

    # Yönetici kurucuyu çıkaramaz; üye ayrılabilir, ayrılınca tekrar ailesiz.
    higher = client.delete(f"{rooms}/members/{owner_id}", headers=admin)
    assert higher.status_code == 403 and higher.json()["code"] == "cannot_kick_higher"
    assert client.delete(f"{API}/families/me/membership", headers=member).status_code == 204
    assert client.get(f"{API}/families/me", headers=member).json() is None
    left = client.get(rooms, headers=owner).json()
    assert left["member_count"] == 2 and member_id not in [m["user"]["id"] for m in left["members"]]
    not_in = client.delete(f"{API}/families/me/membership", headers=member)
    assert not_in.status_code == 400 and not_in.json()["code"] == "not_in_family"


def test_family_list_and_seeded_families(client):
    families = client.get(f"{API}/families", headers=new_guest(client)).json()
    assert {"Gece Kuşları", "Aslanlar", "Müzik Kulübü"} <= {f["name"] for f in families}
    found = client.get(f"{API}/families", headers=new_guest(client), params={"query": "aslan"}).json()
    assert [f["name"] for f in found] == ["Aslanlar"]


# ── CP ────────────────────────────────────────────────────────────────────────

def test_couple_propose_decline_refund_accept_and_one_cp_rule(client):
    a, b, c = rich_guest(client), rich_guest(client), rich_guest(client)
    a_id, b_id = me(client, a)["id"], me(client, b)["id"]
    a_coins = me(client, a)["coin_balance"]

    proposed = client.post(f"{API}/couples/{b_id}", headers=a).json()
    assert proposed["outgoing"][0]["partner"]["id"] == b_id and me(client, a)["coin_balance"] == a_coins - 520
    assert client.get(f"{API}/couples/me", headers=b).json()["incoming"][0]["partner"]["id"] == a_id
    duplicate = client.post(f"{API}/couples/{a_id}", headers=b)
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "cp_request_exists"

    # Reddedilince bedel iade edilir.
    client.delete(f"{API}/couples/{a_id}/request", headers=b)
    assert me(client, a)["coin_balance"] == a_coins

    # C de B'ye teklif eder; B, A'nın teklifini kabul edince C'nin teklifi iadeyle kapanır.
    c_coins = me(client, c)["coin_balance"]
    client.post(f"{API}/couples/{b_id}", headers=a)
    client.post(f"{API}/couples/{b_id}", headers=c)
    own = client.post(f"{API}/couples/{b_id}/accept", headers=a)
    assert own.status_code == 400 and own.json()["code"] == "cannot_accept_own"
    accepted = client.post(f"{API}/couples/{a_id}/accept", headers=b).json()
    assert accepted["active"]["partner"]["id"] == a_id and accepted["incoming"] == []
    assert me(client, a)["cp_partner_id"] == b_id and me(client, b)["cp_partner_id"] == a_id
    assert me(client, c)["coin_balance"] == c_coins and client.get(f"{API}/couples/me", headers=c).json()["outgoing"] == []

    # Aynı anda tek CP.
    taken = client.post(f"{API}/couples/{a_id}", headers=c)
    assert taken.status_code == 409 and taken.json()["code"] == "cp_taken"

    # CP puanı: birbirlerine gönderdikleri hediyeler.
    client.post(f"{API}/gifts/send", headers=a, json={"receiver_id": b_id, "gift_id": 2})
    assert client.get(f"{API}/couples/me", headers=b).json()["active"]["cp_coins"] == 20

    broken = client.delete(f"{API}/couples/me", headers=b).json()
    assert broken["active"] is None and me(client, a)["cp_partner_id"] is None


# ── Sıralamalar ve etkinlikler ────────────────────────────────────────────────

def test_leaderboards(client):
    sender, receiver = rich_guest(client), new_guest(client)
    sender_id, receiver_id = me(client, sender)["id"], me(client, receiver)["id"]
    room = client.post(f"{API}/rooms", headers=sender, json={"title": "Sıralama Odası"}).json()
    sent = client.post(f"{API}/gifts/send", headers=sender,
                       json={"receiver_id": receiver_id, "gift_id": 11, "room_id": room["id"]})   # 19.999 coin
    assert sent.status_code == 200

    # Aynı test veritabanında başka testler de hediye gönderiyor: sıra değil, puan ve tutarlılık kontrol edilir.
    rich = client.get(f"{API}/leaderboards", headers=sender, params={"kind": "rich", "period": "day"}).json()
    assert rich["me"]["user"]["id"] == sender_id and rich["me"]["score"] == 19999
    scores = [e["score"] for e in rich["entries"]]
    assert scores == sorted(scores, reverse=True) and [e["rank"] for e in rich["entries"]] == list(range(1, len(scores) + 1))
    assert rich["entries"][rich["me"]["rank"] - 1]["user"]["id"] == sender_id
    charm = client.get(f"{API}/leaderboards", headers=receiver, params={"kind": "charm", "period": "week"}).json()
    assert charm["me"]["user"]["id"] == receiver_id and charm["me"]["score"] == 19999 * 50 // 100
    rooms = client.get(f"{API}/leaderboards", headers=sender, params={"kind": "rooms", "period": "month"}).json()
    assert room["id"] in [e["room"]["id"] for e in rooms["entries"]]
    families = client.get(f"{API}/leaderboards", headers=sender, params={"kind": "families"}).json()
    assert families["kind"] == "families" and isinstance(families["entries"], list)
    assert client.get(f"{API}/leaderboards", headers=sender, params={"kind": "yanlis"}).status_code == 422


def test_event_rewards_paid_once_after_end(client, monkeypatch):
    from app.core.database import utcnow
    from app.services import event_service

    events = client.get(f"{API}/events", headers=new_guest(client)).json()
    weekend = next(e for e in events if e["title"] == "Hafta Sonu Hediye Yarışı")
    assert weekend["status"] == "active" and events[0]["status"] == "active"

    # Etkinlikte açık ara birinci ol: örnek veride bugün 184.500 coinlik gönderim var, onu geç.
    winner = rich_guest(client)
    for _ in range(4):
        client.post(f"{API}/wallet/purchase", headers=winner, json={"package_id": 6})
    for _ in range(4):   # 4 × 49.999 coin
        assert client.post(f"{API}/gifts/send", headers=winner, json={"receiver_id": 2010, "gift_id": 12}).status_code == 200
    detail = client.get(f"{API}/events/{weekend['id']}", headers=winner).json()
    assert detail["me"]["rank"] == 1

    # Zaman ileri sarılır: etkinlik bitti. İlk bakış ödülü dağıtır, ikincisi tekrar dağıtmaz.
    later = utcnow() + timedelta(days=8)
    monkeypatch.setattr(event_service, "utcnow", lambda: later)
    before = me(client, winner)["coin_balance"]
    ended = client.get(f"{API}/events/{weekend['id']}", headers=winner).json()
    client.get(f"{API}/events/{weekend['id']}", headers=winner)
    client.get(f"{API}/events", headers=winner)
    assert ended["status"] == "ended"
    assert me(client, winner)["coin_balance"] == before + 5000
