"""Play the Full Verification through the real game session and prove every system was hit.

Prepares the hero the way a player would (skill trees, attribute points, levels, refine, sockets,
growth, job change), then fights the boss with every skill, counting what actually happened.
Prints a coverage table and exits 1 if a system never fired.

Run: ``python reference_projects/full_verification_demo/run_trial_smoke.py [--json OUT.json]``
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
SUB_JOBS = (
    "duelist",
    "mystic",
    "weapon_master",
    "sage",
    "hero",
    "forgemaster",
    "rogue",
    "guardian",
    "archmage",  # with the Brave as main job: Aldric's own pair
)
SW = "w_sunbrand:hero_01"


def load():
    project = Project.load_json(HERE / "project.asteria.json", EditorDocument().component_registry)
    return project, GameSessionRuntime(project, project.game_start.instantiate(project))


def world(game, name, **args):
    return game.world_commands.dispatch(WorldCommand(name, args))


def prepare(game, facts, sub="duelist", tier=0):
    """Everything a player does before the fight. ``tier`` (0-2): which job of their line each
    companion fights in (every job of every line gets a turn across the fights)."""
    import trial_classes

    if "hero_02" not in game.save.rpg_state.party_actor_ids:  # hire Mira at the guild
        world(game, "JOIN_PARTY", actor_id="hero_02")
    for actor_id, (_name, line, companion_sub) in trial_classes.LINES.items():
        if actor_id not in game.save.rpg_state.party_actor_ids:
            world(game, "JOIN_PARTY", actor_id=actor_id)
        import dataclasses

        state = game.ensure_actor_progression(actor_id)  # level 12, without touching the party's
        game.save.rpg_state.actor_progression[actor_id] = dataclasses.replace(state, level=12)
        for job in line[: tier + 1]:  # walk the line up to the tier: each job asks for the last
            game.set_classes(actor_id, [job, companion_sub])
        own = game.save.rpg_state.progression_allocations[actor_id]
        own.grant("ap", 40)
        for job in line:
            own.grant(f"jp.{job}", 60)
        for graph_id in [g for g in own.definitions if g.endswith("_tree")]:
            graph = own.definitions[graph_id]
            for _ in range(6):
                for node in graph.nodes:
                    while own.rank(graph_id, node.node_id) < node.max_rank:
                        try:
                            own.allocate(graph_id, node.node_id)
                        except ValueError:
                            break
        game.refresh_actor_combatants(actor_id)
    allocation = game.save.rpg_state.progression_allocations[HERO]
    # the campaign earns these a little at a time; the scripted fights start with plenty
    allocation.grant("ap", 200)
    allocation.grant("stat_points", 12)
    for job in ("brave", "knight", "duelist", "mystic", *SUB_JOBS):
        allocation.grant(f"jp.{job}", 130)
    for graph_id in [g for g in allocation.definitions if g.endswith("_tree")]:
        graph = allocation.definitions[graph_id]
        for _ in range(8):  # several passes: later nodes unlock after earlier ones
            for node in graph.nodes:
                while allocation.rank(graph_id, node.node_id) < node.max_rank:
                    try:
                        allocation.allocate(graph_id, node.node_id)
                        facts["tree_ranks"] += 1
                    except ValueError:
                        break
    game.open_shop("trial_shop")
    game.buy("ruby_item", 1, shop_id="trial_shop")
    facts["bought"] += 1
    game.open_shop_id = None  # walk away from the counter: no shop window stays open
    game.craft({"base": ["iron_ore"], "catalyst": ["fire_dust"]}, station="alchemy")
    facts["crafted"] += 1
    world(game, "DISASSEMBLE", item_id="ruby_item")
    facts["disassembled"] += 1
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
    main = "brave" if sub == "archmage" else "knight"
    for job in ("mystic", "duelist", sub):
        world(game, "SET_CLASSES", actor_id=HERO, class_ids=f"{main},{job}")
        facts["job_changes"] += 1


def fight(game, facts, acc, seed=7, max_rounds=200, encounter="boss_room", crowd=False):
    rng = random.Random(seed)
    game.start_encounter(encounter)
    if crowd:  # nine foes at once outdamage any build: the point is the load, not the odds
        for hero_id in game.active_hero_ids():
            pool = game.battle.member(hero_id).subject.resources
            pool.define("vitality", 900_000, current=900_000, replace=True)
    boss = game.active_enemy_ids()[0]
    facts["opening_" + game.opening] += 1
    seen_phases, seen_states, seen_tags = acc["phases"], acc["states"], acc["tags"]
    used = acc["used"]
    hp_trace = []
    turn = 0
    mixes = 0
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
            if entry.kind == "action" and entry.ability_id in ("counter_strike", "w_counter"):
                facts["reaction_" + entry.ability_id] += 1
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
        turn += 1
        if "concoct" in build and mixes < 2 and turn >= 2:  # mix bombs mid-fight (twice)
            mixes += 1
            recipe = (
                ("healing_herb", "fire_dust") if turn % 10 == 2 else ("fire_dust", "ice_crystal")
            )
            try:
                game.concoct(
                    actor, "concoct", {"base": [recipe[0]], "catalyst": [recipe[1]]}, (boss,)
                )
                facts["concocted"] += 1
                game.end_turn()
                continue
            except Exception:  # noqa: BLE001 - out of ingredients
                pass
        pool = [a for a in build if not game.ability_unavailable(actor, a)]
        rng.shuffle(pool)
        pool.sort(key=lambda a: used[a])  # variety: the least used skill first
        killers = ("executioner", "assassinate", "deathmark")  # instant death must get its roll
        base = lambda a: a.split("__")[0]  # noqa: E731 - a rune variant counts as its skill
        hunting = facts["kill_immune"] == 0  # until the boss has shrugged one off
        pool.sort(key=lambda a: not (base(a) in killers and (used[a] == 0 or hunting)))
        # skills whose system must show up at least once: forms, item / gold costs, lifesteal
        special = (
            "dawn_and_dusk",
            "elemental_edge",
            "arcane_tome",
            "gilded_hammer",
            "molten_strike",
            "vampiric_strike",
            "dark_pact",
            "shadow_feast",
            "blood_rite",
        )
        pool.sort(key=lambda a: not (base(a) in special and used[a] == 0))
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
        if crowd:  # a crowd: the weakest foe first, so the fight ends
            alive = game.active_enemy_ids()
            targets = (
                min(
                    alive,
                    key=lambda e: game.battle.member(e).subject.resources.current("vitality"),
                ),
            )
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
                aimed = base(ability_id) in ("executioner", "assassinate") and not hunting
                if adds and aimed and chosen:
                    chosen = (adds[0],)  # instant death works on the adds, not the boss
                definition = game.battle.ability_runtime.registry.get(ability_id)
                form = rng.choice(definition.forms)["form_id"] if definition.forms else None
                game.use_ability(actor, ability_id, chosen, form=form)
                facts["forms_cast"] += int(form is not None)
                facts["goods_cost_skills"] += int(
                    bool(definition.item_costs or definition.currency_costs)
                )
                facts["hp_cost_skills"] += int(
                    any(c.resource == "vitality" for c in definition.costs)
                )
                facts["bp_gift_skills"] += int(bool(definition.battle_resource_gains))
            except Exception:  # noqa: BLE001 - an ability that cannot be used now is skipped
                continue
            used[ability_id] += 1
            if ability_id in ("draw_bow", "draw_dagger"):  # the weapon swap changed the skills
                gained = "attack_bow" if ability_id == "draw_bow" else "attack_dagger"
                facts["swapped_in_battle"] += int(gained in game.battle.member(actor).ability_ids)
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
    "bought",
    "crafted",
    "disassembled",
    "concocted",
    "reaction_w_counter",
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
    "forms_cast",
    "goods_cost_skills",
    "hp_cost_skills",
    "bp_gift_skills",
)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    facts = Counter()
    acc = {"phases": set(), "states": set(), "tags": set(), "used": Counter()}
    fights = int(argv[argv.index("--fights") + 1]) if "--fights" in argv else len(SUB_JOBS)
    for seed in range(fights):
        project, game = load()
        game.save.rpg_state.currencies["gold"] = 40000.0
        game.refine_rng = random.Random(seed)
        prepare(game, facts, SUB_JOBS[seed % len(SUB_JOBS)], tier=seed % 3)
        build = game.resolve_actor_build(HERO)
        facts["abilities_available"] = len(build.abilities)
        facts["class_growth_stat_power"] = int(build.stats.get("power"))
        fight(game, facts, acc, seed=seed)
        facts["fights"] += 1
    # the crowd: one more fight against the boss and eight wisps (AI and drawing under load)
    project, game = load()
    game.refine_rng = random.Random(99)
    prepare(game, facts, "sage")
    crowd = Counter()
    fight(game, crowd, acc, seed=99, max_rounds=400, encounter="swarm", crowd=True)
    facts["swarm_enemies"] = 9
    facts["swarm_actions"] = crowd["log_action"]
    facts["swarm_victory"] = crowd["victory"]
    used = acc["used"]
    facts["hero_skills_used"] = len({a for a in used if not a.startswith("w_")})
    facts["boss_moves_used"] = len({a for a in used if a.startswith("w_")})
    facts["boss_phases_seen"] = len(acc["phases"])
    facts["status_kinds_seen"] = len({s for _side, s in acc["states"]})
    facts["boss_stances_seen"] = len([t for t in acc["tags"] if t.startswith("stance.")])
    facts["break_seen"] = int("state.broken" in acc["tags"])
    facts["summons"] = facts.get("log_summoned", 0)
    allocation = game.save.rpg_state.progression_allocations[HERO]
    trees = [g for g in allocation.definitions.values() if g.graph_id.endswith("_tree")]
    trees = [t for t in trees if t.graph_id != "spirit_tree"]
    for tree in trees:  # every job must have had a skill played
        skills = {a for n in tree.nodes for r in n.rewards for a in r.granted_abilities}
        if skills & set(used):
            facts["jobs_with_skills_used"] += 1
    facts["jobs_total"] = len(trees)
    width = max(len(k) for k in facts)
    for key in sorted(facts):
        print(f"{key:<{width}}  {facts[key]}")
    print("hero skills:", sorted(a for a in used if not a.startswith("w_")))
    print("boss moves:", sorted(a for a in used if a.startswith("w_")))
    missing = [k for k in REQUIRED if not facts.get(k)]
    if facts["jobs_with_skills_used"] < facts["jobs_total"]:
        missing.append("jobs_with_skills_used")
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
