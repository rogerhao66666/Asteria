"""Server counters: traffic by message type, tick cost, rejections and players."""

from __future__ import annotations

import threading
import time

import pytest

from asteria.multiplayer import MultiplayerClient, MultiplayerServer
from asteria.multiplayer.examples import build_counter_adapter, build_movement_adapter
from asteria.multiplayer.metrics import ServerMetrics


def _wait(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


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


def test_counters_start_empty_and_rates_use_the_players_given():
    clock = iter([0.0, 10.0, 10.0, 10.0]).__next__
    metrics = ServerMetrics(clock=clock)
    metrics.received("command", 100)
    metrics.sent("game_update", 4000)
    metrics.sent("game_update", 1000)
    metrics.tick(0.002)
    metrics.tick(0.004)
    metrics.reject("auth")
    metrics.players(3)
    snapshot = metrics.snapshot(players=4)
    assert snapshot["uptime_seconds"] == 10.0
    assert snapshot["bytes_out"] == 5000 and snapshot["bytes_out_per_second"] == 500.0
    assert snapshot["bytes_out_per_player_second"] == 125.0
    assert snapshot["messages_out"] == {"game_update": 2}
    assert snapshot["ticks"] == 2 and snapshot["tick_ms_average"] == pytest.approx(3.0)
    assert snapshot["tick_ms_worst"] == pytest.approx(4.0)
    assert snapshot["tick_cpu_share"] == pytest.approx(0.0006)
    assert snapshot["rejected"] == {"auth": 1} and snapshot["peak_players"] == 3


def test_a_live_server_counts_what_it_receives_and_sends(start):
    server = start(build_counter_adapter())
    client = MultiplayerClient()
    client.connect(*server.server_address[:2], "Ann")
    try:
        for _ in range(3):
            client.send_command("increment", {"amount": 1})
        client.send_ping()
        assert _wait(lambda: client.revision >= 4)
        assert _wait(lambda: server.metrics_snapshot()["messages_in"].get("ping", 0) == 1)
        snapshot = server.metrics_snapshot()
        assert snapshot["messages_in"]["hello"] == 1 and snapshot["messages_in"]["command"] == 3
        assert snapshot["messages_out"]["welcome"] == 1
        assert snapshot["messages_out"]["game_update"] >= 3
        assert snapshot["bytes_in"] > 0 and snapshot["bytes_out"] > snapshot["bytes_in"]
        assert snapshot["peak_players"] == 1
    finally:
        client.close()


def test_the_tick_loop_reports_its_cost(start):
    server = start(build_movement_adapter())  # 20 Hz simulation
    client = MultiplayerClient()
    client.connect(*server.server_address[:2], "Ann")
    try:
        client.send_input({"move_x": 1.0})
        assert _wait(lambda: server.metrics_snapshot()["ticks"] >= 5)
        snapshot = server.metrics_snapshot()
        assert 0 < snapshot["tick_ms_average"] < 50 and snapshot["tick_cpu_share"] < 0.5
        assert snapshot["messages_out"].get("game_update", 0) >= 3
    finally:
        client.close()


def test_a_rejected_input_is_counted_in_the_acks_not_as_a_connection_error(start):
    server = start(build_counter_adapter())  # no real-time input support
    client = MultiplayerClient()
    client.connect(*server.server_address[:2], "Ann")
    try:
        client.send_input({"move_x": 1})
        assert _wait(lambda: server.metrics_snapshot()["messages_out"].get("input_ack", 0) == 1)
    finally:
        client.close()
