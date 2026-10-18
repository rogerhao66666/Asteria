"""Real-window run of the Full Verification second skill wave (macOS, real Cocoa window, key
events).

    python scripts/full_verification_b11_live_check.py OUTPUT_DIR

The hero opens a skill that has forms (the form list shows before the target), casts it, and
the companion hands a boost point over. Screenshots and ``results.json`` land in OUTPUT_DIR.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(DEMO))
for key in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER", "QT_QPA_PLATFORM"):
    os.environ.pop(key, None)


def _helpers():
    spec = importlib.util.spec_from_file_location(
        "real_machine_validation", REPO / "scripts" / "real_machine_validation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv=None):
    import pygame
    import run_trial_smoke as smoke

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    argv = list(sys.argv[1:] if argv is None else argv)
    evidence = REPO / "docs" / "audits" / "evidence" / "full_verification_b11"
    out = Path(argv[0] if argv else evidence)
    out.mkdir(parents=True, exist_ok=True)
    helper = _helpers()
    pump, key = helper._pump, helper._key
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=1280, height=720
    )
    runtime.open()
    driver = pygame.display.get_driver()
    game, checks, shots = runtime.game, {}, []

    def press(k, wait=0.1):
        key(k)
        pump(runtime, 0.04)
        key(k, up=True)
        pump(runtime, wait)

    def shot(name):
        pygame.image.save(runtime.capture(), str(out / name))
        shots.append(name)

    def turn(limit=20.0):
        deadline = time.perf_counter() + limit
        while time.perf_counter() < deadline:
            if game.battle is None or runtime._victory or runtime._defeat:
                return None
            if not runtime._battle_presentation.busy() and runtime._battle_actor():
                return runtime._battle_actor()
            pump(runtime, 0.1)
        return None

    def open_skill(actor, ability_id):
        commands = runtime.battle_commands
        ids = [r.action_id for r in commands.entries(actor)]
        for _ in range(ids.index("root:Skills") - commands.cursor):
            press(pygame.K_DOWN, 0.04)
        press(pygame.K_RETURN)
        ids = [r.action_id for r in commands.entries(actor)]
        for _ in range(ids.index(ability_id) - commands.cursor):
            press(pygame.K_DOWN, 0.04)
        press(pygame.K_RETURN)

    smoke.prepare(game, Counter(), "hero")
    runtime._ui_mode = "field"
    pump(runtime, 0.4)
    game.start_encounter("boss_room")
    runtime._battle_presentation.begin()
    runtime._advance_to_hero_turn()
    boss = game.active_enemy_ids()[0]
    pool = game.battle.member(boss).subject.resources
    pool.define(
        "vitality", 500000, current=500000, replace=True
    )  # the scripted casts must not end it
    done = set()
    for _ in range(12):
        actor = turn()
        if actor is None:
            break
        commands = runtime.battle_commands
        if actor == "hero_01" and "forms" not in done:
            open_skill(actor, "dawn_and_dusk")
            checks["forms_menu_opens"] = commands.mode == "forms"
            pump(runtime, 0.3)
            shot("b11_forms_menu.png")
            press(pygame.K_DOWN, 0.04)  # Dusk (dark)
            press(pygame.K_RETURN)
            if commands.mode == "target":  # one foe: the engine may pick it for us
                press(pygame.K_RETURN, 0.0)
            pump(runtime, 1.0)
            shot("b11_form_cast.png")
            checks["form_cast_hit_the_boss"] = pool.current("vitality") < 500000
            done.add("forms")
        elif actor == "hero_02" and "gift" not in done:
            before = game.battle.battle_resources.current("hero_01", "bp")
            open_skill(actor, "bp_gift")
            pump(runtime, 0.3)
            shot("b11_gift_target.png")
            press(pygame.K_RETURN, 0.0)  # the first ally in the list
            pump(runtime, 1.0)
            shot("b11_gift_done.png")
            after = game.battle.battle_resources.current("hero_01", "bp")
            checks["bp_given"] = (
                after - before >= 1
                or after == game.battle.battle_resources.maximum("hero_01", "bp")
            )
            done.add("gift")
        else:
            press(pygame.K_RETURN, 0.05)
            while runtime.battle_commands.mode in ("target", "forms", "ingredients"):
                press(pygame.K_RETURN, 0.05)
        if done == {"forms", "gift"}:
            break
    checks["both_turns_played"] = done == {"forms", "gift"}
    runtime.close()
    failed = sorted(k for k, v in checks.items() if not v)
    report = {
        "driver": driver,
        "status": "PASS" if not failed and driver == "cocoa" else "FAIL",
        "checks": checks,
        "failed": failed,
        "screenshots": shots,
    }
    (out / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
