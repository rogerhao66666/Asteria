"""Stats with written formulas: STR / DEX / INT / LUK the player spends points on, the stats they
become, physical and magic defence, accuracy against evasion, critical rate and damage, and an
attack and a resistance per element on gear, accessories, gems, cards and foes.

Every number lives in project data the editor shows: Game Systems > Stat Formulas (derived
stats), Battle > Chance Checks (accuracy, critical) and Interactions (critical damage, element
attack / resistance), the Attributes tree, the jobs' level growth, the gear's modifiers.

* **Attributes** (the Attributes tree, one stat point a rank): STR, DEX, INT, LUK (and VIT for
  health, Twin Arts for STR + INT). Each actor starts with its own and every job grows them.
* **Formulas** (added to what gear, jobs, trees and passives give):

  ======================  ===============================================
  physical attack         power += 2 STR + 0.5 DEX
  magic attack            magic += 2 INT + 0.5 LUK
  physical defence        defense += 1 STR + 0.5 DEX
  magic defence           magic_defense += 1 INT + 0.5 LUK + 0.5 defense
  accuracy                accuracy += 1 DEX + 0.5 LUK
  evasion                 evade += 0.5 DEX + 1 LUK
  critical rate           crit += 0.5 LUK + 0.2 DEX
  critical damage         crit_damage += 0.3 LUK + 0.1 STR  (percent)
  speed                   speed += 0.3 DEX
  ======================  ===============================================

* **Checks**: a blow lands 95% + 0.3% x attacker accuracy - 0.3% x target evasion (30% to
  100%); a critical blow 5% + 0.3% x crit (at most 65%) and deals x(2 + 1% x crit_damage).
* **Two axes**: a skill is physical (power against defence) or magic (magic against magic
  defence) - and, apart from that, of an element or of none. Physical fire, magic fire, plain
  physical and plain magic all exist; every skill's description says which.
* **Elements**: <element>_attack and <element>_resist per element: a blow of that element deals
  x(1 + 1% x attack - 1% x the target's resistance). Weapons, armour, accessories, gems, cards
  and charms raise them; foes have their own.
"""

from __future__ import annotations

import dataclasses

import trial_brave as brave
import trial_content as tc

from asteria.gameplay.formulas import ValueFormula
from asteria.rpg import InteractionRule
from asteria.rpg.derived_stats import DerivedStatRule

HP, SP = tc.HP, tc.SP
ELEMENTS = tuple(brave.ELEMENTS)
ATTRIBUTES = {"str": "STR", "dex": "DEX", "int": "INT", "luk": "LUK"}

FORMULAS = (  # (stat, name, terms, order, description)
    ("power", "Physical Attack", {"str": 2.0, "dex": 0.5}, 0, "Physical blows deal more"),
    ("magic", "Magic Attack", {"int": 2.0, "luk": 0.5}, 0, "Spells deal and heal more"),
    ("defense", "Physical Defence", {"str": 1.0, "dex": 0.5}, 0, "Less from physical blows"),
    (
        "magic_defense",
        "Magic Defence",
        {"int": 1.0, "luk": 0.5, "defense": 0.5},
        1,  # after Physical Defence: half of it (armour included) guards against spells
        "Less from spells",
    ),
    ("accuracy", "Accuracy", {"dex": 1.0, "luk": 0.5}, 0, "+0.3% to land a blow a point"),
    ("evade", "Evasion", {"dex": 0.5, "luk": 1.0}, 0, "-0.3% to be hit a point"),
    ("crit", "Critical Rate", {"luk": 0.5, "dex": 0.2}, 0, "+0.3% critical chance a point"),
    ("crit_damage", "Critical Damage", {"luk": 0.3, "str": 0.1}, 0, "+1% critical damage"),
    ("speed", "Speed", {"dex": 0.3}, 0, "Acts sooner and more often"),
)

ACTOR_ATTRIBUTES = {  # actor: STR, DEX, INT, LUK at level 1
    "hero_01": (12, 8, 10, 6),  # Aldric: a Brave who casts
    "hero_02": (4, 6, 14, 8),  # Mira
    "hero_03": (5, 6, 13, 8),  # Vesper
    "hero_04": (8, 12, 4, 12),  # Cael
    "spirit_knight": (10, 8, 5, 5),
}

ATTRIBUTE_CHARMS = ("charm_lion", "charm_owl", "charm_falcon", "charm_viper", "charm_serpent")
ELEMENT_GEAR = {  # gear / attachment: {stat: amount} (an attribute charm's replace its old ones)
    "w_sunbrand": {"light_attack": 10},
    "w_sunbrand_ex": {"light_attack": 25},
    "w_ash_staff": {"fire_attack": 15},
    "w_saint_staff": {"light_attack": 20},
    "w_bone_scepter": {"dark_attack": 20},
    "w_dragoon_lance": {"wind_attack": 15},
    "w_war_axe": {"earth_attack": 15},
    "w_longbow": {"wind_attack": 10},
    "w_ritual_kris": {"dark_attack": 15},
    "w_demon_ring": {f"{e}_attack": 10 for e in ELEMENTS},
    "a_dawn_robe": {"light_resist": 20, "fire_resist": 10, "magic_defense": 18},
    "a_grave_shroud": {"dark_resist": 25, "magic_defense": 14},
    "a_silk_robe": {"ice_resist": 15, "lightning_resist": 15, "magic_defense": 16},
    "a_linen_robe": {"magic_defense": 8},
    "a_knight_plate": {"earth_resist": 15},
    "a_zealot_mail": {"fire_resist": 20},
    "a_shadow_garb": {"dark_resist": 15, "wind_resist": 10},
    "a_leather_vest": {"wind_resist": 10},
    "a_chain_mail": {"lightning_resist": 10},
    "a_ruby_ring": {"fire_attack": 15},
    "a_moon_pendant": {"ice_attack": 15, "dark_resist": 10, "magic_defense": 8},
    "a_holy_symbol": {"light_attack": 15, "dark_resist": 15, "magic_defense": 10},
    "a_feather_charm": {"wind_attack": 15},
    "a_iron_ring": {"earth_resist": 20},
    "a_life_amulet": {**{f"{e}_resist": 5 for e in ELEMENTS}, "magic_defense": 10},
    "a_phylactery": {"dark_attack": 20},
    "a_warden_ring": {"lightning_resist": 20},
    "a_blood_amulet": {"fire_attack": 10},
    "a_hawk_eye": {"accuracy": 15},
    "a_warden_charm": {"crit_damage": 20},
    "ruby": {"fire_attack": 8},
    "flawless_ruby": {"fire_attack": 16},
    "sapphire": {"ice_attack": 8},
    "flawless_sapphire": {"ice_attack": 16},
    "topaz": {"lightning_attack": 8},
    "flawless_topaz": {"lightning_attack": 16},
    "emerald": {"wind_attack": 8},
    "flawless_emerald": {"wind_attack": 16},
    "diamond": {"earth_resist": 10, "magic_defense": 6},
    "flawless_diamond": {"earth_resist": 20, "magic_defense": 12},
    "amethyst": {"dark_attack": 8},
    "flawless_amethyst": {"dark_attack": 16},
    "card_ancient": {"dark_resist": 30},
    "card_acolyte": {"magic_defense": 8, "fire_resist": 15},
    "card_beast": {"earth_attack": 15},
    "card_hunter": {"accuracy": 20},
    "card_slayer": {"crit_damage": 25},
    "card_vaelor": {"fire_resist": 20},
    "charm_lion": {"str": 15},
    "charm_owl": {"int": 15},
    "charm_falcon": {"dex": 15},
    "charm_viper": {"luk": 15},
    "charm_serpent": {"str": 9, "int": 9},
    "charm_tortoise": {"magic_defense": 20},
}

FOE_STATS = {  # foe: (magic defence x its defence, accuracy, {element stat: amount})
    "goblin_slinger": (0.6, 20, {"wind_attack": 10}),
    "skeleton_hunter": (0.7, 25, {"dark_resist": 20, "light_resist": -20}),
    "mender_wisp": (1.5, 15, {"fire_attack": 20, "ice_resist": -20}),
    "goblin_beast": (0.5, 35, {"fire_attack": 20, "earth_resist": 30, "ice_resist": -15}),
    "skeleton_ancient": (1.5, 40, {"dark_attack": 30, "light_resist": -30, "ice_resist": 20}),
    "crimson_warlord": (
        1.0,
        50,
        {"fire_attack": 30, "dark_attack": 20, "fire_resist": 40, "light_resist": -10},
    ),
    "vigil_acolyte": (1.2, 20, {"fire_attack": 15}),
}

# more kinds of extra effects on the party's skills: (state, to) added to the skill
EXTRAS = {
    "valiant_slash": (("defense_down", "targets"),),
    "heroic_lance": (("bleed", "targets"),),
    "gigaslash": (("power_down", "targets"),),
    "dragon_slayer": (("armor_up", "self"),),
    "arsenal_storm": (("slow", "targets"),),
    "lightbringer": (("regen", "self"),),
    "fire_bolt": (("burn", "targets"),),
    "ice_bolt": (("freeze", "targets"),),
    "lightning_bolt": (("stun", "targets"),),
    "light_bolt": (("blind", "targets"),),
    "dark_bolt": (("silence", "targets"),),
    "wind_bolt": (("haste", "self"),),
    "earth_bolt": (("defense_down", "targets"),),
    "mana_shield": (("mirror", "self"),),
    "arcane_surge": (("focus", "self"),),
}
DRAINS = {"dark_storm": 0.25, "dark_bolt": 0.15}  # magic: drains this share of magic as SP

STATE_NAMES = {
    "defense_down": "Defence Down", "power_down": "Power Down", "magic_down": "Magic Down",
    "armor_up": "Armour Up", "attack_up": "Attack Up", "magic_up": "Magic Up",
    "evasion_up": "Evasion Up", "swift_feet": "Swift Feet", "keen_mind": "Keen Mind",
    "lifelink": "Lifelink", "stoneskin": "Stoneskin", "counter_stance": "Counter Stance",
}  # fmt: skip


def stats(c):
    """The whole stat system: attributes, formulas, checks, elements, foes, descriptions."""
    _attributes(c)
    _formulas(c)
    _checks(c)
    _elements(c)
    _magic_defence(c)
    _foes(c)
    _extras(c)
    describe(c)
    _status_screen(c)


# -- attributes ------------------------------------------------------------------------------
def _attributes(c):
    """STR / DEX / INT / LUK: each actor's own, grown by every job, spent in the Attributes
    tree; the jobs' old attack growth turns into attribute growth."""
    db = c.db
    for actor_id, values in ACTOR_ATTRIBUTES.items():
        actor = db.actors[actor_id]
        base = {**actor.base_stats, **dict(zip(ATTRIBUTES, map(float, values)))}
        db.actors[actor_id] = dataclasses.replace(actor, base_stats=base)
    for class_id, job in list(db.classes.items()):
        growth = dict(job.level_growth)
        if not growth:
            continue
        power, magic = growth.pop("power", 0.0), growth.pop("magic", 0.0)
        speed, crit, evade = (growth.get(k, 0.0) for k in ("speed", "crit", "evade"))
        attributes = {
            "str": round(power / 2, 2),
            "int": round(magic / 2, 2),
            "dex": round(0.4 + speed * 0.5, 2),
            "luk": round(0.3 + (crit + evade) * 3, 2),
        }
        growth.update({k: v for k, v in attributes.items() if v})
        db.classes[class_id] = dataclasses.replace(job, level_growth=growth)
    node, points = tc._node, {"stat_points": 1}

    def bonus(**values):
        return {"stat_bonuses": values}

    int_reward = {**bonus(int=1), "resource_bonuses": {SP: 4}}
    nodes = (
        node("attr_str", "STR (Strength)", 30, points, bonus(str=1)),
        node("attr_dex", "DEX (Dexterity)", 30, points, bonus(dex=1)),
        node("attr_int", "INT (Intellect)", 30, points, int_reward),
        node("attr_luk", "LUK (Luck)", 30, points, bonus(luk=1)),
        node("attr_vit", "VIT (Vitality)", 30, points, {"resource_bonuses": {HP: 70}}),
        node("attr_twin", "Twin Arts (STR + INT)", 30, points, bonus(str=0.5, int=0.5)),
    )  # fmt: skip
    graph = db.progression_graphs["attributes"]
    tags = tuple(dict.fromkeys((*graph.tags, "shared")))  # every hero's tree screen shows it
    db.progression_graphs["attributes"] = dataclasses.replace(graph, nodes=nodes, tags=tags)


def _formulas(c):
    for stat, name, terms, order, text in FORMULAS:
        rule = DerivedStatRule(stat, name, terms=terms, order=order, description=text)
        c.db.derived_stats[stat] = rule


# -- chance checks and critical damage -------------------------------------------------------
def _checks(c):
    db = c.db
    checks = db.outcome_checks
    land = checks["land"]
    checks["land"] = dataclasses.replace(
        land,
        base_chance=0.95,
        source_stat_terms={"accuracy": 0.003},
        target_stat_terms={"evade": -0.003},
        minimum_chance=0.3,
        maximum_chance=1.0,
    )
    # a shield blocks blows, not spells
    checks["block"] = dataclasses.replace(checks["block"], blocked_source_tags=("magic",))
    checks["crit"] = dataclasses.replace(
        checks["crit"], base_chance=0.05, source_stat_terms={"crit": 0.003}, maximum_chance=0.65
    )
    db.interaction_rules["crit_x"] = dataclasses.replace(
        db.interaction_rules["crit_x"],
        multiplier=2.0,
        multiplier_source_terms={"crit_damage": 0.01},
    )


def _elements(c):
    """Element attack / resistance stats: rules, gear, gems, cards, charms."""
    db = c.db
    for element in ELEMENTS:
        db.interaction_rules[f"element_{element}"] = InteractionRule(
            f"element_{element}",
            source_tags_all=(f"damage.{element}",),
            multiplier_source_terms={f"{element}_attack": 0.01},
            multiplier_target_terms={f"{element}_resist": -0.01},
            priority=1,
        )
    for record_id, values in ELEMENT_GEAR.items():
        store = db.equipment if record_id in db.equipment else db.attachments
        record = store[record_id]
        keep = record_id not in ATTRIBUTE_CHARMS
        modifiers = [m for m in record.modifiers if keep and m.stat not in values]
        modifiers += [
            tc._modifier(stat, float(amount), f"{record_id}.{stat}")
            for stat, amount in values.items()
        ]
        store[record_id] = dataclasses.replace(record, modifiers=tuple(modifiers))


def _magic_defence(c):
    """A blow's user stat picks the defence: power against defence, magic against magic
    defence (a twin formula keeps both)."""
    for ability_id, definition in list(c.abilities._definitions.items()):
        changed = False
        effects = []
        for effect in definition.effects:
            operations = []
            for operation in effect.effect.operations:
                value = operation.value
                if isinstance(value, ValueFormula):
                    sources = {t.key for t in value.terms if t.source.value == "source_stat"}
                    if sources == {"magic"}:
                        terms = tuple(
                            dataclasses.replace(t, key="magic_defense")
                            if t.source.value == "target_stat" and t.key == "defense"
                            else t
                            for t in value.terms
                        )
                        if terms != value.terms:
                            value = dataclasses.replace(value, terms=terms)
                            operation = dataclasses.replace(operation, value=value)
                            changed = True
                operations.append(operation)
            effects.append(
                dataclasses.replace(
                    effect, effect=dataclasses.replace(effect.effect, operations=tuple(operations))
                )
            )
        if changed:
            c.abilities._definitions[ability_id] = dataclasses.replace(
                definition, effects=tuple(effects)
            )


def _foes(c):
    db = c.db
    for enemy_id, (ratio, accuracy, elements) in FOE_STATS.items():
        enemy = db.enemies[enemy_id]
        values = {
            **enemy.stats,
            "magic_defense": round(enemy.stats.get("defense", 0.0) * ratio, 1),
            "accuracy": float(accuracy),
            **{k: float(v) for k, v in elements.items()},
        }
        db.enemies[enemy_id] = dataclasses.replace(enemy, stats=values)
    for rules_id, rules in list(db.enemy_level_rules.items()):
        growth = dict(rules.stat_growth)
        growth.update({"magic_defense": growth.get("defense", 0.04), "accuracy": 0.02})
        db.enemy_level_rules[rules_id] = dataclasses.replace(
            rules, stat_growth=tuple(sorted(growth.items()))
        )


# -- more kinds of extra effects ---------------------------------------------------------------
def _extras(c):
    from asteria.gameplay import Effect
    from asteria.gameplay.abilities import AbilityEffect
    from asteria.gameplay.formulas import FormulaTerm

    definitions = c.abilities._definitions
    for ability_id, extras in EXTRAS.items():
        definition = definitions.get(ability_id)
        if definition is None:
            continue
        have = {(s["state"], s["to"]) for s in definition.apply_states}
        extra = [tc._state(s, to) for s, to in extras if (s, to) not in have]
        definitions[ability_id] = dataclasses.replace(
            definition, apply_states=[*definition.apply_states, *extra]
        )
    for ability_id, share in DRAINS.items():
        definition = definitions.get(ability_id)
        if definition is None:
            continue
        drain = ValueFormula((FormulaTerm("source_stat", "magic", share),), minimum=1.0)
        steal = ValueFormula((FormulaTerm("source_stat", "magic", -share),), maximum=-1.0)
        effects = (
            *definition.effects,
            AbilityEffect("selected", Effect(f"{ability_id}.sap", (tc.op(steal, SP),))),
            AbilityEffect("self", Effect(f"{ability_id}.drink", (tc.op(drain, SP),))),
        )
        definitions[ability_id] = dataclasses.replace(definition, effects=effects)


# -- descriptions ------------------------------------------------------------------------------
def _kind(definition):
    """``("Physical" | "Magic" | "Physical + Magic" | "Healing" | "Support", elements)``."""
    harm, heal = set(), False
    for effect in definition.effects:
        for operation in effect.effect.operations:
            value = operation.value
            if operation.target != HP or not isinstance(value, ValueFormula):
                continue
            for term in value.terms:
                if term.source.value != "source_stat":
                    continue
                if term.coefficient < 0:
                    harm.add(term.key)
                elif effect.mode.value != "self" or not harm:
                    heal = True
    elements = [t.split(".", 1)[1] for t in definition.tags if t.startswith("damage.")]
    if harm:
        order = {"power": (0, "Physical"), "magic": (1, "Magic")}
        names = [n for _, n in sorted(order.get(k, (2, k.title())) for k in harm)]
        kind_text = " + ".join(names)
    elif heal:
        kind_text = "Healing"
    else:
        kind_text = "Support"
    return kind_text, elements


def _state_name(state_id):
    return STATE_NAMES.get(state_id) or state_id.replace("_", " ").title()


def describe(c):
    """Every skill says what it is - physical or magic, which element (or none) - and what it
    does besides damage, as its description (shown in the battle menu)."""
    definitions = c.abilities._definitions
    for ability_id, definition in list(definitions.items()):
        kind, elements = _kind(definition)
        if kind not in ("Healing", "Support"):
            if definition.forms:
                element = "Element by form"
            elif elements:
                element = " + ".join(e.title() for e in elements)
            else:
                element = "Non-elemental"
            head = f"{kind} / {element}"
        else:
            head = kind + (f" / {' + '.join(e.title() for e in elements)}" if elements else "")
        parts = [head]
        targets = definition.targeting.maximum_targets
        if targets and targets > 1:
            parts.append("all foes" if kind != "Healing" else "all allies")
        if len(definition.hits) > 1:
            parts.append(f"{len(definition.hits)} hits")
        inflicts = [_state_name(s["state"]) for s in definition.apply_states if s["to"] != "self"]
        buffs = [_state_name(s["state"]) for s in definition.apply_states if s["to"] == "self"]
        if inflicts:
            parts.append("inflicts " + ", ".join(dict.fromkeys(inflicts)))
        if buffs:
            parts.append("user gains " + ", ".join(dict.fromkeys(buffs)))
        if any(e.effect.effect_id.endswith(".sap") for e in definition.effects):
            parts.append("drains SP")
        elif any(e.mode.value == "self" for e in definition.effects) and kind != "Healing":
            parts.append("heals the user")
        text = head if len(parts) == 1 else f"{head}: " + ", ".join(parts[1:])
        definitions[ability_id] = dataclasses.replace(definition, description=text)


def _status_screen(c):
    """The status screen names every stat and lists them in reading order: attributes, attack
    and defence, accuracy and evasion, criticals, speed, then element attack / resistance."""
    library = c.project.battle_presentation_library
    labels = {key: f"{name}" for key, name in ATTRIBUTES.items()}
    labels.update({stat: name for stat, name, *_ in FORMULAS})
    labels["lifesteal"] = "Lifesteal"
    for element in ELEMENTS:
        labels[f"{element}_attack"] = f"{element.title()} Attack %"
        labels[f"{element}_resist"] = f"{element.title()} Resist %"
    labels["crit_damage"] = "Critical Damage %"
    order = (
        *ATTRIBUTES,
        *(stat for stat, *_ in FORMULAS),
        "lifesteal",
        *(f"{e}_{kind}" for e in ELEMENTS for kind in ("attack", "resist")),
    )
    for profile_id in library.ids("rpg_character_screen"):
        profile = library.require("rpg_character_screen", profile_id)
        library.set(
            "rpg_character_screen",
            profile_id,
            dataclasses.replace(
                profile,
                stat_labels=tuple(sorted(labels.items())),
                stat_order=order,
                resource_labels=(*profile.resource_labels, (HP, "HP"), (SP, "SP")),
            ),
        )
