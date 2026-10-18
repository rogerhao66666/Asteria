"""Real-window run of the Full Verification workshop screen and escape command (macOS, Cocoa).

    python scripts/full_verification_b13_live_check.py OUTPUT_DIR

The workshop screen refines, sockets and spends attribute points by key presses; the swarm
fight has an Escape row that runs, the warlord hall refuses it. Output: OUTPUT_DIR.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
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

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    argv = list(sys.argv[1:] if argv is None else argv)
    evidence = REPO / "docs" / "audits" / "evidence" / "full_verification_b13"
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

    game.save.rpg_state.currencies["gold"] = 40000.0
    game.save.rpg_state.progression_allocations["hero_01"].grant("stat_points", 3)
    game.save.rpg_state.inventory.add("ruby_item", 2)
    runtime._ui_mode = "build"
    pump(runtime, 0.3)
    press(pygame.K_8)
    pump(runtime, 0.3)
    shot("b13_workshop_open.png")
    weapon = runtime._current_weapon("hero_01")
    before = weapon.refine_level
    for _ in range(4):
        press(pygame.K_r, 0.05)
    press(pygame.K_a, 0.05)
    press(pygame.K_s, 0.05)
    pump(runtime, 0.3)
    shot("b13_workshop_used.png")
    checks["workshop_opened"] = runtime._ui_mode == "workshop"
    checks["refine_tried"] = "Refine" in getattr(runtime, "_workshop_message", "") or (
        weapon.refine_level != before
    )
    press(pygame.K_c)
    runtime._ui_mode = "field"
    rules = game.project.rpg_database.escape_rules  # a sure thing for the scripted run
    for rule_id, rule in list(rules.items()):
        rules[rule_id] = type(rule)(rule_id, rule.side, base_chance=1.0)
    game.start_encounter("swarm")
    runtime._battle_presentation.begin()
    runtime._advance_to_hero_turn()
    actor = turn()
    commands = runtime.battle_commands
    ids = [r.action_id for r in commands.entries(actor)]
    checks["escape_row_listed"] = "root:Escape" in ids
    pump(runtime, 0.3)
    shot("b13_escape_row.png")
    for _ in range(ids.index("root:Escape") - commands.cursor):
        press(pygame.K_DOWN, 0.04)
    escaped = False
    for _ in range(12):
        press(pygame.K_RETURN, 0.0)
        if game.mode != "battle":
            escaped = True
            break
        actor = turn(8.0)
        if actor is None:
            break
        ids = [r.action_id for r in commands.entries(actor)]
        for _ in range(ids.index("root:Escape") - commands.cursor):
            press(pygame.K_DOWN, 0.04)
    pump(runtime, 0.4)
    shot("b13_after_escape.png")
    checks["escaped_to_the_field"] = escaped
    if game.mode == "battle":
        game.battle = None
        game.mode = "field"
        game.encounter_id = None
    game.start_encounter("boss_room")
    checks["boss_hall_refuses"] = "no_escape" in game.escape_unavailable()
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
