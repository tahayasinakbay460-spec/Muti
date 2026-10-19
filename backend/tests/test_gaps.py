"""
Kapsam ölçümünün (coverage) gösterdiği test edilmemiş önemli yollar:
çıkış yapma, geçersiz refresh token, VIP'te çift istek, sandığın süre dolunca kapanması,
şanslı hediyenin gerçek çekilişi.
"""
import uuid

from tests.conftest import API
from tests.test_api import me, new_guest, receive_until


def test_logout_revokes_refresh_token_and_unknown_token_is_rejected(client):
    tokens = client.post(f"{API}/auth/guest").json()
    assert client.post(f"{API}/auth/logout", json={"refresh_token": tokens["refresh_token"]}).status_code == 204
    # Çıkıştan sonra bu cihazın refresh token'ı işe yaramaz.
    after = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert after.status_code == 401 and after.json()["code"] == "invalid_refresh_token"
    # Zaten geçersiz token'la çıkış sessizce geçer (istemci tekrar denese bile hata görmez).
    assert client.post(f"{API}/auth/logout", json={"refresh_token": tokens["refresh_token"]}).status_code == 204
    # Hiç verilmemiş token (sabahki "veritabanı sıfırlandı" durumu) reddedilir.
    unknown = client.post(f"{API}/auth/refresh", json={"refresh_token": "hic-verilmemis-token"})
    assert unknown.status_code == 401 and unknown.json()["code"] == "invalid_refresh_token"


def test_vip_purchase_is_idempotent(client):
    user = new_guest(client)
    client.post(f"{API}/wallet/purchase", headers=user, json={"package_id": 6})
    before = me(client, user)["coin_balance"]
    headers = {**user, "Idempotency-Key": uuid.uuid4().hex}
    first = client.post(f"{API}/vip/purchase", headers=headers, json={"level": 1}).json()
    again = client.post(f"{API}/vip/purchase", headers=headers, json={"level": 1}).json()
    # Ağ tekrar denemesi ikinci kez para düşürmez ve süreyi ikinci kez uzatmaz.
    assert first["coin_balance"] == again["coin_balance"] == before - 3000
    assert first["status"]["expires_at"] == again["status"]["expires_at"]


def test_chest_closes_when_time_runs_out(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "chest_target_coins", 10)
    monkeypatch.setattr(settings, "chest_open_seconds", 0.3)   # testte 60 sn beklemeyelim
    host = new_guest(client)
    room = client.post(f"{API}/rooms", headers=host, json={"title": "Süreli Sandık"}).json()
    token = host["Authorization"].removeprefix("Bearer ")

    with client.websocket_connect(f"/ws/rooms/{room['id']}?token={token}") as socket:
        receive_until(socket, "chat:history")
        client.post(f"{API}/gifts/send", headers=host, json={"receiver_id": 2010, "gift_id": 1, "room_id": room["id"]})
        opened = receive_until(socket, "room:chest_updated")["chest"]
        assert opened["status"] == "open"
        # Kimse almadan süre doldu: sandık kapanır ve yeni (boş) bir sandık dolmaya başlar.
        closed = receive_until(socket, "room:chest_updated")["chest"]
        assert closed["status"] == "filling" and closed["progress"] == 0 and closed["chest_id"] != opened["chest_id"]
    late = client.post(f"{API}/rooms/{room['id']}/chest/claim", headers=host)
    assert late.status_code == 400 and late.json()["code"] == "chest_closed"


def test_lucky_draw_uses_only_table_multipliers():
    """Gerçek çekiliş (testlerde başka yerde sabitleniyor) yalnızca tablodaki çarpanları üretir."""
    from app.services.gift_service import LUCKY_TABLE, _draw_multiplier, draw_lucky_win

    allowed = {multiplier for multiplier, _ in LUCKY_TABLE}
    draws = [_draw_multiplier() for _ in range(2000)]
    assert set(draws) <= allowed and 0 in draws   # 0 en sık çıkan; 2000 çekilişte mutlaka görülür
    win, best = draw_lucky_win(price=10, quantity=50)
    assert win % 10 == 0 and best in allowed and 0 <= win <= 50 * 10 * max(allowed)
