"""The cast of the Boss Trial campaign: two more party members and the foes of each area.

Woods: goblins (Slinger, Berserker) and the Goblin Beast. Catacombs: skeletons (Grunt, Hunter) and
the Skeleton Ancient. Throne: the Skeleton King (Vaelor) and the acolytes he calls. All data on the
same records the earlier waves use.
"""

from __future__ import annotations

import dataclasses

import trial_content as tc

from asteria.rpg import (
    ClassAssignment,
    ClassDefinition,
    EncounterDefinition,
    EncounterMember,
    EnemyDefinition,
)
from asteria.rpg.enemies import RewardDefinition
from asteria.rpg.enemy_ai import EnemyAIDefinition
from asteria.rpg.enemy_behavior import EnemyBehaviorBinding

HP, SP, SHIELD = tc.HP, tc.SP, tc.SHIELD
ability, op, damage, healing = tc.ability, tc.op, tc.damage, tc.healing
_hits, _state, _rule, _cond = tc._hits, tc._state, tc._rule, tc._cond

VESPER, CAEL = "hero_03", "hero_04"
PARTY_CLASSES = {
    "necromancer": (
        "Necromancer",
        {"magic": 20, "defense": 5, "speed": 6},
        {SP: 140},
        ("curse", "drain_touch", "hex", "bewilder", "word_of_doom", "call_spirit"),
        {"magic": 3.0, "defense": 1.0, "speed": 0.5},
    ),
    "cultist": (
        "Cultist",
        {"power": 10, "speed": 14, "evade": 10},
        {SP: 90},
        (
            "charm",
            "lullaby_dust",
            "blinding_powder",
            "pass_the_torch",
            "martyrs_gift",
            "bloodletting",
        ),
        {"power": 1.6, "speed": 1.2, "evade": 0.1},
    ),
}


def party(c):
    """Vesper (Necromancer) and Cael (Cultist): they join the party in the story."""
    db = c.db
    for class_id, (name, stats, res, skills, growth) in PARTY_CLASSES.items():
        weapon = "staff" if class_id == "necromancer" else "dagger"
        db.add_class(
            ClassDefinition(
                class_id,
                name,
                stat_bonuses=stats,
                resource_bonuses=res,
                granted_tags=(f"class.{class_id}", f"capability.weapon.{weapon}"),
                granted_abilities=skills,
                level_growth=growth,
            )
        )
    hero = db.actors[c.hero_id]
    for actor_id, display, class_id, base, hp, sp in (
        (
            VESPER,
            "Vesper",
            "necromancer",
            {"power": 12, "magic": 40, "defense": 18, "speed": 44},
            2300,
            300,
        ),
        (
            CAEL,
            "Cael",
            "cultist",
            {"power": 36, "magic": 22, "defense": 20, "speed": 58},
            2600,
            200,
        ),
    ):
        db.actors[actor_id] = dataclasses.replace(
            hero,
            actor_id=actor_id,
            display_name=display,
            class_assignments=(
                ClassAssignment(
                    class_id, assignment_id=f"{actor_id}.main", role="main", priority=10
                ),
            ),
            base_stats={**base, "crit": 5.0, "evade": 8.0, "lifesteal": 0.0},
            base_resources={
                HP: {"minimum": 0.0, "maximum": float(hp), "current": float(hp)},
                SP: {"minimum": 0.0, "maximum": float(sp), "current": float(sp)},
            },
            abilities=(),
        )
    cleric = db.classes["cleric"]  # the spirit call belongs to the necromancer now
    db.classes["cleric"] = dataclasses.replace(
        cleric, granted_abilities=tuple(a for a in cleric.granted_abilities if a != "call_spirit")
    )


FOES = {
    # id: (name, art, hp, power, magic, defense, speed, tags, abilities, gold, battle exp)
    "goblin_slinger": (
        "Goblin Slinger",
        1500,
        46,
        20,
        24,
        56,
        ("weak.sword",),
        ("gob_sling", "gob_stab"),
        120,
        20,
    ),
    "goblin_berserker": (
        "Goblin Berserker",
        2600,
        64,
        10,
        30,
        52,
        ("weak.ice", "resist.axe"),
        ("gob_chop", "gob_rage"),
        180,
        25,
    ),
    "goblin_beast": (
        "Goblin Beast",
        9500,
        82,
        40,
        44,
        50,
        ("boss", "weak.lightning", "weak.spear", "immune.sleep"),
        ("beast_maul", "beast_howl", "beast_pounce"),
        1500,
        150,
    ),
    "skeleton_grunt": (
        "Skeleton Grunt",
        2200,
        58,
        10,
        40,
        50,
        ("weak.axe", "weak.light", "resist.dagger", "absorb.dark"),
        ("skel_slash", "skel_guard"),
        160,
        20,
    ),
    "skeleton_hunter": (
        "Skeleton Hunter",
        1800,
        70,
        20,
        30,
        62,
        ("weak.light", "resist.dagger"),
        ("skel_shot", "skel_slash"),
        200,
        25,
    ),
    "skeleton_ancient": (
        "Skeleton Ancient",
        16500,
        96,
        90,
        70,
        58,
        ("boss", "weak.light", "weak.fire", "absorb.dark", "immune.sleep"),
        ("anc_curse", "anc_rain", "anc_drain", "anc_raise"),
        3200,
        150,
    ),
}


def foes(c):
    """The foes of the woods and the catacombs, their moves, behaviour and rewards."""
    db, add = c.db, c.add
    moves = {
        "gob_sling": (
            ability(
                "gob_sling",
                tags=("weapon.bow",),
                effect=op(damage("power", 8)),
                hits=_hits(1.0, tags=("weapon.bow",)),
            ),
            "enemy",
        ),
        "gob_stab": (
            ability(
                "gob_stab",
                tags=("weapon.dagger",),
                effect=op(damage("power", 6)),
                hits=_hits(1.0, 1.0, tags=("weapon.dagger",)),
                apply_states=[_state("bleed")],
            ),
            "enemy",
        ),
        "gob_chop": (
            ability(
                "gob_chop",
                tags=("weapon.axe",),
                effect=op(damage("power", 11)),
                hits=_hits(1.0, tags=("weapon.axe",)),
            ),
            "enemy",
        ),
        "gob_rage": (
            ability(
                "gob_rage", apply_states=[_state("attack_up", "self"), _state("haste", "self")]
            ),
            "self",
        ),
        "beast_maul": (
            ability(
                "beast_maul",
                tags=("weapon.axe",),
                effect=op(damage("power", 7)),
                hits=_hits(1.0, 1.0, 1.4, tags=("weapon.axe",)),
            ),
            "enemy",
        ),
        "beast_howl": (
            ability(
                "beast_howl",
                tags=("magic",),
                apply_states=[_state("attack_up", "allies"), _state("defense_down")],
            ),
            "enemies",
        ),
        "beast_pounce": (
            ability(
                "beast_pounce",
                tags=("weapon.axe", "damage.fire"),
                effect=op(damage("power", 16)),
                hits=_hits(1.6, tags=("weapon.axe", "damage.fire")),
                apply_states=[_state("stun")],
            ),
            "enemy",
        ),
        "skel_slash": (
            ability(
                "skel_slash",
                tags=("weapon.sword",),
                effect=op(damage("power", 7)),
                hits=_hits(1.0, tags=("weapon.sword",)),
            ),
            "enemy",
        ),
        "skel_guard": (ability("skel_guard", apply_states=[_state("stoneskin", "self")]), "self"),
        "skel_shot": (
            ability(
                "skel_shot",
                tags=("weapon.bow",),
                effect=op(damage("power", 9)),
                hits=_hits(1.0, tags=("weapon.bow",)),
                apply_states=[_state("poison")],
            ),
            "enemy",
        ),
        "anc_curse": (
            ability(
                "anc_curse",
                tags=("magic", "damage.dark"),
                effect=op(damage("magic", 5)),
                hits=_hits(1.0, tags=("damage.dark",), checks=["land"]),
                apply_states=[_state("silence"), _state("power_down"), _state("doom")],
            ),
            "enemy",
        ),
        "anc_rain": (
            ability(
                "anc_rain",
                tags=("magic", "damage.dark"),
                effect=op(damage("magic", 6)),
                hits=_hits(1.0, 1.0, 1.2, 1.4, tags=("damage.dark",)),
                targets=6,
            ),
            "enemies",
        ),
        "anc_drain": (
            tc._with_self(
                ability("anc_drain", tags=("magic", "damage.dark"), effect=op(damage("magic", 8))),
                op(healing(25)),
            ),
            "enemy",
        ),
        "anc_raise": (
            ability(
                "anc_raise",
                commands=[
                    {
                        "command": "SUMMON",
                        "args": {"enemy_id": "skeleton_grunt", "count": 2, "owner_id": "@actor"},
                    }
                ],
            ),
            "self",
        ),
    }
    names = {
        "gob_sling": "Sling Stone",
        "gob_stab": "Stab",
        "gob_chop": "Chop",
        "gob_rage": "Rage",
        "beast_maul": "Maul",
        "beast_howl": "Howl",
        "beast_pounce": "Pounce",
        "skel_slash": "Bone Slash",
        "skel_guard": "Guard",
        "skel_shot": "Bone Arrow",
        "anc_curse": "Ancient Curse",
        "anc_rain": "Rain of Bone",
        "anc_drain": "Soul Drain",
        "anc_raise": "Raise the Fallen",
    }
    for ability_id, (definition, target) in moves.items():
        add(definition, target)
        c.skill_names[ability_id] = names[ability_id]
    tc.FX_BY_ABILITY.update(
        {
            "gob_sling": ("cut",),
            "gob_stab": ("cut", "cut"),
            "gob_chop": ("slash",),
            "gob_rage": ("aura",),
            "beast_maul": ("clawd", "clawd", "claw"),
            "beast_howl": ("circle", "aura"),
            "beast_pounce": ("circ", "fire"),
            "skel_slash": ("slash",),
            "skel_guard": ("shield",),
            "skel_shot": ("cutx",),
            "anc_curse": ("spirit", "circle"),
            "anc_rain": ("spirit", "spirit", "explosion", "explosion"),
            "anc_drain": ("spirit", "boost"),
            "anc_raise": ("circle", "smoke"),
        }
    )
    tc.SELF_TARGETED.update({"gob_rage", "skel_guard", "anc_raise"})
    selector = {
        "gob_rage": "self",
        "skel_guard": "self",
        "anc_raise": "self",
        "beast_howl": "self",
    }
    for enemy_id, (
        name,
        hp,
        power,
        magic,
        defense,
        speed,
        tags,
        abilities,
        gold,
        xp,
    ) in FOES.items():
        reward = RewardDefinition(
            currencies={"gold": float(gold)}, experience={"battle_experience": float(xp)}
        )
        db.enemies[enemy_id] = EnemyDefinition(
            enemy_id,
            name,
            stats={
                "power": float(power),
                "magic": float(magic),
                "defense": float(defense),
                "speed": float(speed),
                "crit": 5.0,
                "evade": 3.0,
            },
            resources={HP: float(hp), SHIELD: 4.0 if "boss" in tags else 2.0, SP: 999.0},
            tags=("enemy", *tags),
            abilities=abilities,
            reward=reward,
        )
        rules = []
        for index, ability_id in enumerate(abilities):
            rules.append(
                _rule(
                    f"{enemy_id}.{ability_id}",
                    ability_id,
                    selector.get(ability_id, "first_opponent"),
                    weight=3.0 - 0.5 * index,
                )
            )
        db.enemy_ai[f"{enemy_id}_ai"] = EnemyAIDefinition.from_data(
            {
                "schema": "asteria.rpg.enemy_ai_definition",
                "version": 1,
                "ai_id": f"{enemy_id}_ai",
                "rules": rules,
                "phases": [],
                "initial_phase_id": None,
            }
        )
        db.enemy_behavior_bindings[enemy_id] = EnemyBehaviorBinding.from_data(
            {
                "schema": "asteria.rpg.enemy_behavior_binding",
                "version": 1,
                "enemy_id": enemy_id,
                "ai_id": f"{enemy_id}_ai",
                "tags": [],
            }
        )
    from asteria.rpg.drop_tables import DropEntry, DropTable

    gear = [DropEntry(g, weight=1.0) for g in ("w_sword", "w_axe", "w_spear", "w_dagger", "w_bow")]
    tables = {
        "goblin_loot": DropTable(
            "goblin_loot",
            entries=[
                DropEntry("healing_herb", weight=3.0),
                DropEntry("iron_ore", weight=3.0),
                *gear[:2],
            ],
            nothing_weight=4.0,
        ),
        "bone_loot": DropTable(
            "bone_loot",
            entries=[
                DropEntry("silver_ore", weight=3.0),
                DropEntry("ice_crystal", weight=2.0),
                *gear[2:],
            ],
            nothing_weight=4.0,
        ),
        "beast_spoils": DropTable(
            "beast_spoils",
            entries=gear,
            rolls=2,
            nothing_weight=1.0,
            guaranteed=[DropEntry("ruby_item"), DropEntry("iron_ore", minimum=2, maximum=4)],
        ),
        "ancient_spoils": DropTable(
            "ancient_spoils",
            entries=[
                *gear,
                *(
                    DropEntry(g, weight=0.5)
                    for g in ("a_warden_plate", "a_warden_ring", "a_warden_charm")
                ),
            ],
            rolls=3,
            nothing_weight=1.0,
            guaranteed=[
                DropEntry("ancient_thread"),
                DropEntry("silver_ore", minimum=1, maximum=3),
            ],
        ),
    }
    for table in tables.values():
        db.add_drop_table(table)
    for enemy_id, table in (
        ("goblin_slinger", "goblin_loot"),
        ("goblin_berserker", "goblin_loot"),
        ("goblin_beast", "beast_spoils"),
        ("skeleton_grunt", "bone_loot"),
        ("skeleton_hunter", "bone_loot"),
        ("skeleton_ancient", "ancient_spoils"),
    ):
        enemy = db.enemies[enemy_id]
        db.enemies[enemy_id] = dataclasses.replace(
            enemy, reward=dataclasses.replace(enemy.reward, drop_table_id=table)
        )
    for encounter_id, members, tags in (
        ("woods_patrol", (("goblin_slinger", 2), ("goblin_berserker", 1)), ("woods",)),
        ("woods_ambush", (("goblin_slinger", 3),), ("woods",)),
        (
            "woods_boss",
            (("goblin_beast", 1), ("goblin_slinger", 2)),
            ("boss", "woods", "no_escape"),
        ),
        ("crypt_patrol", (("skeleton_grunt", 2), ("skeleton_hunter", 1)), ("crypt",)),
        ("crypt_guard", (("skeleton_hunter", 2), ("skeleton_grunt", 1)), ("crypt",)),
        (
            "crypt_boss",
            (("skeleton_ancient", 1), ("skeleton_hunter", 2)),
            ("boss", "crypt", "no_escape"),
        ),
    ):
        db.encounters[encounter_id] = EncounterDefinition(
            encounter_id,
            members=tuple(EncounterMember(e, count=n, weight=1.0) for e, n in members),
            tags=tags,
        )
