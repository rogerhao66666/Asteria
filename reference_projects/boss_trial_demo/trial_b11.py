"""Second skill wave of the Boss Trial: ailments that take the choice away, buffs and debuffs,
skills that cost something other than technique points (health, items, gold, boost points), one
skill cast as several elements or weapons, boost points handed to a friend, and a companion.

Everything here is plain data on the same records the first wave uses, so the editor shows and
edits it the same way (Database > Game Data > Abilities / Status Definitions / Classes).
"""

from __future__ import annotations

import dataclasses

import trial_content as tc

from asteria.gameplay import Effect, EffectOperation, EffectOperationKind
from asteria.gameplay.abilities import AbilityCost
from asteria.gameplay.formulas import FormulaTerm, ValueFormula
from asteria.gameplay.modifiers import StatModifier
from asteria.gameplay.states import StateDefinition
from asteria.rpg import BattleStatePolicy, ClassDefinition

HP, SP, BP = tc.HP, tc.SP, tc.BP
ability, op, damage, healing = tc.ability, tc.op, tc.damage, tc.healing
_hits, _state, _with_self = tc._hits, tc._state, tc._with_self
WEAPON_TAGS = tuple(f"weapon.{k}" for k in tc.WEAPONS)
FOLLOW_WEAPON = {f"equip.{k}": f"weapon.{k}" for k in tc.WEAPONS}  # one skill, any weapon
COMPANION_ID = "hero_02"
COMPANION_CLASS = "cleric"
TICK = "rpg.battle.turn_ended"


def flat(amount):
    """A fixed amount (no stat in it): for costs and heals the author wants to read at a glance."""
    return ValueFormula((FormulaTerm("constant", "", float(amount)),))


def cost(resource, amount):
    return AbilityCost(resource, amount)


def forms(*specs):
    """``(form_id, label, tags, power)``: one way to cast a skill each."""
    return [
        {"form_id": i, "label": label, "tags": list(tags), "power": power}
        for i, label, tags, power in specs
    ]


def new_states(c):
    """Ailments that act on the player's choice, and the buffs / debuffs the skills hand out."""
    library, db = c.library, c.db
    states, policies = library.states._definitions, db.battle_state_policies
    mod = StatModifier

    def put(state, policy):
        states[state.state_id] = state
        policies[policy.state_id] = policy

    # the target is picked for you, whatever you chose
    put(
        StateDefinition("confuse", 3, contributed_tags=("status.confuse",)),
        BattleStatePolicy(
            "confuse", base_chance=0.7, tick_trigger=TICK, target_override="random_any"
        ),
    )
    put(
        StateDefinition("charm", 3, contributed_tags=("status.charm",)),
        BattleStatePolicy(
            "charm", base_chance=0.7, tick_trigger=TICK, target_override="random_ally"
        ),
    )
    # only weapon attacks, always at a foe
    put(
        StateDefinition("berserk", 3, contributed_tags=("status.berserk", "stance.fury")),
        BattleStatePolicy(
            "berserk",
            base_chance=0.8,
            tick_trigger=TICK,
            allowed_ability_tags=WEAPON_TAGS,
            target_override="random_opponent",
        ),
    )
    # death when it runs out; bosses are immune
    kill = EffectOperation(EffectOperationKind.RESOURCE_SET, HP, 0.0)
    put(
        StateDefinition(
            "doom", 3, contributed_tags=("status.doom",), on_expire=(Effect("doom.kill", (kill,)),)
        ),
        BattleStatePolicy(
            "doom", base_chance=0.8, tick_trigger=TICK, immune_target_tags=("boss",)
        ),
    )
    # a blinded attacker misses (the "land" check reads the attacker's accuracy)
    put(
        StateDefinition("blind", 3, modifiers=(mod("blind", "accuracy", "add", -70.0),)),
        BattleStatePolicy("blind", base_chance=0.85, tick_trigger=TICK),
    )
    for state_id, stat, how, value in (
        ("slow", "speed", "multiply", 0.5),
        ("magic_down", "magic", "multiply", 0.6),
        ("armor_up", "defense", "multiply", 1.6),
        ("swift_feet", "evade", "add", 30.0),
        ("keen_mind", "crit", "add", 25.0),
    ):
        put(
            StateDefinition(state_id, 3, modifiers=(mod(state_id, stat, how, value),)),
            BattleStatePolicy(
                state_id,
                tick_trigger=TICK,
                **({"base_chance": 0.85} if state_id in ("slow", "magic_down") else {}),
            ),
        )
    put(
        StateDefinition("enchant_dark", 5, contributed_tags=("damage.dark",)),
        BattleStatePolicy("enchant_dark", tick_trigger=TICK),
    )
    # the attacker's accuracy: a plain stat (0 unless a state moves it)
    land = db.outcome_checks["land"]
    db.outcome_checks["land"] = dataclasses.replace(
        land, source_stat_terms={**land.source_stat_terms, "accuracy": 0.01}
    )


def _skills(c):
    """The second wave: (job, id, label, target, definition, divine)."""
    a = ability
    elements = {
        "fire": ("Fire", ("damage.fire",), 1.0),
        "ice": ("Ice", ("damage.ice",), 1.0),
        "lightning": ("Lightning", ("damage.lightning",), 1.0),
        "light": ("Light", ("damage.light",), 1.0),
        "dark": ("Dark", ("damage.dark",), 1.0),
    }

    def element_forms(*names):
        return forms(*((n, elements[n][0], elements[n][1], elements[n][2]) for n in names))

    weapon_master = [
        (
            "versatile_strike",
            "Versatile Strike",
            "enemy",
            a(
                "versatile_strike",
                effect=op(damage("power", 11)),
                sp=10,
                follow_tags=FOLLOW_WEAPON,
                hits=_hits(1.0, 1.0),
            ),
        ),
        (
            "elemental_edge",
            "Elemental Edge",
            "enemy",
            a(
                "elemental_edge",
                tags=("weapon.sword",),
                effect=op(damage("power", 12)),
                sp=12,
                hits=_hits(1.0, 1.2, tags=("weapon.sword",)),
                forms=element_forms("fire", "ice", "lightning", "dark"),
            ),
        ),
        (
            "cripple",
            "Cripple",
            "enemy",
            a(
                "cripple",
                tags=("weapon.dagger",),
                effect=op(damage("power", 6)),
                sp=14,
                hits=_hits(1.0, tags=("weapon.dagger",)),
                apply_states=[_state("slow"), _state("defense_down")],
            ),
        ),
        (
            "war_cry",
            "War Cry",
            "allies",
            a(
                "war_cry",
                sp=18,
                cooldown_turns=4,
                apply_states=[_state("attack_up", "allies"), _state("keen_mind", "allies")],
            ),
        ),
    ]
    sage = [
        (
            "arcane_tome",
            "Arcane Tome",
            "enemy",
            a(
                "arcane_tome",
                tags=("magic",),
                effect=op(damage("magic", 9)),
                sp=16,
                hits=_hits(1.0, 1.0),
                forms=element_forms("fire", "ice", "lightning", "light", "dark"),
            ),
        ),
        (
            "hex",
            "Hex",
            "enemy",
            a(
                "hex",
                tags=("magic", "damage.dark"),
                effect=op(damage("magic", 4)),
                sp=18,
                hits=_hits(1.0, tags=("damage.dark",)),
                apply_states=[_state("magic_down"), _state("power_down"), _state("blind")],
            ),
        ),
        (
            "bewilder",
            "Bewilder",
            "enemy",
            a(
                "bewilder",
                tags=("magic",),
                sp=20,
                apply_states=[_state("confuse"), _state("silence")],
            ),
        ),
        (
            "blood_ether",
            "Blood Ether",
            "self",
            _with_self(a("blood_ether"), op(110, SP)),
        ),
        (
            "word_of_doom",
            "Word of Doom",
            "enemy",
            a(
                "word_of_doom",
                tags=("magic", "damage.dark", "divine"),
                effect=op(damage("magic", 10)),
                sp=40,
                battle_costs={BP: 3},
                hits=_hits(1.0, 1.4, tags=("damage.dark",)),
                apply_states=[_state("doom")],
            ),
        ),
    ]
    hero = [
        (
            "dawn_and_dusk",
            "Dawn and Dusk",
            "enemy",
            a(
                "dawn_and_dusk",
                effect=op(damage("power", 13)),
                sp=18,
                follow_tags=FOLLOW_WEAPON,
                hits=_hits(1.0, 1.0),
                forms=forms(
                    ("light", "Dawn (light)", ("damage.light",), 1.0),
                    ("dark", "Dusk (dark)", ("damage.dark",), 1.0),
                    ("both", "Twilight (both)", ("damage.light", "damage.dark"), 1.3),
                ),
            ),
        ),
        (
            "dark_pact",
            "Dark Pact",
            "enemy",
            a(
                "dark_pact",
                tags=("weapon.sword", "damage.dark", "magic"),
                effect=op(damage("power", 24)),
                hits=_hits(1.0, 1.6, tags=("weapon.sword", "damage.dark")),
                apply_states=[_state("lifelink", "self")],
            ),
        ),
        (
            "pass_the_torch",
            "Pass the Torch",
            "ally",
            a(
                "pass_the_torch",
                battle_costs={BP: 2},
                battle_resource_gains=[{"to": "targets", "resource": BP, "amount": 2}],
            ),
        ),
        (
            "rekindle",
            "Rekindle",
            "self",
            a(
                "rekindle",
                sp=24,
                cooldown_turns=3,
                battle_resource_gains=[{"to": "self", "resource": BP, "amount": 2}],
                apply_states=[_state("swift_feet", "self")],
            ),
        ),
        (
            "twilight_judgment",
            "Twilight Judgment",
            "enemy",
            a(
                "twilight_judgment",
                tags=("weapon.sword", "magic", "divine"),
                effect=op(damage("power", 11)),
                sp=44,
                battle_costs={BP: 3},
                hits=[
                    {"tags": ["damage.light"], "power": 1.5, "checks": ["crit"]},
                    {"tags": ["damage.dark"], "power": 1.5, "checks": ["crit"]},
                    {"tags": ["damage.light", "damage.dark"], "power": 2.5, "checks": ["crit"]},
                ],
                apply_states=[_state("doom")],
            ),
        ),
    ]
    forge = [
        (
            "molten_strike",
            "Molten Strike",
            "enemy",
            a(
                "molten_strike",
                tags=("weapon.axe", "damage.fire"),
                effect=op(damage("power", 16)),
                hits=_hits(1.0, 1.2, tags=("weapon.axe", "damage.fire")),
                item_costs={"fire_dust": 1},
                apply_states=[_state("burn")],
            ),
        ),
        (
            "gilded_hammer",
            "Gilded Hammer",
            "enemy",
            a(
                "gilded_hammer",
                tags=("weapon.axe",),
                effect=op(damage("power", 15)),
                hits=_hits(1.6, 1.6, tags=("weapon.axe",)),
                currency_costs={"gold": 200},
                apply_states=[_state("defense_down")],
            ),
        ),
        (
            "armor_crush",
            "Armor Crush",
            "enemy",
            a(
                "armor_crush",
                tags=("weapon.axe",),
                effect=op(damage("power", 12)),
                sp=16,
                hits=_hits(1.0, tags=("weapon.axe",)),
                apply_states=[_state("defense_down"), _state("power_down")],
            ),
        ),
    ]
    rogue = [
        (
            "blinding_powder",
            "Blinding Powder",
            "enemy",
            a(
                "blinding_powder",
                sp=12,
                apply_states=[_state("blind"), _state("swift_feet", "self")],
            ),
        ),
        (
            "charm",
            "Charm",
            "enemy",
            a("charm", tags=("magic",), sp=16, apply_states=[_state("charm")]),
        ),
        (
            "venom_edge",
            "Venom Edge",
            "enemy",
            a(
                "venom_edge",
                tags=("weapon.dagger",),
                effect=op(damage("power", 7)),
                sp=14,
                hits=_hits(1.0, 1.0, tags=("weapon.dagger",)),
                apply_states=[_state("poison"), _state("bleed")],
            ),
        ),
        (
            "pilfer",
            "Pilfer",
            "enemy",
            a("pilfer", tags=("action.steal",), sp=8),  # robs what it hits (Battle Extras)
        ),
        (
            "lullaby_dust",
            "Lullaby Dust",
            "enemy",
            a("lullaby_dust", sp=14, apply_states=[_state("sleep"), _state("slow")]),
        ),
    ]
    guard = [
        (
            "bastion_aura",
            "Bastion Aura",
            "allies",
            a(
                "bastion_aura",
                sp=20,
                cooldown_turns=4,
                apply_states=[_state("armor_up", "allies"), _state("ward", "allies")],
            ),
        ),
        (
            "martyrs_gift",
            "Martyr's Gift",
            "ally",
            a(
                "martyrs_gift",
                effect=op(flat(1400)),
                battle_resource_gains=[{"to": "targets", "resource": BP, "amount": 1}],
            ),
        ),
        (
            "maddening_howl",
            "Maddening Howl",
            "enemy",
            a("maddening_howl", sp=14, apply_states=[_state("berserk"), _state("power_down")]),
        ),
    ]
    for job, group in (
        ("weapon_master", weapon_master),
        ("sage", sage),
        ("hero", hero),
        ("forgemaster", forge),
        ("rogue", rogue),
        ("guardian", guard),
    ):
        for ability_id, label, target, definition in group:
            yield job, ability_id, label, target, _paid(definition), "divine" in definition.tags


COSTS = {  # what each skill takes besides its technique points: health is a cost like any other
    "blood_ether": ((HP, 500),),
    "dark_pact": ((HP, 700), (SP, 12)),
    "martyrs_gift": ((HP, 800),),
}


def _paid(definition):
    extra = COSTS.get(definition.ability_id)
    if not extra:
        return definition
    return dataclasses.replace(definition, costs=tuple(cost(r, v) for r, v in extra))


FX = {
    "versatile_strike": ("slash", "cut"),
    "elemental_edge": ("slash", "aura"),
    "cripple": ("cutx", "circle"),
    "war_cry": ("aura", "boost"),
    "arcane_tome": ("spark", "aura"),
    "hex": ("spirit", "circle"),
    "bewilder": ("spirit", "circle"),
    "blood_ether": ("boost", "aura"),
    "word_of_doom": ("spirit", "explosion", "spirit"),
    "dawn_and_dusk": ("slash", "spark"),
    "dark_pact": ("spirit", "slash2", "explosion"),
    "pass_the_torch": ("boost", "aura"),
    "rekindle": ("boost", "fire"),
    "twilight_judgment": ("spark", "spirit", "slash2", "explosion"),
    "molten_strike": ("fire", "circ"),
    "gilded_hammer": ("circ", "explosion"),
    "armor_crush": ("circ", "cutd"),
    "blinding_powder": ("smoke", "circle"),
    "charm": ("spirit", "boost"),
    "venom_edge": ("cutx", "clawd"),
    "lullaby_dust": ("smoke", "boost"),
    "pilfer": ("smoke", "cut"),
    "bastion_aura": ("shield", "aura"),
    "martyrs_gift": ("boost", "shield"),
    "maddening_howl": ("circle", "aura"),
    "mend": ("boost",),
    "benediction": ("aura", "boost"),
    "purge": ("boost", "spirit"),
    "starlight": ("spark", "boost"),
    "lullaby": ("smoke", "boost"),
    "bp_gift": ("boost", "aura"),
    "second_breath": ("boost", "aura"),
    "dawn_hymn": ("aura", "boost", "shield"),
}
SELF = {"blood_ether", "rekindle", "second_breath"}


def companion(c):
    """Mira, a cleric who fights beside the hero: heals, cures, and moves boost points around."""
    db = c.db
    cleric_skills = {
        "mend": (
            "Mend",
            "ally",
            ability("mend", mode="selected", effect=op(healing(40)), sp=14, allies=True),
        ),
        "benediction": (
            "Benediction",
            "allies",
            ability(
                "benediction",
                sp=26,
                cooldown_turns=4,
                apply_states=[
                    _state("regen", "allies"),
                    _state("ward", "allies"),
                    _state("armor_up", "allies"),
                ],
            ),
        ),
        "purge": (
            "Purge",
            "ally",
            ability(
                "purge",
                sp=12,
                apply_states=[
                    _state(s, remove=True)
                    for s in (
                        "poison",
                        "burn",
                        "bleed",
                        "silence",
                        "confuse",
                        "charm",
                        "berserk",
                        "doom",
                        "blind",
                        "slow",
                        "defense_down",
                        "power_down",
                        "magic_down",
                    )
                ],
            ),
        ),
        "starlight": (
            "Starlight",
            "enemy",
            ability(
                "starlight",
                tags=("magic", "damage.light"),
                effect=op(damage("magic", 10)),
                sp=16,
                hits=_hits(1.0, 1.0, tags=("damage.light",)),
            ),
        ),
        "lullaby": (
            "Lullaby",
            "enemy",
            ability("lullaby", tags=("magic",), sp=14, apply_states=[_state("sleep")]),
        ),
        "bp_gift": (
            "Boost Gift",
            "ally",
            ability(
                "bp_gift",
                sp=10,
                battle_resource_gains=[{"to": "targets", "resource": BP, "amount": 2}],
            ),
        ),
        "second_breath": (
            "Second Breath",
            "self",
            ability(
                "second_breath",
                sp=18,
                cooldown_turns=3,
                battle_resource_gains=[{"to": "self", "resource": BP, "amount": 2}],
            ),
        ),
        "dawn_hymn": (
            "Dawn Hymn (Divine)",
            "allies",
            _with_self(
                ability(
                    "dawn_hymn",
                    tags=("magic", "divine"),
                    sp=40,
                    battle_costs={BP: 3},
                    apply_states=[_state("regen", "allies"), _state("stoneskin", "allies")],
                ),
                op(healing(30)),
            ),
        ),
    }
    for ability_id, (label, target, definition) in cleric_skills.items():
        c.add(definition, target)
        c.skill_names[ability_id] = label
    db.add_class(
        ClassDefinition(
            COMPANION_CLASS,
            "Cleric",
            stat_bonuses={"magic": 16, "defense": 8, "speed": 8},
            resource_bonuses={SP: 120},
            granted_tags=(f"class.{COMPANION_CLASS}", "capability.weapon.staff"),
            granted_abilities=tuple(cleric_skills),
            level_growth={"magic": 2.8, "defense": 1.6, "speed": 0.6},
        )
    )
    from asteria.rpg import ClassAssignment

    hero = db.actors[c.hero_id]
    db.actors[COMPANION_ID] = dataclasses.replace(
        hero,
        actor_id=COMPANION_ID,
        display_name="Mira",
        class_assignments=(
            ClassAssignment(
                COMPANION_CLASS, assignment_id=f"{COMPANION_ID}.main", role="main", priority=10
            ),
        ),
        base_stats={
            "power": 15.0,
            "magic": 38.0,
            "defense": 22.0,
            "speed": 42.0,
            "crit": 5.0,
            "evade": 8.0,
            "lifesteal": 0.0,
        },
        base_resources={
            HP: {"minimum": 0.0, "maximum": 2400.0, "current": 2400.0},
            SP: {"minimum": 0.0, "maximum": 260.0, "current": 260.0},
        },
        abilities=(),
    )
    party = db.party_setups["main_party"]
    ids = (*party.roster_actor_ids, COMPANION_ID)
    db.party_setups["main_party"] = dataclasses.replace(
        party,
        roster_actor_ids=ids,
        active_actor_ids=ids,
        placements=(
            *party.placements,
            dataclasses.replace(party.placements[0], actor_id=COMPANION_ID, slot_id="slot_2"),
        ),
    )
    tc.FX_BY_ABILITY.update({k: FX[k] for k in cleric_skills})
    tc.SELF_TARGETED.update({"second_breath"})


def expansion(c):
    """Register the second-wave states and skills; returns ``{job: [ability ids]}``."""
    new_states(c)
    by_job = {}
    for job, ability_id, label, target, definition, divine in _skills(c):
        c.add(definition, target)
        c.skill_names[ability_id] = label + (" (Divine)" if divine else "")
        by_job.setdefault(job, []).append(ability_id)
    tc.FX_BY_ABILITY.update(FX)
    tc.SELF_TARGETED.update(SELF)
    return by_job
