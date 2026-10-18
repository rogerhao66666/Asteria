"""Real-window run of the Full Verification demo (macOS, real Cocoa window, real key events).

    python scripts/full_verification_live_check.py OUTPUT_DIR

Prepares the hero (trees, levels, refine, sockets, growth), opens the battle, and plays through
the command menu with key presses: an attack (weapon icon pop-up), a skill, a divine skill and a
fight against the three boss phases. Screenshots and ``results.json`` land in OUTPUT_DIR. The
run reports what it measured; whether the fight plays well is for a person.
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
    evidence = REPO / "docs" / "audits" / "evidence" / "full_verification"
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

    def hero_turn(limit=15.0):
        deadline = time.perf_counter() + limit
        while time.perf_counter() < deadline:
            if game.battle is None or runtime._victory or runtime._defeat:
                return None
            if not runtime._battle_presentation.busy() and runtime._battle_actor():
                return runtime._battle_actor()
            pump(runtime, 0.1)
        return None

    def select(actor, ability_id):
        commands = runtime.battle_commands
        if commands.mode == "root":
            weapons = commands.weapon_ability_ids(actor)
            want = "Attack" if ability_id in weapons else "Skills"
            ids = [r.action_id for r in commands.entries(actor)]
            for _ in range(ids.index(f"root:{want}") - commands.cursor):
                press(pygame.K_DOWN, 0.04)
            press(pygame.K_RETURN)
        ids = [r.action_id for r in commands.entries(actor)]
        for _ in range(ids.index(ability_id) - commands.cursor):
            press(pygame.K_DOWN, 0.04)
        press(pygame.K_RETURN)

    facts = Counter()
    smoke.prepare(game, facts)
    runtime._ui_mode = "field"
    pump(runtime, 0.5)
    shot("trial_field.png")
    checks["prepared"] = bool(facts["tree_ranks"] and facts["refine_success"])

    executed = []
    execute = game.execute

    def counting_execute(actor_id, ability_id, target_ids, **options):
        executed.append(ability_id)
        return execute(actor_id, ability_id, target_ids, **options)

    game.execute = counting_execute
    game.start_encounter("boss_room")
    runtime._battle_presentation.begin()
    runtime._advance_to_hero_turn()
    actor = hero_turn()
    checks["command_menu"] = actor is not None and bool(runtime.battle_commands.entries(actor))
    pump(runtime, 0.6)
    shot("trial_battle_menu.png")

    # an attack: the weapon's icon pops up over the hero while it swings
    boss_id = game.active_enemy_ids()[0]
    boss_pool = game.battle.member(boss_id).subject.resources
    normal_max = boss_pool.maximum("vitality")
    # the scripted skills must not end the fight: the boss soaks them, then goes back to normal
    boss_pool.define("vitality", normal_max * 20, current=normal_max * 20, replace=True)
    attack = "attack_sword" if "attack_sword" in game.battle.member(actor).ability_ids else None
    select(actor, attack)
    if runtime.battle_commands.mode == "target":  # one foe: the engine may pick it for us
        shot("trial_target.png")
        press(pygame.K_RETURN, 0.0)
    for index in range(8):
        pump(runtime, 0.07)
        shot(f"trial_attack_{index}.png")
    checks["attack_executed"] = attack in executed

    # a multi-hit skill and a divine skill
    for ability_id in ("flurry", "sunburst"):
        actor = hero_turn()
        if actor is None or ability_id not in game.battle.member(actor).ability_ids:
            continue
        game.battle.battle_resources.change(
            actor, "bp", 3 - game.battle.battle_resources.current(actor, "bp")
        )
        select(actor, ability_id)
        if runtime.battle_commands.mode == "target":
            press(pygame.K_RETURN, 0.0)
        for index in range(6):
            pump(runtime, 0.12)
            if index in (1, 3):
                shot(f"trial_{ability_id}_{index}.png")
        checks[f"{ability_id}_executed"] = ability_id in executed

    boss_pool.define("vitality", normal_max, current=normal_max, replace=True)
    # play on with the first command of each menu until the boss changes phases, then win
    seen = set()
    finishing = False
    boss = game.active_enemy_ids()[0] if game.active_enemy_ids() else None
    for _ in range(900):
        if runtime._victory or runtime._defeat or game.battle is None:
            break
        pool = game.battle.member(boss).subject.resources if boss else None
        if pool is not None:
            phase = game.battle.enemy_ai.phases.get(boss)
            if phase and phase not in seen:
                seen.add(phase)
                pump(runtime, 0.4)
                shot(f"trial_phase_{phase}.png")
            hero = game.battle.member(game.active_hero_ids()[0]).subject.resources
            hero.set_current(
                "vitality", max(hero.current("vitality"), 0.6 * hero.maximum("vitality"))
            )
            # deterministic: each phase seen puts the boss just under the next phase's threshold
            thresholds = {0: 1.0, 1: 0.60, 2: 0.25}
            if len(seen) < 3 or not finishing:
                wanted = thresholds.get(len(seen), 0.0) * pool.maximum("vitality")
                pool.set_current("vitality", max(wanted, 300.0))
                finishing = len(seen) >= 3  # once in the last phase the boss is left to fall
        if not runtime._battle_presentation.busy() and runtime._battle_actor():
            if runtime.battle_commands.mode in ("ingredients", "target"):
                press(pygame.K_RETURN, 0.05)
            else:
                press(pygame.K_RETURN, 0.05)
        else:
            pump(runtime, 0.05)
    checks["battle_won_by_keys"] = bool(runtime._victory)
    print(
        "boss hp",
        None
        if game.battle is None
        else game.battle.member(boss).subject.resources.current("vitality"),
        "victory",
        runtime._victory,
        "defeat",
        runtime._defeat,
        "iters done",
    )
    checks["three_phases_seen"] = len(seen) >= 3
    pump(runtime, 0.8)
    shot("trial_victory.png")
    runtime.close()

    failed = sorted(k for k, v in checks.items() if not v)
    report = {
        "driver": driver,
        "status": "PASS" if not failed and driver == "cocoa" else "FAIL",
        "checks": checks,
        "failed": failed,
        "phases_seen": sorted(seen),
        "executed": dict(Counter(executed)),
        "screenshots": shots,
        "note": "Whether it plays well is for a person.",
    }
    (out / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
