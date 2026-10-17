"""Last pieces of the campaign: a taunt, a party-wide limit gauge, a skill that needs an item, a
skill that needs a pet, and extra battle command groups (Limit, Beast, Rites)."""

from __future__ import annotations

import dataclasses

import trial_content as tc

from asteria.gameplay.states import StateDefinition
from asteria.rpg import BattleStatePolicy
from asteria.rpg.battle_extensions import ResourceGain

ability, op, damage = tc.ability, tc.op, tc.damage
_hits, _state = tc._hits, tc._state


def systems(c):
    db = c.db
    rules = db.battle_extension_rules["trial"]
    db.battle_extension_rules["trial"] = dataclasses.replace(
        rules,
        taunt_tag="state.taunt",
        shared_gauges={"unity": 100},
        gains=(
            *rules.gains,
            ResourceGain("dealt", "unity", per_max_hp=250.0, shared=True),
            ResourceGain("taken", "unity", per_max_hp=150.0, shared=True),
        ),
    )
    c.library.states._definitions["taunt"] = StateDefinition(
        "taunt", 3, contributed_tags=("state.taunt",)
    )
    db.battle_state_policies["taunt"] = BattleStatePolicy(
        "taunt", tick_trigger="rpg.battle.turn_ended"
    )
    moves = {
        # a tank draws every single-target attack to itself
        "taunting_roar": (
            ability("taunting_roar", sp=12, apply_states=[_state("taunt", "self")]),
            "self",
            "Taunting Roar",
            "",
        ),
        # the party's limit break: the shared gauge fills as the party hits and is hurt
        "unity_strike": (
            ability(
                "unity_strike",
                tags=("weapon.sword", "damage.light", "divine"),
                effect=op(damage("power", 18)),
                hits=_hits(1.0, 1.2, 1.4, 1.6, 2.0, tags=("weapon.sword", "damage.light")),
                gauge_costs={"unity": 100},
                menu_category="Limit",
            ),
            "enemy",
            "Unity Strike",
            "Limit",
        ),
        # needs the Ancient's thread in the bag (not used up)
        "grave_whisper": (
            ability(
                "grave_whisper",
                tags=("magic", "damage.dark"),
                effect=op(damage("magic", 12)),
                hits=_hits(1.0, 1.0, tags=("damage.dark",)),
                sp=24,
                requires_items={"ancient_thread": 1},
                menu_category="Rites",
            ),
            "enemy",
            "Grave Whisper",
            "Rites",
        ),
        # needs a tamed creature: its own strength counts in the formula
        "beast_command": (
            ability(
                "beast_command",
                tags=("pet", "weapon.bow"),
                effect=op(damage("pet_power", 18)),
                hits=_hits(1.0, 1.0, tags=("weapon.bow",)),
                requires_pet="any",
                menu_category="Beast",
            ),
            "enemy",
            "Beast Command",
            "Beast",
        ),
    }
    for ability_id, (definition, target, label, _group) in moves.items():
        c.add(definition, target)
        c.skill_names[ability_id] = label
    tc.FX_BY_ABILITY.update(
        {
            "taunting_roar": ("circle", "aura"),
            "unity_strike": ("slash2", "spark", "slash2", "explosion", "spark"),
            "grave_whisper": ("spirit", "spirit"),
            "beast_command": ("cut", "cut"),
        }
    )
    tc.SELF_TARGETED.add("taunting_roar")

    def grant(class_id, *abilities):
        record = db.classes[class_id]
        db.classes[class_id] = dataclasses.replace(
            record, granted_abilities=(*record.granted_abilities, *abilities)
        )

    grant("knight", "unity_strike", "taunting_roar")
    grant("necromancer", "grave_whisper")
    grant("cultist", "beast_command")
