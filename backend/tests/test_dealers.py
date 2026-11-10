"""
Coin bayisi testleri: panel bayi tanımlar ve stok yükler, bayi kullanıcıya coin satar.
"""
from tests.conftest import API
from tests.test_admin import staff_headers
from tests.test_api import me, new_guest
from tests.test_social import register


def _make_dealer(client, finance, headers, daily_limit=1000) -> int:
    user_id = me(client, headers)["id"]
    created = client.post(f"{API}/admin/dealers", headers=finance,
                          json={"user_id": user_id, "daily_limit": daily_limit, "note": "İstanbul bayi"})
    assert created.status_code == 201, created.text
    return user_id


def test_dealer_flow(client):
    finance = staff_headers(client, "finance")
    dealer, buyer, guest = register(client, "bayi_ahmet"), register(client, "bayi_musteri"), new_guest(client)
    buyer_id = me(client, buyer)["id"]

    assert client.get(f"{API}/dealers/me", headers=dealer).json()["code"] == "not_dealer"
    dealer_id = _make_dealer(client, finance, dealer)
    dealer_coins = me(client, dealer)["coin_balance"]
    assert client.post(f"{API}/admin/dealers", headers=finance, json={"user_id": dealer_id}).json()["code"] == "already_dealer"
    assert client.post(f"{API}/admin/dealers", headers=finance,
                       json={"user_id": me(client, guest)["id"]}).json()["code"] == "guest_cannot_be_dealer"
    # Resmi bayi listesinde görünür
    assert dealer_id in [d["user"]["id"] for d in client.get(f"{API}/dealers", headers=buyer).json()]

    # Stok yükleme: dekont numarası zorunlu, aynı form iki kez gönderilse de bir kez yüklenir
    stock = {"coins": 1500, "paid_kurus": 3825_00, "payment_ref": "DEKONT-001"}
    key = {**finance, "Idempotency-Key": "stok-yukleme-0001"}
    detail = client.post(f"{API}/admin/dealers/{dealer_id}/stock", headers=key, json=stock).json()
    assert detail["dealer"]["stock"] == 1500 and detail["dealer"]["total_paid_kurus"] == 382500
    assert client.post(f"{API}/admin/dealers/{dealer_id}/stock", headers=key, json=stock).json()["dealer"]["stock"] == 1500
    assert detail["suggested_kurus_per_1000"] == 3000 * 85 // 100

    # Satış: stok düşer, alıcının coin'i artar, ikisi de deftere yazılır
    before = me(client, buyer)["coin_balance"]
    sale_headers = {**dealer, "Idempotency-Key": "bayi-satis-00001"}
    sold = client.post(f"{API}/dealers/me/sales", headers=sale_headers, json={"user_id": buyer_id, "coins": 600})
    assert sold.status_code == 200, sold.text
    assert (sold.json()["stock"], sold.json()["sold_today"]) == (900, 600)
    # Aynı anahtar tekrar: ikinci kez satılmaz
    again = client.post(f"{API}/dealers/me/sales", headers=sale_headers, json={"user_id": buyer_id, "coins": 600}).json()
    assert again["stock"] == 900 and again["sale"]["id"] == sold.json()["sale"]["id"]
    assert me(client, buyer)["coin_balance"] == before + 600
    history = client.get(f"{API}/wallet/transactions", headers=buyer).json()
    assert history[0]["type"] == "dealer_topup" and history[0]["amount"] == 600
    # Bayinin stoğu harcanabilir coin değildir: kendi coin bakiyesi değişmedi
    assert me(client, dealer)["coin_balance"] == dealer_coins

    # Kurallar: kendine, misafire satılmaz; günlük sınır (1000) aşılamaz; stok yetmezse satılmaz
    sell = lambda body: client.post(f"{API}/dealers/me/sales", headers=dealer, json=body).json()  # noqa: E731
    assert sell({"user_id": dealer_id, "coins": 10})["code"] == "cannot_sell_to_self"
    assert sell({"user_id": me(client, guest)["id"], "coins": 10})["code"] == "buyer_is_guest"
    assert sell({"user_id": buyer_id, "coins": 500})["code"] == "dealer_daily_limit"
    client.patch(f"{API}/admin/dealers/{dealer_id}", headers=finance, json={"daily_limit": 100_000})
    assert sell({"user_id": buyer_id, "coins": 901})["code"] == "insufficient_balance"
    # Yetersiz stokta günlük sayaç da geri alınır
    assert client.get(f"{API}/dealers/me", headers=dealer).json()["sold_today"] == 600

    # Askıya alınan bayi satamaz ve listeden düşer
    client.patch(f"{API}/admin/dealers/{dealer_id}", headers=finance, json={"status": "suspended"})
    assert sell({"user_id": buyer_id, "coins": 10})["code"] == "dealer_suspended"
    assert dealer_id not in [d["user"]["id"] for d in client.get(f"{API}/dealers", headers=buyer).json()]

    panel = client.get(f"{API}/dealers/me", headers=dealer).json()
    assert panel["status"] == "suspended" and panel["recent_sales"][0]["user"]["id"] == buyer_id
    admin_detail = client.get(f"{API}/admin/dealers/{dealer_id}", headers=finance).json()
    assert admin_detail["orders"][0]["payment_ref"] == "DEKONT-001" and admin_detail["sales"][0]["coins"] == 600


def test_dealer_admin_needs_permission(client):
    moderator = staff_headers(client, "moderator")
    assert client.get(f"{API}/admin/dealers", headers=moderator).status_code == 403
    # Stoktan fazlası geri alınamaz
    finance = staff_headers(client, "finance")
    dealer_id = _make_dealer(client, finance, register(client, "bayi_iade"))
    refund = client.post(f"{API}/admin/dealers/{dealer_id}/stock", headers=finance,
                         json={"coins": -50, "payment_ref": "IADE-1"})
    assert refund.status_code == 402
    assert client.post(f"{API}/admin/dealers/{dealer_id}/stock", headers=finance,
                       json={"coins": 100, "payment_ref": "x"}).status_code == 422
