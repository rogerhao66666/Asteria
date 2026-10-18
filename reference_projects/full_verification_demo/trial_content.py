"""Game data of the Full Verification demo (rules, statuses, gear, jobs, trees, skills, boss)."""

from __future__ import annotations

import dataclasses
import json

from asteria.gameplay import (
    AbilityDefinition,
    Effect,
    EffectOperation,
    EffectOperationKind,
)
from asteria.gameplay.abilities import AbilityCost, AbilityEffect, TargetingRule
from asteria.gameplay.formulas import FormulaTerm, ValueFormula
from asteria.gameplay.modifiers import StatModifier
from asteria.gameplay.states import PeriodicEffect, StateDefinition
from asteria.rpg import BattleStatePolicy
from asteria.rpg.battle_resources import BattleResourceDefinition
from asteria.rpg.gauge_composition import (
    GaugeCompositionDefinition,
    GaugeImpactRule,
    GaugeThresholdRule,
)
from asteria.rpg.interactions import InteractionRule, OutcomeCheckDefinition

HP, SP, BP, SHIELD = "vitality", "technique", "bp", "shield"
WEAPONS = ("sword", "spear", "dagger", "axe", "bow", "staff")
ELEMENTS = ("fire", "ice", "lightning", "light", "dark")


ADVANCED_JOBS = ("weapon_master", "sage", "hero", "forgemaster", "rogue", "guardian")


class Context:
    """What the build steps share."""

    hero_id = "hero_01"
    boss_id = "crimson_warlord"

    def __init__(self, project, root):
        self.project = project
        self.root = root
        self.db = project.rpg_database
        self.library = project.gameplay_library
        self.abilities = project.gameplay_library.abilities
        self.template = {
            k: self.db.battle_targeting[k]
            for k in ("strike", "boss_roar", "heal", "party_barrier", "guard")
        }
        self.skill_names = {}

    def add(self, definition, targeting):
        """Register an ability and its battle targeting (enemy, enemies, ally, allies, self)."""
        self.abilities._definitions[definition.ability_id] = definition
        base = {
            "enemy": "strike",
            "enemies": "boss_roar",
            "ally": "heal",
            "allies": "party_barrier",
            "self": "guard",
        }[targeting]
        self.db.battle_targeting[definition.ability_id] = dataclasses.replace(
            self.template[base], ability_id=definition.ability_id
        )
        return definition.ability_id


# -- small builders -------------------------------------------------------------------------------
def damage(stat, coefficient, defense=6.0):
    """``coefficient`` x the user's ``stat`` minus ``defense`` x the target's defence (min 1)."""
    return ValueFormula(
        (
            FormulaTerm("source_stat", stat, -coefficient),
            FormulaTerm("target_stat", "defense", defense),
        ),
        maximum=-1.0,
    )


def healing(amount_per_magic, stat="magic"):
    return ValueFormula((FormulaTerm("source_stat", stat, amount_per_magic),), minimum=1.0)


def op(value, resource=HP):
    return EffectOperation(EffectOperationKind.RESOURCE_DELTA, resource, value)


def ability(
    ability_id, *, tags=(), effect=None, sp=0, mode="selected", targets=1, allies=False, **extra
):
    effects = (
        () if effect is None else (AbilityEffect(mode, Effect(f"{ability_id}.effect", (effect,))),)
    )
    costs = (AbilityCost(SP, sp),) if sp else ()
    rule = TargetingRule(minimum_targets=1, maximum_targets=targets, allow_self=allows(allies))
    return AbilityDefinition(
        ability_id, targeting=rule, costs=costs, effects=effects, tags=("ability", *tags), **extra
    )


def allows(flag):
    return bool(flag)


# -- steps ----------------------------------------------------------------------------------------
def strip_reference(c):
    """Keep the reference game's map, field and battle presentation; drop its content."""
    db = c.db
    db.progression_graphs.clear()
    db.progression_tracks.clear()
    db.passives.clear()
    db.ability_evolutions.clear()
    db.equipment.clear()
    db.equipment_sets.clear()
    db.equipment_growth.clear()
    db.attachments.clear()
    db.classes.clear()
    for actor_id in [a for a in db.actors if a != c.hero_id]:
        del db.actors[actor_id]
    party = db.party_setups["main_party"]
    db.party_setups["main_party"] = dataclasses.replace(
        party,
        roster_actor_ids=(c.hero_id,),
        active_actor_ids=(c.hero_id,),
        placements=tuple(p for p in party.placements if p.actor_id == c.hero_id),
    )


def rules_and_statuses(c):
    db, library = c.db, c.library
    # boost points, shields and Break: a weakness hit costs the target a shield; at zero it breaks
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
    db.battle_session_rules["trial"] = dataclasses.replace(
        rules,
        rules_id="trial",
        boost_resource_id=BP,
        boost_max_level=3,
        shield_resource_id=SHIELD,
    )
    library.states._definitions["broken"] = dataclasses.replace(
        library.states.get("broken"), contributed_tags=("state.broken",)
    )

    # outcome checks: every hit can crit and can be evaded (stats are plain numbers on actors)
    db.outcome_checks.clear()
    db.outcome_checks["crit"] = OutcomeCheckDefinition(
        "crit", 0.05, source_stat_terms={"crit": 0.01}, success_tags=("outcome.crit",)
    )
    db.outcome_checks["land"] = OutcomeCheckDefinition(
        "land",
        0.95,
        target_stat_terms={"evade": -0.01},
        minimum_chance=0.1,
        failure_tags=("outcome.evade",),
    )

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
    for kind in (*WEAPONS, *ELEMENTS):
        source = f"weapon.{kind}" if kind in WEAPONS else f"damage.{kind}"
        db.interaction_rules[f"resist_{kind}"] = InteractionRule(
            f"resist_{kind}",
            source_tags_all=(source,),
            target_tags_all=(f"resist.{kind}",),
            multiplier=0.5,
        )
    db.interaction_rules["absorb_dark"] = InteractionRule(
        "absorb_dark",
        source_tags_all=("damage.dark",),
        target_tags_all=("absorb.dark",),
        disposition="absorb",
        priority=20,
    )
    db.interaction_rules["reflect_magic"] = InteractionRule(
        "reflect_magic",
        source_tags_all=("magic",),
        target_tags_all=("reflect.magic",),
        disposition="reflect",
        priority=20,
    )
    db.interaction_rules["evade_nullify"] = InteractionRule(
        "evade_nullify",
        source_tags_all=("outcome.evade",),
        disposition="nullify",
        priority=30,
    )
    db.interaction_rules["crit_x"] = InteractionRule(
        "crit_x", source_tags_all=("outcome.crit",), multiplier=1.75, priority=5
    )
    db.interaction_rules["broken"] = InteractionRule(
        "broken", target_tags_all=("state.broken",), multiplier=2.0
    )
    db.interaction_rules["ward"] = InteractionRule(
        "ward", target_tags_all=("state.ward",), multiplier=0.5, priority=-1
    )
    db.interaction_rules["bulwark_stance"] = InteractionRule(
        "bulwark_stance",
        source_tags_any=tuple(f"weapon.{k}" for k in WEAPONS),
        target_tags_all=("stance.bulwark",),
        multiplier=0.4,
    )
    db.interaction_rules["bulwark_magic"] = InteractionRule(
        "bulwark_magic",
        source_tags_all=("magic",),
        target_tags_all=("stance.bulwark",),
        multiplier=1.5,
    )
    db.interaction_rules["fury_stance"] = InteractionRule(
        "fury_stance", source_tags_all=("stance.fury",), multiplier=1.5
    )
    for level, factor in ((1, 2.0), (2, 3.0), (3, 4.0)):
        db.interaction_rules[f"boost_power_{level}"] = InteractionRule(
            f"boost_power_{level}",
            source_tags_all=(f"boost.{level}", "boost.power"),
            multiplier=factor,
        )

    states = library.states._definitions

    def dot(state_id, amount, duration, tag):
        states[state_id] = StateDefinition(
            state_id,
            duration,
            periodic=(PeriodicEffect(1, Effect(f"{state_id}.tick", (op(-amount),)), growth=1.0),),
            contributed_tags=(tag,),
        )

    dot("poison", 140, 4, "status.poison")
    dot("burn", 120, 3, "status.burn")
    dot("bleed", 200, 3, "status.bleed")
    states["regen"] = StateDefinition(
        "regen",
        4,
        periodic=(PeriodicEffect(1, Effect("regen.tick", (op(260),)), growth=0.0),),
        contributed_tags=("status.regen",),
    )
    for plain in ("sleep", "stun", "freeze", "silence", "ward"):
        states[plain] = StateDefinition(
            plain,
            2 if plain != "silence" else 3,
            contributed_tags=(f"state.{plain}" if plain == "ward" else f"status.{plain}",),
        )
    mod = StatModifier
    states["attack_up"] = StateDefinition(
        "attack_up",
        3,
        modifiers=(
            mod("attack_up", "power", "multiply", 1.5),
            mod("a2", "magic", "multiply", 1.5),
        ),
    )
    states["defense_down"] = StateDefinition(
        "defense_down", 3, modifiers=(mod("defense_down", "defense", "multiply", 0.5),)
    )
    states["haste"] = StateDefinition(
        "haste", 3, modifiers=(mod("haste", "speed", "multiply", 1.6),)
    )
    states["evasion_up"] = StateDefinition(
        "evasion_up", 3, modifiers=(mod("evasion_up", "evade", "add", 45.0),)
    )
    states["focus"] = StateDefinition("focus", 3, modifiers=(mod("focus", "crit", "add", 40.0),))
    states["lifelink"] = StateDefinition(
        "lifelink", 3, modifiers=(mod("lifelink", "lifesteal", "add", 0.25),)
    )
    states["mirror"] = StateDefinition("mirror", 3, contributed_tags=("reflect.magic",))
    for element in ("fire", "ice", "lightning", "light"):  # a weapon infused with an element
        states[f"enchant_{element}"] = StateDefinition(
            f"enchant_{element}", 5, contributed_tags=(f"damage.{element}",)
        )
    states["power_down"] = StateDefinition(
        "power_down",
        3,
        modifiers=(
            mod("power_down", "power", "multiply", 0.6),
            mod("pd2", "magic", "multiply", 0.6),
        ),
    )
    states["stoneskin"] = StateDefinition(
        "stoneskin", 3, modifiers=(mod("stoneskin", "defense", "multiply", 2.0),)
    )
    states["magic_up"] = StateDefinition(
        "magic_up", 3, modifiers=(mod("magic_up", "magic", "multiply", 1.5),)
    )
    for stance, tag in (("stance_bulwark", "stance.bulwark"), ("stance_fury", "stance.fury")):
        states[stance] = StateDefinition(stance, 99, contributed_tags=(tag,))
    policies = [
        BattleStatePolicy("poison", tick_trigger="rpg.battle.turn_ended", base_chance=0.9),
        BattleStatePolicy("burn", tick_trigger="rpg.battle.turn_ended", base_chance=0.9),
        BattleStatePolicy("bleed", tick_trigger="rpg.battle.turn_ended", base_chance=0.9),
        BattleStatePolicy("regen", tick_trigger="rpg.battle.turn_ended"),
        BattleStatePolicy(
            "sleep",
            base_chance=0.8,
            prevent_action=True,
            tick_trigger="rpg.battle.turn_ready",
            immune_target_tags=("immune.sleep",),
        ),
        BattleStatePolicy(
            "stun",
            base_chance=0.7,
            prevent_action=True,
            tick_trigger="rpg.battle.turn_ready",
            immune_target_tags=("immune.stun",),
        ),
        BattleStatePolicy(
            "freeze",
            base_chance=0.7,
            prevent_action=True,
            tick_trigger="rpg.battle.turn_ready",
            immune_target_tags=("immune.freeze",),
        ),
        BattleStatePolicy(
            "silence",
            base_chance=0.9,
            blocked_ability_tags=("magic",),
            tick_trigger="rpg.battle.turn_ended",
        ),
        BattleStatePolicy("ward", tick_trigger="rpg.battle.turn_ended"),
        BattleStatePolicy("attack_up", tick_trigger="rpg.battle.turn_ended"),
        BattleStatePolicy("defense_down", tick_trigger="rpg.battle.turn_ended"),
        BattleStatePolicy("haste", tick_trigger="rpg.battle.turn_ended"),
        BattleStatePolicy("evasion_up", tick_trigger="rpg.battle.turn_ended"),
        BattleStatePolicy("focus", tick_trigger="rpg.battle.turn_ended"),
        BattleStatePolicy("lifelink", tick_trigger="rpg.battle.turn_ended"),
        *(
            BattleStatePolicy(name, tick_trigger="rpg.battle.turn_ended")
            for name in (
                "mirror",
                "enchant_fire",
                "enchant_ice",
                "enchant_lightning",
                "enchant_light",
                "power_down",
                "stoneskin",
                "magic_up",
            )
        ),
        BattleStatePolicy("stance_bulwark"),
        BattleStatePolicy("stance_fury"),
    ]
    for policy in policies:
        db.battle_state_policies[policy.state_id] = policy
    # the reference game's "broken" policy clears on "round.end", which the engine never emits;
    # with a timeline scheduler there are no rounds either, so Break lasts until the foe's turn
    # comes up once (duration 2 = it ticks down when the turn is ready, and the turn is lost)
    library.states._definitions["broken"] = dataclasses.replace(
        library.states.get("broken"), duration=2.0, contributed_tags=("state.broken",)
    )
    db.battle_state_policies["broken"] = BattleStatePolicy(
        "broken", prevent_action=True, tick_trigger="rpg.battle.turn_ready"
    )


def _modifier(stat, value, mid, operation="add"):
    return StatModifier(mid, stat, operation, value)


def gear(c):
    """Weapons, a unique weapon with growth, armour set, gems and cards, refine and wear rules."""
    from asteria.rpg import (
        AttachmentDefinition,
        EquipmentDefinition,
        EquipmentSetBonus,
        EquipmentSetDefinition,
        ItemDefinition,
        SocketDefinition,
    )
    from asteria.rpg.durability import DurabilityRules, WearEvent
    from asteria.rpg.equipment_growth import (
        EquipmentGrowthDefinition,
        EquipmentGrowthNodeDefinition,
        EquipmentGrowthReward,
    )
    from asteria.rpg.refine import RefineRules

    db = c.db
    names = {
        "sword": "Iron Sword",
        "spear": "Wyrm Lance",
        "dagger": "Stiletto",
        "axe": "Hand Axe",
        "bow": "Hunter's Bow",
        "staff": "Oak Staff",
    }
    for kind, name in names.items():
        attack = c.add(
            ability(
                f"attack_{kind}",
                tags=(f"weapon.{kind}", "boost.repeat"),
                effect=op(damage("power", 18)),
                hits=[{"tags": [], "power": 1.0, "checks": ["crit", "land"]}],
            ),
            "enemy",
        )
        db.add_equipment(
            EquipmentDefinition(
                f"w_{kind}",
                name,
                slot="weapon",
                tags=("weapon", f"equip.{kind}"),
                granted_abilities=(attack,),
            )
        )
        c.skill_names[attack] = f"Attack ({kind})"

    # Sunbrand: the unique sword with three sockets, a growth graph and refinement
    c.add(
        ability(
            "sunburst",
            tags=("weapon.sword", "damage.light", "magic", "divine"),
            effect=op(damage("power", 13)),
            sp=30,
            battle_costs={"bp": 2},
            hits=[
                {"tags": ["weapon.sword"], "power": 1.0, "checks": ["crit", "land"]},
                {"tags": ["damage.light"], "power": 1.2, "checks": ["crit"]},
                {"tags": ["weapon.sword", "damage.light"], "power": 2.0, "checks": ["crit"]},
            ],
        ),
        "enemy",
    )
    db.add_equipment(
        EquipmentDefinition(
            "w_sunbrand",
            "Sunbrand",
            slot="weapon",
            tags=("weapon", "equip.sword", "unique"),
            modifiers=(_modifier("power", 24, "sunbrand.power"),),
            granted_abilities=("attack_sword", "sunburst"),
            sockets=(
                SocketDefinition("s1", accepted_tags=("gem",)),
                SocketDefinition("s2", accepted_tags=("gem",)),
                SocketDefinition("s3", accepted_tags=("card",), locked=True),
            ),
            growth_id="sunbrand_growth",
        )
    )
    db.add_equipment(
        EquipmentDefinition(
            "w_sunbrand_ex",
            "Dawnbreaker",
            slot="weapon",
            tags=("weapon", "equip.sword", "unique"),
            modifiers=(
                _modifier("power", 60, "dawn.power"),
                _modifier("crit", 10, "dawn.crit"),
            ),
            granted_abilities=("attack_sword", "sunburst"),
            sockets=(
                SocketDefinition("s1", accepted_tags=("gem",)),
                SocketDefinition("s2", accepted_tags=("gem",)),
                SocketDefinition("s3", accepted_tags=("card",)),
            ),
        )
    )
    reward = EquipmentGrowthReward
    db.add_equipment_growth(
        EquipmentGrowthDefinition(
            "sunbrand_growth",
            "Sunbrand Awakening",
            nodes=(
                EquipmentGrowthNodeDefinition(
                    "awaken",
                    "Awaken",
                    auto_unlock=False,
                    rewards=reward(
                        unlocked_sockets=("s3",), modifiers=(_modifier("power", 8, "aw.p"),)
                    ),
                ),
                EquipmentGrowthNodeDefinition(
                    "edge",
                    "Honed Edge",
                    max_rank=3,
                    auto_unlock=False,
                    prerequisites=("awaken",),
                    rewards=[
                        reward(modifiers=(_modifier("power", 6, f"edge.p{i}"),)) for i in (1, 2, 3)
                    ],
                ),
                EquipmentGrowthNodeDefinition(
                    "ember",
                    "Ember Path",
                    auto_unlock=False,
                    prerequisites=("awaken",),
                    exclusive_group="path",
                    rewards=reward(granted_tags=("damage.fire",)),
                ),
                EquipmentGrowthNodeDefinition(
                    "frost",
                    "Frost Path",
                    auto_unlock=False,
                    prerequisites=("awaken",),
                    exclusive_group="path",
                    rewards=reward(granted_tags=("damage.ice",)),
                ),
                EquipmentGrowthNodeDefinition(
                    "dawn",
                    "Dawn",
                    auto_unlock=False,
                    prerequisites=(("edge", 3),),
                    rewards=reward(evolution_equipment_id="w_sunbrand_ex"),
                ),
            ),
        )
    )

    # armour set, two accessories
    pieces = {
        "a_warden_plate": ("Warden Plate", "armor", (_modifier("defense", 22, "wp.d"),)),
        "a_warden_ring": ("Warden Ring", "accessory", (_modifier("evade", 6, "wr.e"),)),
        "a_warden_charm": ("Warden Charm", "accessory", (_modifier("crit", 8, "wc.c"),)),
    }
    for eid, (name, slot, mods) in pieces.items():
        db.add_equipment(
            EquipmentDefinition(eid, name, slot=slot, tags=(slot, "set.warden"), modifiers=mods)
        )
    db.add_equipment_set(
        EquipmentSetDefinition(
            "warden",
            "Warden's Oath",
            equipment_ids=tuple(pieces),
            bonuses=(
                EquipmentSetBonus(2, modifiers=(_modifier("defense", 15, "set2.d"),)),
                EquipmentSetBonus(
                    3,
                    modifiers=(_modifier("power", 20, "set3.p"), _modifier("evade", 8, "set3.e")),
                    tags=("immune.kill",),
                ),
            ),
        )
    )

    # gems (returned when taken out) and cards (consumed), all socketable bag items
    gems = {
        "ruby": ("Ruby", "gem", (_modifier("power", 9, "ruby.p"),)),
        "sapphire": ("Sapphire", "gem", (_modifier("magic", 9, "sapphire.m"),)),
        "topaz": (
            "Topaz",
            "gem",
            (_modifier("speed", 6, "topaz.s"), _modifier("crit", 6, "topaz.c")),
        ),
        "onyx": ("Onyx", "gem", (_modifier("lifesteal", 0.06, "onyx.l"),)),
        "card_wolf": (
            "Wolf Card",
            "card",
            (_modifier("speed", 10, "wolf.s"), _modifier("evade", 10, "wolf.e")),
        ),
        "card_vampire": ("Vampire Card", "card", (_modifier("lifesteal", 0.12, "vamp.l"),)),
        "card_golem": ("Golem Card", "card", (_modifier("defense", 24, "golem.d"),)),
        "card_slayer": ("Slayer Card", "card", (_modifier("crit", 18, "slayer.c"),)),
    }
    for aid, (name, kind, mods) in gems.items():
        tags = ("immune.kill",) if aid == "card_golem" else ()
        db.add_attachment(AttachmentDefinition(aid, name, tags=(kind, *tags), modifiers=mods))
        db.add_item(
            ItemDefinition(
                f"{aid}_item",
                name,
                stack_limit=20,
                attachment_id=aid,
                destroyed_on_removal=kind == "card",
            )
        )
    db.add_refine_rules(
        RefineRules(
            "plus",
            max_level=10,
            equipment_tags=("weapon",),
            bonuses={"power": 3.0, "magic": 3.0},
            currency="gold",
            base_cost=200,
            cost_growth=150,
            success=[1, 1, 1, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2],
            on_fail="drop",
            safe_until=3,
        )
    )
    db.add_durability_rules(
        DurabilityRules(
            "wear",
            default_max=400.0,
            wear=(WearEvent("attack", ["weapon"], 1.0), WearEvent("hit", ["armor"], 1.0)),
            on_break="disable",
            repair_currency="gold",
            repair_cost_per_point=2.0,
        )
    )


# -- hero skills ----------------------------------------------------------------------------------
CRIT = ["crit", "land"]


def _hits(*powers, tags=(), checks=CRIT):
    """One hit per power; every hit rolls its own crit / evade checks."""
    return [{"tags": list(tags), "power": p, "checks": list(checks)} for p in powers]


def _with_self(definition, effect):
    """The ability also changes its user (a heal, a resource ...)."""
    return dataclasses.replace(
        definition,
        effects=(*definition.effects, AbilityEffect("self", Effect("self.effect", (effect,)))),
    )


def _state(state_id, to="targets", remove=False):
    return {"state": state_id, "to": to, "remove": remove}


def hero_skills(c):
    add, names = c.add, c.skill_names

    def skill(ability_id, label, target, definition, *, divine=False):
        names[ability_id] = label + (" (Divine)" if divine else "")
        return add(definition, target)

    # --- Knight: guard, bash, bleed, lifesteal, a gamble on instant death --------------------
    skill(
        "shield_bash",
        "Shield Bash",
        "enemy",
        ability(
            "shield_bash",
            tags=("weapon.sword",),
            effect=op(damage("power", 16)),
            sp=8,
            hits=_hits(1.0),
            apply_states=[_state("stun")],
        ),
    )
    skill(
        "guard_stance",
        "Guard Stance",
        "self",
        ability("guard_stance", sp=6, apply_states=[_state("ward", "self")], cooldown_turns=2),
    )
    skill(
        "cleave",
        "Triple Cleave",
        "enemy",
        ability(
            "cleave",
            tags=("weapon.sword", "weapon.axe"),
            effect=op(damage("power", 10)),
            sp=12,
            hits=_hits(1.0, 1.0, 1.3, tags=("weapon.sword",)),
        ),
    )
    skill(
        "rally",
        "Rally",
        "self",
        ability(
            "rally",
            sp=14,
            apply_states=[_state("attack_up", "self"), _state("regen", "self")],
            cooldown_turns=3,
        ),
    )
    skill(
        "bloodletting",
        "Bloodletting",
        "enemy",
        ability(
            "bloodletting",
            tags=("weapon.axe",),
            effect=op(damage("power", 12)),
            sp=14,
            hits=_hits(1.0, 1.0),
            apply_states=[_state("bleed")],
        ),
    )
    skill(
        "vampiric_strike",
        "Vampiric Strike",
        "enemy",
        _with_self(
            ability(
                "vampiric_strike",
                tags=("weapon.sword", "damage.dark"),
                effect=op(damage("power", 15)),
                sp=16,
                hits=_hits(1.0),
                apply_states=[_state("lifelink", "self")],
            ),
            op(healing(10, "power")),
        ),
    )
    skill(
        "executioner",
        "Executioner",
        "enemy",
        ability(
            "executioner",
            tags=("weapon.axe", "divine"),
            effect=op(damage("power", 12)),
            sp=26,
            battle_costs={"bp": 2},
            hits=[
                {"tags": [], "power": 1.0, "checks": CRIT},
                {
                    "tags": [],
                    "power": 3.0,
                    "checks": ["crit"],
                    "kill": {
                        "chance": 0.2,
                        "resource": HP,
                        "immune_tags": ["boss"],
                        "immune_fraction": 0.12,
                    },
                },
            ],
        ),
        divine=True,
    )
    skill(
        "bastion",
        "Bastion",
        "self",
        ability(
            "bastion",
            tags=("divine",),
            sp=22,
            battle_costs={"bp": 3},
            apply_states=[
                _state("ward", "self"),
                _state("haste", "self"),
                _state("regen", "self"),
            ],
        ),
        divine=True,
    )

    # --- Duelist: speed, crit, evasion, poison, a long flurry ---------------------------------
    skill(
        "quick_slash",
        "Quick Slash",
        "enemy",
        ability(
            "quick_slash",
            tags=("weapon.dagger", "weapon.sword"),
            effect=op(damage("power", 8)),
            sp=5,
            hits=_hits(1.0, 1.0, tags=("weapon.dagger",)),
        ),
    )
    skill(
        "flurry",
        "Flurry",
        "enemy",
        ability(
            "flurry",
            tags=("weapon.dagger",),
            effect=op(damage("power", 5)),
            sp=14,
            hits=_hits(*([1.0] * 6)),
        ),
    )
    skill(
        "poison_edge",
        "Venom Edge",
        "enemy",
        ability(
            "poison_edge",
            tags=("weapon.dagger",),
            effect=op(damage("power", 9)),
            sp=9,
            hits=_hits(1.0),
            apply_states=[_state("poison")],
        ),
    )
    skill(
        "shadow_step",
        "Shadow Step",
        "self",
        ability(
            "shadow_step",
            sp=10,
            apply_states=[_state("evasion_up", "self"), _state("focus", "self")],
            cooldown_turns=3,
        ),
    )
    skill(
        "arrow_rain",
        "Arrow Rain",
        "enemy",
        ability(
            "arrow_rain",
            tags=("weapon.bow",),
            effect=op(damage("power", 6)),
            sp=16,
            hits=[
                {"tags": ["damage.ice"], "power": 1.0, "checks": CRIT},
                {"tags": ["damage.lightning"], "power": 1.0, "checks": CRIT},
                {"tags": ["damage.fire"], "power": 1.0, "checks": CRIT},
                {"tags": [], "power": 1.0, "checks": CRIT},
            ],
        ),
    )
    skill(
        "assassinate",
        "Assassinate",
        "enemy",
        ability(
            "assassinate",
            tags=("weapon.dagger",),
            effect=op(damage("power", 14)),
            sp=20,
            cooldown_turns=2,
            hits=[
                {
                    "tags": [],
                    "power": 1.5,
                    "checks": ["crit"],
                    "kill": {
                        "chance": 0.3,
                        "resource": HP,
                        "immune_tags": ["boss"],
                        "immune_fraction": 0.1,
                    },
                }
            ],
        ),
    )
    skill(
        "phantom_dance",
        "Phantom Dance",
        "enemy",
        ability(
            "phantom_dance",
            tags=("weapon.dagger", "divine"),
            effect=op(damage("power", 7)),
            sp=28,
            battle_costs={"bp": 3},
            hits=[{"tags": [], "power": 0.8 + 0.1 * i, "checks": CRIT} for i in range(8)],
            apply_states=[_state("evasion_up", "self")],
        ),
        divine=True,
    )

    # --- Mystic: elements, healing, curses, barriers, drain -----------------------------------
    skill(
        "fireball",
        "Fireball",
        "enemy",
        ability(
            "fireball",
            tags=("magic", "damage.fire"),
            effect=op(damage("magic", 14)),
            sp=10,
            apply_states=[_state("burn")],
        ),
    )
    skill(
        "frost_lance",
        "Frost Lance",
        "enemy",
        ability(
            "frost_lance",
            tags=("magic", "damage.ice"),
            effect=op(damage("magic", 15)),
            sp=12,
            apply_states=[_state("freeze")],
        ),
    )
    skill(
        "thunder_chain",
        "Thunder Chain",
        "enemy",
        ability(
            "thunder_chain",
            tags=("magic", "damage.lightning"),
            effect=op(damage("magic", 8)),
            sp=16,
            hits=_hits(1.0, 1.0, 1.0, checks=["crit"]),
        ),
    )
    skill(
        "mend",
        "Mend",
        "self",
        ability("mend", tags=("magic",), effect=op(healing(14)), mode="self", sp=12),
    )
    skill(
        "arcane_barrier",
        "Arcane Barrier",
        "self",
        ability(
            "arcane_barrier",
            tags=("magic",),
            sp=14,
            apply_states=[_state("ward", "self")],
            cooldown_turns=2,
        ),
    )
    skill(
        "drain_touch",
        "Drain Touch",
        "enemy",
        _with_self(
            ability(
                "drain_touch",
                tags=("magic", "damage.dark"),
                effect=op(damage("magic", 12)),
                sp=14,
            ),
            op(healing(9)),
        ),
    )
    skill(
        "curse",
        "Hex",
        "enemy",
        ability(
            "curse",
            tags=("magic",),
            sp=12,
            effect=op(damage("magic", 4)),
            apply_states=[_state("silence"), _state("defense_down")],
        ),
    )
    skill(
        "meteor_fall",
        "Meteor Fall",
        "enemy",
        ability(
            "meteor_fall",
            tags=("magic", "divine"),
            effect=op(damage("magic", 9)),
            sp=34,
            battle_costs={"bp": 3},
            hits=[
                {"tags": ["damage.fire"], "power": 1.0, "checks": ["crit"]},
                {"tags": ["damage.ice"], "power": 1.0, "checks": ["crit"]},
                {"tags": ["damage.lightning"], "power": 1.0, "checks": ["crit"]},
                {"tags": ["damage.light"], "power": 2.5, "checks": ["crit"]},
            ],
            apply_states=[_state("burn")],
        ),
        divine=True,
    )
    skill(
        "donate_bp",
        "Focus Breath",
        "self",
        ability(
            "donate_bp",
            sp=0,
            mode="self",
            battle_resource_gains=[{"to": "self", "resource": BP, "amount": 2}],
            cooldown_turns=4,
        ),
    )


# -- jobs, growth, trees --------------------------------------------------------------------------
def _node(node_id, name, ranks, cost, reward, **links):
    """A tree node: ``ranks`` ranks, each costing ``cost`` and giving ``reward`` (cumulative)."""
    from asteria.rpg import ProgressionNodeDefinition, ProgressionNodeRequirement
    from asteria.rpg.progression_graph import ProgressionNodeReward

    def reqs(items):
        return [
            ProgressionNodeRequirement(*item)
            if isinstance(item, tuple)
            else ProgressionNodeRequirement(item)
            for item in items
        ]

    return ProgressionNodeDefinition(
        node_id,
        name,
        max_rank=ranks,
        rank_costs=cost,
        rewards=ProgressionNodeReward(**reward),
        prerequisites=reqs(links.get("needs", ())),
        any_prerequisites=reqs(links.get("any", ())),
        exclusive_group=links.get("group"),
        tags=links.get("tags", ()),
    )


def hero_jobs_and_trees(c):
    from asteria.rpg import ClassAssignment, ClassDefinition, ProgressionGraphDefinition
    from asteria.rpg.ability_build import PassiveDefinition
    from asteria.rpg.battle_extensions import BattleExtensionRules
    from asteria.rpg.job_points import JobPointRules

    db = c.db
    cap = "capability.weapon."
    classes = {
        "knight": ClassDefinition(
            "knight",
            "Knight",
            stat_bonuses={"power": 8, "defense": 12},
            resource_bonuses={HP: 500},
            granted_tags=("class.knight", cap + "sword", cap + "axe", cap + "spear"),
            granted_abilities=("shield_bash",),
            level_growth={"power": 3.4, "defense": 2.6, "speed": 0.4},
        ),
        "duelist": ClassDefinition(
            "duelist",
            "Duelist",
            stat_bonuses={"speed": 14, "crit": 12, "evade": 8},
            resource_bonuses={SP: 30},
            granted_tags=("class.duelist", cap + "dagger", cap + "bow", cap + "sword"),
            granted_abilities=("quick_slash",),
            level_growth={"power": 1.8, "speed": 1.6, "crit": 0.15},
        ),
        "mystic": ClassDefinition(
            "mystic",
            "Mystic",
            stat_bonuses={"magic": 16},
            resource_bonuses={SP: 90},
            granted_tags=("class.mystic", cap + "staff", cap + "dagger"),
            granted_abilities=("fireball",),
            level_growth={"magic": 3.6, "speed": 0.5, "defense": 0.8},
        ),
    }
    for definition in classes.values():
        db.add_class(definition)

    passives = {
        "iron_will": ("Iron Will", (_modifier("defense", 20, "iw.d"),)),
        "keen_eye": ("Keen Eye", (_modifier("crit", 15, "ke.c"),)),
        "vampirism": ("Vampirism", (_modifier("lifesteal", 0.05, "vp.l"),)),
        "arcane_focus": ("Arcane Focus", (_modifier("magic", 18, "af.m"),)),
    }
    for pid, (name, mods) in passives.items():
        db.add_passive(PassiveDefinition(pid, name, modifiers=mods))

    def jp(cls, amount):
        # keystones and divine skills also cost ability points (earned by levelling)
        return {f"jp.{cls}": amount, **({"ap": 2} if amount >= 6 else {})}

    def stat(**kw):
        return {"stat_bonuses": kw}

    def grant(*ids, **kw):
        return {"granted_abilities": ids, **kw}

    knight = ProgressionGraphDefinition(
        "knight_tree",
        "Knight",
        nodes=(
            _node("k_footing", "Footing", 5, jp("knight", 1), stat(power=4)),
            _node(
                "k_bash",
                "Shield Bash",
                1,
                jp("knight", 2),
                grant("shield_bash"),
                needs=["k_footing"],
            ),
            _node(
                "k_cleave",
                "Triple Cleave",
                1,
                jp("knight", 3),
                grant("cleave"),
                needs=[("k_footing", 2)],
            ),
            _node(
                "k_guard",
                "Guard Stance",
                1,
                jp("knight", 3),
                grant("guard_stance"),
                needs=["k_bash"],
            ),
            _node(
                "k_tough",
                "Toughness",
                5,
                jp("knight", 2),
                {"stat_bonuses": {"defense": 5}, "resource_bonuses": {HP: 150}},
                needs=["k_guard"],
            ),
            _node(
                "k_berserker",
                "Berserker",
                1,
                jp("knight", 6),
                {"stat_bonuses": {"power": 30, "defense": -10}, "granted_tags": ("berserk",)},
                needs=[("k_tough", 2)],
                group="k_path",
                tags=("keystone",),
            ),
            _node(
                "k_bulwark",
                "Bulwark",
                1,
                jp("knight", 6),
                {"stat_bonuses": {"defense": 35}, "unlocked_passives": ("iron_will",)},
                needs=[("k_tough", 2)],
                group="k_path",
                tags=("keystone",),
            ),
            _node(
                "k_rally", "Rally", 1, jp("knight", 4), grant("rally"), any=["k_bash", "k_cleave"]
            ),
            _node(
                "k_bleed",
                "Bloodletting",
                1,
                jp("knight", 4),
                grant("bloodletting"),
                needs=["k_cleave"],
            ),
            _node(
                "k_vamp",
                "Vampiric Strike",
                3,
                jp("knight", 4),
                {"granted_abilities": ("vampiric_strike",), "stat_bonuses": {"lifesteal": 0.03}},
                any=["k_bleed", "k_berserker"],
            ),
            _node(
                "k_exec",
                "Executioner",
                1,
                jp("knight", 9),
                grant("executioner"),
                needs=[("k_tough", 3)],
                any=["k_berserker", ("k_vamp", 2)],
            ),
            _node(
                "k_bastion",
                "Bastion",
                1,
                jp("knight", 9),
                grant("bastion"),
                needs=["k_bulwark", ("k_tough", 5)],
            ),
        ),
        tags=("job.knight",),
    )
    duelist = ProgressionGraphDefinition(
        "duelist_tree",
        "Duelist",
        nodes=(
            _node("d_reflex", "Reflexes", 5, jp("duelist", 1), stat(speed=3, evade=1)),
            _node("d_quick", "Quick Slash", 1, jp("duelist", 1), grant("quick_slash")),
            _node("d_flurry", "Flurry", 1, jp("duelist", 3), grant("flurry"), needs=["d_quick"]),
            _node(
                "d_venom",
                "Venom Edge",
                1,
                jp("duelist", 3),
                grant("poison_edge"),
                needs=["d_quick"],
            ),
            _node(
                "d_step",
                "Shadow Step",
                1,
                jp("duelist", 3),
                grant("shadow_step"),
                needs=[("d_reflex", 2)],
            ),
            _node(
                "d_eye",
                "Keen Eye",
                1,
                jp("duelist", 4),
                {"unlocked_passives": ("keen_eye",)},
                needs=["d_step"],
            ),
            _node(
                "d_arrow",
                "Arrow Rain",
                1,
                jp("duelist", 4),
                grant("arrow_rain"),
                any=["d_flurry", "d_venom"],
            ),
            _node("d_crit", "Deadly Aim", 5, jp("duelist", 2), stat(crit=3), needs=["d_eye"]),
            _node(
                "d_assassin",
                "Assassinate",
                1,
                jp("duelist", 8),
                grant("assassinate"),
                needs=[("d_crit", 3)],
                group="d_path",
                tags=("keystone",),
            ),
            _node(
                "d_dance",
                "Phantom Dance",
                1,
                jp("duelist", 9),
                grant("phantom_dance"),
                needs=[("d_crit", 3), "d_flurry"],
                group="d_path",
                tags=("keystone",),
            ),
        ),
        tags=("job.duelist",),
    )
    mystic = ProgressionGraphDefinition(
        "mystic_tree",
        "Mystic",
        nodes=(
            _node("m_study", "Study", 5, jp("mystic", 1), stat(magic=4)),
            _node("m_fire", "Fireball", 1, jp("mystic", 1), grant("fireball")),
            _node(
                "m_frost",
                "Frost Lance",
                1,
                jp("mystic", 3),
                grant("frost_lance"),
                needs=["m_fire"],
            ),
            _node(
                "m_bolt",
                "Thunder Chain",
                1,
                jp("mystic", 3),
                grant("thunder_chain"),
                needs=["m_fire"],
            ),
            _node("m_mend", "Mend", 1, jp("mystic", 2), grant("mend"), needs=["m_study"]),
            _node(
                "m_barrier",
                "Arcane Barrier",
                1,
                jp("mystic", 3),
                grant("arcane_barrier"),
                needs=["m_mend"],
            ),
            _node(
                "m_drain",
                "Drain Touch",
                1,
                jp("mystic", 4),
                grant("drain_touch"),
                any=["m_frost", "m_bolt"],
            ),
            _node("m_hex", "Hex", 1, jp("mystic", 4), grant("curse"), needs=["m_drain"]),
            _node(
                "m_focus",
                "Arcane Focus",
                1,
                jp("mystic", 5),
                {"unlocked_passives": ("arcane_focus",)},
                needs=[("m_study", 3)],
            ),
            _node(
                "m_breath",
                "Focus Breath",
                1,
                jp("mystic", 4),
                grant("donate_bp"),
                needs=["m_focus"],
            ),
            _node(
                "m_meteor",
                "Meteor Fall",
                1,
                jp("mystic", 10),
                grant("meteor_fall"),
                needs=["m_hex", "m_focus", ("m_study", 5)],
            ),
        ),
        tags=("job.mystic",),
    )
    attributes = ProgressionGraphDefinition(
        "attributes",
        "Attributes",
        nodes=(
            _node("attr_str", "Strength", 30, {"stat_points": 1}, stat(power=2)),
            _node(
                "attr_vit",
                "Vitality",
                30,
                {"stat_points": 1},
                {"resource_bonuses": {HP: 70}, "stat_bonuses": {"defense": 1}},
            ),
            _node(
                "attr_dex", "Dexterity", 30, {"stat_points": 1}, stat(speed=1, evade=0.5, crit=0.4)
            ),
            _node(
                "attr_int",
                "Intellect",
                30,
                {"stat_points": 1},
                {"stat_bonuses": {"magic": 2}, "resource_bonuses": {SP: 4}},
            ),
        ),
        tags=("attributes",),
    )
    for graph in (knight, duelist, mystic, attributes):
        db.add_progression_graph(graph)

    db.add_job_point_rules(JobPointRules("jp", per_battle=10, per_enemy=4, secondary=0.5))
    db.add_battle_extension_rules(
        BattleExtensionRules(
            "trial",
            damage_resource=HP,
            lifesteal_stat="lifesteal",
            overkill_rate=0.5,
            overkill_cap=1.0,
            preemptive_chance=0.2,
            surprise_chance=0.05,
        )
    )

    actor = db.actors[c.hero_id]
    db.actors[c.hero_id] = dataclasses.replace(
        actor,
        display_name="Aldric",
        class_assignments=(
            ClassAssignment("knight", assignment_id="hero_01.main", role="main", priority=10),
            ClassAssignment("duelist", assignment_id="hero_01.sub", role="secondary", priority=5),
        ),
        base_stats={
            "power": 40.0,
            "magic": 30.0,
            "defense": 30.0,
            "speed": 40.0,
            "crit": 5.0,
            "evade": 5.0,
            "lifesteal": 0.0,
        },
        base_resources={
            HP: {"minimum": 0.0, "maximum": 3200.0, "current": 3200.0},
            SP: {"minimum": 0.0, "maximum": 220.0, "current": 220.0},
        },
        abilities=(),
    )


# -- the boss -------------------------------------------------------------------------------------
def _rule(rule_id, ability_id, selector, *, conditions=(), priority=0, weight=1.0):
    return {
        "schema": "asteria.rpg.ai_decision_rule",
        "version": 1,
        "rule_id": rule_id,
        "action_kind": "ability",
        "payload": {"ability_id": ability_id},
        "target_selector": selector,
        "conditions": list(conditions),
        "priority": priority,
        "weight": weight,
        "tags": [],
    }


def _cond(kind, negate=False, **params):
    return {"kind": kind, "params": params, "negate": negate}


def boss(c):
    from asteria.rpg import EnemyDefinition
    from asteria.rpg.enemies import LootEntry
    from asteria.rpg.enemy_ai import EnemyAIDefinition
    from asteria.rpg.enemy_behavior import EnemyBehaviorBinding

    db, add = c.db, c.add
    kill_hero = {
        "chance": 0.15,
        "resource": HP,
        "immune_tags": ["immune.kill"],
        "immune_fraction": 0.25,
    }
    moves = {
        "w_combo": ability(
            "w_combo",
            tags=("weapon.sword",),
            effect=op(damage("power", 6)),
            hits=_hits(1.0, 1.0, 1.4),
        ),
        "w_charge": ability(
            "w_charge",
            tags=("weapon.axe",),
            effect=op(damage("power", 14)),
            hits=_hits(1.0),
            apply_states=[_state("defense_down")],
        ),
        "w_poison": ability(
            "w_poison",
            tags=("weapon.dagger",),
            effect=op(damage("power", 5)),
            hits=_hits(1.0, 1.0),
            apply_states=[_state("poison"), _state("bleed")],
        ),
        "w_cinder": ability(
            "w_cinder",
            tags=("magic", "damage.fire"),
            effect=op(damage("magic", 10)),
            apply_states=[_state("burn")],
        ),
        "w_roar": ability(
            "w_roar",
            tags=("damage.lightning", "magic"),
            effect=op(damage("magic", 6)),
            hits=_hits(1.0, 1.0, checks=["land"]),
            apply_states=[_state("stun")],
        ),
        "w_mark": ability(
            "w_mark",
            tags=("damage.dark", "magic"),
            effect=op(damage("magic", 6)),
            hits=[{"tags": [], "power": 1.0, "checks": ["land"], "kill": kill_hero}],
        ),
        "w_eclipse": ability(
            "w_eclipse",
            tags=("damage.dark", "damage.fire", "divine"),
            effect=op(damage("magic", 6)),
            hits=_hits(1.0, 1.4, 1.8, 2.4, checks=["land"]),
            apply_states=[_state("silence")],
        ),
        "w_cry": ability(
            "w_cry",
            apply_states=[
                _state("stance_fury", "self"),
                _state("stance_bulwark", "self", True),
                _state("attack_up", "self"),
            ],
        ),
        "w_iron": ability(
            "w_iron",
            apply_states=[
                _state("stance_bulwark", "self"),
                _state("stance_fury", "self", True),
                _state("ward", "self"),
            ],
        ),
        "w_summon": ability(
            "w_summon",
            commands=[
                {"command": "SUMMON", "args": {"enemy_id": "mender_wisp", "owner_id": "@actor"}}
            ],
        ),
        "w_mend": ability("w_mend", effect=op(healing(40)), allies=True),
    }
    drain = _with_self(
        ability("w_drain", tags=("damage.dark", "magic"), effect=op(damage("magic", 8))),
        op(healing(30)),
    )
    targeting = {
        "w_combo": "enemy",
        "w_charge": "enemy",
        "w_poison": "enemy",
        "w_cinder": "enemy",
        "w_roar": "enemy",
        "w_mark": "enemy",
        "w_eclipse": "enemy",
        "w_cry": "self",
        "w_iron": "self",
        "w_summon": "self",
        "w_mend": "ally",
    }
    for ability_id, definition in moves.items():
        add(definition, targeting[ability_id])
    add(drain, "enemy")
    all_moves = (*moves, "w_drain")

    selector = {"w_cry": "self", "w_iron": "self", "w_summon": "self", "w_mend": "first_ally"}
    first = _cond("round_index", op="==", value=1)

    def rules(*specs):
        out = []
        for ability_id, kwargs in specs:
            out.append(
                _rule(
                    f"{ability_id}",
                    ability_id,
                    selector.get(ability_id, "first_opponent"),
                    **kwargs,
                )
            )
        return out

    opening = [
        ("w_iron", {"conditions": [first], "priority": 10}),
        ("w_combo", {"weight": 3}),
        ("w_charge", {"weight": 2}),
        ("w_poison", {"weight": 2}),
    ]
    ascent = [
        ("w_cry", {"weight": 1}),
        ("w_iron", {"weight": 1}),
        ("w_combo", {"weight": 2}),
        ("w_cinder", {"weight": 2}),
        ("w_drain", {"weight": 2}),
        ("w_mark", {"weight": 1}),
        ("w_roar", {"weight": 1}),
        (
            "w_summon",
            {
                "weight": 8,
                "conditions": [_cond("resource_ratio", resource_id=HP, op="<=", value=0.66)],
            },
        ),
    ]
    last = [
        ("w_eclipse", {"weight": 3}),
        ("w_mark", {"weight": 2}),
        ("w_drain", {"weight": 2}),
        ("w_cry", {"weight": 1}),
        ("w_roar", {"weight": 2}),
        ("w_summon", {"weight": 6}),
    ]
    seen, all_rules = set(), []
    for rule in rules(*opening, *ascent, *last):
        key = (rule["rule_id"], json.dumps(rule["conditions"], sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        all_rules.append(rule)
    # one rule id per (move, phase): rules are phase-scoped by their decision_rule_ids
    phase_rules, rule_data = {}, []
    for phase, specs in (("opening", opening), ("ascent", ascent), ("last_stand", last)):
        ids = []
        for rule in rules(*specs):
            rule = dict(rule, rule_id=f"{phase}.{rule['rule_id']}")
            rule_data.append(rule)
            ids.append(rule["rule_id"])
        phase_rules[phase] = ids

    def phase(phase_id, priority, conditions):
        return {
            "schema": "asteria.rpg.boss_phase_definition",
            "version": 1,
            "phase_id": phase_id,
            "conditions": conditions,
            "priority": priority,
            "decision_rule_ids": phase_rules[phase_id],
            "actions_per_ready": None,
            "enter_hook": None,
            "exit_hook": None,
        }

    ratio = lambda value: [_cond("resource_ratio", resource_id=HP, op="<=", value=value)]  # noqa
    db.enemy_ai.clear()
    db.enemy_behavior_bindings.clear()
    db.enemy_ai["crimson_ai"] = EnemyAIDefinition.from_data(
        {
            "schema": "asteria.rpg.enemy_ai_definition",
            "version": 1,
            "ai_id": "crimson_ai",
            "rules": rule_data,
            "initial_phase_id": "opening",
            "phases": [
                phase("opening", 0, []),
                phase("ascent", 10, ratio(0.66)),
                phase("last_stand", 20, ratio(0.3)),
            ],
        }
    )
    db.enemy_behavior_bindings[c.boss_id] = EnemyBehaviorBinding.from_data(
        {
            "schema": "asteria.rpg.enemy_behavior_binding",
            "version": 1,
            "enemy_id": c.boss_id,
            "ai_id": "crimson_ai",
            "tags": [],
        }
    )
    _ = all_moves, all_rules

    template = db.enemies["ember_hound"]
    reward = dataclasses.replace(
        template.reward,
        experience={},
        currencies={"gold": 6000.0},
        loot=tuple(LootEntry(i) for i in ("ruby_item", "card_slayer_item", "onyx_item")),
    )
    for enemy_id in list(db.enemies):
        del db.enemies[enemy_id]
    db.enemies[c.boss_id] = EnemyDefinition(
        c.boss_id,
        "Vaelor",
        stats={
            "power": 120.0,
            "magic": 110.0,
            "defense": 90.0,
            "speed": 72.0,
            "crit": 10.0,
            "evade": 3.0,
        },
        resources={HP: 24000.0, SHIELD: 6.0, SP: 9999.0},
        tags=(
            "enemy",
            "boss",
            "weak.ice",
            "weak.lightning",
            "weak.dagger",
            "resist.sword",
            "resist.fire",
            "immune.sleep",
        ),
        abilities=tuple(all_moves),
        reward=reward,
    )
    db.enemies["mender_wisp"] = EnemyDefinition(
        "mender_wisp",
        "Skeleton Acolyte",
        stats={"power": 40.0, "magic": 60.0, "defense": 30.0, "speed": 60.0},
        resources={HP: 4200.0, SHIELD: 2.0, SP: 999.0},
        tags=("enemy", "weak.ice", "weak.axe"),
        abilities=("w_mend", "w_cinder"),
        reward=dataclasses.replace(reward, experience={}, loot=()),
    )
    db.enemy_ai["wisp_ai"] = EnemyAIDefinition.from_data(
        {
            "schema": "asteria.rpg.enemy_ai_definition",
            "version": 1,
            "ai_id": "wisp_ai",
            "rules": [
                _rule("mend", "w_mend", "first_ally", weight=1.0),
                _rule("cinder", "w_cinder", "first_opponent", weight=2.0),
            ],
            "phases": [],
            "initial_phase_id": None,
        }
    )
    db.enemy_behavior_bindings["mender_wisp"] = EnemyBehaviorBinding.from_data(
        {
            "schema": "asteria.rpg.enemy_behavior_binding",
            "version": 1,
            "enemy_id": "mender_wisp",
            "ai_id": "wisp_ai",
            "tags": [],
        }
    )
    from asteria.rpg import EncounterDefinition, EncounterMember

    db.encounters.clear()
    db.encounters["boss_room"] = EncounterDefinition(
        "boss_room",
        members=(EncounterMember(c.boss_id, count=1, weight=1.0),),
        tags=("boss", "multi_phase"),
    )
    db.encounters["swarm"] = EncounterDefinition(  # a crowd: the stress test for AI and drawing
        "swarm",
        members=(
            EncounterMember(c.boss_id, count=1, weight=1.0),
            EncounterMember("mender_wisp", count=8, weight=1.0),
        ),
        tags=("boss", "stress"),
    )


# -- the field: the boss and the people who prepare the hero --------------------------------------
SERVICES = {
    # name: (position, line, world command + args)
    "Smith": (
        (-26.0, 26.0),
        "One more fold in the steel. Refine?",
        ("REFINE_EQUIPMENT", {"actor_id": "hero_01", "instance_id": "w_sunbrand:hero_01"}),
    ),
    "Awakener": (
        (-26.0, -26.0),
        "Sunbrand stirs. Awaken it.",
        (
            "UPGRADE_EQUIPMENT",
            {"actor_id": "hero_01", "instance_id": "w_sunbrand:hero_01", "node_id": "awaken"},
        ),
    ),
    "Jeweler": (
        (8.0, 34.0),
        "A ruby for the first socket.",
        (
            "SOCKET_ITEM",
            {
                "actor_id": "hero_01",
                "instance_id": "w_sunbrand:hero_01",
                "socket_id": "s1",
                "item_id": "ruby_item",
            },
        ),
    ),
    "Card Dealer": (
        (24.0, 34.0),
        "A vampire card for the third socket.",
        (
            "SOCKET_ITEM",
            {
                "actor_id": "hero_01",
                "instance_id": "w_sunbrand:hero_01",
                "socket_id": "s3",
                "item_id": "card_vampire_item",
            },
        ),
    ),
    "Mystic Teacher": (
        (30.0, -30.0),
        "Walk the mystic path with me.",
        ("SET_CLASSES", {"actor_id": "hero_01", "class_ids": "knight,mystic"}),
    ),
    "Duelist Teacher": (
        (14.0, -34.0),
        "Speed is a blade.",
        ("SET_CLASSES", {"actor_id": "hero_01", "class_ids": "knight,duelist"}),
    ),
    **{
        name: (
            (x, y),
            line,
            ("SET_CLASSES", {"actor_id": "hero_01", "class_ids": f"knight,{job}"}),
        )
        for name, x, y, line, job in (
            ("Weapon Master Dojo", -44.0, 30.0, "Every weapon, one hand.", "weapon_master"),
            ("Sage's Tower", -44.0, 6.0, "Wisdom of every element.", "sage"),
            ("Hero's Shrine", -44.0, -18.0, "Only the brave may stand here.", "hero"),
            ("Forgemaster's Smithy", 44.0, 30.0, "Temper the steel.", "forgemaster"),
            ("Rogue Guild", 44.0, 6.0, "Take what is not nailed down.", "rogue"),
            ("Guardian Post", 44.0, -18.0, "Hold the line.", "guardian"),
        )
    },
    "Alchemist": (
        (-26.0, 50.0),
        "Combine what you carry.",
        ("OPEN_CRAFTING", {"station": "alchemy"}),
    ),
    "Merchant": ((8.0, 50.0), "Take a look.", ("OPEN_SHOP", {"shop_id": "trial_shop"})),
    "Breaker": ((24.0, 50.0), "I take things apart.", ("DISASSEMBLE", {"item_id": "ruby_item"})),
    "Armory (Bow)": (
        (40.0, 50.0),
        "The bow, in your off hand.",
        ("EQUIP_ITEM", {"actor_id": "hero_01", "equipment_id": "w_bow", "index": 1}),
    ),
    "Armory (Dagger)": (
        (-44.0, 50.0),
        "The dagger, in your off hand.",
        ("EQUIP_ITEM", {"actor_id": "hero_01", "equipment_id": "w_dagger", "index": 1}),
    ),
    "Shrine": (
        (-4.0, 0.0),
        "Power flows into you.",
        (
            "GRANT_EXPERIENCE",
            {
                "actor_id": "hero_01",
                "amount": 12000,
                "level_track": "level_curve",
                "points": "stat_points=3,skill_points=1",
            },
        ),
    ),
}


def _world(command, args):
    from asteria.events.program import EventInstruction

    return EventInstruction("WORLD", {"command": command, "args": args})


def world(c):
    from asteria.core import Entity, Transform
    from asteria.events import EventProgram
    from asteria.events.binding import EventBinding, SceneEventBindings
    from asteria.events.program import EventInstruction
    from asteria.runtime.components2d import Interaction2DComponent

    project = c.project
    scene = project.scene(project.startup_scene_id)
    boss = next(e for e in scene.entities() if e.name == "Astral Tyrant")
    boss.name = "Vaelor"
    bindings = project.scene_event_bindings.setdefault(scene.id, SceneEventBindings())
    project.event_programs.unregister("boss_interaction_event")
    project.event_programs.register(
        "boss_interaction_event",
        EventProgram(
            [
                EventInstruction(
                    "DIALOGUE",
                    {"speaker": "Vaelor", "text": "Kneel, or fall. Your choice, knight."},
                ),
                _world("START_ENCOUNTER", {"encounter_id": "boss_room"}),
                EventInstruction("END", {}),
            ],
            name="Vaelor Encounter",
        ),
    )
    for index, (name, ((x, y), line, (command, args))) in enumerate(SERVICES.items()):
        program_id = f"service_{index}"
        project.event_programs.register(
            program_id,
            EventProgram(
                [
                    EventInstruction("DIALOGUE", {"speaker": name, "text": line}),
                    _world(command, args),
                    EventInstruction("END", {}),
                ],
                name=name,
            ),
        )
        entity = scene.add_entity(Entity(name))
        entity.add_component(Transform(x, y))
        interaction = entity.add_component(Interaction2DComponent())
        interaction.event_binding_id = f"service_{index}_binding"
        interaction.event_program_id = program_id
        interaction.local_scope_id = f"service_{index}"
        interaction.range, interaction.require_facing = 28.0, True
        bindings.add(
            EventBinding(
                f"service_{index}_binding",
                entity.id,
                program_id,
                local_scope_id=f"service_{index}",
            )
        )


# -- start state ----------------------------------------------------------------------------------
COMPANIONS = {  # who joins the hero: (job, weapon)
    "hero_02": ("cleric", "w_staff"),
    "hero_03": ("necromancer", "w_staff"),
    "hero_04": ("cultist", "w_dagger"),
}


def _sub(actor_id):
    import trial_classes

    return trial_classes.LINES[actor_id][2]


def game_start(c):
    from asteria.rpg import ProgressionAllocationRuntime
    from asteria.runtime.game_start import GameStartDefinition

    project, db = c.project, c.db
    hero = c.hero_id
    data = project.game_start.to_data()
    rpg = data["rpg_state"]
    # the hero sets out alone: Mira, Vesper and Cael are hired at the guild in Hearthfold
    rpg["party_active_actor_ids"] = [hero]
    rpg["party_actor_ids"] = [hero]
    rpg["party_placements"] = {hero: "slot_1"}
    rpg["progression"]["totals"] = {}
    rpg["actor_snapshots"] = {}
    allocation = ProgressionAllocationRuntime(
        db.progression_graphs.values(),
        balances={
            "ap": 6,
            "stat_points": 0,
            **{f"jp.{j}": 8 for j in ("knight", "duelist", "mystic")},
            **{f"jp.{j}": 0 for j in ADVANCED_JOBS},
        },
    )
    rpg["progression_allocations"] = {hero: allocation.to_data()}
    import trial_classes

    for who, (_name, line, _unused) in trial_classes.LINES.items():  # each companion's own points
        rpg["progression_allocations"][who] = ProgressionAllocationRuntime(
            db.progression_graphs.values(),
            balances={"ap": 2, **{f"jp.{job}": 4 if job == line[0] else 0 for job in line}},
        ).to_data()
    rpg["actor_progression"] = {
        hero: {
            "schema": "asteria.rpg.actor_progression_state",
            "version": 1,
            "level": 1,
            "experience": 0.0,
            "points": {},
            "active_class_ids": ["knight", "duelist"],
            "unlocked_class_ids": ["knight", "duelist", "mystic"],  # the rest: trainers
        },
        **{
            who: {
                "schema": "asteria.rpg.actor_progression_state",
                "version": 1,
                "level": 1,
                "experience": 0.0,
                "points": {},
                "active_class_ids": [job, _sub(who)],  # a main job and a sub job
                "unlocked_class_ids": [job, _sub(who)],
            }
            for who, (job, _weapon) in COMPANIONS.items()
        },
    }

    def instance(equipment_id, owner=hero):
        return {
            "attachments": {},
            "equipment_id": equipment_id,
            "growth": None,
            "instance_id": f"{equipment_id}:{owner}",
            "schema": "asteria.rpg.equipment_instance",
            "version": 2,
        }

    rpg["loadouts"] = {
        hero: {
            "schema": "asteria.rpg.equipment_loadout",
            "version": 1,
            "slots": [
                {"slot_id": "weapon", "capacity": 2, "accepted_tags": []},
                {"slot_id": "armor", "capacity": 1, "accepted_tags": []},
                {"slot_id": "accessory", "capacity": 2, "accepted_tags": []},
                {"slot_id": "form", "capacity": 1, "accepted_tags": []},
            ],
            "equipped": {
                "weapon": [instance("w_sunbrand"), instance("w_dagger")],
                "armor": [instance("a_warden_plate")],
                "accessory": [instance("a_warden_ring"), instance("a_warden_charm")],
                "form": [instance("f_normal")],
            },
        },
        **{
            who: {
                "schema": "asteria.rpg.equipment_loadout",
                "version": 1,
                "slots": [
                    {"slot_id": "weapon", "capacity": 1, "accepted_tags": []},
                    {"slot_id": "armor", "capacity": 1, "accepted_tags": []},
                    {"slot_id": "accessory", "capacity": 1, "accepted_tags": []},
                ],
                "equipped": {"weapon": [instance(weapon, who)], "armor": [], "accessory": []},
            }
            for who, (_job, weapon) in COMPANIONS.items()
        },
    }
    import trial_items

    counts = {"healing_herb": 8, "ether_leaf": 5}
    for bases, catalysts in trial_items.ALCHEMY.values():
        for item_id in (*bases, *catalysts):
            counts[item_id] = 8
    for _name, (base, catalyst), _ability, _target in trial_items.CONCOCTIONS.values():
        counts[base] = counts[catalyst] = max(counts.get(base, 0), 8)
    for item_id in db.items:
        if item_id.endswith("_item"):
            counts[item_id] = 3 if item_id.startswith("card") else 2
    rpg["inventory"]["counts"] = counts
    rpg["currencies"] = {"gold": 6000.0}
    rpg["pets"], rpg["active_pet_id"] = [], None
    project.game_start = GameStartDefinition.from_data(data)


FX_BY_ABILITY = {  # skills whose look is chosen by hand; the rest follow their damage tags
    "shield_bash": ("circ",),
    "guard_stance": ("shield",),
    "cleave": ("slash2",),
    "rally": ("aura",),
    "bloodletting": ("claw",),
    "vampiric_strike": ("slash", "spirit"),
    "executioner": ("cutx", "cutx"),
    "bastion": ("shield", "boost"),
    "quick_slash": ("cut", "cut"),
    "flurry": ("claw", "clawd", "claw", "clawd", "claw", "clawd"),
    "poison_edge": ("cut", "smoke"),
    "shadow_step": ("smoke",),
    "assassinate": ("cutd",),
    "phantom_dance": ("clawd",) * 4,
    "arcane_barrier": ("shield",),
    "drain_touch": ("spirit",),
    "curse": ("circle",),
    "donate_bp": ("boost",),
    "sunburst": ("slash", "spark", "spark"),
    "w_combo": ("slash2",),
    "w_charge": ("circ",),
    "w_poison": ("clawd", "smoke"),
    "w_cinder": ("fire",),
    "w_roar": ("thunder", "thunder"),
    "w_mark": ("spirit", "circle"),
    "w_eclipse": ("spirit", "fire", "spirit", "explosion"),
    "w_cry": ("aura",),
    "w_iron": ("shield",),
    "w_summon": ("circle",),
    "w_mend": ("boost",),
    "w_drain": ("spirit",),
}
SELF_TARGETED = {
    "guard_stance",
    "rally",
    "bastion",
    "shadow_step",
    "arcane_barrier",
    "mend",
    "donate_bp",
    "w_cry",
    "w_iron",
    "w_summon",
    "w_mend",
}
ELEMENT_FX = (
    ("damage.fire", "fire"),
    ("damage.ice", "ice"),
    ("damage.lightning", "thunder"),
    ("damage.light", "spark"),
    ("damage.dark", "spirit"),
)
WEAPON_FX = (
    ("sword", "slash"),
    ("axe", "circ"),
    ("dagger", "cut"),
    ("spear", "cutx"),
    ("bow", "cutd"),
    ("staff", "spirit"),
)


def _fx_plan(ability_id, definition):
    """The effect sheets a skill shows, one per hit: its own, else by element, else by weapon."""
    if ability_id in FX_BY_ABILITY:
        return FX_BY_ABILITY[ability_id]
    elements = dict(ELEMENT_FX)
    per_hit = []
    for hit in definition.hits or ():
        tags = [t for t in hit["tags"] if t in elements]
        if tags:
            per_hit.append(elements[tags[0]])
    if len(set(per_hit)) > 1 or (per_hit and len(per_hit) == len(definition.hits)):
        return tuple(per_hit)
    for tag, key in ELEMENT_FX:
        if tag in definition.tags:
            return (key,)
    for kind, key in WEAPON_FX:
        if f"weapon.{kind}" in definition.tags:
            return (key,)
    return None


def _apply_fx(beats, ability_id, definition, source):
    from asteria.presentation.battle_motion_sequence import BattleMotionBeat

    plan = _fx_plan(ability_id, definition)
    if not plan:
        return beats
    first = next((b.at for b in beats if b.channel == "vfx"), 0.2)
    keep = tuple(b for b in beats if b.channel != "vfx" or source in ("meteor", "heal"))
    member = "@source" if ability_id in SELF_TARGETED else "@target"
    spacing = 0.09 if len(plan) > 3 else 0.14
    extra = tuple(
        BattleMotionBeat(
            f"fx{i}",
            first + spacing * i,
            "vfx",
            f"battle.fx.{key}",
            member_id=member,
            duration=0.4,
        )
        for i, key in enumerate(plan)
    )
    return tuple(sorted((*keep, *extra), key=lambda b: b.at))


MELEE_TAGS = tuple(f"weapon.{k}" for k in ("sword", "axe", "dagger", "spear"))
MELEE_MOVES = {"w_combo", "w_charge", "w_poison"}


HEAVY_WORDS = ("slam", "cleave", "crush", "hammer", "bash", "charge", "strike", "smash", "bulwark")


def _attack_clip(ability_id, definition):
    """Which of a character's three attack animations a skill plays: the plain swing (a weapon
    attack), the second strip for casting - spells, buffs, gaining an ability, healing and
    support - and the third for the big finishers and the heavy blows (divine skills, many
    hits, slams and axes)."""
    hits = len(definition.hits or ())
    if "divine" in definition.tags or hits >= 3:
        return "attack3"
    if "weapon.axe" in definition.tags or any(w in ability_id for w in HEAVY_WORDS):
        return "attack3"
    if ability_id in SELF_TARGETED or "magic" in definition.tags:
        return "attack2"
    return "attack"


def _apply_attack_clip(beats, ability_id, definition):
    """The user's animation beat plays the skill's own attack clip (Lucifer sheets have three)."""
    clip = _attack_clip(ability_id, definition)
    if clip == "attack":
        return beats
    return tuple(
        dataclasses.replace(b, cue=clip)
        if b.channel == "animation" and b.cue == "attack" and b.member_id == "@source"
        else b
        for b in beats
    )


def _apply_lunge(beats, ability_id, definition):
    """Melee skills step up to the foe, strike and step back (the ``move`` channel)."""
    from asteria.presentation.battle_motion_sequence import BattleMotionBeat

    melee = ability_id in MELEE_MOVES or any(t in definition.tags for t in MELEE_TAGS)
    if not melee or ability_id in SELF_TARGETED:
        return beats
    end = max((b.at for b in beats), default=0.6)
    go = BattleMotionBeat(
        "advance",
        0.0,
        "move",
        "advance",
        member_id="@source",
        duration=0.16,
        easing="ease_out",
    )
    back = BattleMotionBeat(
        "return",
        end + 0.05,
        "move",
        "return",
        member_id="@source",
        duration=0.2,
        easing="ease_in_out",
    )
    return tuple(sorted((go, *beats, back), key=lambda b: b.at))


def presentation(c):
    """Motion sequences for every skill, and the side-view layout of the demo."""
    from asteria.presentation.battle_hud import BattleHudResourceStyle
    from asteria.presentation.particles import particle_effect_asset, preset

    project, abilities = c.project, c.abilities
    sequences = project.battle_presentation_library
    burst = particle_effect_asset(
        preset("explosion", "fx.divine_burst").replace(burst=120, color_start=(255, 215, 120, 255))
    )
    sparkle = particle_effect_asset(preset("heal", "fx.restore"))
    for asset in (burst, sparkle):
        project.assets.register(asset, replace=True)
    bases = {
        k: sequences.require("motion_sequences", k)
        for k in ("strike", "fire_arc", "heal", "meteor")
    }
    for ability_id in abilities.ids():
        definition = abilities.get(ability_id)
        if "divine" in definition.tags:
            source = "meteor"
        elif any(t.startswith("damage.") for t in definition.tags) and "magic" in definition.tags:
            source = "fire_arc"
        elif ability_id in {
            "mend",
            "rally",
            "guard_stance",
            "arcane_barrier",
            "bastion",
            "shadow_step",
            "donate_bp",
            "w_iron",
            "w_cry",
            "w_mend",
        }:
            source = "heal"
        else:
            source = "strike"
        base = bases[source]
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
        beats = _apply_fx(beats, ability_id, definition, source)
        beats = _apply_lunge(beats, ability_id, definition)
        beats = _apply_attack_clip(beats, ability_id, definition)
        sequences.set("motion_sequences", ability_id, dataclasses.replace(base, beats=beats))
    layout = sequences.require("ui_layout", "adaptive")
    sequences.set(
        "ui_layout",
        "adaptive",
        dataclasses.replace(
            layout,
            party_hud="side_list",
            action_menu_placement="actor_bottom_right",  # the menu touches whoever acts
            hud_panel_width=108.0,
            stage_top=0.47,  # feet stay on the grass: the backdrop's wall is the top 44%
            stage_front=0.16,
            hidden_zones=(),  # foes show their name over the head, as in every demo
            overhead_bars=False,  # their health stays hidden (the bestiary tells it)
            front_large_zones=("right",),  # a summon stands left of the party, toward the foe
            menu_over_stage=True,  # the command menu stands beside the acting hero, see-through
            column_size=2,  # four heroes stand two by two: tall sprites do not fit four in a row
        ),
    )
    hud = sequences.require("hud", "adaptive")
    sequences.set(
        "hud",
        "adaptive",
        dataclasses.replace(
            hud,
            resources=(
                *hud.resources,
                BattleHudResourceStyle(
                    "bp", "BP", order=9, presentation="pips", segments=5, show_value=False
                ),
                BattleHudResourceStyle("shield", "SH", order=10, visible=False),
            ),
            show_unmapped_statuses=True,
        ),
    )


def write_manifest(c):
    manifest = json.loads(
        (c.root.parent / "complex_reference_rpg" / "playable_test_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    manifest["title"] = "Full Verification Demo"
    audio = getattr(c, "audio", None)
    if audio:  # the Lucifer campaign has its own music
        manifest["audio"].update(audio)
        manifest["field"]["bgm"] = "town_theme"
        manifest["battle"]["bgm"] = "battle_theme"
    manifest["battle"]["victory_aftermath"] = True
    sprites = manifest["field"]["entity_sprites"]
    sprites["Vaelor"] = sprites.pop(
        "Astral Tyrant", {"sprite": "playable_assets/boss_field.png", "size": [96, 96]}
    )
    for name in SERVICES:
        slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")
        sprites[name] = {"sprite": f"playable_assets/npc_{slug}.png", "size": [40, 40]}
    order = [k for k in c.skill_names]
    manifest["battle"]["skills"] = {a: {"label": c.skill_names[a]} for a in order}
    battle = manifest["battle"]
    battle["heroes"] = ["playable_assets/hero_01_battle.png"] * 2
    battle["enemy_sprites"] = {}
    battle["enemy_layouts"] = {}
    manifest["battle"]["command_style"] = "root"
    (c.root / "playable_test_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def finalize_names(c):
    """Every skill and status carries its player-facing name in the project data (editable in
    the Database), not only in the playtest manifest."""
    abilities = c.abilities._definitions
    for ability_id, definition in list(abilities.items()):
        if definition.display_name:
            continue
        name = c.skill_names.get(ability_id) or ability_id.replace("_", " ").title()
        abilities[ability_id] = dataclasses.replace(definition, display_name=name)
    states = c.library.states._definitions
    for state_id, state in list(states.items()):
        if not state.display_name:
            states[state_id] = dataclasses.replace(
                state, display_name=state_id.replace("_", " ").title()
            )
