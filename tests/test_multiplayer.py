"""End-to-end checks for the optional multiplayer session runtime."""

from __future__ import annotations

import queue
import threading
import time

import pytest

from asteria.multiplayer import MultiplayerClient, MultiplayerServer
from asteria.multiplayer.examples import build_counter_adapter, build_movement_adapter


def _next_message(messages, predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = messages.get(timeout=max(0.01, deadline - time.monotonic()))
        except queue.Empty:
            break
        if predicate(value):
            return value
    raise AssertionError("expected multiplayer message was not received")


@pytest.fixture
def serve_adapter():
    servers = []

    def start(adapter, *, max_players=4):
        server = MultiplayerServer(("127.0.0.1", 0), max_players=max_players, adapter=adapter)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        return server

    yield start

    for server, thread in reversed(servers):
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)
        assert not thread.is_alive()


def _client(messages):
    return MultiplayerClient(on_message=messages.put)


def test_two_clients_receive_ordered_authoritative_commands_and_server_survives_rejection(
    serve_adapter,
):
    server = serve_adapter(build_counter_adapter())
    first_messages, second_messages = queue.Queue(), queue.Queue()
    first, second = _client(first_messages), _client(second_messages)
    try:
        first_welcome = first.connect(*server.server_address[:2], "First")
        second_welcome = second.connect(*server.server_address[:2], "Second")
        assert first_welcome["player_id"] != second_welcome["player_id"]
        assert {p["player_id"] for p in second_welcome["players"]} == {
            first_welcome["player_id"],
            second_welcome["player_id"],
        }

        first.send_command("increment", {"amount": 2})
        update_one = _next_message(
            first_messages,
            lambda value: (
                value.get("type") == "game_update" and value.get("state", {}).get("counter") == 2
            ),
        )
        peer_update_one = _next_message(
            second_messages,
            lambda value: (
                value.get("type") == "game_update" and value.get("state", {}).get("counter") == 2
            ),
        )
        assert peer_update_one["revision"] == update_one["revision"]

        first.send_command("increment", {"amount": 0})
        rejected = _next_message(first_messages, lambda value: value.get("type") == "server_error")
        assert "integer from 1 to 1000" in rejected["message"]
        assert first.connected and second.connected

        second.send_command("increment", {"amount": 3})
        final_first = _next_message(
            first_messages,
            lambda value: (
                value.get("type") == "game_update" and value.get("state", {}).get("counter") == 5
            ),
        )
        final_second = _next_message(
            second_messages,
            lambda value: (
                value.get("type") == "game_update" and value.get("state", {}).get("counter") == 5
            ),
        )
        assert final_first["revision"] > update_one["revision"]
        assert final_second["revision"] == final_first["revision"]
    finally:
        first.close()
        second.close()


def test_two_clients_input_acknowledgements_and_tick_state_are_consistent(serve_adapter):
    server = serve_adapter(build_movement_adapter())
    first_messages, second_messages = queue.Queue(), queue.Queue()
    first, second = _client(first_messages), _client(second_messages)
    try:
        first_welcome = first.connect(*server.server_address[:2], "First")
        second_welcome = second.connect(*server.server_address[:2], "Second")
        first_id, second_id = first_welcome["player_id"], second_welcome["player_id"]

        bad_sequence = first.send_input({"move_x": 2})
        rejected = _next_message(
            first_messages,
            lambda value: (
                value.get("type") == "input_ack" and value.get("sequence") == bad_sequence
            ),
        )
        assert rejected["accepted"] is False
        assert "move_x" in rejected["reason"]

        time.sleep(0.03)
        first_sequence = first.send_input({"move_x": 1, "move_y": 0})
        second_sequence = second.send_input({"move_x": -1, "move_y": 0})
        first_ack = _next_message(
            first_messages,
            lambda value: (
                value.get("type") == "input_ack" and value.get("sequence") == first_sequence
            ),
        )
        second_ack = _next_message(
            second_messages,
            lambda value: (
                value.get("type") == "input_ack" and value.get("sequence") == second_sequence
            ),
        )
        assert first_ack["accepted"] is True
        assert second_ack["accepted"] is True

        first_update = _next_message(
            first_messages,
            lambda value: (
                value.get("type") == "game_update" and value.get("state", {}).get("tick", 0) > 0
            ),
        )
        second_update = _next_message(
            second_messages,
            lambda value: (
                value.get("type") == "game_update" and value.get("state", {}).get("tick", 0) > 0
            ),
        )
        assert first_update["revision"] == second_update["revision"]
        first_players = {
            player["player_id"]: player for player in first_update["state"]["players"]
        }
        second_players = {
            player["player_id"]: player for player in second_update["state"]["players"]
        }
        assert first_players == second_players
        assert first_players[first_id]["x"] > -10.5
        assert first_players[second_id]["x"] < -7.5

        second.close()
        _next_message(
            first_messages,
            lambda value: value.get("type") == "peer_left" and value.get("player_id") == second_id,
        )
        assert second_id not in {player["player_id"] for player in first.players}
    finally:
        first.close()
        second.close()


def test_boss_demo_routes_input_to_the_owning_player_only():
    from asteria.multiplayer.boss_demo import build_boss_adapter

    adapter = build_boss_adapter()
    adapter.on_player_joined("p1", "One")
    adapter.on_player_joined("p2", "Two")
    before = {p["player_id"]: p for p in adapter.initial_state()["players"]}

    adapter.handle_input("p1", {"move_x": 1, "move_y": 0, "attack": False})
    update = adapter.network_tick(0.05)
    after = {p["player_id"]: p for p in update.state["players"]}

    assert after["p1"]["x"] > before["p1"]["x"]
    assert after["p2"]["x"] == before["p2"]["x"]


def test_boss_demo_rejects_invalid_axes_and_attack_values():
    from asteria.multiplayer.boss_demo import build_boss_adapter

    adapter = build_boss_adapter()
    adapter.on_player_joined("p1", "One")
    with pytest.raises(ValueError, match="move_x"):
        adapter.handle_input("p1", {"move_x": 2})
    with pytest.raises(ValueError, match="attack"):
        adapter.handle_input("p1", {"attack": 1})


def test_boss_demo_gives_full_xp_and_random_drops_only_to_players_who_hit():
    from asteria.multiplayer.boss_demo import build_boss_adapter

    adapter = build_boss_adapter()
    adapter.on_player_joined("p1", "One")
    adapter.on_player_joined("p2", "Two")
    adapter.on_player_joined("p3", "Three")
    adapter.handle_input("p1", {"attack": True})
    adapter.handle_input("p2", {"attack": True})
    events = []
    for _ in range(240):
        update = adapter.network_tick(0.05)
        events.extend(update.events)
        if not update.state["boss"]["alive"]:
            break

    kinds = [event["type"] for event in events]
    phases = [event["phase"] for event in events if event["type"] == "boss_phase"]
    assert phases == [2, 3]
    assert kinds.count("boss_defeated") == 1
    xp_awards = [event for event in events if event["type"] == "experience_awarded"]
    assert {(event["player_id"], event["amount"]) for event in xp_awards} == {
        ("p1", 100),
        ("p2", 100),
    }
    loot_awards = [event for event in events if event["type"] == "loot_awarded"]
    assert len(loot_awards) == 1
    assert loot_awards[0]["player_id"] in {"p1", "p2"}
    assert loot_awards[0]["item_id"] == "ancient_shard"
    experience = {p["player_id"]: p["experience"] for p in update.state["players"]}
    assert experience == {"p1": 100, "p2": 100, "p3": 0}

    later = adapter.network_tick(0.05)
    assert "boss_defeated" not in [event["type"] for event in later.events]
    assert "loot_awarded" not in [event["type"] for event in later.events]
    assert "experience_awarded" not in [event["type"] for event in later.events]


def test_boss_demo_allows_a_nearby_player_to_revive_a_downed_ally():
    from asteria.multiplayer.boss_demo import CooperativeBossAdapter

    adapter = CooperativeBossAdapter(
        player_max_health=1,
        boss_damage=1,
        boss_attack_interval=0.05,
        player_spawn_spacing=1.0,
    )
    adapter.on_player_joined("p1", "One")
    adapter.on_player_joined("p2", "Two")
    adapter.network_tick(0.05)
    assert next(p for p in adapter.initial_state()["players"] if p["player_id"] == "p1")["downed"]

    update = adapter.handle_command("p2", "revive", {"target_player_id": "p1"})
    revived = next(p for p in update.state["players"] if p["player_id"] == "p1")
    assert revived["downed"] is False
    assert revived["hp"] == 1
    assert update.events[0]["type"] == "player_revived"


def test_input_replay_and_rate_limit_return_distinct_acknowledgements(serve_adapter):
    import socket

    from asteria.multiplayer.protocol import decode_frame, encode_frame, message

    server = serve_adapter(build_movement_adapter())
    server.input_rate_limit = 1
    connection = socket.create_connection(server.server_address, timeout=2.0)
    reader = connection.makefile("rb")
    try:
        connection.sendall(encode_frame(message("hello", display_name="Raw Client")))
        welcome = decode_frame(reader.readline())
        assert welcome["type"] == "welcome"

        frame = message("input", sequence=1, input_state={"move_x": 1})
        connection.sendall(encode_frame(frame))
        accepted = decode_frame(reader.readline())
        assert accepted["type"] == "input_ack" and accepted["accepted"] is True

        connection.sendall(encode_frame(frame))
        duplicate = decode_frame(reader.readline())
        assert duplicate["accepted"] is False
        assert duplicate["reason"] == "duplicate input"

        connection.sendall(encode_frame(message("input", sequence=2, input_state={"move_x": 0})))
        limited = decode_frame(reader.readline())
        assert limited["accepted"] is False
        assert limited["reason"] == "input rate exceeded"

        time.sleep(1.02)
        connection.sendall(encode_frame(message("input", sequence=3, input_state={"move_x": 0})))
        accepted_again = None
        while accepted_again is None:
            value = decode_frame(reader.readline())
            if value.get("type") == "input_ack" and value.get("sequence") == 3:
                accepted_again = value
        assert accepted_again["accepted"] is True
    finally:
        reader.close()
        connection.close()


def test_boss_demo_uses_an_unoccupied_spawn_after_a_player_leaves():
    from asteria.multiplayer.boss_demo import build_boss_adapter

    adapter = build_boss_adapter()
    adapter.on_player_joined("p1", "One")
    adapter.on_player_joined("p2", "Two")
    adapter.on_player_left("p1")
    update = adapter.on_player_joined("p3", "Three")
    positions = {(player["x"], player["y"]) for player in update.state["players"]}
    assert len(positions) == 2


def test_two_clients_defeat_the_same_authoritative_boss(serve_adapter):
    from asteria.multiplayer.boss_demo import build_boss_adapter

    server = serve_adapter(build_boss_adapter())
    first_messages, second_messages = queue.Queue(), queue.Queue()
    first, second = _client(first_messages), _client(second_messages)
    try:
        first.connect(*server.server_address[:2], "One")
        second.connect(*server.server_address[:2], "Two")
        time.sleep(0.03)
        first_sequence = first.send_input({"attack": True})
        second_sequence = second.send_input({"attack": True})
        for messages, sequence in (
            (first_messages, first_sequence),
            (second_messages, second_sequence),
        ):
            ack = _next_message(
                messages,
                lambda value, expected=sequence: (
                    value.get("type") == "input_ack" and value.get("sequence") == expected
                ),
            )
            assert ack["accepted"] is True

        first_boss = _next_message(
            first_messages,
            lambda value: (
                value.get("type") == "game_update"
                and value.get("state", {}).get("boss", {}).get("hp", 240) < 240
            ),
        )
        second_boss = _next_message(
            second_messages,
            lambda value: (
                value.get("type") == "game_update"
                and value.get("state", {}).get("boss", {}).get("hp", 240) < 240
            ),
        )
        assert first_boss["revision"] == second_boss["revision"]
        assert first_boss["state"]["boss"] == second_boss["state"]["boss"]

        first_done = _next_message(
            first_messages,
            lambda value: (
                value.get("type") == "game_update"
                and value.get("state", {}).get("boss", {}).get("alive") is False
            ),
            timeout=8.0,
        )
        second_done = _next_message(
            second_messages,
            lambda value: (
                value.get("type") == "game_update"
                and value.get("state", {}).get("boss", {}).get("alive") is False
            ),
            timeout=8.0,
        )
        assert first_done["state"]["boss"] == second_done["state"]["boss"]
        assert {p["experience"] for p in first_done["state"]["players"]} == {100}
        assert first_done["revision"] == second_done["revision"]
    finally:
        first.close()
        second.close()


def test_stable_guest_id_restores_server_side_profile_after_reconnect(tmp_path):
    from asteria.multiplayer.server import MultiplayerServer

    database = tmp_path / "server.sqlite3"
    server = MultiplayerServer(("127.0.0.1", 0), store_path=database)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    first = _client(queue.Queue())
    second = _client(queue.Queue())
    duplicate = _client(queue.Queue())
    try:
        welcome = first.connect(*server.server_address[:2], "Ranger", guest_id="guest-ranger-01")
        assert welcome["player_id"] == "guest-ranger-01"
        first.close()

        restored = second.connect(*server.server_address[:2], "Ranger", guest_id="guest-ranger-01")
        assert restored["player_id"] == "guest-ranger-01"
        assert server.store.get_player("guest-ranger-01")["display_name"] == "Ranger"

        try:
            duplicate.connect(*server.server_address[:2], "Impostor", guest_id="guest-ranger-01")
        except Exception as exc:
            assert "already" in str(exc).lower() or "active" in str(exc).lower()
        else:
            raise AssertionError("a second active connection reused the same guest ID")
    finally:
        first.close()
        second.close()
        duplicate.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)
        assert not thread.is_alive()


def test_boss_full_xp_and_random_drop_are_durable_in_sqlite(tmp_path):
    from asteria.multiplayer.boss_demo import build_boss_adapter
    from asteria.multiplayer.persistence import SQLiteMultiplayerStore

    database = tmp_path / "boss.sqlite3"
    store = SQLiteMultiplayerStore(database)
    adapter = build_boss_adapter(store=store)
    for player_id in ("p1", "p2", "idle"):
        adapter.on_player_joined(player_id, player_id)
    adapter.handle_input("p1", {"attack": True})
    adapter.handle_input("p2", {"attack": True})
    for _ in range(200):
        update = adapter.network_tick(0.05)
        if not update.state["boss"]["alive"]:
            break

    assert not update.state["boss"]["alive"]
    store.close()
    restored = SQLiteMultiplayerStore(database)
    assert restored.get_player("p1")["experience"] == 100
    assert restored.get_player("p2")["experience"] == 100
    assert restored.get_player("idle")["experience"] == 0
    assert restored.get_player("p1")["inventory"] in ({}, {"ancient_shard": 1})
    assert restored.get_player("p2")["inventory"] in ({}, {"ancient_shard": 1})
    assert (
        sum(bool(restored.get_player(player_id)["inventory"]) for player_id in ("p1", "p2")) == 1
    )
    restored.close()


def test_boss_demo_types_are_available_from_the_public_multiplayer_package():
    from asteria.multiplayer import CooperativeBossAdapter, build_boss_adapter

    assert isinstance(build_boss_adapter(), CooperativeBossAdapter)


def test_non_serializable_adapter_state_is_rejected_without_advancing_revision(serve_adapter):
    from asteria.multiplayer import AdapterUpdate

    class Adapter:
        def __init__(self):
            self.players = {}
            self.fail_once = True

        def initial_state(self):
            return {"value": 0}

        def on_player_joined(self, player_id, display_name):
            self.players[player_id] = display_name
            return AdapterUpdate(state=self.initial_state())

        def handle_command(self, player_id, command, payload):
            if self.fail_once:
                self.fail_once = False
                return AdapterUpdate(state={"value": object()})
            return AdapterUpdate(state={"value": 1})

        def on_player_left(self, player_id):
            self.players.pop(player_id, None)
            return AdapterUpdate(state=self.initial_state())

    server = serve_adapter(Adapter())
    messages = queue.Queue()
    client = _client(messages)
    try:
        welcome = client.connect(*server.server_address[:2], "One")
        start_revision = welcome["revision"]
        client.send_command("change", {})
        rejected = _next_message(messages, lambda value: value.get("type") == "server_error")
        assert "serializable" in rejected["message"].lower()
        assert client.revision == start_revision

        client.send_command("change", {})
        update = _next_message(
            messages,
            lambda value: (
                value.get("type") == "game_update" and value.get("state", {}).get("value") == 1
            ),
        )
        assert update["revision"] == start_revision + 1
        assert client.revision == update["revision"]
    finally:
        client.close()


def test_protocol_rejects_non_finite_numbers_on_send_and_receive():
    from asteria.multiplayer.protocol import ProtocolError, decode_frame, encode_frame, message

    with pytest.raises(ProtocolError, match="finite"):
        encode_frame(message("game_update", state={"position": float("nan")}))
    with pytest.raises(ProtocolError, match="finite"):
        decode_frame(b'{"protocol":1,"type":"input","value":Infinity}')


def test_replayed_game_command_is_not_applied_twice(serve_adapter):
    import socket

    from asteria.multiplayer.protocol import decode_frame, encode_frame, message

    server = serve_adapter(build_counter_adapter())
    connection = socket.create_connection(server.server_address, timeout=2.0)
    reader = connection.makefile("rb")
    command = message(
        "command",
        command_id="once",
        sequence=1,
        command="increment",
        payload={"amount": 2},
    )
    try:
        connection.sendall(encode_frame(message("hello", display_name="Raw Client")))
        welcome = decode_frame(reader.readline())
        assert welcome["type"] == "welcome"
        connection.sendall(encode_frame(command))
        applied = decode_frame(reader.readline())
        assert applied["type"] == "game_update"
        assert applied["state"]["counter"] == 2

        connection.sendall(encode_frame(command))
        duplicate = decode_frame(reader.readline())
        assert duplicate["type"] == "command_ack"
        assert duplicate["duplicate"] is True
    finally:
        reader.close()
        connection.close()


def test_boss_targets_the_player_with_the_greatest_threat():
    from asteria.multiplayer.boss_demo import build_boss_adapter

    adapter = build_boss_adapter()
    adapter.on_player_joined("p1", "One")
    adapter.on_player_joined("p2", "Two")
    adapter.handle_input("p1", {"attack": True})
    adapter.network_tick(0.05)
    adapter.handle_input("p1", {"attack": False})
    adapter.handle_input("p2", {"attack": True})
    adapter.network_tick(0.05)
    update = adapter.network_tick(0.5)

    assert update.state["boss"]["target_player_id"] == "p2"
