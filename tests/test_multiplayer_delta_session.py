"""Delta updates end to end: clients still see full states, bytes drop, and loss recovers."""

from __future__ import annotations

import queue
import threading
import time

import pytest

from asteria.multiplayer import MultiplayerClient, MultiplayerServer
from asteria.multiplayer.boss_demo import build_boss_adapter
from asteria.multiplayer.examples import build_counter_adapter, build_movement_adapter
from asteria.multiplayer.netsim import LinkProfile, LinkSimulator


@pytest.fixture
def start():
    started = []

    def run(adapter, **options):
        server = MultiplayerServer(("127.0.0.1", 0), adapter=adapter, **options)
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


def _updates(box):
    items = []
    while True:
        try:
            items.append(box.get_nowait())
        except queue.Empty:
            return [m for m in items if m["type"] == "game_update"]


def test_a_delta_client_still_receives_complete_authoritative_states(start):
    server = start(build_counter_adapter())
    box = queue.Queue()
    watcher = MultiplayerClient(on_message=box.put)
    driver = MultiplayerClient()
    watcher.connect(*server.server_address[:2], "Watcher")
    driver.connect(*server.server_address[:2], "Driver")
    try:
        for _ in range(5):
            driver.send_command("increment", {"amount": 2})
        assert _wait(lambda: watcher.revision >= 7)
        updates = _updates(box)
        assert [m["state"]["counter"] for m in updates if m["state"].get("counter")][-1] == 10
        assert all("state_delta" not in m and "state" in m for m in updates)
        assert any(m.get("delta") for m in updates)  # at least one arrived as a delta
        assert watcher.delta_misses == 0 and server.metrics_snapshot()["delta_bytes_saved"] > 0
    finally:
        watcher.close()
        driver.close()


def test_a_client_that_does_not_ask_for_deltas_gets_full_states(start):
    server = start(build_counter_adapter())
    box = queue.Queue()
    legacy = MultiplayerClient(on_message=box.put)
    driver = MultiplayerClient()
    legacy.connect(*server.server_address[:2], "Legacy", delta=False)
    driver.connect(*server.server_address[:2], "Driver")
    try:
        driver.send_command("increment", {"amount": 1})
        assert _wait(lambda: legacy.revision >= 3)
        assert not any(m.get("delta") for m in _updates(box))
    finally:
        legacy.close()
        driver.close()


def test_a_server_can_switch_deltas_off(start):
    server = start(build_counter_adapter(), delta=False)
    box = queue.Queue()
    client = MultiplayerClient(on_message=box.put)
    other = MultiplayerClient()
    client.connect(*server.server_address[:2], "A")
    other.connect(*server.server_address[:2], "B")
    try:
        other.send_command("increment", {})
        assert _wait(lambda: client.revision >= 3)
        assert server.metrics_snapshot()["delta_bytes_saved"] == 0
    finally:
        client.close()
        other.close()


def test_a_delta_that_does_not_fit_asks_for_a_resync_instead_of_corrupting_state(start):
    server = start(build_counter_adapter())
    box = queue.Queue()
    watcher = MultiplayerClient(on_message=box.put)
    driver = MultiplayerClient()
    watcher.connect(*server.server_address[:2], "Watcher")
    driver.connect(*server.server_address[:2], "Driver")
    try:
        driver.send_command("increment", {"amount": 1})
        assert _wait(lambda: watcher.revision >= 3)
        watcher._state_revision = 9999  # the client "lost" the state the next delta builds on
        _updates(box)
        driver.send_command("increment", {"amount": 1})
        assert _wait(lambda: watcher.delta_misses >= 1)
        assert _wait(lambda: watcher._state_revision == watcher.revision)  # the resync landed
        assert watcher._state["counter"] == 2  # the full state, not a corrupted patch
        driver.send_command("increment", {"amount": 1})
        assert _wait(lambda: watcher._state["counter"] == 3)
    finally:
        watcher.close()
        driver.close()


def test_real_time_updates_get_much_smaller_with_deltas(start):
    def traffic(delta):
        server = start(build_boss_adapter(), delta=delta)
        clients = [MultiplayerClient() for _ in range(3)]
        try:
            for index, client in enumerate(clients):
                client.connect(*server.server_address[:2], f"P{index}", delta=delta)
            for step in range(30):
                for client in clients:
                    client.send_input({"move_x": 1.0 if step % 2 else -1.0})
                time.sleep(0.05)
            snapshot = server.metrics_snapshot()
            return snapshot["bytes_out"]
        finally:
            for client in clients:
                client.close()

    full, small = traffic(False), traffic(True)
    assert small < full * 0.8, (small, full)


def test_deltas_survive_a_lossy_link(start):
    server = start(build_movement_adapter())
    lossy = LinkProfile(delay_ms=20, jitter_ms=20, loss=0.25)
    box = queue.Queue()
    with LinkSimulator(server.server_address[:2], downstream=lossy, seed=21) as link:
        far = MultiplayerClient(on_message=box.put)
        near = MultiplayerClient()
        far.connect(*link.address, "Far", heartbeat=0.3)
        near.connect(*server.server_address[:2], "Near", heartbeat=0.3)
        try:
            for _ in range(25):
                near.send_input({"move_x": 1.0})
                time.sleep(0.05)
            near.send_input({"move_x": 0.0})
            time.sleep(1.5)

            def players(state):
                return {p["player_id"]: (p["x"], p["y"]) for p in state["players"]}

            latest = [m for m in _updates(box) if m.get("state")][-1]["state"]
            assert far._state is not None and players(far._state) == players(latest)
            assert far.delta_misses + far.gaps > 0  # loss really happened, and was repaired
            assert far._state is not latest
        finally:
            far.close()
            near.close()
