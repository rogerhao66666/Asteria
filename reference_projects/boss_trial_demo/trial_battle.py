"""Battle rules of the Boss Trial (phase 4): every Battle category carries designed entries
that a fight uses.

* **Resources**: Momentum (+1 each turn a member ends, 10 at most, gone after the fight) feeds
  Aldric's Momentum Strike (3) and the Party Rush combo (2); Soul (+1 each round, 6 at most)
  feeds Vesper's Soul Burst (3).
* **Chance checks**: Block (the defender's defence) halves a foe's blow (an interaction rule
  reads ``outcome.block``); foes' attacks roll it.
* **Turn order**: a swift timeline (a shorter scale) for a catacomb patrol.
* **Cast & recovery / costs**: the big spells charge (cast time) and can be broken; their price
  is paid when they start and lost when they are broken.
* **Sequences**: Party Rush - Aldric leads, every other member strikes in turn (a combo
  started by the ``BATTLE_SEQUENCE`` world command).
* **Gauges**: Overdrive - a critical hit adds Momentum; at 10 the striker gets Attack Up.
* **Counters & follow-ups**: Cover (Aldric wards an ally a foe hits) and Follow-up (Cael strikes
  whoever an ally just hit with a weapon).
* **Victory & defeat**: the Acolytes' Vigil is won by holding out eight rounds against warded
  Vigil Acolytes (a damage interaction rule zeroes blows against them).
* **Escape**: an easy one in the woods, a hard one in the catacombs.
* **General rules**: gauntlet rules (boost up to 5) for the vigil.
"""

from __future__ import annotations

import dataclasses

import trial_content as tc

from asteria.rpg import (
    ActionSequenceDefinition,
    ActionTimingDefinition,
    ActionTransactionPolicy,
    BattleEscapeRule,
    BattleObjectiveDefinition,
    BattleResourceDefinition,
    BattleSchedulerDefinition,
    EncounterDefinition,
    EncounterMember,
    GaugeCompositionDefinition,
    InteractionRule,
    OutcomeCheckDefinition,
    ReactionDefinition,
)

HP = tc.HP
ability, op, damage = tc.ability, tc.op, tc.damage
CHARGED = {  # big spells: (cast time, startup, recovery)
    "holy_judgment": (0.6, 0.1, 0.2),
    "mass_cure": (0.4, 0.1, 0.2),
    "death_coil": (0.5, 0.1, 0.2),
    "soul_harvest": (0.6, 0.1, 0.25),
    "forbidden_rite": (0.5, 0.1, 0.2),
    "frost_nova": (0.3, 0.1, 0.15),
}


def rules(c):
    resources(c)
    checks(c)
    turn_order_and_timing(c)
    combos_and_gauges(c)
    reactions(c)
    vigil(c)


def resources(c):
    db = c.db
    for resource_id, maximum, trigger in (
        ("momentum", 10.0, "rpg.battle.turn_ended"),
        ("soul", 6.0, "rpg.battle.round_started"),
    ):
        db.battle_resources[resource_id] = BattleResourceDefinition.from_data(
            {
                "schema": "asteria.rpg.battle_resource",
                "version": 1,
                "resource_id": resource_id,
                "minimum": 0.0,
                "maximum": maximum,
                "start_mode": "fixed",
                "start_value": 0.0,
                "end_mode": "reset_to_start",
                "overflow_limit": None,
                "rules": [{"trigger": trigger, "amount": 1.0}],
            }
        )
    c.add(
        ability(
            "momentum_strike",
            tags=("weapon.sword", "finisher"),
            effect=op(damage("power", 26)),
            battle_costs={"momentum": 3},
            hits=tc._hits(1.0, 1.5, tags=("weapon.sword",)),
        ),
        "enemy",
    )
    c.add(
        ability(
            "soul_burst",
            tags=("magic", "damage.dark", "finisher"),
            effect=op(damage("magic", 14)),
            battle_costs={"soul": 3},
            targets=6,
            hits=tc._hits(1.0, 1.2, tags=("damage.dark",)),
        ),
        "enemies",
    )
    c.skill_names.update({"momentum_strike": "Momentum Strike", "soul_burst": "Soul Burst"})
    tc.FX_BY_ABILITY.update({"momentum_strike": ("slash2", "cutx"), "soul_burst": ("spirit",)})
    for actor_id, skill in (("hero_01", "momentum_strike"), ("hero_03", "soul_burst")):
        actor = db.actors[actor_id]
        db.actors[actor_id] = dataclasses.replace(actor, abilities=(*actor.abilities, skill))


def checks(c):
    db = c.db
    db.outcome_checks["block"] = OutcomeCheckDefinition.from_data(
        {
            "schema": "asteria.rpg.outcome_check",
            "version": 1,
            "check_id": "block",
            "base_chance": 0.05,
            "minimum_chance": 0.0,
            "maximum_chance": 0.5,
            "source_stat_terms": {},
            "target_stat_terms": {"defense": 0.002},
            "required_source_tags": [],
            "required_target_tags": [],
            "success_tags": ["outcome.block"],
            "failure_tags": [],
        }
    )
    db.interaction_rules["blocked_half"] = InteractionRule(
        "blocked_half", source_tags_all=("outcome.block",), multiplier=0.5, priority=4
    )
    for enemy in db.enemies.values():  # a foe's blows can be blocked
        for ability_id in enemy.abilities:
            definition = c.abilities._definitions.get(ability_id)
            if definition is None or not definition.hits:
                continue
            hits = tuple(
                {**h, "checks": [*h.get("checks", []), "block"]}
                if "block" not in h.get("checks", [])
                else h
                for h in definition.hits
            )
            c.abilities._definitions[ability_id] = dataclasses.replace(definition, hits=hits)


def turn_order_and_timing(c):
    db = c.db
    db.battle_schedulers["swift_timeline"] = BattleSchedulerDefinition.from_data(
        {
            "schema": "asteria.rpg.battle_scheduler_definition",
            "version": 1,
            "scheduler_id": "swift_timeline",
            "mode": "continuous",
            "timeline_scale": 60.0,
            "minimum_speed": 1.0,
        }
    )
    for ability_id, (cast, startup, recovery) in CHARGED.items():
        if ability_id not in c.abilities._definitions:
            continue
        db.action_timings[ability_id] = ActionTimingDefinition.from_data(
            {
                "schema": "asteria.rpg.action_timing_definition",
                "version": 1,
                "ability_id": ability_id,
                "startup": startup,
                "cast_time": cast,
                "recovery": recovery,
                "interruptible": True,
                "interrupt_threshold": 0.0,
                "priority": 0,
            }
        )
        db.action_transactions[ability_id] = ActionTransactionPolicy.from_data(
            {
                "schema": "asteria.rpg.action_transaction_policy",
                "version": 1,
                "ability_id": ability_id,
                "cost_commit": "start",  # paid when the charge starts
                "interrupt_cost": "keep",  # and lost when it is broken
            }
        )


def combos_and_gauges(c):
    db = c.db
    db.action_sequences["party_rush"] = ActionSequenceDefinition.from_data(
        {
            "schema": "asteria.rpg.action_sequence_definition",
            "version": 1,
            "sequence_id": "party_rush",
            "min_participants": 2,
            "max_participants": 4,
            "participant_policy": "all_available",
            "interruption_policy": "skip_step",
            "tags": ["combo"],
            "steps": [
                {
                    "ability_id": "rush_blow",
                    "participant_index": index,
                    "repeat": 1,
                    "delay": 0.1 * index,
                    "target_policy": "inherit",
                    "emitted_tags": [],
                    "required_previous_tags": [],
                }
                for index in range(4)
            ],
        }
    )
    c.add(
        ability(
            "rush_blow",
            tags=("combo",),
            menu_category="Combo",  # a combo's blow (the sequence needs every member to know it)
            effect=op(damage("power", 9)),
            hits=tc._hits(1.0),
        ),
        "enemy",
    )
    c.add(
        ability(
            "party_rush",
            tags=("combo",),
            battle_costs={"momentum": 2},
            commands=[
                {
                    "command": "BATTLE_SEQUENCE",
                    "args": {
                        "sequence_id": "party_rush",
                        "actor_id": "@actor",
                        "target_id": "@target",
                    },
                }
            ],
        ),
        "enemy",
    )
    c.skill_names.update({"party_rush": "Party Rush", "rush_blow": "Rush Blow"})
    tc.FX_BY_ABILITY.update({"party_rush": ("circ",), "rush_blow": ("slash",)})
    for actor_id in ("hero_01", "hero_02", "hero_03", "hero_04"):  # every member can take part
        actor = db.actors[actor_id]
        extra = ("party_rush", "rush_blow") if actor_id == "hero_01" else ("rush_blow",)
        db.actors[actor_id] = dataclasses.replace(actor, abilities=(*actor.abilities, *extra))
    db.gauge_compositions["overdrive"] = GaugeCompositionDefinition.from_data(
        {
            "schema": "asteria.rpg.gauge_composition",
            "version": 1,
            "composition_id": "overdrive",
            "impacts": [
                {
                    "schema": "asteria.rpg.gauge_impact_rule",
                    "version": 1,
                    "impact_id": "crit_charges",
                    "trigger": "battle.hit",
                    "resource_id": "momentum",
                    "recipient": "source",
                    "delta": 1.0,
                    "value_scale": 0.0,
                    "required_outcome_tags_all": ["outcome.crit"],
                    "required_outcome_tags_any": [],
                    "blocked_outcome_tags": [],
                    "priority": 0,
                }
            ],
            "thresholds": [
                {
                    "schema": "asteria.rpg.gauge_threshold_rule",
                    "version": 1,
                    "threshold_id": "overdrive",
                    "resource_id": "momentum",
                    "comparison": "at_or_above",
                    "threshold": 10.0,
                    "state_id": "attack_up",
                    "emit_trigger": "battle.overdrive",
                    "reset_to": 0.0,
                    "reset_to_maximum": False,
                    "include_cast_in_shift": False,
                    "priority": 0,
                }
            ],
        }
    )


def reactions(c):
    db = c.db
    c.add(ability("intercept", tags=("support",), apply_states=[{"state": "ward"}]), "ally")
    c.add(
        ability(
            "chase_strike",
            tags=("weapon.dagger", "follow_up"),
            effect=op(damage("power", 8)),
            hits=tc._hits(1.0, tags=("weapon.dagger",)),
        ),
        "enemy",
    )
    c.skill_names.update({"intercept": "Intercept", "chase_strike": "Chase Strike"})
    tc.FX_BY_ABILITY.update({"intercept": ("shield",), "chase_strike": ("cut",)})
    db.add_reaction(
        ReactionDefinition(
            "cover",
            "rpg.battle.after_action",
            "allies_of_targets_except_targets",
            target_selector="event_targets",
            ability_id="intercept",
            reactor_tags=("trait.cover",),
            blocked_tags=("support", "magic", "follow_up", "combo"),
        )
    )
    db.add_reaction(
        ReactionDefinition(
            "follow_up",
            "rpg.battle.after_action",
            "allies_of_source_except_source",
            target_selector="event_targets",
            ability_id="chase_strike",
            reactor_tags=("trait.follow_up",),
            blocked_tags=("support", "magic", "follow_up", "combo"),
        )
    )
    for actor_id, trait, skill in (
        ("hero_01", "trait.cover", "intercept"),
        ("hero_04", "trait.follow_up", "chase_strike"),
    ):
        actor = db.actors[actor_id]
        db.actors[actor_id] = dataclasses.replace(
            actor, tags=(*actor.tags, trait), abilities=(*actor.abilities, skill)
        )


def vigil(c):
    """The Acolytes' Vigil in the throne hall: hold out eight rounds against three acolytes on
    round turns, under gauntlet rules, with no running away."""
    db = c.db
    db.battle_objectives["vigil_survive"] = BattleObjectiveDefinition.from_data(
        {
            "schema": "asteria.rpg.battle_objective_definition",
            "version": 1,
            "objective_id": "vigil_survive",
            "priority": 6,
            "success_mode": "all",
            "success_conditions": [
                {"kind": "round_index", "subject_id": "round", "operator": ">=", "value": 8},
                {
                    "kind": "side_active_count",
                    "subject_id": "heroes",
                    "operator": ">=",
                    "value": 1,
                },
            ],
            "winning_sides": ["heroes"],
            "defeated_sides": ["enemies"],
            "failure_mode": "any",
            "failure_conditions": [],
            "failure_winning_sides": ["enemies"],
            "failure_defeated_sides": ["heroes"],
        }
    )
    for rule_id, base in (("woods_escape", 0.8), ("crypt_escape", 0.25)):
        db.escape_rules[rule_id] = BattleEscapeRule.from_data(
            {
                "schema": "asteria.rpg.battle_escape_rule",
                "version": 1,
                "rule_id": rule_id,
                "side": "heroes",
                "base_chance": base,
                "minimum_chance": 0.0,
                "maximum_chance": 1.0,
                "source_stat": "speed",
                "source_scale": 0.002,
                "opponent_stat": None,
                "opponent_scale": 0.0,
            }
        )
    base = db.battle_session_rules["trial"]
    db.battle_session_rules["vigil_gauntlet"] = dataclasses.replace(
        base, rules_id="vigil_gauntlet", boost_max_level=5
    )
    acolyte = db.enemies["mender_wisp"]  # the same acolytes, far too sturdy to fell in time
    db.enemies["vigil_acolyte"] = dataclasses.replace(
        acolyte,
        enemy_id="vigil_acolyte",
        display_name="Vigil Acolyte",
        resources={**acolyte.resources, HP: 60000.0},
        # no capture, no instant death, no Doom: the vigil is held, not won early
        tags=(*acolyte.tags, "boss", "immune.kill", "immune.doom", "vigil.warded"),
    )
    # the vigil's ward: blows barely scratch them (a damage interaction rule), so the vigil is
    # held for eight rounds, not won by killing
    db.interaction_rules["vigil_ward"] = InteractionRule(
        "vigil_ward", target_tags_all=("vigil.warded",), multiplier=0.0, priority=10
    )
    binding = db.enemy_behavior_bindings.get("mender_wisp")
    if binding is not None:
        db.enemy_behavior_bindings["vigil_acolyte"] = dataclasses.replace(
            binding, enemy_id="vigil_acolyte"
        )
    db.encounters["acolyte_vigil"] = EncounterDefinition(
        "acolyte_vigil",
        members=(EncounterMember("vigil_acolyte", count=3, weight=1.0),),
        tags=(
            "throne",
            "no_escape",
            "scheduler:classic_rounds",  # rounds: the vigil counts them, Soul grows by them
            "objective:vigil_survive",
            "rules:vigil_gauntlet",
        ),
    )
    for encounter_id, extra in (
        ("woods_patrol", ("escape:woods_escape",)),
        ("woods_ambush", ("escape:woods_escape",)),
        ("crypt_patrol", ("escape:crypt_escape", "scheduler:swift_timeline")),
        ("crypt_guard", ("escape:crypt_escape",)),
    ):
        encounter = db.encounters[encounter_id]
        db.encounters[encounter_id] = dataclasses.replace(
            encounter, tags=(*encounter.tags, *extra)
        )
