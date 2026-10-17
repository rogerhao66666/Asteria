"""Real-window run of the Boss Trial third wave: steal, capture, pet unit (macOS, Cocoa).

    python scripts/boss_trial_b12_live_check.py OUTPUT_DIR

A goblin slinger is captured, fights as its own unit in the next battle, and Pilfer steals
from the boss through the real command menu.
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
DEMO = REPO / "reference_projects" / "boss_trial_demo"
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
    out = Path(argv[0] if argv else REPO / "docs" / "audits" / "evidence" / "boss_trial_b12")
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

    smoke.prepare(game, Counter(), "rogue")
    runtime._ui_mode = "field"
    pump(runtime, 0.4)
    game.start_encounter("woods_ambush")
    runtime._battle_presentation.begin()
    wisp = next(e for e in game.active_enemy_ids() if e.startswith("goblin_slinger"))

    class Lucky:
        def random(self):
            return 0.0

    checks["wisp_captured"] = bool(game.attempt_capture("hero_01", wisp, rng=Lucky()))
    for member_id in tuple(game.active_enemy_ids()):
        game.battle.member(member_id).subject.resources.set_current("vitality", 0)
    game.finish_victory()
    runtime._battle_presentation = runtime._battle_presentation  # same window, next battle
    game.start_encounter("boss_room")
    runtime._battle_presentation.begin()
    runtime._advance_to_hero_turn()
    pet_unit = next((m for m in game.battle.members if m.startswith("pet:")), None)
    checks["pet_fights_as_a_unit"] = pet_unit is not None
    boss = next(e for e in game.active_enemy_ids() if e.startswith("crimson"))
    game.battle.member(boss).subject.resources.define(
        "vitality", 500000, current=500000, replace=True
    )
    shot_done = set()
    for _ in range(40):
        actor = turn()
        if actor is None:
            break
        if actor not in ("hero_01", "hero_02") and actor.startswith("pet:"):
            pump(runtime, 0.3)
            shot("b12_pet_turn.png")
            shot_done.add("pet")
            press(pygame.K_RETURN, 0.05)
            while runtime.battle_commands.mode in ("target", "forms"):
                press(pygame.K_RETURN, 0.05)
        elif actor == "hero_01" and "steal" not in shot_done:
            before = game.save.rpg_state.inventory.count("ancient_thread")
            open_skill(actor, "pilfer")
            if runtime.battle_commands.mode == "target":
                press(pygame.K_RETURN, 0.0)
            pump(runtime, 1.0)
            shot("b12_steal.png")
            checks["stolen_through_the_menu"] = (
                game.save.rpg_state.inventory.count("ancient_thread") > before
            )
            shot_done.add("steal")
        else:
            press(pygame.K_RETURN, 0.05)
            while runtime.battle_commands.mode in ("target", "forms", "ingredients"):
                press(pygame.K_RETURN, 0.05)
        if shot_done >= {"pet", "steal"}:
            break
    checks["both_seen"] = shot_done >= {"pet", "steal"}
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
