"""
Yönetim paneli rolleri ve panel oturumu testleri: rol yetkileri, şifreyle açılan panel oturumu,
kayan süre, kritik işlemde şifreyi yeniden sorma, personel yönetimi ve işlem kaydı.
"""
import time

from app.core.security import create_staff_token
from tests.conftest import API, auth_headers
from tests.test_admin import admin, staff_headers  # noqa: F401  (fixture)
from tests.test_api import me, new_guest
from tests.test_social import register


def _old_session(client, headers: dict, seconds_ago: int) -> dict:
    """Şifresi `seconds_ago` saniye önce girilmiş gibi bir panel oturumu."""
    token, _ = create_staff_token(me(client, headers)["id"], int(time.time()) - seconds_ago)
    return {**headers, "X-Staff-Token": token}


def test_panel_needs_its_own_password_session(client):
    login = client.post(f"{API}/auth/login", json={"username": "admin", "password": "demo1234"}).json()
    headers = auth_headers(login)

    # Uygulama oturumu tek başına panele yetmez.
    missing = client.get(f"{API}/admin/stats", headers=headers)
    assert missing.status_code == 401 and missing.json()["code"] == "staff_session_required"

    wrong = client.post(f"{API}/admin/session", headers=headers, json={"password": "yanlis"})
    assert wrong.status_code == 401 and wrong.json()["code"] == "staff_password_invalid"

    session = client.post(f"{API}/admin/session", headers=headers, json={"password": "demo1234"}).json()
    assert session["role"] == "admin" and "staff.manage" in session["permissions"] and session["expires_in"] > 0

    # Her başarılı istekte süresi uzatılmış token cevapla geri gelir (kayan pencere).
    ok = client.get(f"{API}/admin/stats", headers={**headers, "X-Staff-Token": session["staff_token"]})
    assert ok.status_code == 200 and ok.headers["X-Staff-Token"]
    # Sayfa yenilenince açık oturumun rolü ve yetkileri yeniden okunur.
    current = client.get(f"{API}/admin/session", headers={**headers, "X-Staff-Token": session["staff_token"]}).json()
    assert current["role"] == "admin" and current["idle_minutes"] == 15

    # Başka bir kişinin panel token'ı işe yaramaz.
    moderator = staff_headers(client, "moderator")
    stolen = client.get(f"{API}/admin/stats", headers={**headers, "X-Staff-Token": moderator["X-Staff-Token"]})
    assert stolen.json()["code"] == "staff_session_required"

    # Personel olmayan biri oturum açamaz.
    guest = new_guest(client)
    assert client.post(f"{API}/admin/session", headers=guest, json={"password": "x"}).json()["code"] == "staff_only"


def test_session_expires_after_shift_and_asks_password_for_critical_actions(client, admin):  # noqa: F811
    target_id = me(client, new_guest(client))["id"]

    # 12 saatten eski şifre: oturum uzatılmaz, kapanır.
    expired = _old_session(client, admin, 13 * 3600)
    assert client.get(f"{API}/admin/session", headers=expired).json()["code"] == "staff_session_required"

    # 10 dk önce girilmiş şifre: bakmak serbest, ban için şifre yeniden sorulur.
    stale = _old_session(client, admin, 600)
    assert client.get(f"{API}/admin/users/{target_id}", headers=stale).status_code == 200
    denied = client.post(f"{API}/admin/users/{target_id}/ban", headers=stale, json={"reason": "Spam hesap"})
    assert denied.status_code == 401 and denied.json()["code"] == "staff_reauth_required"

    # Uzatılmış token şifrenin girildiği anı korur: uzatma, kritik işlem iznini tazelemez.
    renewed = client.get(f"{API}/admin/stats", headers=stale).headers["X-Staff-Token"]
    again = client.post(f"{API}/admin/users/{target_id}/ban", headers={**admin, "X-Staff-Token": renewed}, json={"reason": "Spam hesap"})
    assert again.json()["code"] == "staff_reauth_required"

    # Şifre yeniden girilince olur.
    assert client.post(f"{API}/admin/users/{target_id}/ban", headers=admin, json={"reason": "Spam hesap"}).status_code == 200


def test_roles_only_reach_their_own_pages(client):
    moderator, finance = staff_headers(client, "moderator"), staff_headers(client, "finance")
    target_id = me(client, new_guest(client))["id"]

    def code(response):
        return response.status_code, response.json().get("code") if response.status_code >= 400 else None

    # Moderatör: şikâyet, ban, oda, mesaj evet; para ve personel hayır.
    assert client.get(f"{API}/admin/reports", headers=moderator).status_code == 200
    assert client.get(f"{API}/admin/rooms", headers=moderator).status_code == 200
    for method, path, body in [
        ("get", "/admin/finance", None), ("get", "/admin/transactions", None), ("get", "/admin/staff", None),
        ("get", "/admin/catalog/gifts", None), ("get", "/admin/staff/actions", None),
        ("post", f"/admin/users/{target_id}/balance", {"currency": "coin", "amount": 5, "reason": "deneme"}),
    ]:
        assert code(client.request(method, f"{API}{path}", headers=moderator, json=body)) == (403, "permission_denied"), path

    # Finans: para evet; ban, şikâyet, mesaj hayır.
    assert client.get(f"{API}/admin/finance", headers=finance).status_code == 200
    added = client.post(f"{API}/admin/users/{target_id}/balance", headers=finance,
                        json={"currency": "coin", "amount": 5, "reason": "İade"})
    assert added.status_code == 200
    for method, path, body in [
        ("post", f"/admin/users/{target_id}/ban", {"reason": "deneme"}), ("get", "/admin/reports", None),
        ("get", "/admin/conversations", None), ("post", "/admin/broadcast", {"text": "Merhaba herkes"}),
    ]:
        assert code(client.request(method, f"{API}{path}", headers=finance, json=body)) == (403, "permission_denied"), path

    # Moderatör ban yapabilir; personeli banlayamaz.
    assert client.post(f"{API}/admin/users/{target_id}/ban", headers=moderator, json={"reason": "Spam hesap"}).status_code == 200
    finance_id = me(client, finance)["id"]
    staff_ban = client.post(f"{API}/admin/users/{finance_id}/ban", headers=moderator, json={"reason": "deneme"})
    assert staff_ban.json()["code"] == "cannot_ban_staff"


def test_report_decision_needs_matching_permission(client):
    moderator = staff_headers(client, "moderator")
    reporter, target = new_guest(client), new_guest(client)
    target_id = me(client, target)["id"]
    client.post(f"{API}/reports", headers=reporter, json={"target_type": "user", "target_id": target_id, "reason": "spam"})
    report = next(r for r in client.get(f"{API}/admin/reports", headers=moderator).json() if r["target_id"] == target_id)

    stale = _old_session(client, moderator, 600)
    denied = client.post(f"{API}/admin/reports/{report['id']}/resolve", headers=stale, json={"action": "ban_user", "note": "Spam"})
    assert denied.json()["code"] == "staff_reauth_required"
    resolved = client.post(f"{API}/admin/reports/{report['id']}/resolve", headers=moderator, json={"action": "ban_user", "note": "Spam"})
    assert resolved.status_code == 204 and resolved.headers["X-Staff-Token"]


def test_admin_manages_staff_and_sees_action_log(client, admin):  # noqa: F811
    new_staff = register(client, "yenimod")
    new_staff_id = me(client, new_staff)["id"]
    admin_id = me(client, admin)["id"]

    granted = client.put(f"{API}/admin/staff/{new_staff_id}", headers=admin, json={"role": "moderator"}).json()
    assert granted["role"] == "moderator" and granted["role_label"] == "Moderatör"
    assert new_staff_id in [m["user"]["id"] for m in client.get(f"{API}/admin/staff", headers=admin).json()]
    assert client.put(f"{API}/admin/staff/{new_staff_id}", headers=admin, json={"role": "moderator"}).json()["code"] == "role_unchanged"

    # Yeni moderatör kendi şifresiyle panele girer.
    session = client.post(f"{API}/admin/session", headers=new_staff, json={"password": "gizli123"}).json()
    panel = {**new_staff, "X-Staff-Token": session["staff_token"]}
    assert client.get(f"{API}/admin/reports", headers=panel).status_code == 200

    # Rol alınınca açık panel bir sonraki istekte kapanır.
    assert client.put(f"{API}/admin/staff/{new_staff_id}", headers=admin, json={"role": None}).json() is None
    assert client.get(f"{API}/admin/reports", headers=panel).json()["code"] == "staff_only"

    # Kural: kendi rolünü değiştiremez, misafire rol verilmez, rol adı bilinmeli.
    assert client.put(f"{API}/admin/staff/{admin_id}", headers=admin, json={"role": "finance"}).json()["code"] == "cannot_change_own_role"
    guest_id = me(client, new_guest(client))["id"]
    assert client.put(f"{API}/admin/staff/{guest_id}", headers=admin, json={"role": "finance"}).json()["code"] == "guest_account"
    assert client.put(f"{API}/admin/staff/{new_staff_id}", headers=admin, json={"role": "owner"}).status_code == 422
    assert client.put(f"{API}/admin/staff/999999", headers=admin, json={"role": "finance"}).status_code == 404

    log = client.get(f"{API}/admin/staff/actions", headers=admin, params={"actor_id": admin_id, "limit": 5}).json()
    assert [entry["action"] for entry in log[:2]] == ["staff_role_changed", "staff_role_changed"]
    assert log[0]["actor"]["id"] == admin_id and log[0]["target_id"] == new_staff_id and log[0]["detail"] == "Moderatör → yok"
    older = client.get(f"{API}/admin/staff/actions", headers=admin, params={"before_id": log[0]["id"], "limit": 1}).json()
    assert older[0]["id"] < log[0]["id"]
