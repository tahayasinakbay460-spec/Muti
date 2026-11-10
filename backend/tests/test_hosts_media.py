"""
Yayıncılık (başvuru, onay, ajans şartı), ajans ay sonu komisyonu ve fotoğraf yükleme testleri.
"""
from datetime import date

from tests.conftest import API
from tests.test_admin import adult_birth_date, make_host, staff_headers
from tests.test_api import me, new_guest
from tests.test_social import register

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200          # imzası PNG olan küçük dosya
FAKE_JPEG = b"<html><script>alert(1)</script></html>"  # adı jpeg, içi değil


# ── Yayıncılık ────────────────────────────────────────────────────────────────

def test_host_application_rules_and_review(client, guest):
    assert client.post(f"{API}/hosts/apply", headers=guest, json={
        "birth_date": adult_birth_date(), "intro": "Misafir olarak deniyorum.", "accept_rules": True,
    }).json()["code"] == "guest_cannot_apply"

    user = register(client, "yayinci_aday")
    young = date(date.today().year - 16, 1, 1).isoformat()
    assert client.post(f"{API}/hosts/apply", headers=user, json={
        "birth_date": young, "intro": "On altı yaşındayım ama denerim.", "accept_rules": True,
    }).json()["code"] == "underage"
    # Kuralları kabul etmeden başvuru olmaz
    assert client.post(f"{API}/hosts/apply", headers=user, json={
        "birth_date": adult_birth_date(), "intro": "Kural kutusu boş.", "accept_rules": False,
    }).status_code == 422

    status = client.post(f"{API}/hosts/apply", headers=user, json={
        "birth_date": adult_birth_date(), "intro": "Müzik odası açmak istiyorum.", "accept_rules": True,
    }).json()
    assert status["application"]["status"] == "pending" and not status["can_apply"]
    assert client.post(f"{API}/hosts/apply", headers=user, json={
        "birth_date": adult_birth_date(), "intro": "İkinci kez başvuruyorum.", "accept_rules": True,
    }).json()["code"] == "cannot_apply_now"

    # Finans rolü başvuru göremez; moderatör reddeder, sebep kişiye gider
    finance = staff_headers(client, "finance")
    assert client.get(f"{API}/admin/host-applications", headers=finance).status_code == 403
    moderator = staff_headers(client, "moderator")
    application = next(a for a in client.get(f"{API}/admin/host-applications", headers=moderator).json()
                       if a["user"]["id"] == me(client, user)["id"])
    assert application["age"] == 25 or application["age"] == 24
    rejected = client.post(f"{API}/admin/host-applications/{application['id']}/review", headers=moderator,
                           json={"approve": False, "note": "Tanıtım çok kısa"}).json()
    assert rejected["status"] == "rejected"
    # Aynı başvuruya ikinci karar verilemez
    again = client.post(f"{API}/admin/host-applications/{application['id']}/review", headers=moderator, json={"approve": True})
    assert again.json()["code"] == "already_reviewed"
    status = client.get(f"{API}/hosts/me", headers=user).json()
    assert not status["is_host"] and not status["can_apply"] and status["reapply_after"]
    assert any("Tanıtım çok kısa" in n["text"] for n in client.get(f"{API}/notifications", headers=user).json())


def test_only_hosts_join_agencies_and_revoke_removes_membership(client):
    owner = register(client, "ajans_sahibi_h")
    host = register(client, "ajans_yayincisi_h")
    owner_id, host_id = me(client, owner)["id"], me(client, host)["id"]
    admin = staff_headers(client, "admin")
    client.post(f"{API}/admin/agencies", headers=admin, json={"name": "Yayıncı Ajansı", "owner_id": owner_id})

    # Yayıncı olmayan davet edilemez
    assert client.post(f"{API}/agencies/me/members/{host_id}", headers=owner).json()["code"] == "not_host"
    make_host(client, host)
    assert me(client, host)["is_host"]
    client.post(f"{API}/agencies/me/members/{host_id}", headers=owner)
    assert client.post(f"{API}/agencies/me/invite/accept", headers=host).json()["role"] == "member"

    # Yayıncılık geri alınınca ajanstan da çıkar
    assert client.post(f"{API}/admin/hosts/{host_id}/revoke", headers=admin, json={"note": "Kural ihlali"}).status_code == 204
    assert not me(client, host)["is_host"]
    assert client.get(f"{API}/agencies/me", headers=host).json()["role"] is None


# ── Ajans ay sonu komisyonu ───────────────────────────────────────────────────

def test_agency_month_settlement_pays_once(client):
    finance = staff_headers(client, "finance")
    this_month = date.today().strftime("%Y-%m")
    agency_id = 1   # örnek veri: Yıldız Ajans (sahibi mert)
    assert client.post(f"{API}/admin/agencies/{agency_id}/settle", headers=finance,
                       json={"month": this_month}).json()["code"] == "month_not_finished"

    overview = client.get(f"{API}/admin/agency-settlements", headers=finance).json()
    row = next(r for r in overview if r["agency_id"] == agency_id)
    assert not row["settled"]
    month = row["month"]
    owner = client.post(f"{API}/auth/login", json={"username": "mert", "password": "demo1234"}).json()
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    before = me(client, owner_headers)["diamond_balance"]

    paid = client.post(f"{API}/admin/agencies/{agency_id}/settle", headers=finance, json={"month": month}).json()
    assert paid["settled"] and paid["commission_diamonds"] == paid["host_diamonds"] * paid["commission_percent"] // 100
    assert me(client, owner_headers)["diamond_balance"] == before + paid["commission_diamonds"]
    # İkinci kez ödenmez
    assert client.post(f"{API}/admin/agencies/{agency_id}/settle", headers=finance,
                       json={"month": month}).json()["code"] == "already_settled"
    assert me(client, owner_headers)["diamond_balance"] == before + paid["commission_diamonds"]
    # Moderatörün para yetkisi yok
    moderator = staff_headers(client, "moderator")
    assert client.post(f"{API}/admin/agencies/{agency_id}/settle", headers=moderator, json={"month": month}).status_code == 403
    # Ajans sahibi panelinde geçmiş ödemeyi görür
    dashboard = client.get(f"{API}/agencies/me", headers=owner_headers).json()["dashboard"]
    assert dashboard["settlements"][0]["month"] == month


# ── Fotoğraf ──────────────────────────────────────────────────────────────────

def upload(client, headers, kind, data=PNG, content_type="image/png"):
    return client.post(f"{API}/media", headers={**headers, "Content-Type": content_type}, params={"kind": kind}, content=data)


def test_image_upload_rules_and_ownership(client, guest):
    assert upload(client, guest, "avatar").json()["code"] == "guest_cannot_upload"
    user, other = register(client, "foto_sahibi"), register(client, "foto_hirsizi")
    assert upload(client, user, "avatar", FAKE_JPEG, "image/jpeg").json()["code"] == "invalid_image_file"
    assert upload(client, user, "avatar", PNG, "application/pdf").json()["code"] == "unsupported_image"
    assert upload(client, user, "chat").status_code == 422      # sohbet fotoğrafı bu uçtan yüklenmez

    avatar = upload(client, user, "avatar")
    assert avatar.status_code == 201, avatar.text
    url = avatar.json()["url"]
    # Herkese açık adres token istemez ve türü doğru söyler
    image = client.get(url)
    assert image.status_code == 200 and image.content == PNG
    assert image.headers["content-type"] == "image/png" and image.headers["x-content-type-options"] == "nosniff"

    assert client.patch(f"{API}/users/me", headers=user, json={"avatar_url": url}).json()["avatar_url"] == url
    # Başkası bu fotoğrafı kendi profiline koyamaz; avatar için yüklenen kapak olamaz
    assert client.patch(f"{API}/users/me", headers=other, json={"avatar_url": url}).json()["code"] == "invalid_avatar"
    assert client.patch(f"{API}/users/me", headers=user, json={"cover_url": url}).json()["code"] == "invalid_cover"
    assert client.patch(f"{API}/users/me", headers=user,
                        json={"avatar_url": "https://kotu-site.example/x.jpg"}).json()["code"] == "invalid_avatar"
    # Uydurma ad
    assert client.get(f"{API}/media/images/{'0' * 32}.png").status_code == 404
    assert client.get(f"{API}/media/images/..%2F..%2F.env").status_code == 404

    # Anı ve oda kapağı
    moment_url = upload(client, user, "moment").json()["url"]
    moment = client.post(f"{API}/moments", headers=user, json={"text": "Yeni fotoğraf", "image_url": moment_url})
    assert moment.status_code == 201 and moment.json()["image_url"] == moment_url
    room = client.post(f"{API}/rooms", headers=user, json={"title": "Fotoğraflı oda"}).json()
    cover_url = upload(client, user, "room_cover").json()["url"]
    updated = client.patch(f"{API}/rooms/{room['id']}", headers=user, json={"cover_url": cover_url})
    assert updated.json()["cover_url"] == cover_url
    assert client.patch(f"{API}/rooms/{room['id']}", headers=user, json={"cover_url": moment_url}).json()["code"] == "invalid_cover"


def test_chat_photo_is_private(client):
    sender, receiver, stranger = register(client, "foto_gonderen"), register(client, "foto_alan"), new_guest(client)
    chat_id = client.post(f"{API}/conversations", headers=sender, json={"user_id": me(client, receiver)["id"]}).json()["id"]
    sent = client.post(f"{API}/conversations/{chat_id}/image", headers={**sender, "Content-Type": "image/png"}, content=PNG)
    assert sent.status_code == 201, sent.text
    message = sent.json()
    assert message["kind"] == "image" and message["text"] == "📷 Fotoğraf"
    assert client.get(f"{API}{message['media_url']}", headers=receiver).content == PNG
    assert client.get(f"{API}{message['media_url']}", headers=stranger).status_code == 404
    assert client.get(f"{API}{message['media_url']}").status_code == 401


def test_account_deletion_removes_public_photos(client):
    user = register(client, "foto_silinecek")
    url = upload(client, user, "avatar").json()["url"]
    client.patch(f"{API}/users/me", headers=user, json={"avatar_url": url})
    assert client.get(url).status_code == 200
    assert client.request("DELETE", f"{API}/users/me", headers=user, json={"password": "gizli123"}).status_code == 204
    assert client.get(url).status_code == 404
