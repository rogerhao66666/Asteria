"""Bad links: latency, jitter and frame loss between clients and the server, and what recovers."""

from __future__ import annotations

import queue
import threading
import time

import pytest

from asteria.multiplayer import MultiplayerClient, MultiplayerServer
from asteria.multiplayer.examples import build_counter_adapter, build_movement_adapter
from asteria.multiplayer.netsim import LinkProfile, LinkSimulator


@pytest.fixture
def start():
    started = []

    def run(adapter):
        server = MultiplayerServer(("127.0.0.1", 0), adapter=adapter)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        started.append((server, thread))
        return server

    yield run
    for server, thread in started:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


def _wait(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def _drain(box):
    items = []
    while True:
        try:
            items.append(box.get_nowait())
        except queue.Empty:
            return items


def test_profiles_are_validated():
    with pytest.raises(ValueError):
        LinkProfile(delay_ms=-1)
    with pytest.raises(ValueError):
        LinkProfile(loss=1.0)
    with pytest.raises(ValueError):
        LinkProfile(bytes_per_second=-5)


def test_the_proxy_adds_the_configured_delay_each_way(start):
    server = start(build_counter_adapter())
    profile = LinkProfile(delay_ms=60)
    box = queue.Queue()
    with LinkSimulator(server.server_address[:2], upstream=profile, downstream=profile) as link:
        client = MultiplayerClient(on_message=box.put)
        started = time.monotonic()
        client.connect(*link.address, "Ann")
        join_time = time.monotonic() - started
        try:
            assert join_time >= 0.11  # hello up + welcome down, 60 ms each
            sent = time.monotonic()
            client.send_ping()
            while time.monotonic() - sent < 3:
                try:
                    if box.get(timeout=0.1)["type"] == "pong":
                        break
                except queue.Empty:
                    continue
            assert 0.11 <= time.monotonic() - sent < 1.0
        finally:
            client.close()


def test_frames_keep_their_order_even_with_jitter(start):
    server = start(build_counter_adapter())
    profile = LinkProfile(delay_ms=10, jitter_ms=40)
    box = queue.Queue()
    with LinkSimulator(server.server_address[:2], downstream=profile, seed=3) as link:
        watcher = MultiplayerClient(on_message=box.put)
        driver = MultiplayerClient()
        watcher.connect(*link.address, "Watcher")
        driver.connect(*server.server_address[:2], "Driver")
        try:
            for _ in range(25):
                driver.send_command("increment", {"amount": 1})
            assert _wait(lambda: watcher.revision >= 26)
            revisions = [m["revision"] for m in _drain(box) if m["type"] == "game_update"]
            assert revisions == sorted(revisions) and len(set(revisions)) == len(revisions)
            assert watcher.gaps == 0
        finally:
            watcher.close()
            driver.close()


def test_loss_never_eats_the_handshake_and_is_counted(start):
    server = start(build_counter_adapter())
    lossy = LinkProfile(loss=0.6)
    with LinkSimulator(
        server.server_address[:2], upstream=lossy, downstream=lossy, seed=7
    ) as link:
        client = MultiplayerClient()
        client.connect(*link.address, "Ann")
        try:
            for _ in range(40):
                client.send_ping()
            assert _wait(lambda: link.stats["up"]["frames"] >= 41)
            assert 5 < link.stats["up"]["dropped"] < 40
            assert client.player_id
        finally:
            client.close()


def test_a_client_on_a_lossy_link_notices_gaps_and_catches_up(start):
    server = start(build_counter_adapter())
    lossy = LinkProfile(delay_ms=15, jitter_ms=15, loss=0.35)
    box = queue.Queue()
    with LinkSimulator(server.server_address[:2], downstream=lossy, seed=11) as link:
        watcher = MultiplayerClient(on_message=box.put)
        driver = MultiplayerClient()
        watcher.connect(*link.address, "Watcher", heartbeat=0.3)
        driver.connect(*server.server_address[:2], "Driver")
        try:
            for _ in range(60):
                driver.send_command("increment", {"amount": 1})
                time.sleep(0.01)
            final = driver.revision
            assert _wait(lambda: watcher.revision >= final, timeout=8.0)
            # the last update the watcher applied carries the full, current state
            deadline = time.monotonic() + 8.0
            counter = None
            while time.monotonic() < deadline and counter != 60:
                for message in _drain(box):
                    state = message.get("state") if message["type"] == "game_update" else None
                    if state and "counter" in state:
                        counter = state["counter"]
                time.sleep(0.05)
            assert counter == 60
            assert watcher.gaps > 0  # updates really were lost on the way
        finally:
            watcher.close()
            driver.close()


def test_the_server_limits_how_often_one_player_can_ask_for_a_resync(start):
    server = start(build_counter_adapter())
    client = MultiplayerClient()
    client.connect(*server.server_address[:2], "Ann")
    try:
        for _ in range(6):
            client._send({"protocol": 1, "type": "resync_request"})
        assert _wait(
            lambda: server.metrics_snapshot()["messages_in"].get("resync_request", 0) >= 6
        )
        snapshot = server.metrics_snapshot()
        assert snapshot["messages_out"].get("game_update", 0) == 1
        assert snapshot["rejected"]["resync rate"] == 5
    finally:
        client.close()


def test_real_time_movement_stays_consistent_for_players_on_different_links(start):
    server = start(build_movement_adapter())
    laggy = LinkProfile(delay_ms=40, jitter_ms=30, loss=0.1)
    boxes = [queue.Queue(), queue.Queue()]
    with LinkSimulator(
        server.server_address[:2], upstream=laggy, downstream=laggy, seed=5
    ) as link:
        near = MultiplayerClient(on_message=boxes[0].put)
        far = MultiplayerClient(on_message=boxes[1].put)
        near.connect(*server.server_address[:2], "Near", heartbeat=0.3)
        far.connect(*link.address, "Far", heartbeat=0.3)
        try:
            for _ in range(20):
                near.send_input({"move_x": 1.0})
                far.send_input({"move_x": -1.0})
                time.sleep(0.05)
            near.send_input({"move_x": 0.0})
            far.send_input({"move_x": 0.0})
            time.sleep(1.5)  # everything settles; a heartbeat fixes any lost last update

            def last_positions(box):
                best = None
                for message in _drain(box):
                    if message["type"] == "game_update" and message.get("state"):
                        best = message["state"]
                return best

            a, b = last_positions(boxes[0]), last_positions(boxes[1])
            assert a and b
            assert {p["player_id"]: (p["x"], p["y"]) for p in a["players"]} == {
                p["player_id"]: (p["x"], p["y"]) for p in b["players"]
            }
        finally:
            near.close()
            far.close()
