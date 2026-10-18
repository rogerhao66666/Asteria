"""The big skill trees of the Boss Trial (phase 2), four styles side by side:

* **Atlas of Fate** (Path of Exile): one shared passive web every party member walks with ability
  points (2 a level). Six sectors (Might, Arcana, Bulwark, Swiftness, Precision, Vigor) start
  at their own gate; small nodes lead out to notables and to a keystone that trades one
  strength for another; bridges join neighbouring sectors, so a build can wander across.
* **Specializations** (World of Warcraft): every job tree gets three exclusive specs (Priest:
  Holy / Discipline / Shadow ...); a spec opens two ranked talents and a capstone passive.
* **Runes** (Diablo III): the job's signature skill takes one of three runes (Ember: fire and
  burn, Echo: twice the hits, Siphon: heals the user); the rune node grants a tag and an ability
  evolution that needs the tag swaps the skill for its rune version.
* **Skill books** (MapleStory): a ten-rank book per job, bought with skill points earned per
  level (the shrine and the Job Master's training).
"""

from __future__ import annotations

import dataclasses
import math

import trial_content as tc

from asteria.rpg import ProgressionGraphDefinition
from asteria.rpg.ability_build import AbilityEvolutionRule, PassiveDefinition

HP, SP = tc.HP, tc.SP
STAT = {  # keyword -> (stat or resource, amount per rank)
    "power": ("power", 6),
    "magic": ("magic", 6),
    "defense": ("defense", 5),
    "speed": ("speed", 3),
    "crit": ("crit", 2),
    "evade": ("evade", 2),
    "hp": (HP, 220),
    "sp": (SP, 18),
}

SPECS = {  # job: three (spec id, name, first stat, second stat)
    "knight": (
        ("protection", "Protection", "defense", "hp"),
        ("retribution", "Retribution", "power", "crit"),
        ("valor", "Valor", "hp", "power"),
    ),
    "duelist": (
        ("blades", "Blades", "power", "crit"),
        ("footwork", "Footwork", "speed", "evade"),
        ("precision", "Precision", "crit", "speed"),
    ),
    "mystic": (
        ("arcana", "Arcana", "magic", "crit"),
        ("wards", "Wards", "defense", "hp"),
        ("flow", "Flow", "sp", "magic"),
    ),
    "weapon_master": (
        ("arms", "Arms", "power", "defense"),
        ("fury", "Fury", "crit", "power"),
        ("arsenal", "Arsenal", "speed", "power"),
    ),
    "sage": (
        ("elements", "Elements", "magic", "crit"),
        ("wisdom", "Wisdom", "sp", "magic"),
        ("insight", "Insight", "crit", "speed"),
    ),
    "hero": (
        ("champion", "Champion", "power", "hp"),
        ("paragon", "Paragon", "magic", "defense"),
        ("legend", "Legend", "hp", "crit"),
    ),
    "forgemaster": (
        ("anvil", "Anvil", "defense", "hp"),
        ("flame", "Flame", "power", "crit"),
        ("craft", "Craft", "magic", "sp"),
    ),
    "rogue": (
        ("assassination", "Assassination", "crit", "power"),
        ("subtlety", "Subtlety", "evade", "speed"),
        ("outlaw", "Outlaw", "speed", "crit"),
    ),
    "guardian": (
        ("bulwark", "Bulwark", "defense", "hp"),
        ("sentinel", "Sentinel", "hp", "evade"),
        ("retaliation", "Retaliation", "power", "defense"),
    ),
    "cleric": (
        ("mercy", "Mercy", "magic", "sp"),
        ("faith", "Faith", "defense", "hp"),
        ("radiance", "Radiance", "crit", "magic"),
    ),
    "priest": (
        ("holy", "Holy", "magic", "sp"),
        ("discipline", "Discipline", "defense", "magic"),
        ("shadow", "Shadow", "crit", "magic"),
    ),
    "bishop": (
        ("sanctity", "Sanctity", "magic", "hp"),
        ("judgment", "Judgment", "crit", "magic"),
        ("grace", "Grace", "sp", "defense"),
    ),
    "necromancer": (
        ("bone", "Bone", "defense", "magic"),
        ("blood", "Blood", "hp", "magic"),
        ("unholy", "Unholy", "magic", "crit"),
    ),
    "lich": (
        ("frost", "Frost", "magic", "speed"),
        ("plague", "Plague", "crit", "magic"),
        ("phylactery", "Phylactery", "hp", "defense"),
    ),
    "death_lord": (
        ("dominion", "Dominion", "magic", "power"),
        ("dread", "Dread", "crit", "magic"),
        ("harvest", "Harvest", "hp", "magic"),
    ),
    "cultist": (
        ("frenzy", "Frenzy", "speed", "power"),
        ("ritual", "Ritual", "magic", "sp"),
        ("shadows", "Shadows", "evade", "crit"),
    ),
    "zealot": (
        ("fervor", "Fervor", "power", "speed"),
        ("brand", "Brand", "crit", "power"),
        ("crusade", "Crusade", "hp", "defense"),
    ),
    "heretic": (
        ("blasphemy", "Blasphemy", "magic", "power"),
        ("hex", "Hex", "crit", "speed"),
        ("martyr", "Martyr", "hp", "magic"),
    ),
}

RUNES = (  # rune id, name, what it does to a damaging / a supporting skill
    ("ember", "Ember", "fire + burn", "attack_up"),
    ("echo", "Echo", "twice the hits", "haste"),
    ("siphon", "Siphon", "heals its user", "regen"),
)

SECTORS = (  # id, name, stat, keystone (name, bonus, cost)
    ("might", "Might", "power", ("Berserker's Oath", {"power": 60}, {"defense": -30})),
    ("arcana", "Arcana", "magic", ("Arcane Overflow", {"magic": 60}, {"defense": -25})),
    ("bulwark", "Bulwark", "defense", ("Unwavering", {"defense": 60}, {"speed": -20})),
    (
        "swiftness",
        "Swiftness",
        "speed",
        ("Wind Dancer", {"speed": 30, "evade": 20}, {"defense": -25}),
    ),
    ("precision", "Precision", "crit", ("Deadeye", {"crit": 25}, {"magic": -20})),
    ("vigor", "Vigor", "hp", ("Juggernaut", {"defense": 30}, {"speed": -25})),
)


def _bonus(keyword, scale=1.0):
    key, amount = STAT[keyword]
    value = amount * scale
    if key in (HP, SP):
        return {"resource_bonuses": {key: value}}
    return {"stat_bonuses": {key: value}}


def _merge(*rewards):
    out = {}
    for reward in rewards:
        for kind, values in reward.items():
            out.setdefault(kind, {})
            for key, value in values.items():
                out[kind][key] = out[kind].get(key, 0) + value
    return out


# -- the Atlas of Fate ---------------------------------------------------------------------------
def fate_web():
    """Six sectors around a ring; positions are authored so the tree screen draws a web."""
    nodes, positions = [], {}
    count = len(SECTORS)
    for index, (sector, name, stat, (key_name, key_gain, key_cost)) in enumerate(SECTORS):
        angle = 2 * math.pi * index / count - math.pi / 2

        def place(node_id, radius, spread=0.0, angle=angle):
            a = angle + spread
            positions[node_id] = (
                round(math.cos(a) * radius * 70),
                round(math.sin(a) * radius * 70),
            )

        gate = f"web_{sector}_gate"
        nodes.append(
            tc._node(gate, f"Gate of {name}", 1, {"ap": 1}, _bonus(stat, scale=2), tags=("gate",))
        )
        place(gate, 1.4)
        previous = gate
        for step in range(1, 7):
            node_id = f"web_{sector}_{step}"
            notable = step in (3, 6)
            reward = _bonus(stat, scale=4 if notable else 1.2)
            if notable:  # a notable also gives a little of the sector's neighbours
                other = SECTORS[(index + 1) % count][2]
                reward = _merge(reward, _bonus(other, scale=1.5))
            nodes.append(
                tc._node(
                    node_id,
                    f"{name} {'Notable' if notable else 'Node'} {step}",
                    1,
                    {"ap": 2 if notable else 1},
                    reward,
                    needs=[previous],
                    tags=("notable",) if notable else (),
                )
            )
            place(node_id, 1.4 + step * 0.75, spread=0.12 if step % 2 else -0.12)
            previous = node_id
        keystone = f"web_{sector}_keystone"
        stats = dict(key_gain)
        for stat_id, value in key_cost.items():
            stats[stat_id] = stats.get(stat_id, 0) + value
        nodes.append(
            tc._node(
                keystone,
                key_name,
                1,
                {"ap": 4},
                {"stat_bonuses": stats},
                needs=[previous],
                tags=("keystone",),
            )
        )
        place(keystone, 1.4 + 7 * 0.75)
        # a bridge to the next sector: reachable from either side's third node
        bridge = f"web_{sector}_bridge"
        after = SECTORS[(index + 1) % count]
        nodes.append(
            tc._node(
                bridge,
                f"{name}-{after[1]} Crossing",
                1,
                {"ap": 2},
                _merge(_bonus(stat, scale=2), _bonus(after[2], scale=2)),
                any=[f"web_{sector}_3", f"web_{after[0]}_3"],
                tags=("bridge",),
            )
        )
        place(bridge, 3.6, spread=math.pi / count)
    return ProgressionGraphDefinition(
        "fate_web",
        "Atlas of Fate",
        nodes=tuple(nodes),
        tags=("shared",),
        editor_view="graph",
        node_positions=positions,
    )


# -- specs, runes and skill books on every job tree -----------------------------------------------
def _rune_variant(c, base_id, rune):
    """The rune version of a skill: a new ability (and its battle targeting) next to the base."""
    rune_id, rune_name, _what, support_state = rune
    base = c.abilities._definitions[base_id]
    new_id = f"{base_id}__{rune_id}"
    hits = list(base.hits or ())
    states = list(base.apply_states or ())
    tags = list(base.tags)
    definition = base
    if hits:  # a damaging skill
        if rune_id == "ember":
            hits = [
                {
                    **h,
                    "tags": [t for t in h.get("tags", []) if not t.startswith("damage.")]
                    + ["damage.fire"],
                }
                for h in hits
            ]
            tags = [t for t in tags if not t.startswith("damage.")] + ["damage.fire"]
            states.append({"state": "burn", "to": "targets", "remove": False})
        elif rune_id == "echo":
            hits = [{**h, "power": round(h.get("power", 1.0) * 0.6, 3)} for h in hits * 2]
        definition = dataclasses.replace(base, hits=tuple(hits))
    else:
        states.append({"state": support_state, "to": "targets", "remove": False})
    definition = dataclasses.replace(
        definition, ability_id=new_id, tags=tuple(tags), apply_states=tuple(states)
    )
    if rune_id == "siphon":
        definition = tc._with_self(definition, tc.op(tc.healing(2.5)))
    c.abilities._definitions[new_id] = definition
    c.db.battle_targeting[new_id] = dataclasses.replace(
        c.db.battle_targeting[base_id], ability_id=new_id
    )
    if base_id in tc.FX_BY_ABILITY:
        tc.FX_BY_ABILITY[new_id] = tc.FX_BY_ABILITY[base_id]
    if base_id in tc.SELF_TARGETED:
        tc.SELF_TARGETED.add(new_id)
    label = c.skill_names.get(base_id, base_id.replace("_", " ").title())
    c.skill_names[new_id] = f"{label} ({rune_name})"
    return new_id


def _signature(c, job):
    """The skill a job's runes change: its first skill (the class's, else the tree's) that does
    not already evolve with battle experience."""
    evolving = {rule.source_ability_id for rule in c.db.ability_evolutions.values()}
    graph = c.db.progression_graphs[f"{job}_tree"]
    candidates = [
        *c.db.classes[job].granted_abilities,
        *(a for n in graph.nodes for r in n.rewards for a in r.granted_abilities),
    ]
    return next(
        (a for a in candidates if a not in evolving and a in c.abilities._definitions), None
    )


def extend_job_tree(c, job):
    """Specs, runes and a skill book on ``job``'s tree."""
    graph_id = f"{job}_tree"
    graph = c.db.progression_graphs[graph_id]
    root = graph.nodes[0]  # the tree's first node ("<job>_core", or "k_footing" ...)
    core = root.node_id
    two = min(2, root.max_rank)
    jp = f"jp.{job}"
    nodes = list(graph.nodes)
    for spec_id, name, first, second in SPECS[job]:
        gate = f"{job}_spec_{spec_id}"
        nodes.append(
            tc._node(
                gate,
                f"Spec: {name}",
                1,
                {jp: 2},
                _bonus(first, scale=2),
                needs=[(core, two)],
                group=f"{job}_spec",
                tags=("spec",),
            )
        )
        talent_a, talent_b = f"{gate}_t1", f"{gate}_t2"
        nodes.append(tc._node(talent_a, f"{name} I", 3, {jp: 1}, _bonus(first), needs=[gate]))
        nodes.append(
            tc._node(talent_b, f"{name} II", 3, {jp: 1}, _bonus(second), needs=[(talent_a, 2)])
        )
        passive_id = f"{job}_{spec_id}_capstone"
        key, amount = STAT[first]
        modifiers = []
        if key not in (HP, SP):
            modifiers.append(tc._modifier(key, amount * 4, f"{passive_id}.{key}"))
        key2, amount2 = STAT[second]
        if key2 not in (HP, SP):
            modifiers.append(tc._modifier(key2, amount2 * 3, f"{passive_id}.{key2}"))
        if not modifiers:
            modifiers.append(tc._modifier("defense", 10, f"{passive_id}.defense"))
        c.db.add_passive(
            PassiveDefinition(passive_id, f"{name} Mastery", modifiers=tuple(modifiers))
        )
        nodes.append(
            tc._node(
                f"{gate}_capstone",
                f"{name} Capstone",
                1,
                {jp: 3, "ap": 1},
                {"unlocked_passives": (passive_id,)},
                needs=[(talent_b, 3)],
                tags=("capstone",),
            )
        )
    signature = _signature(c, job)
    if signature and signature in c.abilities._definitions:
        for rune in RUNES:
            variant = _rune_variant(c, signature, rune)
            tag = f"rune.{signature}.{rune[0]}"
            nodes.append(
                tc._node(
                    f"{job}_rune_{rune[0]}",
                    f"Rune: {rune[1]} ({c.skill_names.get(signature, signature)})",
                    1,
                    {jp: 2},
                    {"granted_tags": (tag,)},
                    needs=[(core, 1)],
                    group=f"{job}_rune",
                    tags=("rune",),
                )
            )
            c.db.ability_evolutions[f"{job}.rune.{rune[0]}"] = AbilityEvolutionRule(
                f"{job}.rune.{rune[0]}", signature, variant, required_tags=(tag,), priority=5
            )
    book_reward = _bonus(SPECS[job][0][2], scale=0.6)
    nodes.append(
        tc._node(
            f"{job}_book",
            f"{c.db.classes[job].display_name} Skill Book",
            10,
            {"skill_points": 1},
            book_reward,
            needs=[(core, 1)],
            tags=("book",),
        )
    )
    c.db.progression_graphs[graph_id] = dataclasses.replace(graph, nodes=tuple(nodes))


def trees(c):
    """The shared web, then specs / runes / a book on every job tree."""
    c.db.add_progression_graph(fate_web())
    for job in SPECS:
        if f"{job}_tree" in c.db.progression_graphs:
            extend_job_tree(c, job)
