"""Validate four independent native Cocoa clients; run from a desktop terminal on macOS."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DEMO = ROOT / "reference_projects/diablo_multiplayer_demo"


def wait(p, timeout=30):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if p():
            return
        time.sleep(0.02)
    raise TimeoutError("verification deadline exceeded")


if len(sys.argv) > 1:
    folder = Path(sys.argv[1])
    player = sys.argv[2]
    port = int(sys.argv[3])
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=640, height=360
    )
    runtime.multiplayer_bridge.profile.update(port=port, guest_id=player, player_name=player)
    try:
        runtime.open()
        runtime._ui_mode = "field"
        assert runtime.multiplayer_bridge.connected
        wait(lambda: (folder / "go").exists())
        time.sleep(0.15)
        assert runtime.multiplayer_bridge.send_input(
            {"move_x": 0.0, "move_y": 0.0, "attack": True}, force=True
        )
        runtime.multiplayer_bridge.send_command("pickup", {"operation_id": player + "-ground"})
        end = time.monotonic() + 15
        while time.monotonic() < end:
            runtime.pg.event.pump()
            runtime._sync_multiplayer_player()
            runtime._draw_field(False)
            runtime.pg.display.flip()
            state = runtime.multiplayer_bridge.state
            if (
                not state.get("boss", {}).get("alive", True)
                and len(state.get("players", [])) == 4
                and all(p["experience"] == 100 for p in state["players"])
            ):
                driver = runtime.pg.display.get_driver()
                assert driver == "cocoa", driver
                runtime.pg.image.save(
                    runtime.pg.display.get_surface(), str(folder / f"{player}.png")
                )
                from asteria.runtime.network_bag_screen import NetworkBagScreen

                NetworkBagScreen(runtime).draw()
                runtime.pg.display.flip()
                runtime.pg.image.save(
                    runtime.pg.display.get_surface(), str(folder / f"{player}-bag.png")
                )
                (folder / f"{player}.json").write_text(
                    json.dumps({"driver": driver, "state": state})
                )
                wait(lambda: (folder / "release").exists())
                break
            time.sleep(0.02)
        else:
            raise AssertionError(f"{player} failed to observe four rewards: {state}")
    finally:
        runtime.close()
else:
    from asteria.multiplayer.boss_demo import build_boss_adapter
    from asteria.multiplayer.persistence import SQLiteMultiplayerStore
    from asteria.multiplayer.rules import load_rules
    from asteria.multiplayer.server import MultiplayerServer

    folder = Path(tempfile.mkdtemp(prefix="asteria-four-native-", dir="/private/tmp"))
    server = MultiplayerServer(
        ("127.0.0.1", 0),
        store_path=folder / "server.sqlite3",
        rules=load_rules(DEMO / ".asteria/multiplayer-rules.json"),
        adapter=build_boss_adapter(),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    workers = []
    logs = []
    try:
        for i in range(1, 5):
            log = (folder / f"player-{i}.log").open("w")
            logs.append(log)
            env = dict(os.environ, SDL_VIDEODRIVER="cocoa", SDL_AUDIODRIVER="coreaudio")
            workers.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        __file__,
                        str(folder),
                        f"player-{i}",
                        str(server.server_address[1]),
                    ],
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
            )
        wait(lambda: len(server.adapter.players) == 4)
        (folder / "go").touch()
        wait(lambda: all((folder / f"player-{i}.json").exists() for i in range(1, 5)))
        assert all(
            server.adapter.store.get_player(f"player-{i}")["experience"] == 100
            for i in range(1, 5)
        )
        snapshots = [
            json.loads((folder / f"player-{i}.json").read_text())["state"] for i in range(1, 5)
        ]
        for snapshot in snapshots:
            assert sum(p["inventory"].get("ancient_shard", 0) for p in snapshot["players"]) == 1
            assert sum(p["inventory"].get("healing_crystal", 0) for p in snapshot["players"]) == 1
            assert snapshot["combat_log"][-1]["player_id"] == snapshot["kill_credit"]
        (folder / "release").touch()
        assert all(p.wait(timeout=15) == 0 for p in workers)
        server.shutdown()
        server.server_close()
        thread.join(2)
        store = SQLiteMultiplayerStore(folder / "server.sqlite3")
        try:
            assert all(store.get_player(f"player-{i}")["experience"] == 100 for i in range(1, 5))
            assert (
                sum(
                    store.get_player(f"player-{i}")["inventory"].get("ancient_shard", 0)
                    for i in range(1, 5)
                )
                == 1
            )
            assert (
                sum(
                    store.get_player(f"player-{i}")["inventory"].get("healing_crystal", 0)
                    for i in range(1, 5)
                )
                == 1
            )
        finally:
            store.close()
        (folder / "result.json").write_text(
            json.dumps(
                {
                    "passed": True,
                    "independent_processes": 4,
                    "native_driver": "cocoa",
                    "experience_each": 100,
                    "sqlite_reopened": True,
                }
            )
        )
        print("FOUR_NATIVE_PASS " + str(folder), flush=True)
    finally:
        (folder / "release").touch()
        for p in workers:
            if p.poll() is None:
                p.terminate()
        for log in logs:
            log.close()
        print("ARTIFACTS " + str(folder), flush=True)
