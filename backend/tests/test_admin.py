"""
Yönetim paneli ve ajans testleri.
"""
from datetime import date

import pytest

from tests.conftest import API, auth_headers
from tests.test_api import me, new_guest
from tests.test_social import register


def staff_headers(client, username: str) -> dict:
    """Personel hesabıyla giriş yapar ve panel oturumunu açar (şifre ikinci kez sorulur)."""
    response = client.post(f"{API}/auth/login", json={"username": username, "password": "demo1234"})
    assert response.status_code == 200, response.text
    headers = auth_headers(response.json())
    session = client.post(f"{API}/admin/session", headers=headers, json={"password": "demo1234"})
    assert session.status_code == 200, session.text
    return {**headers, "X-Staff-Token": session.json()["staff_token"]}


def adult_birth_date() -> str:
    return date(date.today().year - 25, 1, 15).isoformat()


def make_host(client, headers) -> None:
    """Kişiyi başvuru + panel onayıyla yayıncı yapar (ajansa yalnızca yayıncılar katılır)."""
    applied = client.post(f"{API}/hosts/apply", headers=headers, json={
        "birth_date": adult_birth_date(), "intro": "Akşamları sohbet odası açıyorum.", "accept_rules": True,
    })
    assert applied.status_code == 200, applied.text
    moderator = staff_headers(client, "moderator")
    pending = client.get(f"{API}/admin/host-applications", headers=moderator).json()
    application = next(a for a in pending if a["user"]["id"] == me(client, headers)["id"])
    reviewed = client.post(f"{API}/admin/host-applications/{application['id']}/review", headers=moderator,
                           json={"approve": True})
    assert reviewed.status_code == 200, reviewed.text


@pytest.fixture
def admin(client) -> dict:
    return staff_headers(client, "admin")


def test_admin_endpoints_are_admin_only(client, admin, guest):
    for path in ("/admin/stats", "/admin/reports", "/admin/users", "/admin/rooms", "/admin/agencies"):
        denied = client.get(f"{API}{path}", headers=guest)
        assert denied.status_code == 403 and denied.json()["code"] == "staff_only"
    stats = client.get(f"{API}/admin/stats", headers=admin).json()
    assert stats["users_total"] > 10 and stats["open_reports"] >= 3 and stats["rooms_active"] >= 6
    assert me(client, admin)["staff_role"] == "admin" and me(client, guest)["staff_role"] is None


def test_ban_is_immediate_and_reversible(client, admin):
    user = register(client, "banlanacak")
    user_id = me(client, user)["id"]
    login = {"username": "banlanacak", "password": "gizli123"}
    refresh_token = client.post(f"{API}/auth/login", json=login).json()["refresh_token"]

    with client.websocket_connect(f"/ws/me?token={user['Authorization'].removeprefix('Bearer ')}") as socket:
        banned = client.post(f"{API}/admin/users/{user_id}/ban", headers=admin, json={"reason": "Spam hesap"}).json()
        assert banned["is_active"] is False
        # Açık bağlantı kapatıldı.
        assert socket.receive()["code"] == 4401

    # Süresi dolmamış token anında reddedilir; yenileme ve giriş de olmaz.
    assert client.get(f"{API}/users/me", headers=user).json()["code"] == "account_disabled"
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": refresh_token}).status_code == 401
    assert client.post(f"{API}/auth/login", json=login).json()["code"] == "account_disabled"
    assert client.post(f"{API}/admin/users/{user_id}/ban", headers=admin, json={"reason": "tekrar"}).json()["code"] == "already_banned"

    # Banlı kullanıcı yönetici aramasında görünür.
    found = client.get(f"{API}/admin/users", headers=admin, params={"query": "banlanacak"}).json()
    assert [(u["user"]["id"], u["is_active"]) for u in found] == [(user_id, False)]

    client.delete(f"{API}/admin/users/{user_id}/ban", headers=admin)
    assert client.post(f"{API}/auth/login", json=login).status_code == 200

    admin_id = me(client, admin)["id"]
    assert client.post(f"{API}/admin/users/{admin_id}/ban", headers=admin, json={"reason": "deneme"}).json()["code"] == "cannot_ban_staff"


def test_reports_are_resolved_together(client, admin):
    reports = client.get(f"{API}/admin/reports", headers=admin).json()
    burak = [r for r in reports if r["target_type"] == "user" and r["target_id"] == 2006]
    assert len(burak) == 2 and burak[0]["target_label"] == "Burak" and burak[0]["reporter"]

    wrong = client.post(f"{API}/admin/reports/{burak[0]['id']}/resolve", headers=admin, json={"action": "close_room"})
    assert wrong.status_code == 400 and wrong.json()["code"] == "invalid_report_action"
    done = client.post(f"{API}/admin/reports/{burak[0]['id']}/resolve", headers=admin,
                       json={"action": "dismiss", "note": "Kanıt yok"})
    assert done.status_code == 204
    # Aynı kişi hakkındaki diğer şikâyet de kapandı.
    assert not [r for r in client.get(f"{API}/admin/reports", headers=admin).json() if r["target_id"] == 2006]
    closed = [r for r in client.get(f"{API}/admin/reports", headers=admin, params={"status": "closed"}).json() if r["target_id"] == 2006]
    assert {r["status"] for r in closed} == {"dismissed"} and closed[0]["resolution_note"] == "Kanıt yok"
    again = client.post(f"{API}/admin/reports/{burak[1]['id']}/resolve", headers=admin, json={"action": "dismiss"})
    assert again.status_code == 409

    # Oda şikâyeti: oda kapatılır.
    room_report = next(r for r in reports if r["target_type"] == "room")
    client.post(f"{API}/admin/reports/{room_report['id']}/resolve", headers=admin, json={"action": "close_room"})
    assert client.get(f"{API}/rooms/{room_report['target_id']}", headers=admin).status_code == 404


def test_report_can_ban_user(client, admin):
    reporter, target = new_guest(client), new_guest(client)
    target_id = me(client, target)["id"]
    client.post(f"{API}/reports", headers=reporter, json={"target_type": "user", "target_id": target_id, "reason": "fraud"})
    report = next(r for r in client.get(f"{API}/admin/reports", headers=admin).json() if r["target_id"] == target_id)
    client.post(f"{API}/admin/reports/{report['id']}/resolve", headers=admin, json={"action": "ban_user", "note": "Dolandırıcılık"})
    assert client.get(f"{API}/users/me", headers=target).status_code == 401


def test_balance_adjustment_is_written_to_ledger(client, admin, guest):
    user_id = me(client, guest)["id"]
    added = client.post(f"{API}/admin/users/{user_id}/balance", headers=admin,
                        json={"currency": "coin", "amount": 250, "reason": "Hatalı ödeme iadesi"}).json()
    assert added == {"currency": "coin", "balance": 750}
    too_much = client.post(f"{API}/admin/users/{user_id}/balance", headers=admin,
                           json={"currency": "coin", "amount": -10_000, "reason": "Düzeltme"})
    assert too_much.status_code == 402
    assert client.post(f"{API}/admin/users/{user_id}/balance", headers=admin,
                       json={"currency": "coin", "amount": 0, "reason": "x y z"}).status_code == 422
    detail = client.get(f"{API}/admin/users/{user_id}", headers=admin).json()
    assert detail["coin_balance"] == 750
    assert detail["recent_transactions"][0]["label"] == "Yönetici düzeltmesi: Hatalı ödeme iadesi"


def test_admin_room_list_and_close(client, admin, guest):
    room = client.post(f"{API}/rooms", headers=guest, json={"title": "Kapatılacak"}).json()
    assert room["id"] in [r["id"] for r in client.get(f"{API}/admin/rooms", headers=admin).json()]
    assert client.delete(f"{API}/admin/rooms/{room['id']}", headers=admin).status_code == 204
    assert client.get(f"{API}/rooms/{room['id']}", headers=guest).status_code == 404
    assert client.delete(f"{API}/admin/rooms/{room['id']}", headers=admin).status_code == 404


# ── Ajans ─────────────────────────────────────────────────────────────────────

def test_agency_flow(client, admin):
    owner, host, other, fan = new_guest(client), register(client, "ajans_akis_yayincisi"), new_guest(client), new_guest(client)
    owner_id, host_id = me(client, owner)["id"], me(client, host)["id"]
    make_host(client, host)

    # Komisyon üst sınırı (.env AGENCY_COMMISSION_MAX_PERCENT = 15) aşılamaz.
    too_high = client.post(f"{API}/admin/agencies", headers=admin,
                           json={"name": "Test Ajans", "owner_id": owner_id, "commission_percent": 20})
    assert too_high.json()["code"] == "commission_too_high"
    agency = client.post(f"{API}/admin/agencies", headers=admin,
                         json={"name": "Test Ajans", "owner_id": owner_id, "commission_percent": 10}).json()
    assert agency["owner"]["id"] == owner_id and agency["member_count"] == 0
    duplicate = client.post(f"{API}/admin/agencies", headers=admin, json={"name": "Başka", "owner_id": owner_id})
    assert duplicate.status_code == 409

    assert client.post(f"{API}/agencies/me/members/{host_id}", headers=other).json()["code"] == "not_agency_owner"
    dashboard = client.post(f"{API}/agencies/me/members/{host_id}", headers=owner).json()
    assert dashboard["members"][0]["status"] == "invited"
    assert client.post(f"{API}/agencies/me/members/{host_id}", headers=owner).json()["code"] == "already_in_agency"

    invite = client.get(f"{API}/agencies/me", headers=host).json()
    assert invite["role"] is None and invite["invite"]["name"] == "Test Ajans"
    joined = client.post(f"{API}/agencies/me/invite/accept", headers=host).json()
    assert joined["role"] == "member" and joined["agency"]["member_count"] == 1

    # Yayıncı hediye aldıkça ajans paneli bu ayki kazancı ve tahmini komisyonu gösterir.
    client.put(f"{API}/agencies/me/members/{host_id}/target", headers=owner, json={"monthly_target": 1000})
    # 299 coin: ajans yayıncısı %60 → 179 elmas (bağımsız olsaydı %50 → 149); ajans %10 → 29 elmas
    client.post(f"{API}/gifts/send", headers=fan, json={"receiver_id": host_id, "gift_id": 6})
    panel = client.get(f"{API}/agencies/me", headers=owner).json()
    assert panel["role"] == "owner"
    member = panel["dashboard"]["members"][0]
    assert (member["month_diamonds"], member["monthly_target"], member["progress_percent"]) == (179, 1000, 17)
    assert panel["dashboard"]["estimated_commission"] == 299 * 10 // 100
    assert client.get(f"{API}/agencies/me", headers=host).json()["my_month_diamonds"] == 179
    income = client.get(f"{API}/wallet/income", headers=host).json()
    assert (income["share_percent"], income["agency_name"]) == (60, "Test Ajans")

    left = client.delete(f"{API}/agencies/me/membership", headers=host).json()
    assert left["role"] is None and client.delete(f"{API}/agencies/me/membership", headers=host).status_code == 400
    # Ajanstan ayrılınca bağımsız pay (%50); ajansa yeni kazanç yazılmaz ama geçmiş kazancı durur.
    client.post(f"{API}/admin/users/{me(client, fan)['id']}/balance", headers=admin,
                json={"currency": "coin", "amount": 500, "reason": "Test coini"})
    client.post(f"{API}/gifts/send", headers=fan, json={"receiver_id": host_id, "gift_id": 6})
    assert client.get(f"{API}/agencies/me", headers=host).json()["my_month_diamonds"] == 179 + 149
    assert client.get(f"{API}/agencies/me", headers=owner).json()["dashboard"]["estimated_commission"] == 29
    assert client.get(f"{API}/wallet/income", headers=host).json()["share_percent"] == 50

    # Davet reddedilebilir ve sahibi daveti geri çekebilir.
    client.post(f"{API}/agencies/me/members/{host_id}", headers=owner)
    assert client.post(f"{API}/agencies/me/invite/decline", headers=host).json()["invite"] is None
    client.post(f"{API}/agencies/me/members/{host_id}", headers=owner)
    assert client.delete(f"{API}/agencies/me/members/{host_id}", headers=owner).json()["members"] == []
    assert client.post(f"{API}/agencies/me/invite/accept", headers=host).status_code == 404


def test_revenue_rates_are_public_to_users(client, guest):
    rates = client.get(f"{API}/economy/rates", headers=guest).json()
    assert (rates["independent_host_percent"], rates["agency_host_percent"], rates["agency_commission_max_percent"]) == (50, 60, 15)
    # Ajans yayıncısı + en yüksek komisyon bile hediyenin tamamını almaz: sahte hediye döngüsü zarar ettirir
    assert rates["agency_host_percent"] + rates["agency_commission_max_percent"] < 100


def test_seeded_agency_invite_for_main_user(client, muti):
    mine = client.get(f"{API}/agencies/me", headers=muti).json()
    assert mine["invite"]["name"] == "Yıldız Ajans" and mine["invite"]["commission_percent"] == 15
