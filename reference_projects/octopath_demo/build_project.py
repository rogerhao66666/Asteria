"""Build the Octopath-style battle demo from the Complex Reference RPG (its CC0 art, map and
field).

Everything here is ordinary project data - no engine code knows about this game:

* four travellers, each with a main and a secondary job, two weapon kinds each (dual wielding);
* weapon and element weaknesses (sword, spear, dagger, axe, bow, staff; fire, ice, lightning,
  light),
  shields per enemy, Break (no turn, double damage), Boost (attacks repeat, spells grow stronger);
* divine skills that spend several boost points; a skill that needs two weapon kinds equipped;
  skills of
  several hits and several damage types; a pet called into battle; concocting ingredients in
  battle;
  giving boost points to an ally; poison that worsens every turn, sleep, silence, attack up,
  defence down;
* particle bursts on divine skills and an aura on the boss in the field.

Run: ``python reference_projects/octopath_demo/build_project.py`` (writes this folder; idempotent).
Play: ``python -m asteria.runtime.preview reference_projects/octopath_demo/project.asteria.json``.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REFERENCE = REPO / "reference_projects" / "complex_reference_rpg"
sys.path.insert(0, str(REPO / "src"))

from asteria.editor import EditorDocument  # noqa: E402
from asteria.gameplay import AbilityDefinition, Effect, EffectOperation, EffectOperationKind  # noqa: E402
from asteria.gameplay.abilities import AbilityCost, AbilityEffect, TargetingRule  # noqa: E402
from asteria.gameplay.conditions import ConditionGroup, TagCondition  # noqa: E402
from asteria.gameplay.formulas import FormulaTerm, ValueFormula  # noqa: E402
from asteria.gameplay.modifiers import StatModifier  # noqa: E402
from asteria.gameplay.states import PeriodicEffect, StateDefinition  # noqa: E402
from asteria.presentation.particles import particle_effect_asset, preset  # noqa: E402
from asteria.project import Project  # noqa: E402
from asteria.rpg import BattleStatePolicy, EnemyDefinition  # noqa: E402
from asteria.rpg.battle_resources import BattleResourceDefinition  # noqa: E402
from asteria.rpg.composition import (
    CompositionOutput,
    CompositionRecipeDefinition,
    CompositionSelection,
)  # noqa: E402
from asteria.rpg.gauge_composition import (  # noqa: E402
    GaugeCompositionDefinition,
    GaugeImpactRule,
    GaugeThresholdRule,
)
from asteria.rpg.interactions import InteractionRule  # noqa: E402
from asteria.rpg.items import ItemDefinition  # noqa: E402

HP, SP, BP, SHIELD = "vitality", "technique", "bp", "shield"
WEAPONS = ("sword", "spear", "dagger", "axe", "bow", "staff")
ELEMENTS = ("fire", "ice", "lightning", "light")


# -- small builders -------------------------------------------------------------------------------
def damage(stat, coefficient, defense=6.0):
    """Damage: ``coefficient`` x the user's ``stat`` minus ``defense`` x the target's defence (at
    least 1)."""
    return ValueFormula(
        (
            FormulaTerm("source_stat", stat, -coefficient),
            FormulaTerm("target_stat", "defense", defense),
        ),
        maximum=-1.0,
    )


def healing(amount_per_magic):
    return ValueFormula((FormulaTerm("source_stat", "magic", amount_per_magic),), minimum=1.0)


def op(value):
    return EffectOperation(EffectOperationKind.RESOURCE_DELTA, HP, value)


def ability(
    ability_id, *, tags=(), effect=None, sp=0, mode="selected", targets=1, allies=False, **extra
):
    effects = (
        () if effect is None else (AbilityEffect(mode, Effect(f"{ability_id}.effect", (effect,))),)
    )
    costs = (AbilityCost(SP, sp),) if sp else ()
    rule = TargetingRule(minimum_targets=1, maximum_targets=targets, allow_self=allies)
    return AbilityDefinition(
        ability_id, targeting=rule, costs=costs, effects=effects, tags=("ability", *tags), **extra
    )


def main():
    target = (
        HERE / "playable_assets"
    )  # the reference game's CC0 art first; new art is written into it below
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(REFERENCE / "playable_assets", target)
    registry = EditorDocument().component_registry
    project = Project.load_json(REFERENCE / "project.asteria.json", registry)
    project.name = "Asteria Octopath-style Battle Demo"
    db, library = project.rpg_database, project.gameplay_library
    abilities = library.abilities
    template = {
        k: db.battle_targeting[k]
        for k in ("strike", "boss_roar", "heal", "party_barrier", "guard")
    }

    def add(definition, targeting):
        """Register an ability with its battle targeting: one / all opponents, one / all allies, or
        self."""
        abilities._definitions[definition.ability_id] = definition
        base = {
            "enemy": "strike",
            "enemies": "boss_roar",
            "ally": "heal",
            "allies": "party_barrier",
            "self": "guard",
        }[targeting]
        db.battle_targeting[definition.ability_id] = dataclasses.replace(
            template[base], ability_id=definition.ability_id
        )
        return definition.ability_id

    # -- boost points, shields, Break -------------------------------------------------------------
    db.battle_resources[BP] = dataclasses.replace(db.battle_resources["momentum"], resource_id=BP)
    db.battle_resources[SHIELD] = BattleResourceDefinition(
        SHIELD, minimum=0, maximum=1, start_mode="maximum", subject_maximum=True
    )
    for old in ("momentum", "stagger", "rage"):
        db.battle_resources.pop(old, None)
    db.gauge_compositions.clear()
    db.gauge_compositions["break"] = GaugeCompositionDefinition(
        "break",
        impacts=(
            GaugeImpactRule(
                "weak_hit",
                SHIELD,
                "battle.hit",
                recipient="target",
                delta=-1.0,
                required_outcome_tags_all=("outcome.weak",),
            ),
        ),
        thresholds=(
            GaugeThresholdRule(
                "break",
                SHIELD,
                "at_or_below",
                0.0,
                state_id="broken",
                timeline_shift=1.5,
                emit_trigger="battle.break",
                reset_to_maximum=True,
            ),
        ),
    )
    rules = next(iter(db.battle_session_rules.values()))
    db.battle_session_rules.clear()
    db.battle_session_rules["octopath"] = dataclasses.replace(
        rules,
        rules_id="octopath",
        boost_resource_id=BP,
        boost_max_level=3,
        shield_resource_id=SHIELD,
    )
    library.states._definitions["broken"] = dataclasses.replace(
        library.states.get("broken"), contributed_tags=("state.broken",)
    )

    # -- weaknesses and multipliers (any number; nothing is fixed by the engine) ------------------
    db.interaction_rules.clear()
    for kind in WEAPONS:
        db.interaction_rules[f"weak_{kind}"] = InteractionRule(
            f"weak_{kind}",
            source_tags_all=(f"weapon.{kind}",),
            target_tags_all=(f"weak.{kind}",),
            multiplier=1.3,
            outcome_tags=("outcome.weak",),
            priority=10,
        )
    for element in ELEMENTS:
        db.interaction_rules[f"weak_{element}"] = InteractionRule(
            f"weak_{element}",
            source_tags_all=(f"damage.{element}",),
            target_tags_all=(f"weak.{element}",),
            multiplier=1.3,
            outcome_tags=("outcome.weak",),
            priority=10,
        )
    for kind in (*WEAPONS, *ELEMENTS):  # resistances: half damage, no shield lost
        source = f"weapon.{kind}" if kind in WEAPONS else f"damage.{kind}"
        db.interaction_rules[f"resist_{kind}"] = InteractionRule(
            f"resist_{kind}",
            source_tags_all=(source,),
            target_tags_all=(f"resist.{kind}",),
            multiplier=0.5,
        )
    db.interaction_rules["absorb_fire"] = InteractionRule(  # fire heals what carries absorb.fire
        "absorb_fire",
        source_tags_all=("damage.fire",),
        target_tags_all=("absorb.fire",),
        disposition="absorb",
        priority=20,
    )
    db.interaction_rules["reflect_magic"] = InteractionRule(  # spells bounce back to the caster
        "reflect_magic",
        source_tags_all=("magic",),
        target_tags_all=("reflect.magic",),
        disposition="reflect",
        priority=20,
    )
    db.interaction_rules["broken"] = InteractionRule(
        "broken", target_tags_all=("state.broken",), multiplier=2.0
    )
    for level, factor in (
        (1, 2.0),
        (2, 3.0),
        (3, 4.0),
    ):  # spells: one stronger cast per boost level
        db.interaction_rules[f"boost_power_{level}"] = InteractionRule(
            f"boost_power_{level}",
            source_tags_all=(f"boost.{level}", "boost.power"),
            multiplier=factor,
        )

    # -- statuses ---------------------------------------------------------------------------------
    states = library.states._definitions
    states["poison"] = StateDefinition(
        "poison",
        4,
        periodic=(
            PeriodicEffect(1, Effect("poison.tick", (op(-180),)), growth=1.0),
        ),  # 180, 360, 540...
        contributed_tags=("status.poison",),
    )
    states["sleep"] = StateDefinition("sleep", 2, contributed_tags=("status.sleep",))
    states["silence"] = StateDefinition("silence", 3, contributed_tags=("status.silence",))
    states["attack_up"] = StateDefinition(
        "attack_up",
        3,
        modifiers=(
            StatModifier("attack_up", "power", "multiply", 1.5),
            StatModifier("attack_up.magic", "magic", "multiply", 1.5),
        ),
    )
    states["defense_down"] = StateDefinition(
        "defense_down", 3, modifiers=(StatModifier("defense_down", "defense", "multiply", 0.5),)
    )
    for policy in (
        BattleStatePolicy(
            "poison", tick_trigger="rpg.battle.turn_ended", immune_target_tags=("immune.poison",)
        ),
        BattleStatePolicy(
            "sleep",
            base_chance=0.8,
            prevent_action=True,
            tick_trigger="rpg.battle.turn_ready",
            immune_target_tags=("immune.sleep",),
        ),
        BattleStatePolicy(
            "silence",
            base_chance=0.9,
            blocked_ability_tags=("magic",),
            tick_trigger="rpg.battle.turn_ended",
        ),
        BattleStatePolicy("attack_up", tick_trigger="rpg.battle.turn_ended"),
        BattleStatePolicy("defense_down", tick_trigger="rpg.battle.turn_ended"),
    ):
        db.battle_state_policies[policy.state_id] = policy

    # -- weapons: what is carried (equip.*) and its basic attack (weapon.*) -----------------------
    weapon_names = {
        "sword": "Iron Sword",
        "spear": "Steel Spear",
        "dagger": "Stiletto",
        "axe": "Hand Axe",
        "bow": "Hunter's Bow",
        "staff": "Oak Staff",
    }
    base_weapon = db.equipment["weapon_01"]
    for kind, name in weapon_names.items():
        attack = add(
            ability(
                f"attack_{kind}",
                tags=(f"weapon.{kind}", "boost.repeat"),
                effect=op(damage("power", 18)),
            ),
            "enemy",
        )
        db.equipment[f"w_{kind}"] = dataclasses.replace(
            base_weapon,
            equipment_id=f"w_{kind}",
            display_name=name,
            tags=("weapon", f"equip.{kind}"),
            granted_abilities=(attack,),
            sockets=(),
            growth_id=None,
            icon_id=base_weapon.icon_id,
        )

    # -- jobs and their skills --------------------------------------------------------------------
    two_weapons = ConditionGroup(
        (TagCondition("source", "equip.sword"), TagCondition("source", "equip.spear"))
    )
    jobs = {
        "warrior": [
            add(
                ability(
                    "level_slash",
                    tags=("weapon.sword",),
                    effect=op(damage("power", 14)),
                    sp=6,
                    mode="selected",
                    targets=6,
                ),
                "enemies",
            ),
            add(
                ability(
                    "thousand_spears",
                    tags=("weapon.spear",),
                    effect=op(damage("power", 9)),
                    sp=12,
                    hits=[{"tags": ["weapon.spear"]}] * 4,
                ),
                "enemy",
            ),
            add(
                ability(
                    "abide", effect=None, sp=5, apply_states=[{"state": "attack_up", "to": "self"}]
                ),
                "self",
            ),
            add(
                ability(
                    "twin_fang",
                    effect=op(damage("power", 16)),
                    sp=10,
                    conditions=two_weapons,
                    hits=[{"tags": ["weapon.sword"]}, {"tags": ["weapon.spear"]}],
                ),
                "enemy",
            ),
            add(
                ability(
                    "brand_of_valor",
                    tags=("divine",),
                    effect=op(damage("power", 22)),
                    battle_costs={BP: 3},
                    hits=[
                        {"tags": ["weapon.sword"]},
                        {"tags": ["weapon.spear"]},
                        {"tags": ["weapon.sword"]},
                        {"tags": ["weapon.spear"]},
                        {"tags": ["damage.lightning"], "power": 1.5},
                    ],
                ),
                "enemy",
            ),
        ],
        "merchant": [
            add(
                ability(
                    "donate_bp",
                    sp=4,
                    battle_resource_gains=[{"to": "targets", "resource": BP, "amount": 1}],
                    allies=True,
                ),
                "ally",
            ),
            add(
                ability("collect", tags=("weapon.spear",), effect=op(damage("power", 15)), sp=3),
                "enemy",
            ),
        ],
        "hunter": [
            add(
                ability(
                    "rain_of_arrows",
                    tags=("weapon.bow",),
                    effect=op(damage("power", 11)),
                    sp=8,
                    targets=6,
                ),
                "enemies",
            ),
            add(
                ability(
                    "true_strike", tags=("weapon.bow",), effect=op(damage("power", 28)), sp=10
                ),
                "enemy",
            ),
            add(
                ability(
                    "call_frost_lynx",
                    sp=10,
                    commands=[
                        {
                            "command": "SUMMON",
                            "args": {"actor_id": "hero_07", "owner_id": "@actor"},
                        }
                    ],
                ),
                "self",
            ),
            add(
                ability(
                    "arrowstorm",
                    tags=("divine",),
                    effect=op(damage("power", 14)),
                    battle_costs={BP: 3},
                    hits=[{"tags": ["weapon.bow"]}] * 5 + [{"tags": ["damage.ice"], "power": 1.5}],
                ),
                "enemy",
            ),
        ],
        "thief": [
            add(
                ability(
                    "venom_strike",
                    tags=("weapon.dagger",),
                    effect=op(damage("power", 12)),
                    sp=6,
                    apply_states=[{"state": "poison"}],
                ),
                "enemy",
            ),
            add(
                ability(
                    "armor_corrosive",
                    tags=("weapon.dagger",),
                    effect=op(damage("power", 8)),
                    sp=7,
                    apply_states=[{"state": "defense_down"}],
                ),
                "enemy",
            ),
        ],
        "apothecary": [
            add(ability("concoct", concoct_station="concoct"), "self"),
            add(
                ability(
                    "amputation",
                    tags=("weapon.axe",),
                    effect=op(damage("power", 12)),
                    sp=8,
                    hits=[{"tags": ["weapon.axe"]}, {"tags": ["weapon.axe"]}],
                ),
                "enemy",
            ),
            add(ability("first_aid", effect=op(healing(28)), sp=5, allies=True), "ally"),
            add(
                ability(
                    "last_stand",
                    tags=("divine",),
                    effect=op(healing(40)),
                    battle_costs={BP: 3},
                    targets=6,
                    allies=True,
                    apply_states=[{"state": "attack_up", "to": "allies"}],
                ),
                "allies",
            ),
        ],
        "cleric": [
            add(
                ability(
                    "heal_wounds",
                    tags=("magic",),
                    effect=op(healing(18)),
                    sp=10,
                    targets=6,
                    allies=True,
                ),
                "allies",
            ),
            add(
                ability(
                    "holy_light",
                    tags=("magic", "damage.light", "boost.power"),
                    effect=op(damage("magic", 24)),
                    sp=8,
                ),
                "enemy",
            ),
            add(
                ability(
                    "cleanse",
                    tags=("magic",),
                    sp=6,
                    allies=True,
                    apply_states=[
                        {"state": s, "remove": True} for s in ("poison", "sleep", "silence")
                    ],
                ),
                "ally",
            ),
        ],
        "scholar": [
            add(
                ability(
                    "fireball",
                    tags=("magic", "damage.fire", "boost.power"),
                    effect=op(damage("magic", 16)),
                    sp=10,
                    targets=6,
                ),
                "enemies",
            ),
            add(
                ability(
                    "icewind",
                    tags=("magic", "damage.ice", "boost.power"),
                    effect=op(damage("magic", 16)),
                    sp=10,
                    targets=6,
                ),
                "enemies",
            ),
            add(
                ability(
                    "lightning_bolt",
                    tags=("magic", "damage.lightning", "boost.power"),
                    effect=op(damage("magic", 30)),
                    sp=10,
                ),
                "enemy",
            ),
            add(
                ability(
                    "elemental_barrage",
                    tags=("magic", "boost.power"),
                    effect=op(damage("magic", 13)),
                    sp=16,
                    hits=[
                        {"tags": ["damage.fire"]},
                        {"tags": ["damage.ice"]},
                        {"tags": ["damage.lightning"]},
                    ],
                ),
                "enemy",
            ),
            add(
                ability(
                    "elemental_storm",
                    tags=("magic", "divine"),
                    effect=op(damage("magic", 15)),
                    battle_costs={BP: 3},
                    targets=6,
                    hits=[
                        {"tags": ["damage.fire"]},
                        {"tags": ["damage.ice"]},
                        {"tags": ["damage.lightning"]},
                    ],
                ),
                "enemies",
            ),
        ],
        "dancer": [
            add(
                ability(
                    "peacock_strut",
                    sp=8,
                    targets=6,
                    allies=True,
                    apply_states=[{"state": "attack_up", "to": "allies"}],
                ),
                "allies",
            ),
            add(
                ability("sleepy_waltz", tags=("magic",), sp=9, apply_states=[{"state": "sleep"}]),
                "enemy",
            ),
        ],
        "beast": [
            add(
                ability(
                    "lynx_pounce",
                    tags=("weapon.dagger", "damage.ice"),
                    effect=op(damage("power", 20)),
                ),
                "enemy",
            ),
        ],
    }
    base_class = db.classes["warden"]
    db.classes.clear()
    for job, granted in jobs.items():
        db.classes[job] = dataclasses.replace(
            base_class,
            class_id=job,
            display_name=job.title(),
            granted_tags=(f"job.{job}",),
            granted_abilities=tuple(granted),
        )

    # -- concoct: ingredients picked in battle make an item that acts at once ---------------------
    db.composition_recipes.clear()
    concoctions = {
        "healing_salve": ("Healing Salve", ("healing_herb", "healing_herb"), "salve_heal", "ally"),
        "fire_bomb": ("Fire Bomb", ("healing_herb", "fire_dust"), "bomb_fire", "enemies"),
        "frost_bomb": ("Frost Bomb", ("healing_herb", "ice_crystal"), "bomb_ice", "enemies"),
        "storm_flask": ("Storm Flask", ("fire_dust", "ice_crystal"), "flask_storm", "enemy"),
    }
    product_abilities = {
        "salve_heal": ability("salve_heal", effect=op(healing(45)), allies=True),
        "bomb_fire": ability(
            "bomb_fire", tags=("damage.fire",), effect=op(damage("magic", 12)), targets=6
        ),
        "bomb_ice": ability(
            "bomb_ice", tags=("damage.ice",), effect=op(damage("magic", 12)), targets=6
        ),
        "flask_storm": ability(
            "flask_storm",
            tags=("damage.lightning",),
            effect=op(damage("magic", 30)),
            apply_states=[{"state": "defense_down"}],
        ),
    }
    for recipe_id, (name, (base, catalyst), ability_id, targeting) in concoctions.items():
        add(product_abilities[ability_id], targeting)
        db.items[recipe_id] = ItemDefinition(
            recipe_id, name, tags=("concoction",), battle_ability=ability_id
        )
        db.composition_recipes[recipe_id] = CompositionRecipeDefinition(
            recipe_id,
            name,
            station="concoct",
            selections=(
                CompositionSelection("base", (base,)),
                CompositionSelection("catalyst", (catalyst,)),
            ),
            outputs=(CompositionOutput(recipe_id),),
        )

    # -- the travellers (main / secondary job, two weapon kinds) and the pet ----------------------
    travellers = {
        "hero_01": ("Garrick", "warrior", "merchant", ("sword", "spear")),
        "hero_02": ("Sera", "hunter", "thief", ("bow", "dagger")),
        "hero_03": ("Bram", "apothecary", "cleric", ("axe", "staff")),
        "hero_04": ("Ione", "scholar", "dancer", ("staff", "dagger")),
        "hero_07": ("Frost Lynx", "beast", "beast", ()),
    }
    for actor_id, (name, main_job, sub_job, _weapons) in travellers.items():
        actor = db.actors[actor_id]
        assignments = list(actor.class_assignments)
        assignments[0] = dataclasses.replace(
            assignments[0], class_id=main_job, progression_track_ids=()
        )
        if len(assignments) > 1:
            assignments[1] = dataclasses.replace(
                assignments[1], class_id=sub_job, progression_track_ids=()
            )
        db.actors[actor_id] = dataclasses.replace(
            actor, display_name=name, class_assignments=tuple(assignments)
        )

    # only the demo's skills: no skill trees, passives or evolutions of the reference game, no old
    # equipment
    db.progression_graphs.clear()
    db.progression_tracks.clear()  # the reference game's level-up skills
    db.passives.clear()
    db.ability_evolutions.clear()
    for equipment_id in [k for k in db.equipment if not k.startswith("w_")]:
        del db.equipment[equipment_id]
    db.equipment_sets.clear()
    db.equipment_growth.clear()
    db.attachments.clear()
    for actor_id, actor in list(db.actors.items()):
        db.actors[actor_id] = dataclasses.replace(actor, abilities=())
    for actor_id in list(db.actors):  # the demo party only
        if actor_id not in travellers:
            del db.actors[actor_id]
    party = db.party_setups["main_party"]
    actives = ("hero_01", "hero_02", "hero_03", "hero_04")
    db.party_setups["main_party"] = dataclasses.replace(
        party,
        roster_actor_ids=(*actives, "hero_07"),
        active_actor_ids=actives,
        placements=tuple(p for p in party.placements if p.actor_id in actives),
    )

    # -- enemies: shields and weaknesses per enemy, and what they do ------------------------------
    enemy_abilities = {
        "boss_cleave": add(
            ability("boss_cleave", tags=("weapon.axe",), effect=op(damage("power", 15))), "enemy"
        ),
        "boss_roar": add(
            ability(
                "boss_roar",
                effect=op(damage("power", 6)),
                targets=6,
                apply_states=[{"state": "silence"}],
            ),
            "enemies",
        ),
        "boss_nova": add(
            ability("boss_nova", tags=("damage.fire",), effect=op(damage("power", 12)), targets=6),
            "enemies",
        ),
        "meteor": add(
            ability(
                "meteor",
                tags=("damage.fire",),
                effect=op(damage("power", 20)),
                apply_states=[{"state": "poison"}],
            ),
            "enemy",
        ),
        "summon_wisp": add(
            ability(
                "summon_wisp",
                commands=[
                    {
                        "command": "SUMMON",
                        "args": {"enemy_id": "mender_wisp", "owner_id": "@actor"},
                    }
                ],
            ),
            "self",
        ),
        "sleep_spores": add(
            ability(
                "sleep_spores", effect=op(damage("power", 3)), apply_states=[{"state": "sleep"}]
            ),
            "enemy",
        ),
        "add_mend": add(ability("add_mend", effect=op(healing(25)), allies=True), "ally"),
        "venom_bite": add(
            ability(
                "venom_bite", effect=op(damage("power", 9)), apply_states=[{"state": "poison"}]
            ),
            "enemy",
        ),
        "add_bite": add(ability("add_bite", effect=op(damage("power", 12))), "enemy"),
    }
    foes = {
        "astral_tyrant": (
            "Grimgarde",
            26000,
            6,
            ("sword", "axe", "ice", "lightning"),
            ("boss_cleave", "boss_roar", "boss_nova", "summon_wisp", "meteor"),
        ),
        "mender_wisp": (
            "Sporecap",
            3800,
            3,
            ("axe", "staff", "fire"),
            ("sleep_spores", "add_mend"),
        ),
        "ember_hound": (
            "Venom Hound",
            4600,
            4,
            ("spear", "bow", "ice", "light"),
            ("venom_bite", "add_bite"),
        ),
    }
    for enemy_id, (name, hp, shields, weak, skills) in foes.items():
        enemy = db.enemies[enemy_id]
        resources = dict(enemy.resources)
        resources.update({HP: hp, SHIELD: shields})
        tags = tuple(t for t in enemy.tags if not t.startswith("weak.")) + tuple(
            f"weak.{w}" for w in weak
        )
        db.enemies[enemy_id] = EnemyDefinition(
            enemy_id,
            name,
            stats=dict(enemy.stats),
            resources=resources,
            tags=tags,
            abilities=tuple(enemy_abilities[s] for s in skills),
            reward=dataclasses.replace(enemy.reward, experience={})
            if enemy.reward is not None
            else None,
        )
    for enemy_id, enemy in list(db.enemies.items()):
        if enemy_id not in foes and enemy.reward is not None:
            db.enemies[enemy_id] = dataclasses.replace(
                enemy, reward=dataclasses.replace(enemy.reward, experience={})
            )
    db.encounters["boss_room"] = dataclasses.replace(
        db.encounters["boss_room"],
        members=(
            dataclasses.replace(
                db.encounters["boss_room"].members[0], enemy_id="astral_tyrant", count=1
            ),
            dataclasses.replace(
                db.encounters["boss_room"].members[0], enemy_id="mender_wisp", count=1
            ),
            dataclasses.replace(
                db.encounters["boss_room"].members[0], enemy_id="ember_hound", count=1
            ),
        ),
    )

    # -- more kinds of enemy: each fights differently (all of it data) ----------------------------
    add_monster_types(project, db, add)

    # -- drop the reference game's skills nothing here uses (the Database stays readable) ---------
    used = {a for job in db.classes.values() for a in job.granted_abilities}
    used |= {a for weapon in db.equipment.values() for a in weapon.granted_abilities}
    used |= {a for enemy in db.enemies.values() for a in enemy.abilities}
    used |= {item.battle_ability for item in db.items.values() if item.battle_ability}
    for ai in db.enemy_ai.values():
        used |= {r.payload.get("ability_id") for r in ai.rules if r.payload.get("ability_id")}
    for ability_id in list(abilities.ids()):
        if ability_id not in used:
            del abilities._definitions[ability_id]
            db.battle_targeting.pop(ability_id, None)
            db.action_timings.pop(ability_id, None)

    # -- what the battle shows: sequences for the new skills, particle bursts for divine skills ---
    sequences = project.battle_presentation_library
    burst = particle_effect_asset(
        preset("explosion", "fx.divine_burst").replace(burst=120, color_start=(255, 245, 190, 255))
    )
    sparkle = particle_effect_asset(preset("heal", "fx.restore"))
    aura = particle_effect_asset(
        preset("sparkle", "fx.boss_aura").replace(color_start=(255, 120, 200, 255), rate=24)
    )
    for asset in (burst, sparkle, aura):
        project.assets.register(asset, replace=True)
    looks = {"strike": [], "fire_arc": [], "heal": [], "meteor": []}
    for ability_id in abilities.ids():
        definition = abilities.get(ability_id)
        if "divine" in definition.tags:
            looks["meteor"].append(ability_id)
        elif any(t.startswith("damage.") for t in definition.tags) and "magic" in definition.tags:
            looks["fire_arc"].append(ability_id)
        elif definition.effects and not any(
            o.value is not None and str(getattr(o.value, "terms", "")).find("-") >= 0
            for e in definition.effects
            for o in e.effect.operations
        ):
            looks["heal"].append(ability_id)
        else:
            looks["strike"].append(ability_id)
    for source, ability_ids in looks.items():
        base = sequences.require("motion_sequences", source)
        for ability_id in ability_ids:
            beats = base.beats
            if source == "meteor":
                beats = tuple(
                    dataclasses.replace(b, cue="fx.divine_burst") if b.channel == "vfx" else b
                    for b in beats
                )
            if source == "heal":
                beats = tuple(
                    dataclasses.replace(b, cue="fx.restore") if b.channel == "vfx" else b
                    for b in beats
                )
            sequences.set(
                "motion_sequences",
                ability_id,
                dataclasses.replace(base, sequence_id=ability_id, beats=beats)
                if hasattr(base, "sequence_id")
                else dataclasses.replace(base, beats=beats),
            )

    # both sides stand nearer their edges: the command menu fits on the heroes' side, enemies stay
    # visible
    layout = sequences.require("ui_layout", "adaptive")
    sequences.set("ui_layout", "adaptive", dataclasses.replace(layout, stage_front=0.2))

    from asteria.runtime.environment2d import ParticleEmitter2DComponent

    scene = project.scene(project.startup_scene_id)
    boss = next(e for e in scene.entities() if e.name == "Astral Tyrant")
    boss.name = "Grimgarde"
    emitter = boss.try_get(ParticleEmitter2DComponent) or boss.add_component(
        ParticleEmitter2DComponent()
    )
    emitter.effect_id, emitter.offset_y = "fx.boss_aura", -30.0

    # -- the starting party, jobs, two weapons each and the bag (in the game start), then write the
    from asteria.runtime.game_start import GameStartDefinition

    data = project.game_start.to_data()
    rpg = data["rpg_state"]
    rpg["party_active_actor_ids"] = list(actives)
    rpg["party_actor_ids"] = [*actives, "hero_07"]
    placements = rpg.get("party_placements", {})
    rpg["party_placements"] = (
        {k: v for k, v in placements.items() if k in actives}
        if isinstance(placements, dict)
        else [p for p in placements if p.get("actor_id") in actives]
    )
    rpg["progression_allocations"] = {}
    rpg["progression"]["totals"] = {}
    rpg["actor_snapshots"] = {}  # rebuilt from the actors, jobs and weapons when play starts
    for key in ("actor_progression", "loadouts"):
        if isinstance(rpg.get(key), dict):
            rpg[key] = {k: v for k, v in rpg[key].items() if k in travellers}
    for actor_id, (_name, main_job, sub_job, weapons) in travellers.items():
        progress = rpg["actor_progression"].get(actor_id)
        if progress is not None:
            progress["active_class_ids"] = (
                [main_job] if main_job == sub_job else [main_job, sub_job]
            )
            progress["unlocked_class_ids"] = list(dict.fromkeys(progress["active_class_ids"]))
        loadout = rpg["loadouts"].get(actor_id)
        if loadout is None:
            continue
        for slot in loadout["slots"]:
            if slot["slot_id"] == "weapon":
                slot["capacity"] = 2
        loadout["equipped"]["weapon"] = [
            {
                "attachments": {},
                "equipment_id": f"w_{kind}",
                "growth": None,
                "instance_id": f"w_{kind}:{actor_id}",
                "schema": "asteria.rpg.equipment_instance",
                "version": 2,
            }
            for kind in weapons
        ]
        loadout["equipped"]["accessory"] = []
    rpg["inventory"]["counts"] = {
        "healing_herb": 6,
        "fire_dust": 4,
        "ice_crystal": 4,
        "ether_leaf": 3,
    }
    project.game_start = GameStartDefinition.from_data(data)
    path = HERE / "project.asteria.json"
    project.save_json(path)
    Project.load_json(path, registry)  # it must load back

    # -- assets and the playable manifest ---------------------------------------------------------
    manifest = json.loads((REFERENCE / "playable_test_manifest.json").read_text(encoding="utf-8"))
    manifest["title"] = "Octopath-style Battle Demo"
    sprites = manifest["field"]["entity_sprites"]
    sprites["Grimgarde"] = sprites.pop(
        "Astral Tyrant", {"sprite": "playable_assets/boss_field.png", "size": [96, 96]}
    )
    for name, (_enemy, _encounter, _xy, _behaviour) in FIELD_FOES.items():
        wide = MONSTERS[_enemy][1].startswith("Boss/")
        sprites[name] = {
            "sprite": f"playable_assets/field_{_enemy}.png",
            "size": [64, 32] if wide else [48, 48],
        }
    names = {f"attack_{k}": f"Attack ({v})" for k, v in weapon_names.items()}
    order = [f"attack_{k}" for k in WEAPONS] + [a for job in jobs.values() for a in job]
    labels = {}
    for (
        ability_id
    ) in order:  # basic attacks first (keys 1-2), then the job skills; divine skills marked
        name = names.get(ability_id) or ability_id.replace("_", " ").title()
        if "divine" in abilities.get(ability_id).tags:
            name += " (Divine)"
        labels[ability_id] = {"label": name}
    manifest["battle"]["skills"] = labels
    (HERE / "playable_test_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {path.relative_to(REPO)}: {len(abilities.ids())} abilities, {len(db.classes)} "
        f"jobs, "
        f"{len(db.enemies)} enemies, {len(db.composition_recipes)} concoctions"
    )


# -- more enemy types -----------------------------------------------------------------------------
NINJA = (
    REPO
    / "local_reference"
    / "free_assets"
    / "ninja_adventure"
    / "extracted"
    / "Ninja Adventure - Asset Pack"
    / "Actor"
)
MONSTERS = {  # enemy id: (name, art, hp, shields, tags, skills, speed)
    "gel_slime": (
        "Gel Slime",
        "Monster/Slime/Slime.png",
        2400,
        2,
        ("weak.lightning", "weak.staff", "weak.dagger", "absorb.fire", "resist.sword"),
        ("gel_slam", "split"),
        40,
    ),
    "bone_wraith": (
        "Bone Wraith",
        "Monster/Skull/SpriteSheet.png",
        3600,
        4,
        ("weak.light", "weak.axe", "weak.fire", "resist.dagger", "immune.poison", "undead"),
        ("grave_chill", "life_drain"),
        55,
    ),
    "pit_viper": (
        "Pit Viper",
        "Monster/Snake/Snake.png",
        2200,
        3,
        ("weak.sword", "weak.bow", "weak.ice"),
        ("venom_fang", "constrict"),
        95,
    ),
    "mirror_gazer": (
        "Mirror Gazer",
        "Monster/Eye/Eye.png",
        3000,
        3,
        ("weak.dagger", "weak.spear", "weak.bow", "reflect.magic", "immune.sleep"),
        ("hypno_gaze", "eye_beam"),
        60,
    ),
    "web_spinner": (
        "Web Spinner",
        "Monster/SpiderRed/SpriteSheet.png",
        2800,
        3,
        ("weak.fire", "weak.axe", "resist.ice"),
        ("sticky_web", "spider_bite"),
        70,
    ),
    "iron_samurai": (
        "Iron Samurai",
        "Boss/GiantBlueSamurai",
        14000,
        8,
        (
            "weak.spear",
            "weak.lightning",
            "weak.dagger",
            "resist.sword",
            "resist.axe",
            "resist.bow",
            "immune.sleep",
            "boss",
        ),
        ("iai_slash", "war_cry", "whirlwind"),
        65,
    ),
}
ENCOUNTERS = {  # encounter id: enemy ids
    "slime_pit": ("gel_slime", "gel_slime", "web_spinner"),
    "old_crypt": ("bone_wraith", "iron_guard"),
    "gazer_nest": ("mirror_gazer", "pit_viper", "pit_viper"),
    "samurai_duel": ("iron_samurai", "bone_wraith"),
}
FIELD_FOES = {  # field entity: (enemy art shown, encounter, position, behaviour)
    "Gel Slime": ("gel_slime", "slime_pit", (-110.0, -40.0), "wander"),
    "Bone Wraith": ("bone_wraith", "old_crypt", (-110.0, 45.0), "wander"),
    "Mirror Gazer": ("mirror_gazer", "gazer_nest", (110.0, -50.0), "idle"),
    "Iron Samurai": ("iron_samurai", "samurai_duel", (120.0, 22.0), "idle"),
}


def _strip(frames, scale):
    from PIL import Image

    w, h = frames[0].size
    sheet = Image.new("RGBA", (w * scale * len(frames), h * scale), (0, 0, 0, 0))
    for i, frame in enumerate(frames):
        sheet.alpha_composite(
            frame.resize((w * scale, h * scale), Image.NEAREST), (i * w * scale, 0)
        )
    return sheet


def _flash(frame):
    from PIL import Image

    white = Image.new("RGBA", frame.size, (255, 255, 255, 255))
    out = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    out.paste(white, (0, 0), frame.getchannel("A"))
    return out


def _darken(frame):
    from PIL import ImageEnhance

    return ImageEnhance.Brightness(frame).enhance(0.35)


def monster_sheet(relative):
    """Battle sheet from a 4 x 4 walk sheet (16 px): idle / attack from the walk, a flash for hit,
    dark for KO."""
    from PIL import Image

    sheet = Image.open(NINJA / relative).convert("RGBA")
    walk = [sheet.crop((48, r * 16, 64, r * 16 + 16)) for r in range(4)]  # the right-facing column
    frames = walk + [_flash(walk[0]), _darken(walk[0])]
    clips = {
        "idle": {"frames": [0, 1, 2, 3], "frame_duration": 0.16, "loop": True},
        "attack": {
            "frames": [0, 1, 2, 3, 0],
            "frame_duration": 0.07,
            "loop": False,
            "events": {"2": ["hit"]},
        },
        "hit": {"frames": [4, 0, 4, 0], "frame_duration": 0.07, "loop": False},
        "ko": {"frames": [5], "frame_duration": 0.5, "loop": False},
    }
    return _strip(frames, 4), (64, 64), clips, walk[0]


def giant_sheet(relative, cell=(96, 48)):
    """Battle sheet from a boss's Idle / Hit strips (each frame ``cell`` px): idle, attack, hit, a
    dark KO frame."""
    from PIL import Image

    base = NINJA / relative
    w, h = cell
    idle = Image.open(base / "Idle.png").convert("RGBA")
    hit = Image.open(base / "Hit.png").convert("RGBA")
    frames = [idle.crop((c * w, 0, c * w + w, h)) for c in range(idle.width // w)]
    count = len(frames)
    frames += [hit.crop((c * w, 0, c * w + w, h)) for c in range(min(3, hit.width // w))]
    frames.append(_darken(frames[-1]))
    n = len(frames)
    clips = {
        "idle": {"frames": list(range(count)), "frame_duration": 0.14, "loop": True},
        "attack": {
            "frames": [0, 2, 4, 4, 2, 0],
            "frame_duration": 0.07,
            "loop": False,
            "events": {"2": ["hit"]},
        },
        "hit": {"frames": list(range(count, n - 1)), "frame_duration": 0.09, "loop": False},
        "ko": {"frames": [n - 1], "frame_duration": 0.5, "loop": False},
    }
    return _strip(frames, 2), (w * 2, h * 2), clips, frames[0]


def add_monster_types(project, db, add):
    """Six new kinds of enemy - each a different problem to solve - with art, AI, encounters and
    field spots."""
    from asteria.assets.canonical import AssetSource, CanonicalAsset
    from asteria.core import Entity, Transform
    from asteria.presentation.battle_combatant_visuals import (
        BattleCombatantVisualProfile,
        BattleVisualAssetSet,
        BattleVisualStateDefinition,
        BattleVisualTransform,
    )
    from asteria.rpg.enemy_ai import EnemyAIDefinition
    from asteria.rpg.enemy_behavior import EnemyBehaviorBinding
    from asteria.runtime.field_ai import FieldAIComponent, VisibleEncounterComponent

    weak, multi = damage, ability
    skills = {
        # Gel Slime: fire heals it (absorb); it splits into another slime
        "gel_slam": (multi("gel_slam", effect=op(weak("power", 11))), "enemy", "first_opponent"),
        "split": (
            multi(
                "split",
                commands=[
                    {"command": "SUMMON", "args": {"enemy_id": "gel_slime", "owner_id": "@actor"}}
                ],
            ),
            "self",
            "self",
        ),
        # Bone Wraith: undead - immune to poison; drains life, chills and silences
        "grave_chill": (
            multi(
                "grave_chill",
                tags=("damage.ice",),
                effect=op(weak("power", 8)),
                targets=6,
                apply_states=[{"state": "silence"}],
            ),
            "enemies",
            "all_opponents",
        ),
        "life_drain": (
            multi("life_drain", effect=op(weak("power", 14)), battle_resource_gains=[]),
            "enemy",
            "random_opponent",
        ),
        # Pit Viper: very fast; poison and armour-breaking coils
        "venom_fang": (
            multi("venom_fang", effect=op(weak("power", 9)), apply_states=[{"state": "poison"}]),
            "enemy",
            "random_opponent",
        ),
        "constrict": (
            multi(
                "constrict",
                effect=op(weak("power", 7)),
                apply_states=[{"state": "defense_down"}],
                hits=[{"tags": []}, {"tags": []}],
            ),
            "enemy",
            "first_opponent",
        ),
        # Mirror Gazer: spells bounce back (reflect); it puts the whole party to sleep
        "hypno_gaze": (
            multi("hypno_gaze", tags=("magic",), targets=6, apply_states=[{"state": "sleep"}]),
            "enemies",
            "all_opponents",
        ),
        "eye_beam": (
            multi("eye_beam", tags=("magic", "damage.lightning"), effect=op(weak("magic", 16))),
            "enemy",
            "random_opponent",
        ),
        # Web Spinner: weakens defences, fast bites
        "sticky_web": (
            multi("sticky_web", targets=6, apply_states=[{"state": "defense_down"}]),
            "enemies",
            "all_opponents",
        ),
        "spider_bite": (
            multi("spider_bite", effect=op(weak("power", 6)), hits=[{"tags": []}] * 3),
            "enemy",
            "random_opponent",
        ),
        # Iron Samurai: armoured mid-boss with many shields; resists most weapons
        "iai_slash": (
            multi("iai_slash", tags=("weapon.sword",), effect=op(weak("power", 24))),
            "enemy",
            "random_opponent",
        ),
        "war_cry": (
            multi("war_cry", apply_states=[{"state": "attack_up", "to": "self"}]),
            "self",
            "self",
        ),
        "whirlwind": (
            multi(
                "whirlwind",
                tags=("weapon.sword",),
                effect=op(weak("power", 9)),
                targets=6,
                hits=[{"tags": []}, {"tags": []}],
            ),
            "enemies",
            "all_opponents",
        ),
    }
    life = skills["life_drain"][0]
    skills["life_drain"] = (
        AbilityDefinition(
            "life_drain",
            targeting=life.targeting,
            tags=life.tags,
            effects=(
                *life.effects,
                AbilityEffect("self", Effect("life_drain.heal", (op(healing(10)),))),
            ),
        ),
        "enemy",
        "random_opponent",
    )
    for ability_id, (definition, targeting, _selector) in skills.items():
        add(definition, targeting)

    library = project.battle_presentation_library
    states = tuple(
        BattleVisualStateDefinition(role, role) for role in ("idle", "attack", "hit", "ko")
    )
    out = HERE / "playable_assets" / "battle"
    out.mkdir(parents=True, exist_ok=True)
    template_enemy = db.enemies["ember_hound"]
    for enemy_id, (name, art, hp, shields, tags, moves, speed) in MONSTERS.items():
        image, frame, clips, field_frame = (
            giant_sheet(art) if art.startswith("Boss/") else monster_sheet(art)
        )
        image.save(out / f"{enemy_id}.png")
        side = 48 / max(field_frame.size)
        field_frame.resize(
            (round(field_frame.width * side), round(field_frame.height * side)), 0
        ).save(HERE / "playable_assets" / f"field_{enemy_id}.png")
        asset_id = f"battle.combatant.{enemy_id}"
        project.assets.register(
            CanonicalAsset(
                asset_id,
                "sprite_sheet",
                AssetSource(
                    f"playable_assets/battle/{enemy_id}.png",
                    "project",
                    (("license", "CC0 1.0"), ("source", "Ninja Adventure Asset Pack")),
                ),
                tags=frozenset({"battle", "combatant", "enemy"}),
                metadata=(("clips", clips), ("frame_size", list(frame)), ("pivot", [0.5, 1.0])),
            ),
            replace=True,
        )
        scale = 0.8 if art.startswith("Boss/") else 0.5
        library.set(
            "combatant_visuals",
            enemy_id,
            BattleCombatantVisualProfile(
                enemy_id,
                BattleVisualAssetSet(asset_id),
                states,
                BattleVisualTransform(scale_x=scale, scale_y=scale),
            ),
        )
        stats = dict(template_enemy.stats)
        stats["speed"] = float(speed)
        db.enemies[enemy_id] = EnemyDefinition(
            enemy_id,
            name,
            stats=stats,
            resources={HP: hp, SHIELD: shields, SP: 999},
            tags=("enemy", *tags),
            abilities=moves,
            reward=dataclasses.replace(template_enemy.reward, experience={})
            if template_enemy.reward
            else None,
        )
        rules = []
        for move in moves:
            _definition, _targeting, selector = skills[move]
            rules.append(
                {
                    "schema": "asteria.rpg.ai_decision_rule",
                    "version": 1,
                    "rule_id": move,
                    "action_kind": "ability",
                    "payload": {"ability_id": move},
                    "target_selector": selector,
                    "conditions": [],
                    "priority": 1,
                    "weight": 1.0,
                    "tags": [],
                }
            )
        db.enemy_ai[f"{enemy_id}_ai"] = EnemyAIDefinition.from_data(
            {
                "schema": "asteria.rpg.enemy_ai_definition",
                "version": 1,
                "ai_id": f"{enemy_id}_ai",
                "rules": rules,
                "phases": [
                    {
                        "schema": "asteria.rpg.boss_phase_definition",
                        "version": 1,
                        "phase_id": "main",
                        "conditions": [],
                        "priority": 1,
                        "decision_rule_ids": list(moves),
                        "actions_per_ready": None,
                        "enter_hook": None,
                        "exit_hook": None,
                    }
                ],
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
    credits = HERE / "playable_assets" / "CREDITS.md"
    text = credits.read_text(encoding="utf-8")
    row = (
        "| `battle/gel_slime.png`, `bone_wraith.png`, `pit_viper.png`, `mirror_gazer.png`, "
        "`web_spinner.png`, "
        "`iron_samurai.png` and their `field_*.png` (Octopath demo enemies) | "
        "[Ninja Adventure Asset Pack](https://pixel-boy.itch.io/ninja-adventure-asset-pack) — "
        "Monster/Slime, "
        "Skull, Snake, Eye, SpiderRed, Boss/GiantBlueSamurai; frames cropped and scaled, hit / "
        "KO frames flashed / "
        "darkened (built by `reference_projects/octopath_demo/build_project.py`) | Pixel-boy, "
        "AAA | "
        "[CC0 1.0](http://creativecommons.org/publicdomain/zero/1.0/) |\n"
    )
    if "Octopath demo enemies" not in text:
        i = text.index("\n## Licensing")
        credits.write_text(text[:i].rstrip("\n") + "\n" + row + text[i:], encoding="utf-8")

    # the Skeleton Knight (the reference project's iron_guard art): armoured, slow, hits hard
    add(
        ability(
            "shield_bash",
            tags=("weapon.axe",),
            effect=op(damage("power", 16)),
            apply_states=[{"state": "defense_down"}],
        ),
        "enemy",
    )
    guard = db.enemies["iron_guard"]
    db.enemies["iron_guard"] = EnemyDefinition(
        "iron_guard",
        "Skeleton Knight",
        stats=dict(guard.stats),
        resources={HP: 4200, SHIELD: 5, SP: 999},
        tags=(
            "enemy",
            "undead",
            "immune.poison",
            "weak.light",
            "weak.staff",
            "weak.axe",
            "resist.dagger",
            "resist.bow",
        ),
        abilities=("shield_bash",),
        reward=dataclasses.replace(guard.reward, experience={}) if guard.reward else None,
    )

    base = db.encounters["boss_room"]
    for encounter_id, members in ENCOUNTERS.items():
        counts = {}
        for enemy_id in members:
            counts[enemy_id] = counts.get(enemy_id, 0) + 1
        db.encounters[encounter_id] = dataclasses.replace(
            base,
            encounter_id=encounter_id,
            tags=("demo",),
            members=tuple(
                dataclasses.replace(base.members[0], enemy_id=e, count=n)
                for e, n in counts.items()
            ),
        )

    scene = project.scene(project.startup_scene_id)
    for entity in [e for e in scene.entities() if e.name in FIELD_FOES]:
        scene.remove_entity(entity.id)
    for name, (_enemy, encounter_id, (x, y), behaviour) in FIELD_FOES.items():
        entity = scene.add_entity(Entity(name))
        entity.add_component(Transform(x, y))
        touch = entity.add_component(VisibleEncounterComponent())
        touch.encounter_id, touch.touch_radius = encounter_id, 14.0
        ai = entity.add_component(FieldAIComponent())
        ai.behaviour, ai.speed, ai.wander_radius = behaviour, 20.0, 24.0


if __name__ == "__main__":
    main()
