"""Six advanced jobs of the Boss Trial: weapon master, sage, hero, forgemaster, rogue, guardian.

Each job has its own stats and growth, seven skills of different kinds (multi-hit, instant death,
dispel, mirror, element infusion, a refine done in battle, damage from DEFENCE, gold from a hit,
divine skills that spend three boost points...), and a skill tree built from the same pattern:
a ranked core, skills behind prerequisites, two exclusive keystones and a passive.
"""

from __future__ import annotations

import trial_content as tc

from asteria.gameplay.conditions import ConditionGroup, TagCondition
from asteria.rpg import ClassDefinition, ProgressionGraphDefinition
from asteria.rpg.ability_build import PassiveDefinition

HP, SP, BP = tc.HP, tc.SP, tc.BP
CRIT = tc.CRIT
_hits, _state, _with_self = tc._hits, tc._state, tc._with_self
ability, op, damage, healing = tc.ability, tc.op, tc.damage, tc.healing
CAP = "capability.weapon."
JOB_IDS = ("weapon_master", "sage", "hero", "forgemaster", "rogue", "guardian")

CLASSES = {
    "weapon_master": dict(
        name="Weapon Master",
        stats={"power": 10, "speed": 6, "crit": 8},
        res={SP: 40},
        grow={"power": 2.6, "speed": 1.0, "crit": 0.12},
        caps=("sword", "axe", "spear", "dagger", "bow", "staff"),
        first="arsenal_barrage",
    ),
    "sage": dict(
        name="Sage",
        stats={"magic": 18, "defense": 6},
        res={SP: 120},
        grow={"magic": 3.2, "defense": 1.2},
        caps=("staff", "dagger"),
        first="holy_light",
    ),
    "hero": dict(
        name="Hero",
        stats={"power": 8, "magic": 8, "defense": 8, "speed": 6, "crit": 6, "evade": 4},
        res={HP: 300, SP: 60},
        grow={"power": 2.2, "magic": 2.2, "defense": 1.8, "speed": 0.8},
        caps=("sword", "spear"),
        first="brave_slash",
    ),
    "forgemaster": dict(
        name="Forgemaster",
        stats={"power": 12, "defense": 10},
        res={HP: 300, SP: 50},
        grow={"power": 3.0, "defense": 2.0},
        caps=("axe", "sword"),
        first="temper",
    ),
    "rogue": dict(
        name="Rogue",
        stats={"speed": 18, "crit": 14, "evade": 14},
        res={SP: 40},
        grow={"speed": 1.8, "crit": 0.2, "evade": 0.15, "power": 1.4},
        caps=("dagger", "bow"),
        first="mug",
    ),
    "guardian": dict(
        name="Guardian",
        stats={"defense": 22},
        res={HP: 900, SP: 30},
        grow={"defense": 3.4, "power": 1.2},
        caps=("sword", "axe"),
        first="shield_wall",
    ),
}

PASSIVES = {
    "arms_mastery": ("Arms Mastery", {"power": 14, "crit": 6}),
    "sages_calm": ("Sage's Calm", {"magic": 20, "defense": 8}),
    "heros_heart": ("Hero's Heart", {"power": 8, "magic": 8, "defense": 8}),
    "forge_fire": ("Forge Fire", {"power": 18}),
    "shadow_step_passive": ("Cutpurse's Luck", {"evade": 16, "speed": 8}),
    "iron_wall": ("Iron Wall", {"defense": 34}),
}

FX = {  # hand-picked looks (the rest follow their damage tags)
    "arsenal_barrage": ("slash", "cut", "slash", "cut"),
    "weapon_dance": ("slash", "circ", "cutx", "cut", "cutd"),
    "disarm": ("circ", "circle"),
    "guard_break": ("circ", "spirit"),
    "sharpen": ("aura",),
    "blade_storm": ("clawd",) * 6,
    "edge_of_ages": ("fire", "ice", "thunder", "slash2", "explosion"),
    "holy_light": ("boost",),
    "dispel": ("spirit", "circle"),
    "mirror_veil": ("shield",),
    "tri_blast": ("fire", "ice", "thunder"),
    "purify": ("boost",),
    "gaia_blessing": ("aura", "boost"),
    "genesis": ("spark", "fire", "ice", "thunder", "explosion"),
    "brave_slash": ("slash", "slash2"),
    "rally_cry": ("aura", "boost"),
    "holy_blade": ("slash", "spark"),
    "second_wind": ("boost",),
    "resolute": ("shield", "aura"),
    "lightning_strike": ("thunder", "cutx"),
    "hero_finale": ("slash2", "spark", "spark", "explosion"),
    "temper": ("fire", "aura"),
    "enchant_frost": ("ice", "aura"),
    "enchant_storm": ("thunder", "aura"),
    "anvil_slam": ("circ", "explosion"),
    "hammer_combo": ("slash", "slash2", "circ", "explosion"),
    "quick_refine": ("fire", "boost"),
    "masterwork": ("fire", "slash2", "explosion", "aura"),
    "mug": ("cut", "spark"),
    "vanish": ("smoke",),
    "backstab": ("cutx",),
    "poison_cloud": ("smoke", "smoke"),
    "smoke_bomb": ("smoke", "circle"),
    "deathmark": ("spirit", "cutx"),
    "shadow_feast": ("clawd", "spirit", "clawd", "explosion"),
    "shield_wall": ("shield", "aura"),
    "provoke": ("circle", "aura"),
    "retaliate": ("circ", "slash"),
    "fortify": ("aura", "boost"),
    "bulwark_charge": ("circ", "explosion"),
    "last_bastion": ("boost", "shield"),
    "aegis": ("shield", "aura", "spark"),
    "draw_bow": ("aura",),
    "draw_dagger": ("aura",),
    "counter_stance": ("shield", "circ"),
}
SELF = {
    "sharpen",
    "holy_light",
    "mirror_veil",
    "purify",
    "gaia_blessing",
    "genesis",
    "rally_cry",
    "second_wind",
    "resolute",
    "temper",
    "enchant_frost",
    "enchant_storm",
    "quick_refine",
    "vanish",
    "shield_wall",
    "fortify",
    "last_bastion",
    "aegis",
    "draw_bow",
    "draw_dagger",
    "counter_stance",
    "hero_finale_heal",
}


def _kill(chance, tags=("boss",), fraction=0.1):
    return {
        "chance": chance,
        "resource": HP,
        "immune_tags": list(tags),
        "immune_fraction": fraction,
    }


def _skills(c):
    """Every advanced skill: (job, id, label, target, definition, divine)."""
    both = ConditionGroup(
        (TagCondition("source", "equip.sword"), TagCondition("source", "equip.dagger"))
    )
    refine = [
        {
            "command": "REFINE_EQUIPMENT",
            "args": {"actor_id": "hero_01", "instance_id": "w_sunbrand:hero_01"},
        }
    ]
    gold = [{"command": "CHANGE_CURRENCY", "args": {"currency_id": "gold", "amount": 150}}]

    def a(*args, **kw):
        return ability(*args, **kw)

    wm = [
        (
            "arsenal_barrage",
            "Arsenal Barrage",
            "enemy",
            a(
                "arsenal_barrage",
                tags=("weapon.sword", "weapon.dagger"),
                effect=op(damage("power", 9)),
                sp=14,
                conditions=both,
                hits=[
                    {"tags": [t], "power": 1.0, "checks": CRIT}
                    for t in ("weapon.sword", "weapon.dagger", "weapon.sword", "weapon.dagger")
                ],
            ),
        ),
        (
            "weapon_dance",
            "Weapon Dance",
            "enemy",
            a(
                "weapon_dance",
                effect=op(damage("power", 8)),
                sp=18,
                hits=[
                    {"tags": [f"weapon.{k}"], "power": 1.0, "checks": CRIT}
                    for k in ("sword", "axe", "spear", "dagger", "bow")
                ],
            ),
        ),
        (
            "disarm",
            "Disarm",
            "enemy",
            a(
                "disarm",
                tags=("weapon.spear",),
                effect=op(damage("power", 7)),
                sp=12,
                hits=_hits(1.0, tags=("weapon.spear",)),
                apply_states=[_state("power_down")],
            ),
        ),
        (
            "guard_break",
            "Guard Break",
            "enemy",
            a(
                "guard_break",
                tags=("weapon.axe",),
                effect=op(damage("power", 12)),
                sp=14,
                hits=_hits(1.0, tags=("weapon.axe",)),
                apply_states=[_state("defense_down"), _state("stun")],
            ),
        ),
        (
            "sharpen",
            "Sharpen",
            "self",
            a(
                "sharpen",
                sp=10,
                cooldown_turns=3,
                apply_states=[_state("attack_up", "self"), _state("focus", "self")],
            ),
        ),
        (
            "blade_storm",
            "Blade Storm",
            "enemy",
            a(
                "blade_storm",
                tags=("weapon.sword",),
                effect=op(damage("power", 5)),
                sp=24,
                hits=_hits(*([1.0] * 6)),
            ),
        ),
        (
            "draw_bow",
            "Draw Bow",
            "self",
            a(
                "draw_bow",
                commands=[
                    {
                        "command": "EQUIP_ITEM",
                        "args": {"actor_id": "hero_01", "equipment_id": "w_bow", "index": 1},
                    }
                ],
            ),
        ),
        (
            "draw_dagger",
            "Draw Dagger",
            "self",
            a(
                "draw_dagger",
                commands=[
                    {
                        "command": "EQUIP_ITEM",
                        "args": {"actor_id": "hero_01", "equipment_id": "w_dagger", "index": 1},
                    }
                ],
            ),
        ),
        (
            "edge_of_ages",
            "Edge of Ages",
            "enemy",
            a(
                "edge_of_ages",
                tags=("weapon.sword", "divine"),
                effect=op(damage("power", 6)),
                sp=40,
                battle_costs={BP: 3},
                hits=[
                    {"tags": [t], "power": 0.8 + 0.25 * i, "checks": ["crit"]}
                    for i, t in enumerate(
                        (
                            "damage.fire",
                            "damage.ice",
                            "damage.lightning",
                            "weapon.sword",
                            "damage.light",
                        )
                    )
                ],
            ),
        ),
    ]
    sage = [
        (
            "holy_light",
            "Holy Light",
            "self",
            a(
                "holy_light",
                tags=("magic", "damage.light"),
                effect=op(healing(22)),
                mode="self",
                sp=14,
            ),
        ),
        (
            "dispel",
            "Dispel",
            "enemy",
            a(
                "dispel",
                tags=("magic",),
                effect=op(damage("magic", 5)),
                sp=12,
                apply_states=[
                    _state("stance_bulwark", remove=True),
                    _state("stance_fury", remove=True),
                    _state("ward", remove=True),
                ],
            ),
        ),
        (
            "mirror_veil",
            "Mirror Veil",
            "self",
            a(
                "mirror_veil",
                tags=("magic",),
                sp=14,
                cooldown_turns=3,
                apply_states=[_state("mirror", "self")],
            ),
        ),
        (
            "tri_blast",
            "Tri-Blast",
            "enemy",
            a(
                "tri_blast",
                tags=("magic",),
                effect=op(damage("magic", 8)),
                sp=22,
                hits=[
                    {"tags": [t], "power": 1.0, "checks": ["crit"]}
                    for t in ("damage.fire", "damage.ice", "damage.lightning")
                ],
            ),
        ),
        (
            "purify",
            "Purify",
            "self",
            a(
                "purify",
                tags=("magic",),
                sp=10,
                apply_states=[
                    _state(x, "self", True)
                    for x in ("poison", "burn", "bleed", "silence", "defense_down", "power_down")
                ],
            ),
        ),
        (
            "gaia_blessing",
            "Gaia's Blessing",
            "self",
            a(
                "gaia_blessing",
                tags=("magic",),
                sp=22,
                cooldown_turns=4,
                apply_states=[
                    _state("regen", "self"),
                    _state("ward", "self"),
                    _state("magic_up", "self"),
                ],
            ),
        ),
        (
            "genesis",
            "Genesis",
            "enemy",
            _with_self(
                a(
                    "genesis",
                    tags=("magic", "divine"),
                    effect=op(damage("magic", 7)),
                    sp=44,
                    battle_costs={BP: 3},
                    hits=[
                        {"tags": [t], "power": 1.0 + 0.2 * i, "checks": ["crit"]}
                        for i, t in enumerate(
                            (
                                "damage.light",
                                "damage.fire",
                                "damage.ice",
                                "damage.lightning",
                                "damage.light",
                            )
                        )
                    ],
                ),
                op(healing(12)),
            ),
        ),
    ]
    hero = [
        (
            "brave_slash",
            "Brave Slash",
            "enemy",
            a(
                "brave_slash",
                tags=("weapon.sword",),
                effect=op(damage("power", 12)),
                sp=8,
                hits=[
                    {"tags": [], "power": 1.0, "checks": ["crit"]},
                    {"tags": [], "power": 1.3, "checks": ["crit"]},
                ],
                apply_states=[_state("focus", "self")],
            ),
        ),
        (
            "rally_cry",
            "Rally Cry",
            "self",
            a(
                "rally_cry",
                sp=16,
                cooldown_turns=4,
                apply_states=[
                    _state("attack_up", "self"),
                    _state("haste", "self"),
                    _state("regen", "self"),
                ],
            ),
        ),
        (
            "holy_blade",
            "Holy Blade",
            "enemy",
            a(
                "holy_blade",
                tags=("weapon.sword", "damage.light"),
                effect=op(damage("power", 14)),
                sp=16,
                hits=_hits(1.0, 1.0, tags=("damage.light",)),
            ),
        ),
        (
            "second_wind",
            "Second Wind",
            "self",
            a(
                "second_wind",
                tags=("magic",),
                effect=op(healing(18)),
                mode="self",
                sp=18,
                apply_states=[
                    _state(x, "self", True) for x in ("poison", "burn", "bleed", "defense_down")
                ],
            ),
        ),
        (
            "resolute",
            "Resolute",
            "self",
            a(
                "resolute",
                sp=16,
                cooldown_turns=3,
                apply_states=[_state("ward", "self"), _state("stoneskin", "self")],
            ),
        ),
        (
            "lightning_strike",
            "Lightning Strike",
            "enemy",
            a(
                "lightning_strike",
                tags=("weapon.spear", "damage.lightning"),
                effect=op(damage("power", 15)),
                sp=20,
                hits=_hits(1.0, tags=("damage.lightning",)),
                apply_states=[_state("stun")],
            ),
        ),
        (
            "hero_finale",
            "Hero's Finale",
            "enemy",
            _with_self(
                a(
                    "hero_finale",
                    tags=("weapon.sword", "damage.light", "divine"),
                    effect=op(damage("power", 13)),
                    sp=46,
                    battle_costs={BP: 3},
                    hits=[
                        {"tags": ["damage.light"], "power": p, "checks": ["crit"]}
                        for p in (1.0, 1.4, 1.8, 3.0)
                    ],
                ),
                op(healing(10, "power")),
            ),
        ),
    ]
    forge = [
        (
            "temper",
            "Temper",
            "self",
            a(
                "temper",
                sp=10,
                apply_states=[
                    _state("enchant_fire", "self"),
                    _state("enchant_ice", "self", True),
                    _state("enchant_lightning", "self", True),
                    _state("attack_up", "self"),
                ],
            ),
        ),
        (
            "enchant_frost",
            "Frost Temper",
            "self",
            a(
                "enchant_frost",
                sp=10,
                apply_states=[
                    _state("enchant_ice", "self"),
                    _state("enchant_fire", "self", True),
                    _state("enchant_lightning", "self", True),
                ],
            ),
        ),
        (
            "enchant_storm",
            "Storm Temper",
            "self",
            a(
                "enchant_storm",
                sp=10,
                apply_states=[
                    _state("enchant_lightning", "self"),
                    _state("enchant_fire", "self", True),
                    _state("enchant_ice", "self", True),
                ],
            ),
        ),
        (
            "anvil_slam",
            "Anvil Slam",
            "enemy",
            a(
                "anvil_slam",
                tags=("weapon.axe",),
                effect=op(damage("power", 18)),
                sp=16,
                hits=_hits(1.0, tags=("weapon.axe",)),
                apply_states=[_state("stun"), _state("defense_down")],
            ),
        ),
        (
            "hammer_combo",
            "Hammer Combo",
            "enemy",
            a(
                "hammer_combo",
                tags=("weapon.axe",),
                effect=op(damage("power", 8)),
                sp=20,
                hits=_hits(1.0, 1.1, 1.2, 2.0, tags=("weapon.axe",)),
            ),
        ),
        (
            "quick_refine",
            "Quick Refine",
            "self",
            a(
                "quick_refine",
                sp=20,
                cooldown_turns=2,
                commands=refine,
                apply_states=[_state("attack_up", "self")],
            ),
        ),
        (
            "masterwork",
            "Masterwork",
            "enemy",
            a(
                "masterwork",
                tags=("weapon.axe", "weapon.sword", "damage.fire", "divine"),
                effect=op(damage("power", 9)),
                sp=40,
                battle_costs={BP: 3},
                commands=refine,
                hits=[
                    {"tags": ["weapon.axe"], "power": 1.0, "checks": ["crit"]},
                    {"tags": ["damage.fire"], "power": 1.4, "checks": ["crit"]},
                    {"tags": ["weapon.sword"], "power": 1.8, "checks": ["crit"]},
                    {"tags": ["damage.fire"], "power": 3.0, "checks": ["crit"]},
                ],
                apply_states=[_state("enchant_fire", "self")],
            ),
        ),
    ]
    rogue = [
        (
            "mug",
            "Mug",
            "enemy",
            a(
                "mug",
                tags=("weapon.dagger",),
                effect=op(damage("power", 9)),
                sp=8,
                hits=_hits(1.0, 1.0, tags=("weapon.dagger",)),
                commands=gold,
            ),
        ),
        (
            "vanish",
            "Vanish",
            "self",
            a(
                "vanish",
                sp=12,
                cooldown_turns=3,
                apply_states=[_state("evasion_up", "self"), _state("haste", "self")],
            ),
        ),
        (
            "backstab",
            "Backstab",
            "enemy",
            a(
                "backstab",
                tags=("weapon.dagger",),
                effect=op(damage("power", 16)),
                sp=14,
                hits=[{"tags": [], "power": 1.0, "checks": ["crit", "crit"]}],
                apply_states=[_state("focus", "self")],
            ),
        ),
        (
            "poison_cloud",
            "Poison Cloud",
            "enemy",
            a(
                "poison_cloud",
                effect=op(damage("power", 4)),
                sp=14,
                apply_states=[_state("poison"), _state("burn"), _state("bleed")],
            ),
        ),
        (
            "smoke_bomb",
            "Smoke Bomb",
            "enemy",
            a(
                "smoke_bomb",
                effect=op(damage("power", 3)),
                sp=12,
                apply_states=[_state("defense_down"), _state("power_down")],
            ),
        ),
        (
            "deathmark",
            "Deathmark",
            "enemy",
            a(
                "deathmark",
                tags=("weapon.dagger", "damage.dark"),
                effect=op(damage("power", 8)),
                sp=24,
                cooldown_turns=2,
                hits=[
                    {
                        "tags": [],
                        "power": 1.0,
                        "checks": ["crit"],
                        "kill": _kill(0.35, fraction=0.14),
                    }
                ],
            ),
        ),
        (
            "shadow_feast",
            "Shadow Feast",
            "enemy",
            a(
                "shadow_feast",
                tags=("weapon.dagger", "damage.dark", "divine"),
                effect=op(damage("power", 6)),
                sp=38,
                battle_costs={BP: 3},
                hits=[{"tags": [], "power": 0.8 + 0.15 * i, "checks": CRIT} for i in range(9)],
                apply_states=[_state("lifelink", "self")],
            ),
        ),
    ]
    guard = [
        (
            "shield_wall",
            "Shield Wall",
            "self",
            a(
                "shield_wall",
                sp=8,
                cooldown_turns=3,
                apply_states=[_state("stoneskin", "self"), _state("ward", "self")],
            ),
        ),
        (
            "provoke",
            "Provoke",
            "enemy",
            a(
                "provoke",
                effect=op(damage("defense", 4)),
                sp=10,
                apply_states=[_state("power_down"), _state("attack_up", "self")],
            ),
        ),
        (
            "retaliate",
            "Retaliate",
            "enemy",
            a(
                "retaliate",
                tags=("weapon.axe",),
                effect=op(damage("defense", 9)),
                sp=14,
                hits=_hits(1.0, 1.0, tags=("weapon.axe",)),
            ),
        ),
        (
            "fortify",
            "Fortify",
            "self",
            a(
                "fortify",
                sp=14,
                cooldown_turns=4,
                apply_states=[_state("regen", "self"), _state("stoneskin", "self")],
            ),
        ),
        (
            "bulwark_charge",
            "Bulwark Charge",
            "enemy",
            a(
                "bulwark_charge",
                tags=("weapon.sword",),
                effect=op(damage("defense", 14)),
                sp=18,
                hits=_hits(1.0, tags=("weapon.sword",)),
                apply_states=[_state("stun")],
            ),
        ),
        (
            "last_bastion",
            "Last Bastion",
            "self",
            a(
                "last_bastion",
                tags=("magic",),
                effect=op(healing(26, "defense")),
                mode="self",
                sp=26,
                apply_states=[_state("ward", "self"), _state("stoneskin", "self")],
                cooldown_turns=4,
            ),
        ),
        (
            "counter_stance",
            "Counter Stance",
            "self",
            a(
                "counter_stance",
                sp=14,
                cooldown_turns=3,
                apply_states=[_state("counter_stance", "self"), _state("stoneskin", "self")],
            ),
        ),
        (
            "aegis",
            "Aegis",
            "self",
            a(
                "aegis",
                tags=("divine",),
                sp=36,
                battle_costs={BP: 3},
                apply_states=[
                    _state("ward", "self"),
                    _state("stoneskin", "self"),
                    _state("mirror", "self"),
                    _state("regen", "self"),
                ],
            ),
        ),
    ]
    for job, group in (
        ("weapon_master", wm),
        ("sage", sage),
        ("hero", hero),
        ("forgemaster", forge),
        ("rogue", rogue),
        ("guardian", guard),
    ):
        for ability_id, label, target, definition in group:
            yield job, ability_id, label, target, definition, "divine" in definition.tags


def _tree(job, label, skills):
    """core (ranked) -> skills behind prerequisites -> two exclusive keystones -> a passive."""
    core = f"{job}_core"
    nodes = [
        tc._node(
            core, f"{label} Training", 5, {f"jp.{job}": 1}, {"stat_bonuses": CLASSES[job]["grow"]}
        )
    ]
    ids = [f"{job}_{s}" for s in skills]
    for index, skill in enumerate(skills):
        cost = {f"jp.{job}": 1 + index}
        if index >= 5:
            cost["ap"] = 2
        links = {}
        if index == 0:
            links["needs"] = [core]
        elif index in (1, 2):
            links["needs"] = [(core, index + 1)]
        elif index in (3, 4):
            links["needs"] = [ids[index - 2]]
        elif index == 5:
            links["any"] = [ids[3], ids[4]]
            links["needs"] = [(core, 4)]
        else:
            links["needs"] = [(core, 5), ids[5]]
            links["any"] = [f"{job}_keyA", f"{job}_keyB"]
        nodes.append(
            tc._node(
                ids[index],
                skill.replace("_", " ").title(),
                1,
                cost,
                {"granted_abilities": (skill,)},
                **links,
            )
        )
    stats = CLASSES[job]["stats"]
    nodes.append(
        tc._node(
            f"{job}_keyA",
            "Path of Might",
            1,
            {f"jp.{job}": 5, "ap": 2},
            {"stat_bonuses": {k: v * 2 for k, v in stats.items()}},
            needs=[(core, 3)],
            group=f"{job}_path",
            tags=("keystone",),
        )
    )
    nodes.append(
        tc._node(
            f"{job}_keyB",
            "Path of Resilience",
            1,
            {f"jp.{job}": 5, "ap": 2},
            {"resource_bonuses": {HP: 600}, "stat_bonuses": {"defense": 14}},
            needs=[(core, 3)],
            group=f"{job}_path",
            tags=("keystone",),
        )
    )
    passive = {
        "weapon_master": "arms_mastery",
        "sage": "sages_calm",
        "hero": "heros_heart",
        "forgemaster": "forge_fire",
        "rogue": "shadow_step_passive",
        "guardian": "iron_wall",
    }[job]
    nodes.append(
        tc._node(
            f"{job}_passive",
            "Mastery",
            1,
            {f"jp.{job}": 8},
            {"unlocked_passives": (passive,)},
            needs=[(core, 5)],
        )
    )
    return ProgressionGraphDefinition(
        f"{job}_tree", label, nodes=tuple(nodes), tags=(f"job.{job}",)
    )


def advanced_jobs(c):
    """Register the six jobs, their passives, skills, trees and skill looks."""
    db = c.db
    for job in JOB_IDS:
        spec = CLASSES[job]
        db.add_class(
            ClassDefinition(
                job,
                spec["name"],
                stat_bonuses=spec["stats"],
                resource_bonuses=spec["res"],
                granted_tags=(f"class.{job}", *(CAP + k for k in spec["caps"])),
                granted_abilities=(spec["first"],),
                level_growth=spec["grow"],
            )
        )
    for pid, (name, stats) in PASSIVES.items():
        db.add_passive(
            PassiveDefinition(
                pid,
                name,
                modifiers=tuple(tc._modifier(k, v, f"{pid}.{k}") for k, v in stats.items()),
            )
        )
    by_job = {job: [] for job in JOB_IDS}
    for job, ability_id, label, target, definition, divine in _skills(c):
        c.add(definition, target)
        c.skill_names[ability_id] = label + (" (Divine)" if divine else "")
        by_job[job].append(ability_id)
    for job in JOB_IDS:
        db.add_progression_graph(_tree(job, CLASSES[job]["name"], by_job[job]))
    tc.FX_BY_ABILITY.update(FX)
    tc.SELF_TARGETED.update(SELF)
    return by_job
