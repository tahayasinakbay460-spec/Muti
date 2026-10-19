"""
Oda içi etkinlik testleri: PK, birlikte izleme, karaoke, iki kişilik oyunlar (Dört Bağla, Taş-Kağıt-Makas).
"""
from contextlib import ExitStack

import pytest

from tests.conftest import API
from tests.test_api import me, new_guest, receive_until


def token(headers: dict) -> str:
    return headers["Authorization"].removeprefix("Bearer ")


def new_room(client, host: dict, title: str) -> dict:
    return client.post(f"{API}/rooms", headers=host, json={"title": title}).json()


def join(stack: ExitStack, client, room_id: int, headers: dict):
    """Odaya WebSocket ile katılır ve katılımın tamamlanmasını bekler (bkz. test_api)."""
    socket = stack.enter_context(client.websocket_connect(f"/ws/rooms/{room_id}?token={token(headers)}"))
    receive_until(socket, "chat:history")
    return socket


# ── PK ────────────────────────────────────────────────────────────────────────

def test_pk_counts_gifts_to_team_seats_and_picks_winner(client):
    host, blue_player, fan, listener = new_guest(client), new_guest(client), new_guest(client), new_guest(client)
    client.post(f"{API}/wallet/purchase", headers=fan, json={"package_id": 6})
    room = new_room(client, host, "PK Odası")
    rooms = f"{API}/rooms/{room['id']}"
    host_id, blue_id, fan_id = me(client, host)["id"], me(client, blue_player)["id"], me(client, fan)["id"]

    with ExitStack() as stack:
        socket = join(stack, client, room["id"], host)
        join(stack, client, room["id"], blue_player)
        client.post(f"{rooms}/seats/0", headers=host)            # kırmızı takım (ilk yarı)
        client.post(f"{rooms}/seats/7", headers=blue_player)     # mavi takım (ikinci yarı)

        denied = client.post(f"{rooms}/pk", headers=listener, json={"minutes": 3})
        assert denied.status_code == 403 and denied.json()["code"] == "not_room_moderator"
        assert client.post(f"{rooms}/pk", headers=host, json={"minutes": 2}).status_code == 422

        started = client.post(f"{rooms}/pk", headers=host, json={"minutes": 3}).json()
        assert started["status"] == "running" and started["red_seats"] == [0, 1, 2, 3]
        assert client.post(f"{rooms}/pk", headers=host, json={"minutes": 3}).json()["code"] == "pk_running"
        receive_until(socket, "room:pk_updated")

        gift = {"room_id": room["id"], "quantity": 1}
        client.post(f"{API}/gifts/send", headers=fan, json={**gift, "receiver_id": host_id, "gift_id": 6})       # 299
        assert receive_until(socket, "room:pk_updated")["pk"]["red"] == 299
        client.post(f"{API}/gifts/send", headers=fan, json={**gift, "receiver_id": blue_id, "gift_id": 1})       # 10
        assert receive_until(socket, "room:pk_updated")["pk"]["blue"] == 10
        # Koltukta olmayan birine giden hediye sayılmaz.
        client.post(f"{API}/gifts/send", headers=fan, json={**gift, "receiver_id": me(client, listener)["id"], "gift_id": 1})

        ended = client.delete(f"{rooms}/pk", headers=host).json()
        assert ended["status"] == "ended" and ended["winner"] == "red" and (ended["red"], ended["blue"]) == (299, 10)
        assert ended["mvp"]["user"]["id"] == fan_id and ended["mvp"]["coins"] == 309
        assert client.delete(f"{rooms}/pk", headers=host).json()["code"] == "no_pk"


def test_pk_ends_by_itself_when_time_is_up(client, monkeypatch):
    import asyncio

    from app.services import activity_service

    host = new_guest(client)
    room = new_room(client, host, "Süreli PK")
    real_sleep = asyncio.sleep
    monkeypatch.setattr(activity_service.asyncio, "sleep", lambda _seconds: real_sleep(0.2))   # 1 dk yerine 0.2 sn
    with ExitStack() as stack:
        socket = join(stack, client, room["id"], host)
        client.post(f"{API}/rooms/{room['id']}/pk", headers=host, json={"minutes": 1})
        receive_until(socket, "room:pk_updated")
        ended = receive_until(socket, "room:pk_updated")["pk"]
        assert ended["status"] == "ended" and ended["winner"] == "draw"


# ── Birlikte izleme ve karaoke ────────────────────────────────────────────────

@pytest.mark.parametrize("url, video_id", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ?t=42", "dQw4w9WgXcQ"),
    ("youtube.com/shorts/abcdefghijk", "abcdefghijk"),
    ("https://m.youtube.com/watch?feature=share&v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
])
def test_youtube_links_are_parsed(url, video_id):
    from app.services.activity_service import parse_youtube_id
    assert parse_youtube_id(url) == video_id


def test_watch_together_controls(client):
    host, listener = new_guest(client), new_guest(client)
    room = new_room(client, host, "Film Gecesi")
    media_url = f"{API}/rooms/{room['id']}/media"

    bad = client.put(media_url, headers=host, json={"url": "https://kotu-site.example/video"})
    assert bad.status_code == 400 and bad.json()["code"] == "invalid_video_url"
    assert client.put(media_url, headers=listener, json={"url": "https://youtu.be/dQw4w9WgXcQ"}).status_code == 403

    with ExitStack() as stack:
        socket = join(stack, client, room["id"], listener)
        media = client.put(media_url, headers=host, json={"url": "https://youtu.be/dQw4w9WgXcQ"}).json()
        assert media["video_id"] == "dQw4w9WgXcQ" and media["paused"] is False and media["started_at"]
        assert receive_until(socket, "room:media_updated")["media"]["video_id"] == "dQw4w9WgXcQ"

        paused = client.post(f"{media_url}/control", headers=host, json={"action": "pause", "position": 42}).json()
        assert paused["paused"] is True and paused["position"] == 42
        played = client.post(f"{media_url}/control", headers=host, json={"action": "play"}).json()
        # Kaldığı 42. saniyeden devam: başlangıç anı "şimdi - 42 sn" olur.
        from datetime import datetime
        elapsed = (datetime.fromisoformat(played["server_time"]) - datetime.fromisoformat(played["started_at"])).total_seconds()
        assert played["paused"] is False and 41.5 < elapsed < 43
        sought = client.post(f"{media_url}/control", headers=host, json={"action": "seek", "position": 90}).json()
        assert sought["position"] == 90

        snapshot = client.get(f"{API}/rooms/{room['id']}/activities", headers=listener).json()
        assert snapshot["media"]["video_id"] == "dQw4w9WgXcQ"
        assert client.delete(media_url, headers=host).status_code == 204
        # Kuyrukta önceki durdur/oynat/sar yayınları da var: kapanış yayınına kadar oku.
        assert any(receive_until(socket, "room:media_updated")["media"] is None for _ in range(5))
    assert client.post(f"{media_url}/control", headers=host, json={"action": "play"}).status_code == 404


def test_karaoke_queue(client):
    host, singer, other = new_guest(client), new_guest(client), new_guest(client)
    room = new_room(client, host, "Karaoke")
    karaoke = f"{API}/rooms/{room['id']}/karaoke"
    singer_id = me(client, singer)["id"]

    outside = client.post(f"{karaoke}/queue", headers=other)
    assert outside.status_code == 400 and outside.json()["code"] == "not_in_room"
    with ExitStack() as stack:
        join(stack, client, room["id"], singer)
        join(stack, client, room["id"], other)
        assert [u["id"] for u in client.post(f"{karaoke}/queue", headers=singer).json()["queue"]] == [singer_id]
        assert client.post(f"{karaoke}/queue", headers=singer).json()["code"] == "already_in_queue"
        client.post(f"{karaoke}/queue", headers=other)
        assert client.post(f"{karaoke}/next", headers=singer).status_code == 403
        now = client.post(f"{karaoke}/next", headers=host).json()
        assert now["singer"]["id"] == singer_id and len(now["queue"]) == 1
        assert client.delete(f"{karaoke}/queue", headers=other).json()["queue"] == []


# ── İki kişilik oyunlar ───────────────────────────────────────────────────────

def test_connect_four_turns_rules_and_vertical_win(client):
    a, b, watcher = new_guest(client), new_guest(client), new_guest(client)
    room = new_room(client, a, "Dört Bağla")
    with ExitStack() as stack:
        sa, sb, sw = (join(stack, client, room["id"], h) for h in (a, b, watcher))
        sa.send_json({"event": "game:duel_create", "payload": {"game": "connect4"}})
        table = receive_until(sw, "game:duel_updated")["table"]
        assert table["status"] == "waiting" and len(table["players"]) == 1
        sa.send_json({"event": "game:duel_join", "payload": {"table_id": table["table_id"]}})
        assert receive_until(sa, "error")["code"] == "cannot_join_own"

        sb.send_json({"event": "game:duel_join", "payload": {"table_id": table["table_id"]}})
        table = receive_until(sw, "game:duel_updated")["table"]
        assert table["status"] == "playing" and len(table["players"]) == 2
        sockets = {0: sa, 1: sb}
        first, second = sockets[table["turn"]], sockets[1 - table["turn"]]

        def play(socket, column):
            socket.send_json({"event": "game:duel_move", "payload": {"table_id": table["table_id"], "move": column}})

        play(second, 3)
        assert receive_until(second, "error")["code"] == "not_your_turn"
        play(first, 9)
        assert receive_until(first, "error")["code"] == "invalid_move"

        # Sıradaki 0. sütuna, diğeri 1. sütuna oynar: 4. taşla dikey dörtlü tamamlanır.
        for _ in range(3):
            play(first, 0)
            receive_until(sw, "game:duel_updated")
            play(second, 1)
            receive_until(sw, "game:duel_updated")
        play(first, 0)
        final = receive_until(sw, "game:duel_updated")["table"]
        assert final["status"] == "finished" and final["reason"] == "win" and final["winner"] == table["turn"]
        assert [row[0] for row in final["board"]][-4:] == [table["turn"] + 1] * 4


def test_connect_four_column_full_and_winner_check():
    from app.realtime.duels import connect4_winner

    board = [[0] * 7 for _ in range(6)]
    for i in range(4):            # çapraz (sol alttan sağ üste)
        board[5 - i][i] = 1
    assert connect4_winner(board, 2, 3) and not connect4_winner([[0] * 7 for _ in range(5)] + [[2, 2, 2, 0, 0, 0, 0]], 5, 2)


def test_rock_paper_scissors_hides_choices_until_both_chose(client):
    a, b = new_guest(client), new_guest(client)
    room = new_room(client, a, "TKM")
    with ExitStack() as stack:
        sa, sb = join(stack, client, room["id"], a), join(stack, client, room["id"], b)
        sa.send_json({"event": "game:duel_create", "payload": {"game": "rps"}})
        table_id = receive_until(sb, "game:duel_updated")["table"]["table_id"]
        sb.send_json({"event": "game:duel_join", "payload": {"table_id": table_id}})
        receive_until(sb, "game:duel_updated")

        def choose(socket, move):
            socket.send_json({"event": "game:duel_move", "payload": {"table_id": table_id, "move": move}})

        choose(sa, "rock")
        seen_by_b = receive_until(sb, "game:duel_updated")["table"]
        # Rakip yalnızca "seçti" bilgisini görür, taş olduğunu göremez.
        assert seen_by_b["chosen"] == [True, False] and seen_by_b["last_round"] is None and "rock" not in str(seen_by_b)
        choose(sa, "paper")
        assert receive_until(sa, "error")["code"] == "already_chosen"

        choose(sb, "scissors")      # taş makası yener → 1-0
        round_one = receive_until(sb, "game:duel_updated")["table"]
        assert round_one["scores"] == [1, 0] and round_one["last_round"] == {"choices": ["rock", "scissors"], "winner": 0}
        choose(sa, "paper")
        receive_until(sb, "game:duel_updated")
        choose(sb, "rock")          # kağıt taşı yener → 2-0, oyun biter
        final = receive_until(sb, "game:duel_updated")["table"]
        assert final["status"] == "finished" and final["winner"] == 0 and final["scores"] == [2, 0]


def test_duel_forfeit_on_timeout_and_on_leaving(client, monkeypatch):
    from app.realtime.duels import duels

    monkeypatch.setattr(duels, "move_seconds", 0.3)
    a, b, watcher = new_guest(client), new_guest(client), new_guest(client)
    room = new_room(client, a, "Süre")
    with ExitStack() as stack:
        sa, sb, sw = (join(stack, client, room["id"], h) for h in (a, b, watcher))
        sa.send_json({"event": "game:duel_create", "payload": {"game": "connect4"}})
        table_id = receive_until(sw, "game:duel_updated")["table"]["table_id"]
        sb.send_json({"event": "game:duel_join", "payload": {"table_id": table_id}})
        playing = receive_until(sw, "game:duel_updated")["table"]
        timed_out = receive_until(sw, "game:duel_updated")["table"]
        # Sırası gelen oynamadı: rakibi hükmen kazanır.
        assert timed_out["reason"] == "forfeit" and timed_out["winner"] == 1 - playing["turn"]

        monkeypatch.setattr(duels, "move_seconds", 45)
        sb.send_json({"event": "game:duel_create", "payload": {"game": "rps"}})
        second = receive_until(sw, "game:duel_updated")["table"]
        if second["table_id"] == table_id:   # bitmiş masanın kapanma yayını araya girebilir
            second = receive_until(sw, "game:duel_updated")["table"]
        sa.send_json({"event": "game:duel_join", "payload": {"table_id": second["table_id"]}})
        receive_until(sw, "game:duel_updated")
        sb.send_json({"event": "game:duel_leave", "payload": {"table_id": second["table_id"]}})
        left = receive_until(sw, "game:duel_updated")["table"]
        assert left["reason"] == "forfeit" and left["winner"] == 1   # masayı açan (0) ayrıldı, katılan (1) kazandı

    snapshot = client.get(f"{API}/rooms/{room['id']}/activities", headers=watcher).json()
    assert all(t["status"] == "finished" for t in snapshot["duels"])
