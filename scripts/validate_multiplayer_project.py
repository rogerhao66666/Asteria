"""Native four-process acceptance for the original project ECS; run on macOS desktop."""

from __future__ import annotations

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
DEMO = ROOT / "reference_projects/arpg_multiplayer_demo"


def wait(predicate, timeout=60):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if predicate():
            return
        time.sleep(0.03)
    raise TimeoutError("native project acceptance deadline exceeded")


if len(sys.argv) == 4:
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    folder, pid, port = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    rt = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=960, height=540
    )
    rt.multiplayer_bridge.profile.update(port=port, guest_id=pid, player_name=pid)
    try:
        rt.open()
        rt._ui_mode = "field"
        assert rt.multiplayer_bridge.connected
        wait(lambda: (folder / "go").exists())
        rt._frame([], 0.04)
        assert rt.multiplayer_bridge.state["schema"] == "asteria.multiplayer.project_state"
        rt.game.allocate_progression("hero", "attributes", "a_str", 1)
        began = time.monotonic()
        pressed = False
        while time.monotonic() - began < 80:
            rt.pg.event.pump()
            events = []
            attack = int((time.monotonic() - began) / 0.4) % 2 == 0
            if attack != pressed:
                events.append(
                    rt.pg.event.Event(rt.pg.KEYDOWN if attack else rt.pg.KEYUP, key=rt.pg.K_j)
                )
                pressed = attack
            rt._frame(events, 0.04)
            rt.pg.display.flip()
            state = rt.multiplayer_bridge.state
            players = state.get("players", [])
            if len(players) == 4 and all(p["experience"] >= 100 for p in players):
                rt._frame([rt.pg.event.Event(rt.pg.KEYUP, key=rt.pg.K_j)], 0.04)
                # Walk to each owned original ECS drop and use the actual pickup input.
                import math

                from asteria.core import Transform
                from asteria.runtime.loot import LootComponent, LooterComponent

                movement_keys = {"a": rt.pg.K_a, "d": rt.pg.K_d, "w": rt.pg.K_w, "s": rt.pg.K_s}
                held = set()
                loot_deadline = time.monotonic() + 15
                while time.monotonic() < loot_deadline:
                    owners = rt.multiplayer_bridge.state.get("loot_owners", {})
                    candidates = [
                        e for e, _ in rt.game.scene.query(LootComponent) if owners.get(e.id) == pid
                    ]
                    if not candidates:
                        break
                    pos = rt.game.player.get(Transform)
                    target = min(
                        candidates,
                        key=lambda e: math.hypot(
                            e.get(Transform).x - pos.x, e.get(Transform).y - pos.y
                        ),
                    )
                    t = target.get(Transform)
                    close = (
                        math.hypot(t.x - pos.x, t.y - pos.y)
                        < rt.game.player.get(LooterComponent).pickup_radius * 0.85
                    )
                    desired = set()
                    if not close:
                        if abs(t.x - pos.x) > 3:
                            desired.add("d" if t.x > pos.x else "a")
                        if abs(t.y - pos.y) > 3:
                            desired.add("s" if t.y > pos.y else "w")
                    movement = [
                        rt.pg.event.Event(rt.pg.KEYDOWN, key=movement_keys[k])
                        for k in desired - held
                    ]
                    movement += [
                        rt.pg.event.Event(rt.pg.KEYUP, key=movement_keys[k])
                        for k in held - desired
                    ]
                    held = desired
                    if close:
                        movement.append(rt.pg.event.Event(rt.pg.KEYDOWN, key=rt.pg.K_g))
                    rt._frame(movement, 0.04)
                    rt._frame([rt.pg.event.Event(rt.pg.KEYUP, key=rt.pg.K_g)], 0.04)
                    rt.pg.display.flip()
                    time.sleep(0.06)
                rt._frame(
                    [rt.pg.event.Event(rt.pg.KEYUP, key=movement_keys[k]) for k in held], 0.04
                )
                if rt.game.save.rpg_state.equipment_bag:
                    rt.game.equip_from_bag("hero", 0)
                for _ in range(15):
                    rt._frame([], 0.04)
                    time.sleep(0.04)
                rt.save_playtest()
                for _ in range(15):
                    rt._frame([], 0.04)
                    time.sleep(0.04)
                assert rt.pg.display.get_driver() == "cocoa"
                rt.pg.image.save(rt.pg.display.get_surface(), str(folder / f"{pid}.png"))
                (folder / f"{pid}.json").write_text(json.dumps(rt.multiplayer_bridge.state))
                wait(lambda: (folder / "release").exists())
                break
            time.sleep(0.04)
        else:
            raise AssertionError(
                f"{pid}: XP/state not converged; error={rt._multiplayer_error}; players={players}"
            )
    finally:
        rt.close()
else:
    from asteria.multiplayer.persistence import SQLiteMultiplayerStore
    from asteria.multiplayer.project_demo import build_project_adapter
    from asteria.multiplayer.rules import load_rules
    from asteria.multiplayer.server import MultiplayerServer

    rules = load_rules(DEMO / ".asteria/multiplayer-rules.json")
    rules["project_runtime"] = {
        "start_scene": "Greenvale Fields",
        "start_position": [896, 212],
        "initial_class_cycle": ["warrior", "ranger", "mage", "warrior"],
        "initial_points": {"ap": 10},
    }
    folder = Path(tempfile.mkdtemp(prefix="asteria-project-native-", dir="/private/tmp"))
    store = SQLiteMultiplayerStore(folder / "server.sqlite3")
    adapter = build_project_adapter(
        store=store, project_path=DEMO / "project.asteria.json", project_root=DEMO, rules=rules
    )
    server = MultiplayerServer(("127.0.0.1", 0), adapter=adapter, store=store, rules=rules)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    processes, logs = [], []
    try:
        for i in range(1, 5):
            log = (folder / f"player-{i}.log").open("w")
            logs.append(log)
            env = dict(os.environ, SDL_VIDEODRIVER="cocoa", SDL_AUDIODRIVER="coreaudio")
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        __file__,
                        str(folder),
                        f"player-{i}",
                        str(server.server_address[1]),
                    ],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    env=env,
                )
            )
        wait(lambda: len(adapter.players) == 4)
        (folder / "go").touch()

        def completed():
            if any(p.poll() is not None and p.returncode != 0 for p in processes):
                raise AssertionError(f"native client failed; see logs in {folder}")
            return all((folder / f"player-{i}.json").exists() for i in range(1, 5))

        wait(completed, timeout=100)
        records = {f"player-{i}": store.get_player(f"player-{i}") for i in range(1, 5)}
        assert all(p["experience"] >= 100 for p in records.values())
        assert len({s.player.id for s in adapter.players.values()}) == 4
        import sqlite3

        with sqlite3.connect(folder / "server.sqlite3") as database:
            claims = database.execute(
                "SELECT drop_id, owner_player_id, claimed_by FROM world_drops "
                "WHERE claimed_by IS NOT NULL"
            ).fetchall()
            assert claims, "native original loot was never picked up"
            assert all(owner == claimed for _, owner, claimed in claims)
        assert any(
            any(
                items
                for items in record["game_state"]["project_demo"]["save"]["rpg_state"]["loadouts"][
                    "hero"
                ]["equipped"].values()
            )
            for record in records.values()
        ), "no original equipment was equipped"

        (folder / "release").touch()
        assert all(p.wait(timeout=20) == 0 for p in processes)
        server.shutdown()
        server.server_close()
        thread.join(2)
        store.close()
        with SQLiteMultiplayerStore(folder / "server.sqlite3") as reopened:
            assert all(
                reopened.get_player(pid)["game_state"].get("project_demo") for pid in records
            )
            assert all(
                reopened.get_player(pid)["experience"] == r["experience"]
                for pid, r in records.items()
            )
        (folder / "result.json").write_text(
            json.dumps(
                {
                    "passed": True,
                    "processes": 4,
                    "driver": "cocoa",
                    "original_ecs_combat": True,
                    "original_loot_claimed": True,
                    "equipment_equipped": True,
                    "sqlite_reopened": True,
                }
            )
        )
        print("FOUR_PROJECT_NATIVE_PASS " + str(folder), flush=True)
    finally:
        (folder / "release").touch()
        for p in processes:
            if p.poll() is None:
                p.terminate()
        for log in logs:
            log.close()
        print("ARTIFACTS " + str(folder), flush=True)
