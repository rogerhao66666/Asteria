"""New Game Plus: start a fresh game that keeps chosen parts of a finished one (YEP NewGamePlus).

``NewGamePlusRules`` is project data naming what carries over. ``carry_over`` takes the old
``GameRuntimeSave`` and the new one made from the project's game start, and returns the new one
with those parts copied in; the old save is left untouched.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

CARRY = ("levels", "inventory", "currencies", "equipment", "pets", "abilities", "world")


@dataclass(frozen=True, slots=True)
class NewGamePlusRules:
    """``carry``: any of ``levels`` (actor level, experience, points), ``inventory`` (bag items,
    unequipped gear), ``currencies``, ``equipment`` (what actors wear), ``pets``, ``abilities``
    (learned abilities and skill-tree spending) and ``world`` (bestiary / counters).
    ``carry_switches`` are event switch name prefixes that stay on; ``level_cap`` (0 = none) limits
    carried actor levels; ``keep_currency_share`` scales carried currency."""

    rules_id: str
    carry: tuple[str, ...] = ()
    carry_switches: tuple[str, ...] = ()
    level_cap: int = 0
    keep_currency_share: float = 1.0

    def __init__(
        self, rules_id, *, carry=(), carry_switches=(), level_cap=0, keep_currency_share=1.0
    ):
        rules_id = str(rules_id).strip()
        if not rules_id:
            raise ValueError("rules_id is required")
        carry = tuple(dict.fromkeys(str(x) for x in carry))
        unknown = [x for x in carry if x not in CARRY]
        if unknown:
            raise ValueError(f"unknown carry-over parts: {', '.join(unknown)}")
        if int(level_cap) < 0:
            raise ValueError("level_cap must be >= 0")
        share = float(keep_currency_share)
        if not 0.0 <= share <= 1.0:
            raise ValueError("keep_currency_share must be between 0 and 1")
        object.__setattr__(self, "rules_id", rules_id)
        object.__setattr__(self, "carry", carry)
        object.__setattr__(
            self, "carry_switches", tuple(sorted({str(x) for x in carry_switches if str(x)}))
        )
        object.__setattr__(self, "level_cap", int(level_cap))
        object.__setattr__(self, "keep_currency_share", share)

    def to_data(self):
        return {
            "schema": "asteria.rpg.new_game_plus_rules",
            "version": 1,
            "rules_id": self.rules_id,
            "carry": list(self.carry),
            "carry_switches": list(self.carry_switches),
            "level_cap": self.level_cap,
            "keep_currency_share": self.keep_currency_share,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.new_game_plus_rules" or data.get("version") != 1:
            raise ValueError("unsupported new game plus rules")
        return cls(
            data["rules_id"],
            carry=data.get("carry", ()),
            carry_switches=data.get("carry_switches", ()),
            level_cap=data.get("level_cap", 0),
            keep_currency_share=data.get("keep_currency_share", 1.0),
        )


def carry_over(rules, old, new):
    """Copy what ``rules`` names from the finished save ``old`` into the fresh save ``new``."""
    if not isinstance(rules, NewGamePlusRules):
        raise TypeError("rules must be NewGamePlusRules")
    carry = set(rules.carry)
    before, after = old.rpg_state, new.rpg_state
    shared = [x for x in after.party_actor_ids if x in before.actor_progression]
    if "levels" in carry:
        from .save_state import ActorProgressionState

        for actor_id in shared:
            state = before.actor_progression[actor_id]
            level = min(state.level, rules.level_cap) if rules.level_cap else state.level
            kept = state if level == state.level else None
            after.actor_progression[actor_id] = ActorProgressionState(
                level,
                state.experience if kept else 0.0,
                points=dict(state.points),
                unlocked_class_ids=state.unlocked_class_ids,
                active_class_ids=state.active_class_ids,
            )
    if "inventory" in carry:
        for item_id in sorted(before.inventory.item_ids()):
            after.inventory.add(item_id, before.inventory.count(item_id))
        after.equipment_bag = list(before.equipment_bag)
    if "currencies" in carry:
        for key, value in before.currencies.items():
            after.currencies[key] = (
                after.currencies.get(key, 0.0) + value * rules.keep_currency_share
            )
    if "equipment" in carry:
        for actor_id in shared:
            if actor_id in before.loadouts:
                after.loadouts[actor_id] = copy.deepcopy(before.loadouts[actor_id])
    if "pets" in carry:
        after.pets = copy.deepcopy(before.pets)
        after.active_pet_id = before.active_pet_id
    if "abilities" in carry:
        for actor_id in shared:
            if actor_id in before.actor_snapshots:
                after.actor_snapshots[actor_id] = copy.deepcopy(before.actor_snapshots[actor_id])
            if actor_id in before.progression_allocations:
                after.progression_allocations[actor_id] = copy.deepcopy(
                    before.progression_allocations[actor_id]
                )
    if "world" in carry:
        after.world = copy.deepcopy(before.world)
    for name, value in old.event_context.switches.items():
        if value and any(name.startswith(prefix) for prefix in rules.carry_switches):
            new.event_context.set_switch(name, True)
    return new
