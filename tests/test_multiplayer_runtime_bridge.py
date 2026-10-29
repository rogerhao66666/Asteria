from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from asteria.multiplayer.boss_demo import build_boss_adapter
from asteria.multiplayer.server import MultiplayerServer
from asteria.runtime.multiplayer_preview import (
    MultiplayerPreviewBridge,
    load_runtime_multiplayer_profile,
    map_network_position,
)


def _profile(*, host, port, guest_id="guest-1"):
    return {
        "schema": "asteria.multiplayer.profile",
        "version": 1,
        "session_name": "Co-op test",
        "server_address": host,
        "port": port,
        "player_name": guest_id,
        "guest_id": guest_id,
        "connect_on_run": True,
    }


def _wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_runtime_multiplayer_profile_is_opt_in_and_uses_project_settings_dir(tmp_path):
    settings = tmp_path / ".asteria"
    settings.mkdir()
    profile_path = settings / "multiplayer.json"
    profile_path.write_text(json.dumps(_profile(host="127.0.0.1", port=8765)))

    profile = load_runtime_multiplayer_profile(tmp_path)

    assert profile["guest_id"] == "guest-1"
    assert profile["port"] == 8765
    profile["connect_on_run"] = False
    profile_path.write_text(json.dumps(profile))
    assert load_runtime_multiplayer_profile(tmp_path) is None


def test_runtime_multiplayer_profile_rejects_invalid_guest_and_port(tmp_path):
    settings = tmp_path / ".asteria"
    settings.mkdir()
    profile_path = settings / "multiplayer.json"
    profile_path.write_text(json.dumps(_profile(host="127.0.0.1", port=70000)))

    with pytest.raises(ValueError, match="port"):
        load_runtime_multiplayer_profile(tmp_path)

    profile_path.write_text(json.dumps(_profile(host="127.0.0.1", port=8765, guest_id="../bad")))
    with pytest.raises(ValueError, match="guest_id"):
        load_runtime_multiplayer_profile(tmp_path)


def test_multiplayer_preview_bridge_connects_sends_input_and_tracks_authoritative_state():
    server = MultiplayerServer(("127.0.0.1", 0), adapter=build_boss_adapter())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    bridge = MultiplayerPreviewBridge(_profile(host="127.0.0.1", port=server.server_address[1]))
    try:
        bridge.connect()
        assert bridge.connected
        assert bridge.player_id == "guest-1"
        assert bridge.state["players"][0]["player_id"] == "guest-1"

        bridge.send_input({"move_x": 1.0, "move_y": 0.0, "attack": True}, force=True)
        assert _wait_for(lambda: bridge.acked_input_sequence > 0)

        assert _wait_for(
            lambda: (
                bridge.state["players"][0]["x"] > -3.0
                and bridge.state["boss"]["hp"] < bridge.state["boss"]["max_hp"]
            )
        )
    finally:
        bridge.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=1.0)


def test_multiplayer_preview_bridge_exposes_disconnect_without_raising_during_gameplay():
    bridge = MultiplayerPreviewBridge(_profile(host="127.0.0.1", port=1))

    assert bridge.connect() is False
    assert not bridge.connected
    assert bridge.error
    assert bridge.send_input({"move_x": 0.0, "move_y": 0.0, "attack": False}) is False


def test_network_positions_are_mapped_around_the_game_world_boss_anchor():
    boss = {"x": 2.0, "y": -1.0}
    player = {"x": 5.0, "y": 3.0}

    assert map_network_position(player, boss, origin=(100.0, 200.0), scale=16.0) == (
        148.0,
        264.0,
    )


def test_multiplayer_runtime_profile_missing_file_keeps_ordinary_projects_offline(tmp_path):
    assert load_runtime_multiplayer_profile(Path(tmp_path)) is None


def test_arpg_project_runtime_joins_the_shared_boss_and_draws_the_map_overlay(
    monkeypatch, tmp_path
):
    pygame = pytest.importorskip("pygame")
    from asteria.core import Transform
    from asteria.editor import EditorDocument
    from asteria.multiplayer.client import MultiplayerClient
    from asteria.multiplayer.rules import load_rules
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    demo_root = (
        Path(__file__).resolve().parents[1] / "reference_projects" / "arpg_multiplayer_demo"
    )
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = Project.load_json(
        demo_root / "project.asteria.json", EditorDocument().component_registry
    )
    server = MultiplayerServer(
        ("127.0.0.1", 0),
        store_path=tmp_path / "multiplayer.sqlite3",
        rules=load_rules(demo_root / ".asteria" / "multiplayer-rules.json"),
        adapter=build_boss_adapter(),
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    runtime = PlayableTestRuntime(
        project,
        project.game_start.instantiate(project),
        demo_root,
        width=640,
        height=360,
    )
    second_client = MultiplayerClient()
    try:
        runtime.multiplayer_bridge.profile["port"] = server.server_address[1]
        runtime.open()
        runtime._ui_mode = "field"
        assert runtime.multiplayer_bridge.connected
        second_client.connect(
            "127.0.0.1",
            server.server_address[1],
            "Mage",
            guest_id="arpg-demo-player-two",
        )
        assert _wait_for(lambda: len(runtime.multiplayer_bridge.state.get("players", ())) == 2)

        runtime.multiplayer_bridge.send_input(
            {"move_x": 0.0, "move_y": 0.0, "attack": True}, force=True
        )
        second_client.send_input({"move_x": 0.0, "move_y": 0.0, "attack": True})
        assert _wait_for(
            lambda: runtime.multiplayer_bridge.state.get("boss", {}).get("hp", 240) < 240
        )
        runtime._sync_multiplayer_player()
        runtime._draw_field(False)

        state = runtime.multiplayer_bridge.state
        assert len(state["players"]) == 2
        assert state["boss"]["hp"] < state["boss"]["max_hp"]
        assert pygame.display.get_surface().get_size() == (640, 360)
        assert runtime.game.player.get(Transform).x != runtime._network_origin[0]
    finally:
        second_client.close()
        runtime.close()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=1.0)


def test_project_snapshot_replaces_scene_and_maps_guest_without_local_simulation():
    from types import SimpleNamespace

    from asteria.core import Transform
    from asteria.core.serialization import serialize_scene
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.combat import CombatantComponent
    from asteria.runtime.game_session import GameSessionRuntime
    from asteria.runtime.multiplayer_preview import apply_project_snapshot

    demo_root = (
        Path(__file__).resolve().parents[1] / "reference_projects" / "arpg_multiplayer_demo"
    )
    project = Project.load_json(
        demo_root / "project.asteria.json", EditorDocument().component_registry
    )
    save = project.game_start.instantiate(project)
    game = GameSessionRuntime(project, save)
    game.prepare_action_player()
    resources = game.combat.state(game.player)
    resources.resources.set_current("hp", 17)
    data = serialize_scene(game.scene)
    original_id = game.player.id
    dynamic_id = "f4e34bc9-71ad-418a-a215-94d32cb19a1d"
    player_record = next(e for e in data["entities"] if e["id"] == original_id)
    player_record["id"] = dynamic_id
    transform = next(c for c in player_record["components"] if c["type"] == "asteria.Transform")
    transform["fields"]["x"] = 123.0
    runtime = SimpleNamespace(project=project, game=game, save=save)
    snapshot = {
        "schema": "asteria.multiplayer.project_state",
        "scene": data,
        "players": [
            {"player_id": "guest-two", "entity_id": dynamic_id, "game_save": save.to_data()}
        ],
        "combatants": {
            dynamic_id: {
                "resources": resources.resources.to_data(),
                "stats": resources.stats.to_data(),
                "tags": resources.tags.to_data(),
            }
        },
        "controllers": {dynamic_id: {"facing": "left", "intent_x": -1}},
        "actions": {dynamic_id: {}},
        "projectiles": [{"uid": 1, "projectile_id": "test", "x": 5, "y": 7, "vx": 9, "vy": 0}],
    }
    assert apply_project_snapshot(runtime, snapshot, "guest-two")
    assert game.player.id == dynamic_id
    assert game.scene.get_entity(original_id) is None
    assert game.player.get(Transform).x == 123
    assert game.player.get(CombatantComponent).state.resources.current("hp") == 17
    assert runtime.save.player_entity_id == dynamic_id
    assert game.projectiles.views()[0].x == 5
    assert dynamic_id in game.entity_actions.running


def test_authoritative_menu_commands_do_not_mutate_projected_save():
    from types import SimpleNamespace

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.game_session import GameSessionRuntime
    from asteria.runtime.multiplayer_preview import install_authoritative_commands

    demo_root = (
        Path(__file__).resolve().parents[1] / "reference_projects" / "arpg_multiplayer_demo"
    )
    project = Project.load_json(
        demo_root / "project.asteria.json", EditorDocument().component_registry
    )
    game = GameSessionRuntime(project, project.game_start.instantiate(project))
    calls = []
    runtime = SimpleNamespace(
        game=game,
        _multiplayer_connected=lambda: True,
        multiplayer_bridge=SimpleNamespace(
            send_command=lambda command, payload: calls.append((command, payload))
        ),
    )
    before = game.save.to_data()
    install_authoritative_commands(runtime)
    game.equip_from_bag("ignored-client-actor", 0)
    game.allocate_progression("ignored-client-actor", "tree", "node", 2)
    game.unequip_to_bag("ignored-client-actor", "weapon")
    assert calls == [
        ("equip", {"index": 0}),
        ("allocate", {"graph_id": "tree", "node_id": "node", "count": 2}),
        ("unequip", {"slot_id": "weapon"}),
    ]
    assert game.save.to_data() == before


def test_runtime_forwards_ability_inputs_and_immediately_releases_them():
    from types import SimpleNamespace

    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    runtime = object.__new__(PlayableTestRuntime)
    calls = []
    runtime.multiplayer_bridge = SimpleNamespace(
        connected=True, send_input=lambda state, force=False: calls.append((state, force)) or True
    )
    runtime.message = "connected"
    runtime._send_multiplayer_input(0, 0, {"ability_1": 1, "dash": 1})
    runtime._send_multiplayer_input(0, 0, {})
    assert calls[0][0]["actions"] == {"ability_1": 1, "dash": 1}
    assert calls[1][0]["actions"] == {}
    assert all(force for _, force in calls)


def test_project_server_drives_real_runtime_frames_and_skill_screen(monkeypatch, tmp_path):
    pygame = pytest.importorskip("pygame")
    from asteria.core import Transform
    from asteria.editor import EditorDocument
    from asteria.multiplayer.client import MultiplayerClient
    from asteria.multiplayer.persistence import SQLiteMultiplayerStore
    from asteria.multiplayer.project_demo import build_project_adapter
    from asteria.project import Project
    from asteria.runtime.network_bag_screen import NetworkSkillTreeScreen
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    demo_root = (
        Path(__file__).resolve().parents[1] / "reference_projects" / "arpg_multiplayer_demo"
    )
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    store = SQLiteMultiplayerStore(tmp_path / "world.sqlite3")
    adapter = build_project_adapter(store=store, project_path=demo_root / "project.asteria.json")
    server = MultiplayerServer(("127.0.0.1", 0), adapter=adapter, store=store)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    project = Project.load_json(
        demo_root / "project.asteria.json", EditorDocument().component_registry
    )
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), demo_root, width=960, height=540
    )
    other = MultiplayerClient()
    try:
        runtime.multiplayer_bridge.profile["port"] = server.server_address[1]
        runtime.open()
        runtime._ui_mode = "field"
        other.connect("127.0.0.1", server.server_address[1], "Second", guest_id="frame-player-two")
        assert _wait_for(lambda: len(runtime.multiplayer_bridge.state["players"]) == 2)
        runtime._frame([], 1 / 60)
        assert not runtime._multiplayer_error
        from asteria.runtime.input_map import RawInputState

        j_actions = runtime.input.input_map.evaluate(RawInputState(keys={"j"})).actions
        f_actions = runtime.input.input_map.evaluate(RawInputState(keys={"f"})).actions
        assert j_actions["attack"] == 1 and j_actions["pickup"] == 0
        assert f_actions["pickup"] == 1 and f_actions["attack"] == 0
        player_id = runtime.multiplayer_bridge.player_id
        local_entity_id = runtime.game.player.id
        assert local_entity_id == adapter.players[player_id].player.id
        assert runtime.game.scene.get_entity(adapter.players["frame-player-two"].player.id)

        # A connected frame must never invoke the client's combat/AI/event simulation.
        def local_simulation_forbidden(*args, **kwargs):
            raise AssertionError("client simulated authoritative gameplay")

        runtime.game.field_update = local_simulation_forbidden
        runtime.game.update_events = local_simulation_forbidden
        runtime.game.prepare_action_player = local_simulation_forbidden
        start = adapter.players[player_id].player.get(Transform).x
        runtime._frame([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a)], 1 / 60)
        assert _wait_for(lambda: adapter.players[player_id].player.get(Transform).x < start), (
            start,
            adapter.players[player_id].player.get(Transform).x,
            runtime.input.current.actions.get("move_left"),
            adapter.inputs[player_id].actions.get("move_left"),
            runtime._ui_mode,
            runtime._network_event_busy,
            runtime.game.cutscene_active,
            runtime.multiplayer_bridge.error,
        )
        runtime._frame([pygame.event.Event(pygame.KEYUP, key=pygame.K_a)], 1 / 60)
        # Original skill screen keyboard confirmation sends allocation to the server.
        screen = NetworkSkillTreeScreen(runtime)
        selected = None
        for index, graph_id in enumerate(screen.graphs()):
            graph = runtime.project.rpg_database.progression_graphs[graph_id]
            allocation = screen._allocation()
            for node in graph.nodes:
                if allocation.preview_allocate(graph_id, node.node_id, 1).allowed:
                    selected = (index, graph_id, node.node_id)
                    break
            if selected:
                break
        assert selected is not None
        screen.graph_index, graph_id, screen.node_id = selected
        before = screen._allocation().rank(graph_id, screen.node_id)
        runtime._skill_tree, runtime._ui_mode = screen, "skills"
        runtime._frame([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)], 1 / 60)
        node_id = screen.node_id
        server_session = adapter.players[player_id]
        actor_id = server_session._actor_of(server_session.player)
        assert _wait_for(
            lambda: (
                server_session.save.rpg_state.progression_allocations[actor_id].rank(
                    graph_id, node_id
                )
                == before + 1
            )
        )

        def projected():
            runtime._sync_multiplayer_player()
            return screen._allocation().rank(graph_id, node_id) == before + 1

        assert _wait_for(projected)
        runtime._frame([pygame.event.Event(pygame.KEYUP, key=pygame.K_RETURN)], 1 / 60)
        assert screen._allocation().rank(graph_id, node_id) == before + 1
        # Saving is a server command; it never writes a client save file.
        runtime.save_playtest()
        assert _wait_for(
            lambda: bool(store.get_player(player_id)["game_state"].get("project_demo"))
        )
        runtime.multiplayer_bridge.close()
        before_disconnect = runtime.save.to_data()
        assert runtime._network_gameplay_frozen()
        assert runtime.game.equip_from_bag(actor_id, 0) is None
        assert runtime.save_playtest() is None
        runtime.open_slots("load")
        runtime._frame([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a)], 1 / 60)
        assert runtime.save.to_data() == before_disconnect
    finally:
        other.close()
        runtime.close()
        server.shutdown()
        server.server_close()
        store.close()
        thread.join(timeout=1)


def test_project_snapshot_keeps_each_guests_class_appearance():
    import copy
    from types import SimpleNamespace

    from asteria.core.serialization import serialize_scene
    from asteria.project import Project
    from asteria.runtime.actor_link import ClassAppearanceComponent
    from asteria.runtime.component_registry import default_component_registry
    from asteria.runtime.components2d import SpriteRenderer2D
    from asteria.runtime.game_session import GameSessionRuntime
    from asteria.runtime.multiplayer_preview import apply_project_snapshot

    root = Path(__file__).resolve().parents[1] / "reference_projects" / "arpg_multiplayer_demo"
    project = Project.load_json(root / "project.asteria.json", default_component_registry())
    save = project.game_start.instantiate(project)
    game = GameSessionRuntime(project, save)
    scene = serialize_scene(game.scene)
    original = next(e for e in scene["entities"] if e["id"] == game.player.id)
    peer = copy.deepcopy(original)
    peer["id"] = "88463086-1f65-4f03-a53a-f0bb74c5e1fe"
    scene["entities"].append(peer)
    local_save, remote_save = save.to_data(), save.to_data()
    for value, class_id in ((local_save, "warrior"), (remote_save, "mage")):
        progress = value["rpg_state"]["actor_progression"]["hero"]
        progress["unlocked_class_ids"].append(class_id)
        progress["active_class_ids"] = [class_id]
    runtime = SimpleNamespace(project=project, game=game, save=save)
    state = {
        "schema": "asteria.multiplayer.project_state",
        "scene": scene,
        "players": [
            {"player_id": "local", "entity_id": original["id"], "game_save": local_save},
            {"player_id": "remote", "entity_id": peer["id"], "game_save": remote_save},
        ],
    }
    assert apply_project_snapshot(runtime, state, "local")
    local, remote = game.player, game.scene.get_entity(peer["id"])
    assert (
        local.get(SpriteRenderer2D).sprite_sheet_asset_id
        == local.get(ClassAppearanceComponent).parsed()["warrior"][0]
    )
    assert (
        remote.get(SpriteRenderer2D).sprite_sheet_asset_id
        == remote.get(ClassAppearanceComponent).parsed()["mage"][0]
    )
    assert (
        local.get(SpriteRenderer2D).sprite_sheet_asset_id
        != remote.get(SpriteRenderer2D).sprite_sheet_asset_id
    )


def test_command_confirmation_waits_for_projected_revision():
    bridge = MultiplayerPreviewBridge(_profile(host="127.0.0.1", port=8765))
    bridge._pending_commands["operation"] = "equip"
    bridge._command_results.append({"accepted": True, "command_id": "operation", "revision": 7})
    assert bridge.command_results(6) == ()
    assert bridge.command_results(7) == (
        {"accepted": True, "command_id": "operation", "revision": 7, "command": "equip"},
    )
    assert bridge.command_results(7) == ()


def test_opted_in_project_connection_failure_freezes_gameplay_without_enabling_offline_fallback():
    from types import SimpleNamespace

    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    runtime = object.__new__(PlayableTestRuntime)
    runtime.multiplayer_bridge = SimpleNamespace(connected=False)
    runtime._authoritative_project_mode = True
    assert runtime._network_gameplay_frozen()
    runtime._authoritative_project_mode = False
    assert not runtime._network_gameplay_frozen()
    runtime.multiplayer_bridge = None
    assert not runtime._network_gameplay_frozen()


def test_bridge_reconnect_accepts_a_restarted_servers_revision_zero():
    class FakeClient:
        connected = False
        player_id = "guest-1"

        def __init__(self, **kwargs):
            pass

        def close(self):
            self.connected = False

        def connect(self, *args, **kwargs):
            self.connected = True
            return {"revision": 0, "state": {"server": "restarted"}}

    bridge = MultiplayerPreviewBridge(
        _profile(host="127.0.0.1", port=8765), client_factory=FakeClient
    )
    bridge._revision = 400
    bridge._state = {"server": "old"}
    assert bridge.connect()
    assert bridge.revision == 0
    assert bridge.state == {"server": "restarted"}
    bridge.close()


def test_project_snapshot_replaces_only_the_implicit_boss_attack_binding():
    from asteria.runtime.input_map import (
        InputActionMap,
        InputActionTracker,
        InputBinding,
        RawInputState,
    )
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    runtime = object.__new__(PlayableTestRuntime)
    runtime.input = InputActionTracker(
        InputActionMap(
            {"attack": [InputBinding("key", "f")], "pickup": [InputBinding("key", "f")]}
        )
    )
    runtime._network_legacy_attack_injected = True
    runtime._enable_authoritative_project_controls()
    assert runtime.input.input_map.evaluate(RawInputState(keys={"j"})).actions["attack"] == 1
    actions = runtime.input.input_map.evaluate(RawInputState(keys={"f"})).actions
    assert actions["attack"] == 0 and actions["pickup"] == 1
    assert runtime._authoritative_project_mode
    # Project-authored or user-chosen bindings survive snapshot mode detection.
    runtime.input.input_map.set_bindings("attack", [InputBinding("key", "x")])
    runtime._enable_authoritative_project_controls()
    assert runtime.input.input_map.bindings("attack") == (InputBinding("key", "x"),)


def test_bridge_interpolates_remote_positions_and_tracks_accepted_input():
    moments = iter((1.0, 1.1))
    bridge = MultiplayerPreviewBridge(
        _profile(host="127.0.0.1", port=8765), clock=lambda: next(moments)
    )
    bridge._on_message(
        {
            "type": "game_update",
            "revision": 1,
            "state": {"players": [{"player_id": "remote", "x": 0, "y": 0}]},
        }
    )
    bridge._on_message(
        {
            "type": "game_update",
            "revision": 2,
            "state": {"players": [{"player_id": "remote", "x": 10, "y": 4}]},
        }
    )
    bridge._on_message({"type": "input_ack", "sequence": 7, "accepted": True, "reason": ""})

    assert bridge.remote_positions(now=1.15)["remote"] == pytest.approx((5, 2))
    assert bridge.acked_input_sequence == 7
    assert bridge.acked_input_revision == 2


def test_multiplayer_preview_predicts_locally_and_reconciles_acked_inputs():
    from types import SimpleNamespace

    from asteria.multiplayer.smoothing import InputPredictor
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    transform = SimpleNamespace(x=100.0, y=200.0)
    player = SimpleNamespace(get=lambda _component: transform)
    save = SimpleNamespace(player_position=(100.0, 200.0))
    state = {
        "boss": {"x": 0.0, "y": 0.0},
        "players": [{"player_id": "local", "x": -2.6, "y": 0.0}],
    }
    bridge = SimpleNamespace(
        connected=True,
        player_id="local",
        state=state,
        acked_input_sequence=1,
        acked_input_revision=4,
        snapshot=lambda: (state, (), 5),
    )
    runtime = object.__new__(PlayableTestRuntime)
    runtime.multiplayer_bridge = bridge
    runtime.multiplayer_profile = {"preview_movement_speed": 4.0}
    runtime._authoritative_project_mode = False
    runtime._network_origin = (100.0, 200.0)
    runtime._network_scale = 16.0
    runtime._network_predictor = InputPredictor((-3.0, 0.0), speed=4.0)
    runtime._network_predictor.apply_local(1, 1.0, 0.0, 0.1)
    runtime._network_predictor.apply_local(2, 1.0, 0.0, 0.1)
    runtime._network_prediction_sequence = 2
    runtime._network_input_prediction_sequences = {1: 1}
    runtime._network_prediction_reconciled_revision = -1
    runtime._network_revision = -1
    runtime.game = SimpleNamespace(player=player, save=save)

    runtime._predict_multiplayer_player(1.0, 0.0, 0.1)
    assert runtime._network_predictor.position == pytest.approx((-1.8, 0.0))
    runtime._sync_multiplayer_player()

    assert runtime._network_predictor.position == pytest.approx((-1.8, 0.0))
    assert (transform.x, transform.y) == pytest.approx((71.2, 200.0))
    assert runtime._network_input_prediction_sequences == {}
