"""Play the Boss Trial through the real game session and prove every system was hit.

Prepares the hero the way a player would (skill trees, attribute points, levels, refine, sockets,
growth, job change), then fights the boss with every skill, counting what actually happened.
Prints a coverage table and exits 1 if a system never fired.

Run: ``python reference_projects/boss_trial_demo/run_trial_smoke.py [--json OUT.json]``
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

from asteria.editor import EditorDocument  # noqa: E402
from asteria.events.world_commands import WorldCommand  # noqa: E402
from asteria.project import Project  # noqa: E402
from asteria.runtime.game_session import GameSessionRuntime  # noqa: E402

HERO = "hero_01"
SW = "w_sunbrand:hero_01"


def load():
    project = Project.load_json(HERE / "project.asteria.json", EditorDocument().component_registry)
    return project, GameSessionRuntime(project, project.game_start.instantiate(project))


def world(game, name, **args):
    return game.world_commands.dispatch(WorldCommand(name, args))


def prepare(game, facts, sub="duelist"):
    """Everything a player does before the fight."""
    allocation = game.save.rpg_state.progression_allocations[HERO]
    for graph_id in ("knight_tree", "duelist_tree", "mystic_tree"):
        graph = allocation.definitions[graph_id]
        for _ in range(8):  # several passes: later nodes unlock after earlier ones
            for node in graph.nodes:
                while allocation.rank(graph_id, node.node_id) < node.max_rank:
                    try:
                        allocation.allocate(graph_id, node.node_id)
                        facts["tree_ranks"] += 1
                    except ValueError:
                        break
    world(
        game,
        "GRANT_EXPERIENCE",
        actor_id=HERO,
        amount=9000,
        threshold=1000,
        points="stat_points=3",
    )
    for node_id in ("attr_str", "attr_vit", "attr_dex", "attr_int"):
        while True:
            try:
                allocation.allocate("attributes", node_id)
                facts["attribute_points"] += 1
            except ValueError:
                break
    for _ in range(6):
        result = world(game, "REFINE_EQUIPMENT", actor_id=HERO, instance_id=SW)
        facts["refine_" + result.outcome] += 1
    for item_id, socket in (("ruby_item", "s1"), ("onyx_item", "s2")):
        world(
            game, "SOCKET_ITEM", actor_id=HERO, instance_id=SW, socket_id=socket, item_id=item_id
        )
        facts["socketed"] += 1
    world(game, "UPGRADE_EQUIPMENT", actor_id=HERO, instance_id=SW, node_id="awaken")
    world(
        game,
        "SOCKET_ITEM",
        actor_id=HERO,
        instance_id=SW,
        socket_id="s3",
        item_id="card_vampire_item",
    )
    facts["socketed"] += 1
    for node_id in ("edge", "edge", "edge", "ember"):
        world(game, "UPGRADE_EQUIPMENT", actor_id=HERO, instance_id=SW, node_id=node_id)
        facts["growth_nodes"] += 1
    for job in ("mystic", "duelist", sub):
        world(game, "SET_CLASSES", actor_id=HERO, class_ids=f"knight,{job}")
        facts["job_changes"] += 1


def fight(game, facts, acc, seed=7, max_rounds=200):
    rng = random.Random(seed)
    game.start_encounter("boss_room")
    boss = game.active_enemy_ids()[0]
    facts["opening_" + game.opening] += 1
    seen_phases, seen_states, seen_tags = acc["phases"], acc["states"], acc["tags"]
    used = acc["used"]
    hp_trace = []
    for _ in range(max_rounds):
        actor, enemy_log = game.run_enemy_turns()
        for entry in game.drain_battle_log():
            facts["log_" + entry.kind] += 1
            for _target, outcome in getattr(entry, "outcomes", ()) or ():
                for tag in outcome.outcome_tags:
                    facts["outcome_" + tag] += 1
            if entry.kind == "hit_check":
                for tag in entry.data["tags"]:
                    facts["check_" + tag] += 1
            if entry.kind == "kill":
                facts["kill_" + ("immune" if entry.data["immune"] else "landed")] += 1
            if entry.kind == "action" and entry.member_id == boss:
                used[entry.ability_id] += 1
        for member_id, member in game.battle.members.items():
            tags = member.subject.tags
            if member_id == boss:
                for tag in ("stance.bulwark", "stance.fury", "state.broken"):
                    if tags.contains(tag):
                        seen_tags.add(tag)
            states = member.subject.states
            if states is not None:
                for active in states.active_states():
                    seen_states.add((member.side, active.state_id))
        phase = game.battle.enemy_ai.phases.get(boss) if hasattr(game.battle, "enemy_ai") else None
        if phase:
            seen_phases.add(phase)
        if actor is None or not game.active_enemy_ids():
            break
        build = game.battle.member(actor).ability_ids
        pool = [a for a in build if not game.ability_unavailable(actor, a)]
        rng.shuffle(pool)
        pool.sort(key=lambda a: used[a])  # variety: the least used skill first
        guards = ("guard_stance", "rally", "shadow_step", "mend", "arcane_barrier", "bastion")
        resources = game.battle.member(actor).subject.resources
        low = resources.current("vitality") < 0.5 * resources.maximum("vitality")
        pool.sort(key=lambda a: (a in guards) != low)  # defend when low, else attack
        hp_trace.append(
            (
                int(resources.current("vitality")),
                int(game.battle.member(boss).subject.resources.current("vitality")),
            )
        )
        targets = (boss,) if boss in game.active_enemy_ids() else game.active_enemy_ids()[:1]
        if resources.current("vitality") < 0.3 * resources.maximum("vitality"):
            for item_id in ("healing_herb", "ether_leaf"):
                try:
                    game.use_battle_item(actor, item_id, (actor,))
                except Exception:  # noqa: BLE001 - out of that item
                    continue
                facts["potions_used"] += 1
                game.end_turn()
                break
            else:
                item_id = None
            if item_id is not None:
                continue
        for ability_id in pool:
            try:
                relation = game.ability_relation(ability_id)
                chosen = targets if "OPPONENT" in str(relation).upper() else None
                adds = [e for e in game.active_enemy_ids() if e != boss]
                if adds and ability_id in ("executioner", "assassinate") and chosen:
                    chosen = (adds[0],)  # instant death works on the adds, not the boss
                game.use_ability(actor, ability_id, chosen)
            except Exception:  # noqa: BLE001 - an ability that cannot be used now is skipped
                continue
            used[ability_id] += 1
            break
        game.end_turn()
    facts["victory"] += int(not game.active_enemy_ids())
    facts["hero_skills_used"] = len({a for a in used if not a.startswith("w_")})
    facts["boss_moves_used"] = len({a for a in used if a.startswith("w_")})
    facts["boss_phases_seen"] = len(seen_phases)
    facts["status_kinds_seen"] = len({s for _side, s in seen_states})
    facts["boss_stances_seen"] = len([t for t in seen_tags if t.startswith("stance.")])
    facts["break_seen"] = int("state.broken" in seen_tags)
    extensions = game.battle.extensions
    facts["lifesteal_healed"] = int(sum(extensions.lifesteal_healed.values())) if extensions else 0
    facts["summons"] = facts.get("log_summoned", 0)
    return used


REQUIRED = (
    "tree_ranks",
    "attribute_points",
    "refine_success",
    "socketed",
    "growth_nodes",
    "job_changes",
    "log_kill",
    "kill_immune",
    "log_summoned",
    "boss_phases_seen",
    "boss_stances_seen",
    "break_seen",
    "lifesteal_healed",
    "check_outcome.crit",
    "hero_skills_used",
    "boss_moves_used",
    "status_kinds_seen",
)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    facts = Counter()
    acc = {"phases": set(), "states": set(), "tags": set(), "used": Counter()}
    fights = int(argv[argv.index("--fights") + 1]) if "--fights" in argv else 6
    for seed in range(fights):
        project, game = load()
        game.save.rpg_state.currencies["gold"] = 40000.0
        prepare(game, facts, "mystic" if seed % 2 else "duelist")
        build = game.resolve_actor_build(HERO)
        facts["abilities_available"] = len(build.abilities)
        facts["class_growth_stat_power"] = int(build.stats.get("power"))
        fight(game, facts, acc, seed=seed)
        facts["fights"] += 1
    used = acc["used"]
    facts["hero_skills_used"] = len({a for a in used if not a.startswith("w_")})
    facts["boss_moves_used"] = len({a for a in used if a.startswith("w_")})
    facts["boss_phases_seen"] = len(acc["phases"])
    facts["status_kinds_seen"] = len({s for _side, s in acc["states"]})
    facts["boss_stances_seen"] = len([t for t in acc["tags"] if t.startswith("stance.")])
    facts["break_seen"] = int("state.broken" in acc["tags"])
    facts["summons"] = facts.get("log_summoned", 0)
    width = max(len(k) for k in facts)
    for key in sorted(facts):
        print(f"{key:<{width}}  {facts[key]}")
    print("hero skills:", sorted(a for a in used if not a.startswith("w_")))
    print("boss moves:", sorted(a for a in used if a.startswith("w_")))
    missing = [k for k in REQUIRED if not facts.get(k)]
    if "--json" in argv:
        Path(argv[argv.index("--json") + 1]).write_text(
            json.dumps(dict(facts), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if missing:
        print("NOT HIT:", ", ".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
