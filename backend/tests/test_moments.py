"""
Anılar, ziyaretçiler, takipçiler (arkadaşlık istekleri), profil başarıları, yayın odam ve ajans başvurusu.
"""
from tests.conftest import API, auth_headers
from tests.test_admin import make_host
from tests.test_social import register


def login(client, username: str) -> dict:
    response = client.post(f"{API}/auth/login", json={"username": username, "password": "demo1234"})
    assert response.status_code == 200, response.text
    return auth_headers(response.json())


# ── Anılar ────────────────────────────────────────────────────────────────────

def test_moment_feeds_and_paging(client, muti):
    explore = client.get(f"{API}/moments?feed=explore", headers=muti).json()
    assert len(explore) >= 10
    ids = [m["id"] for m in explore]
    assert ids == sorted(ids, reverse=True)
    # İmleçli sayfalama: before_id'den eskiler gelir
    older = client.get(f"{API}/moments?feed=explore&before_id={ids[2]}", headers=muti).json()
    assert all(m["id"] < ids[2] for m in older)

    # Takip akışı: yalnızca takip ettiklerim (Merve, Selin) ve ben
    following = client.get(f"{API}/moments?feed=following", headers=muti).json()
    authors = {m["user"]["id"] for m in following}
    assert authors and authors <= {102938, 2001, 2003}
    assert client.get(f"{API}/moments?feed=nope", headers=muti).status_code == 422


def test_create_like_delete_moment(client, muti):
    images = client.get(f"{API}/moments/image-options", headers=muti).json()["images"]
    assert images

    # Boş paylaşım ve listede olmayan görsel reddedilir
    assert client.post(f"{API}/moments", headers=muti, json={"text": "   "}).status_code == 422
    bad = client.post(f"{API}/moments", headers=muti, json={"text": "x", "image_url": "https://evil.example/a.jpg"})
    assert bad.status_code == 400 and bad.json()["code"] == "invalid_image"

    created = client.post(f"{API}/moments", headers=muti, json={"text": " Merhaba anılar ", "image_url": images[0]})
    assert created.status_code == 201
    moment = created.json()
    assert moment["text"] == "Merhaba anılar" and moment["is_mine"] and moment["like_count"] == 0
    assert client.get(f"{API}/users/102938/moments", headers=muti).json()[0]["id"] == moment["id"]

    merve = login(client, "merve")
    liked = client.post(f"{API}/moments/{moment['id']}/like", headers=merve).json()
    assert liked == {"is_liked": True, "like_count": 1}
    seen_by_merve = client.get(f"{API}/users/102938/moments", headers=merve).json()[0]
    assert seen_by_merve["is_liked"] and not seen_by_merve["is_mine"]
    # Sahibine bildirim gider
    notes = client.get(f"{API}/notifications", headers=muti).json()
    assert any(n["type"] == "moment_like" and n["data"].get("moment_id") == moment["id"] for n in notes)
    assert client.post(f"{API}/moments/{moment['id']}/like", headers=merve).json() == {"is_liked": False, "like_count": 0}

    # Başkasının anısını silemez; sahibi siler
    denied = client.delete(f"{API}/moments/{moment['id']}", headers=merve)
    assert denied.status_code == 403 and denied.json()["code"] == "not_moment_owner"
    assert client.delete(f"{API}/moments/{moment['id']}", headers=muti).status_code == 204
    assert client.post(f"{API}/moments/{moment['id']}/like", headers=merve).status_code == 404
    assert client.delete(f"{API}/moments/{moment['id']}", headers=muti).status_code == 404


def test_moment_comments(client, muti, guest):
    merve, selin = login(client, "merve"), login(client, "selin")
    moment = client.post(f"{API}/moments", headers=muti, json={"text": "Yorum denemesi"}).json()
    base = f"{API}/moments/{moment['id']}/comments"

    assert client.post(base, headers=merve, json={"text": "   "}).status_code == 422
    denied = client.post(base, headers=guest, json={"text": "selam"})
    assert denied.status_code == 403 and denied.json()["code"] == "guest_cannot_post"

    first = client.post(base, headers=merve, json={"text": " Çok güzel! "})
    assert first.status_code == 201 and first.json()["text"] == "Çok güzel!" and first.json()["can_delete"]
    second = client.post(base, headers=selin, json={"text": "Katılıyorum"}).json()

    comments = client.get(base, headers=muti).json()
    assert [c["id"] for c in comments] == [first.json()["id"], second["id"]]     # eskiden yeniye
    assert all(c["can_delete"] for c in comments)                                 # anının sahibi hepsini silebilir
    assert not client.get(base, headers=selin).json()[0]["can_delete"]           # başkasının yorumu
    assert client.get(f"{API}/users/102938/moments", headers=muti).json()[0]["comment_count"] == 2
    notes = client.get(f"{API}/notifications", headers=muti).json()
    assert any(n["type"] == "moment_comment" and n["data"].get("moment_id") == moment["id"] for n in notes)

    # Başkasının yorumunu silemez; anının sahibi siler
    denied = client.delete(f"{base}/{first.json()['id']}", headers=selin)
    assert denied.status_code == 403 and denied.json()["code"] == "not_comment_owner"
    assert client.delete(f"{base}/{first.json()['id']}", headers=muti).status_code == 204
    assert client.delete(f"{base}/{first.json()['id']}", headers=muti).status_code == 404
    assert client.delete(f"{base}/{second['id']}", headers=selin).status_code == 204
    assert client.get(base, headers=muti).json() == []
    assert client.get(f"{API}/users/102938/moments", headers=muti).json()[0]["comment_count"] == 0
    assert client.get(f"{API}/moments/999999/comments", headers=muti).status_code == 404

    # Yorumlu anı silinince yorumlar da gider
    client.post(base, headers=merve, json={"text": "son"})
    assert client.delete(f"{API}/moments/{moment['id']}", headers=muti).status_code == 204


def test_follow_lists_of_any_profile(client, muti):
    # Muti, Merve (2001) ve Selin'i (2003) takip ediyor
    following = client.get(f"{API}/users/102938/following", headers=muti).json()
    assert {2001, 2003} <= {u["id"] for u in following}
    merve = login(client, "merve")
    followers = client.get(f"{API}/users/2001/followers", headers=merve).json()
    assert 102938 in {u["id"] for u in followers}
    assert client.get(f"{API}/users/999999/followers", headers=muti).status_code == 404

    # Engel varsa liste boş; engellediğim kişi başkasının listesinde de görünmez
    assert client.put(f"{API}/users/2001/block", headers=muti).status_code == 200
    assert client.get(f"{API}/users/2001/following", headers=muti).json() == []
    assert 2001 not in {u["id"] for u in client.get(f"{API}/users/102938/following", headers=muti).json()}
    client.delete(f"{API}/users/2001/block", headers=muti)


def test_guest_cannot_post_and_blocked_moments_hidden(client, guest, muti):
    denied = client.post(f"{API}/moments", headers=guest, json={"text": "selam"})
    assert denied.status_code == 403 and denied.json()["code"] == "guest_cannot_post"

    blocker = register(client, "momentblocker")
    merve_moments = client.get(f"{API}/users/2001/moments", headers=blocker).json()
    assert merve_moments
    assert client.put(f"{API}/users/2001/block", headers=blocker).status_code == 200
    assert client.get(f"{API}/users/2001/moments", headers=blocker).json() == []
    explore = client.get(f"{API}/moments?feed=explore", headers=blocker).json()
    assert all(m["user"]["id"] != 2001 for m in explore)
    # Engelliyken beğenemez
    assert client.post(f"{API}/moments/{merve_moments[0]['id']}/like", headers=blocker).status_code == 403
    assert client.get(f"{API}/users/999999/moments", headers=muti).status_code == 404


# ── Ziyaretçiler ve takipçiler ────────────────────────────────────────────────

def test_profile_visits_are_recorded_once(client, muti):
    visitor = register(client, "profilevisitor")
    before = client.get(f"{API}/users/me", headers=muti).json()["visitors_count"]
    for _ in range(2):
        assert client.get(f"{API}/users/102938", headers=visitor).status_code == 200
    me = client.get(f"{API}/users/me", headers=muti).json()
    assert me["visitors_count"] == before + 1     # iki bakış, tek ziyaretçi

    visitors = client.get(f"{API}/users/me/visitors", headers=muti).json()
    assert visitors[0]["user"]["username"] == "profilevisitor"
    # Kendi profiline bakmak sayılmaz
    client.get(f"{API}/users/102938", headers=muti)
    assert client.get(f"{API}/users/me", headers=muti).json()["visitors_count"] == before + 1


def test_followers_become_friend_requests(client):
    fan = register(client, "friendlyfan")
    target = register(client, "friendtarget")
    target_id = client.get(f"{API}/users/me", headers=target).json()["id"]
    fan_id = client.get(f"{API}/users/me", headers=fan).json()["id"]

    client.post(f"{API}/users/{target_id}/follow", headers=fan)
    followers = client.get(f"{API}/users/me/followers", headers=target).json()
    assert [f["id"] for f in followers] == [fan_id] and followers[0]["is_following"] is False   # istek

    # Geri takip = arkadaş
    client.post(f"{API}/users/{fan_id}/follow", headers=target)
    followers = client.get(f"{API}/users/me/followers", headers=target).json()
    assert followers[0]["is_following"] is True
    assert client.get(f"{API}/users/me", headers=target).json()["friends_count"] == 1


def test_profile_extras_are_computed(client, muti):
    extras = client.get(f"{API}/users/102938/profile", headers=muti).json()
    assert extras["stats"]["rooms_count"] >= 1 and extras["stats"]["gifts_sent_coins"] > 0
    achievements = {a["id"]: a for a in extras["achievements"]}
    assert achievements["host"]["is_unlocked"] and achievements["first_moment"]["is_unlocked"]
    assert achievements["loyal"]["is_unlocked"]           # 428 gündür üye
    # Kazanılanlar önde
    flags = [a["is_unlocked"] for a in extras["achievements"]]
    assert flags == sorted(flags, reverse=True)
    assert client.get(f"{API}/users/999999/profile", headers=muti).status_code == 404


# ── Yayın odam ────────────────────────────────────────────────────────────────

def test_my_rooms_dashboard_and_room_followers(client, muti, guest):
    mine = client.get(f"{API}/rooms/mine", headers=muti).json()
    assert mine, "örnek veride ana kullanıcının odası var"
    stats = mine[0]
    assert stats["room"]["host_id"] == 102938
    assert stats["follower_count"] == 5 and stats["gift_count"] >= 4 and stats["gift_diamonds"] >= 4600
    assert 0 <= stats["month_gift_diamonds"] <= stats["gift_diamonds"]
    assert client.get(f"{API}/rooms/mine", headers=guest).json() == []

    room_id = stats["room"]["id"]
    followers = client.get(f"{API}/rooms/{room_id}/followers", headers=muti).json()
    assert len(followers) == 5
    denied = client.get(f"{API}/rooms/{room_id}/followers", headers=guest)
    assert denied.status_code == 403


# ── Ajans: liste, başvuru, kabul, seviyeler ───────────────────────────────────

def test_agency_application_flow(client):
    owner = login(client, "mert")          # Yıldız Ajans'ın sahibi
    agencies = client.get(f"{API}/agencies?query=yıldız", headers=owner).json()
    assert agencies and agencies[0]["name"] == "Yıldız Ajans"
    agency_id = agencies[0]["id"]
    assert client.get(f"{API}/agencies?query={agency_id}", headers=owner).json()[0]["id"] == agency_id

    host = register(client, "agencyapplicant")
    make_host(client, host)
    host_id = client.get(f"{API}/users/me", headers=host).json()["id"]
    state = client.get(f"{API}/agencies/me", headers=host).json()
    assert state["role"] is None and state["tiers"][0]["min_diamonds"] == 0 and state["my_tier_index"] == 0

    assert client.post(f"{API}/agencies/999999/apply", headers=host).status_code == 404
    applied = client.post(f"{API}/agencies/{agency_id}/apply", headers=host).json()
    assert applied["application"]["id"] == agency_id
    again = client.post(f"{API}/agencies/{agency_id}/apply", headers=host)
    assert again.status_code == 409 and again.json()["code"] == "already_in_agency"
    # Ajans sahibi başka ajansa başvuramaz
    assert client.post(f"{API}/agencies/{agency_id}/apply", headers=owner).json()["code"] == "owner_cannot_apply"

    # Geri çek ve yeniden başvur
    assert client.delete(f"{API}/agencies/me/application", headers=host).json()["application"] is None
    assert client.delete(f"{API}/agencies/me/application", headers=host).status_code == 404
    client.post(f"{API}/agencies/{agency_id}/apply", headers=host)

    dashboard = client.get(f"{API}/agencies/me", headers=owner).json()["dashboard"]
    statuses = {m["user"]["id"]: m["status"] for m in dashboard["members"]}
    assert statuses[host_id] == "applied"
    notes = client.get(f"{API}/notifications", headers=owner).json()
    assert any(n["type"] == "agency_application" for n in notes)

    # Başvurusu olmayanı kabul edemez; başvuranı kabul eder
    assert client.post(f"{API}/agencies/me/applications/2005/accept", headers=owner).status_code == 404
    accepted = client.post(f"{API}/agencies/me/applications/{host_id}/accept", headers=owner).json()
    assert {m["user"]["id"]: m["status"] for m in accepted["members"]}[host_id] == "active"
    member_state = client.get(f"{API}/agencies/me", headers=host).json()
    assert member_state["role"] == "member" and member_state["agency"]["id"] == agency_id
    # Sahibi olmayan kabul edemez
    assert client.post(f"{API}/agencies/me/applications/{host_id}/accept", headers=host).status_code == 403
