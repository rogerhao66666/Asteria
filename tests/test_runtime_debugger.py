"""CB10 / EDT-10, EDT-11: live debugger over the loopback debug channel, play-test spawn, log."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pygame = pytest.importorskip("pygame")

from asteria.runtime.debug_server import DebugClient, DebugClientError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"


@pytest.fixture
def attached(runtime):
    server = runtime.enable_debugger(token="secret-token")
    client = DebugClient(server.port, "secret-token", pump=lambda: runtime._frame([], 0.016))
    client.connect()
    yield runtime, client
    client.close()


def test_snapshot_shows_the_spec_inspection_items(attached):
    runtime, client = attached
    runtime._ui_mode = "field"
    snapshot = client.request("snapshot")
    assert snapshot["mode"] == "field"
    assert {"player", "party", "inventory", "currencies", "switches", "variables", "quests", "world"} <= set(snapshot)
    hero = snapshot["party"]["hero_01"]
    assert "vitality" in hero["resources"] and "power" in hero["stats"] and isinstance(hero["abilities"], list)


def test_field_debug_actions_change_the_live_game(attached):
    runtime, client = attached
    runtime._ui_mode = "field"
    game = runtime.game
    before = game.save.rpg_state.inventory.count("ether_leaf")
    assert client.request("give_item", item_id="ether_leaf", quantity=3) == before + 3
    assert client.request("remove_item", item_id="ether_leaf", quantity=1) == before + 2
    assert client.request("teleport", x=12.5, y=-4) == [12.5, -4.0]
    assert client.request("set_resource", member_id="hero_01", resource_id="vitality", value=100) == 100
    assert game.save.rpg_state.actor_snapshots["hero_01"].resources["values"]["vitality"]["current"] == 100
    client.request("set_stat", member_id="hero_01", stat="power", value=999)
    assert game.save.rpg_state.actor_snapshots["hero_01"].stats["values"]["power"] == 999
    client.request("set_switch", name="debug.flag", value=True)
    client.request("set_variable", name="debug.count", value="7")
    assert (
        game.save.event_context.get_switch("debug.flag") and game.save.event_context.get_variable("debug.count") == "7"
    )
    assert client.request("trigger_event", program_id="boss_interaction_event") == "boss_interaction_event"
    with pytest.raises(DebugClientError):
        client.request("give_item", item_id="no_such_item")
    with pytest.raises(DebugClientError):
        client.request("format_disk")
    assert client.request("snapshot")["inventory"]["ether_leaf"] == before + 2  # the game kept running


def test_battle_debug_actions_states_spawn_and_kill(attached):
    runtime, client = attached
    game = runtime.game
    game.start_encounter("boss_room")
    snapshot = client.request("snapshot")
    assert set(snapshot["battle"]["members"]) == set(game.battle.members)
    assert client.request("set_resource", member_id="hero_01", resource_id="vitality", value=50) == 50
    spawned = client.request("spawn_enemy", enemy_id="mender_wisp")
    assert spawned in game.battle.members and spawned in game.active_enemy_ids()
    assert client.request("kill_enemy", target_id=spawned) is True
    assert spawned not in game.active_enemy_ids()
    with pytest.raises(DebugClientError):
        client.request("teleport", x=0, y=0)  # field only


def test_requests_without_the_token_are_refused(runtime):
    server = runtime.enable_debugger(token="right")
    intruder = DebugClient(server.port, "wrong", pump=server.poll)
    intruder.connect()
    with pytest.raises(DebugClientError, match="invalid token"):
        intruder.request("give_item", item_id="ether_leaf")
    intruder.close()


def test_debugger_dock_attaches_inspects_and_executes(runtime):
    from PySide6.QtWidgets import QApplication

    from asteria.editor.debugger_widget import DebuggerWidget

    QApplication.instance() or QApplication([])
    server = runtime.enable_debugger(token="t")
    widget = DebuggerWidget()
    widget.attach(server.port, "t", pump=lambda: runtime._frame([], 0.016))
    snapshot = widget.refresh()
    assert snapshot is not None and widget.tree.topLevelItemCount() >= 8
    widget.set_args("give_item", item_id="ether_leaf", quantity=2)
    before = runtime.game.save.rpg_state.inventory.count("ether_leaf")
    assert widget.execute_current() == before + 2
    assert widget.history.count() == 1 and widget.history.item(0).text().startswith("✓ give_item")
    widget.set_args("give_item", item_id="nope", quantity=1)
    assert widget.execute_current() is None and widget.history.item(1).text().startswith("✗")
    widget.detach()


def test_play_test_spawn_point_and_debug_channel_in_a_separate_process(tmp_path):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    log = tmp_path / "game.log"
    with open(log, "w") as out:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "asteria.runtime.preview",
                str(ROOT / "project.asteria.json"),
                "--debug-port",
                str(port),
                "--debug-token",
                "tok",
                "--spawn",
                "20",
                "-6",
                "--frames",
                "4000",
            ],
            stdout=out,
            stderr=subprocess.STDOUT,
            env=env,
        )
    try:
        client = DebugClient(port, "tok", timeout=5)
        client.connect(retries=100, delay=0.1)
        snapshot = client.request("snapshot")
        assert snapshot["mode"] == "field" and snapshot["player"]["position"] == [20.0, -6.0]
        assert client.request("give_item", item_id="ether_leaf", quantity=1) >= 1
        client.close()
        deadline = time.time() + 5
        while "asteria-debug: listening" not in log.read_text() and time.time() < deadline:
            time.sleep(0.05)
        assert f"asteria-debug: listening on 127.0.0.1:{port}" in log.read_text()  # play-test log captured
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_launcher_passes_debug_spawn_and_captures_the_log(tmp_path):
    from asteria.core import Scene
    from asteria.editor import EditorDocument
    from asteria.editor.playmode import create_play_session
    from asteria.editor.runtime_launcher import launch_play_session
    from asteria.project import Project

    project = Project("P")
    project.add_scene(Scene("S"))
    session = create_play_session(EditorDocument(project, file_path=tmp_path / "p.asteria.json"))
    captured = {}

    class Fake:
        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

    def factory(args, **kwargs):
        captured.update(args=args, kwargs=kwargs)
        kwargs["stdout"].write("hello from the game\n")
        kwargs["stdout"].flush()
        return Fake()

    process = launch_play_session(session, popen_factory=factory, debug=True, spawn=(3, 4), capture_log=True)
    args = captured["args"]
    assert args[args.index("--spawn") + 1 : args.index("--spawn") + 3] == ["3.0", "4.0"]
    assert int(args[args.index("--debug-port") + 1]) == process.debug_port and process.debug_token
    assert "hello from the game" in process.read_log()
    process.stop()


def test_shell_play_from_selection_restart_and_debugger_attach(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QApplication

    from asteria.core import Entity, Scene, Transform
    from asteria.editor import shell as shell_module
    from asteria.editor.runtime_launcher import RuntimeProcess
    from asteria.project import Project

    app = QApplication.instance() or QApplication([])
    project = Project("P")
    scene = project.add_scene(Scene("Map"))
    hero = scene.add_entity(Entity("Hero"))
    hero.add_component(Transform(40.0, 12.0))
    calls = []

    class Fake:
        def poll(self):
            return None

        def terminate(self):
            calls.append("terminate")

        def wait(self, timeout=None):
            return 0

    def fake_launch(session, **kwargs):
        calls.append(kwargs)
        path = tmp_path / f"snap{len(calls)}.json"
        path.write_text("{}")
        return RuntimeProcess(Fake(), path, None, 50000 + len(calls), "tok")

    monkeypatch.setattr(shell_module, "launch_play_session", fake_launch)
    window = shell_module.AsteriaEditorWindow(project)
    window.document.file_path = tmp_path / "p.asteria.json"
    window.document.selection.set_single("entity", hero)
    assert window.play_from_selection()
    assert calls[-1] == {"debug": True, "capture_log": True, "spawn": (40.0, 12.0)}
    assert window.debugger_widget.client is not None and window.debugger_widget.client.port == 50001
    assert window.restart_play()  # stops and relaunches the same way
    assert "terminate" in calls and calls[-1]["spawn"] == (40.0, 12.0)
    assert window.debugger_widget.client.port == 50003
    window.stop_play()
    assert window.debugger_widget.client is None
    window.document.mark_saved()
    window.close()
    app.processEvents()
