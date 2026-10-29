"""Balance check of the ARPG demo's builds: each build plays a fixed rotation against one dummy
and against a cluster of five, with the skill points a hero has at that level, and reports the
damage per second.

    python scripts/arpg_balance.py [--level 10] [--seconds 20] [--json OUT]

Headless; the numbers compare builds with each other (no gear, same points), not with players.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "reference_projects" / "arpg_demo"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import arpg_builds as builds  # noqa: E402

from asteria.core import Entity, Transform  # noqa: E402
from asteria.editor import EditorDocument  # noqa: E402
from asteria.project import Project  # noqa: E402
from asteria.runtime.character_control import Hurtbox2DComponent  # noqa: E402
from asteria.runtime.combat import CombatantComponent  # noqa: E402
from asteria.runtime.playable_test_runtime import PlayableTestRuntime  # noqa: E402

DEMO = REPO / "reference_projects" / "arpg_demo"


def _runtime():
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=960, height=540
    )
    runtime.open()
    runtime._ui_mode = "field"
    for _ in range(30):
        runtime._frame([], 1 / 60)
    return runtime


def _dummies(game, count, level):
    """Targets that cannot die or fight back, ``count`` of them in front of the hero."""
    x, y = game.player.get(Transform).x, game.player.get(Transform).y
    ids = []
    for i in range(count):
        entity = Entity(f"Dummy {i}")
        offset = (0, 0) if count == 1 else ((i % 3 - 1) * 14, (i // 3) * 18 - 9)
        entity.add_component(Transform(x + 36 + offset[0], y + offset[1]))
        hurt = entity.add_component(Hurtbox2DComponent())
        hurt.team, hurt.width, hurt.height = "foe", 14.0, 14.0
        combatant = entity.add_component(CombatantComponent())
        combatant.team, combatant.resources = "foe", "hp=1000000"
        combatant.stats = f"defense={2 + level}"
        game.scene.add_entity(entity)
        ids.append(entity.id)
    return ids


def _spend(game, class_id, branch):
    """Learn the build's skills first, then its passives and keystone, as far as the points the
    level-ups gave go."""
    tree = game.project.rpg_database.progression_graphs[f"{class_id}_tree"]
    spec = next(b for b in builds.BRANCHES[class_id] if b[0] == branch)
    skills, passives, keystone = spec[2], [p[0] for p in spec[3]], spec[4][0]
    wanted = [*skills, *passives, keystone]
    progress = True
    while progress:
        progress = False
        for node_id in wanted:
            node = tree.node(node_id)
            try:
                game.allocate_progression("hero", tree.graph_id, node.node_id)
                progress = True
            except ValueError:
                continue


# what each build wears when the check is run with gear: the weapon of its class and the unique
# that pushes its stat; every other slot is a rare drop rolled at the hero's level
BUILD_GEAR = {
    "berserker": ("bloodreaver",),
    "guardian": ("iron_mace", "ironbound_helm", "ironbound_plate", "ironbound_boots"),
    "warlord": ("battle_axe", "gauntlets"),
    "marksman": ("long_bow", "wyrm_amulet"),
    "venomancer": ("viper_fang",),
    "skirmisher": ("hunting_bow", "windrunner_boots"),
    "pyromancer": ("yew_staff", "phoenix_circlet"),
    "cryomancer": ("oak_staff", "glacier_ring"),
    "stormcaller": ("tempest_staff", "storm_cowl", "storm_robe", "storm_gloves"),
}
RARE_SLOTS = ("helm", "armor", "gloves", "boots", "amulet", "ring")


def _wear(game, branch, level):
    import random

    from asteria.rpg.loot import roll_equipment

    db = game.project.rpg_database
    rng = random.Random(branch)
    state = game.save.rpg_state
    made = 0

    def put(equipment_id, rarity=None):
        nonlocal made
        made += 1
        state.equipment_bag.append(
            roll_equipment(
                db.equipment[equipment_id],
                rng,
                item_level=level,
                rarity_id=rarity,
                rarities=db.loot_rarities(),
                affixes=db.affixes,
                instance_id=f"gear:{made}",
            )
        )
        try:
            game.equip_from_bag("hero", len(state.equipment_bag) - 1)
        except Exception:  # noqa: BLE001 - a slot the hero's rules do not take
            state.equipment_bag.pop()

    named = BUILD_GEAR[branch]
    slots = {db.equipment[i].slot for i in named}
    for equipment_id in named:
        put(equipment_id)
    for slot in RARE_SLOTS:
        if slot not in slots:
            pool = sorted(
                i
                for i, e in db.equipment.items()
                if e.slot == slot and "rarity:" not in " ".join(e.tags)
            )
            put(rng.choice(pool), "rare")
    game.refresh_actor_combatants("hero")


def measure(class_id, branch, *, level, seconds, targets, gear=False):
    runtime = _runtime()
    game = runtime.game
    game.set_classes("", [class_id])
    while game.save.rpg_state.actor_progression["hero"].level < level:
        game.grant_actor_experience("hero", 4000, **game.action_progression)
    _spend(game, class_id, branch)
    if gear:
        _wear(game, branch, level)
    ids = set(_dummies(game, targets, level))
    for _ in range(10):
        runtime._frame([], 1 / 60)
    from asteria.runtime.action_combat import ActionCombatComponent, parse_bindings

    bindings = parse_bindings(game.player.get(ActionCombatComponent).bindings)
    order = [b for k, b in bindings.items() if k.startswith("skill_")] + [bindings["attack"]]
    scene = game.scene

    def remaining():
        values = []
        for entity_id in ids:
            entity = scene.get_entity(entity_id)
            state = game.combat.state(entity) if entity is not None else None
            values.append(state.resources.current("hp") if state is not None else 0.0)
        return sum(values)

    start = remaining()  # damage over time (burn, poison, bleed) counts as well as hits
    for _ in range(int(seconds * 60)):
        state = game.combat.state(game.player)
        state.resources.set_current("mp", state.resources.maximum("mp"))  # a mana-fed rotation
        for value in order:
            ability = game.action_combat.bound_ability(game.player, value)
            if ability and game.action_combat.use(game.player, ability) == "used":
                break
        runtime._frame([], 1 / 60)
    state = game.combat.state(game.player)
    stats = game.combat.effective_stats(state)
    hp = state.resources.maximum("hp")
    # hits a standard monster blow (power 24, ratio 1.1) takes to kill the hero
    hits = hp / max(1.0, 24 * 1.1 - 0.5 * stats.get("defense"))
    measure.last = (
        hp,
        stats.get("defense"),
        stats.get("power"),
        stats.get("magic"),
        stats.get("dexterity"),
        stats.get("crit"),
    )
    return (start - remaining()) / seconds, hits


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", type=int, default=10)
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--json", default="")
    parser.add_argument("--gear", action="store_true", help="wear the build's gear")
    args = parser.parse_args(argv)
    rows = {}
    for class_id, branches in builds.BRANCHES.items():
        for branch, title, *_ in branches:
            single, hits = measure(
                class_id, branch, level=args.level, seconds=args.seconds, targets=1, gear=args.gear
            )
            cluster, _ = measure(
                class_id, branch, level=args.level, seconds=args.seconds, targets=5, gear=args.gear
            )
            rating = (single * 0.5 + cluster * 0.5) * hits**0.5
            rows[f"{class_id}/{branch}"] = {
                "single": round(single, 1),
                "cluster": round(cluster, 1),
                "hits_to_die": round(hits, 1),
                "rating": round(rating, 1),
            }
            print(
                f"{class_id:8} {title:12} single {single:7.1f}  cluster-of-5 {cluster:7.1f}  "
                f"survives {hits:5.1f} hits  rating {rating:7.1f}  "
                f"hp/def/pow/mag/dex/crit {measure.last}"
            )
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
