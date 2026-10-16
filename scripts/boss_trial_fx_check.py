"""Real-window check that each skill of the Boss Trial shows its own effect (macOS, real window).

    python scripts/boss_trial_fx_check.py OUTPUT_DIR

Casts a list of skills one by one with real key presses and saves a frame in the middle of each
effect (``fx_<skill>.png``) plus ``fx_results.json``.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import boss_trial_live_check as live  # noqa: E402

SKILLS = (
    "arsenal_barrage",
    "weapon_dance",
    "dispel",
    "mirror_veil",
    "tri_blast",
    "holy_blade",
    "lightning_strike",
    "hero_finale",
    "temper",
    "anvil_slam",
    "hammer_combo",
    "quick_refine",
    "mug",
    "backstab",
    "poison_cloud",
    "shield_wall",
    "bulwark_charge",
    "aegis",
    "fireball",
    "meteor_fall",
    "executioner",
    "flurry",
)


def main(argv=None):
    import pygame

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0] if argv else REPO / "docs" / "audits" / "evidence" / "boss_trial")
    out.mkdir(parents=True, exist_ok=True)
    helper = live._helpers()
    pump, key = helper._pump, helper._key
    import run_trial_smoke as smoke

    project = Project.load_json(
        live.DEMO / "project.asteria.json", EditorDocument().component_registry
    )
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), live.DEMO, width=1280, height=720
    )
    runtime.open()
    game = runtime.game
    facts = Counter()
    seen, shots = {}, []
    done = []

    def press(k, wait=0.1):
        key(k)
        pump(runtime, 0.04)
        key(k, up=True)
        pump(runtime, wait)

    def hero_turn():
        deadline = time.perf_counter() + 20
        while time.perf_counter() < deadline:
            if runtime._victory or runtime._defeat:
                return None
            if not runtime._battle_presentation.busy() and runtime._battle_actor():
                return runtime._battle_actor()
            pump(runtime, 0.1)

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

    # the hero knows knight + duelist + mystic skills for this check (the trees are all open)
    smoke.prepare(game, facts, "mystic")
    allocation = game.save.rpg_state.progression_allocations[smoke.HERO]
    for graph_id in [g for g in allocation.definitions if g.endswith("_tree")]:
        for _ in range(8):
            for node in allocation.definitions[graph_id].nodes:
                while allocation.rank(graph_id, node.node_id) < node.max_rank:
                    try:
                        allocation.allocate(graph_id, node.node_id)
                    except ValueError:
                        break
    runtime._ui_mode = "field"
    pump(runtime, 0.4)
    game.start_encounter("boss_room")
    runtime._battle_presentation.begin()
    runtime._advance_to_hero_turn()
    boss = game.active_enemy_ids()[0]
    tank = game.battle.member(boss).subject.resources  # the boss must outlive every test skill
    tank.define("vitality", 10_000_000, current=10_000_000, replace=True)
    for ability_id in SKILLS:
        actor = hero_turn()
        if actor is None:
            break
        pool = game.battle.member(boss).subject.resources
        pool.set_current("vitality", pool.maximum("vitality"))
        hero = game.battle.member(actor).subject.resources
        hero.set_current("technique", hero.maximum("technique"))
        game.battle.battle_resources.change(
            actor, "bp", 3 - game.battle.battle_resources.current(actor, "bp")
        )
        if ability_id not in game.battle.member(actor).ability_ids:
            seen[ability_id] = "not available"
            continue
        select(actor, ability_id)
        if runtime.battle_commands.mode == "target":
            press(pygame.K_RETURN, 0.0)
        pump(runtime, 0.28)
        name = f"fx_{ability_id}.png"
        pygame.image.save(runtime.capture(), str(out / name))
        shots.append(name)
        done.append(ability_id)
        seen[ability_id] = "shown"
        pump(runtime, 1.0)
    runtime.close()
    report = {"skills": seen, "screenshots": shots}
    (out / "fx_results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if len(done) >= 16 else 1


if __name__ == "__main__":
    raise SystemExit(main())
