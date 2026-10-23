"""Module-level classes and helpers of the game session: errors, log entries, equip offers,
cast merging, condition text."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from asteria.runtime.collision import CombinedQuery


class _EitherBlocks(CombinedQuery):
    """Two ``collides_world_point`` queries: a point is blocked when either blocks it."""

    def __init__(self, first, second):
        super().__init__(first, second)
        self.first, self.second = first, second

    def collides_world_point(self, x, y):
        return self.first.collides_world_point(x, y) or self.second.collides_world_point(x, y)


class GameSessionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BattleLogEntry:
    """One canonical battle fact, in order, for presentation adapters to consume.

    kinds: ``battle_started``, ``turn``, ``action``, ``gauge``, ``capture``, ``summoned``,
    ``battle_finished``.
    ``outcomes`` pairs each target with its non-mutating interaction outcome.
    """

    sequence: int
    kind: str
    member_id: str = ""
    ability_id: str = ""
    target_ids: tuple[str, ...] = ()
    outcomes: tuple = ()
    data: object = None


def _merge_casts(first, second):
    """One casting form made of two (a skill's form and its input-step choices): tags joined,
    power multiplied, costs added, states joined."""
    if first is None:
        return dict(second)
    merged = dict(first)
    merged["tags"] = [*first.get("tags", ()), *second.get("tags", ())]
    merged["power"] = float(first.get("power", 1.0)) * float(second.get("power", 1.0))
    for key in ("resource_costs", "battle_costs"):
        costs = dict(first.get(key, {}))
        for resource, amount in second.get(key, {}).items():
            costs[resource] = costs.get(resource, 0.0) + float(amount)
        merged[key] = costs
    merged["apply_states"] = [*first.get("apply_states", ()), *second.get("apply_states", ())]
    return merged


@dataclasses.dataclass(frozen=True, slots=True)
class EquipOffer:
    """A question waiting for the player: wear the bag's ``instance_id`` on ``actor_id``
    (in place of ``replaces`` when the slot is full and the rules offer a swap)?"""

    instance_id: str
    actor_id: str
    slot_id: str
    replaces: str = ""


def describe_condition(condition, tr=None):
    """Plain words for an ability condition (menus: why it cannot be used)."""
    from asteria.gameplay.conditions import (
        ConditionGroup,
        NumericCondition,
        StateCondition,
        TagCondition,
    )

    if tr is None:  # no game: English (``GameSessionRuntime.tr`` words it in the player's)

        def tr(key, english, **params):
            return english.format(**params) if params else english

    if isinstance(condition, TagCondition):
        text = (
            condition.tag.split(".", 1)[-1].replace("_", " ")
            if condition.tag.startswith("equip.")
            else condition.tag
        )
        return text if condition.present else tr("battle.condition.not", "no {what}", what=text)
    if isinstance(condition, ConditionGroup):
        parts = [describe_condition(c, tr) for c in condition.conditions]
        any_of = str(getattr(condition.mode, "value", condition.mode)) == "any"
        joiner = tr("battle.condition.or", " or ") if any_of else " + "
        return joiner.join(parts) if parts else tr("battle.condition.some", "conditions")
    if isinstance(condition, StateCondition):
        state = getattr(condition, "state_id", "")
        return tr("battle.condition.state", "state {state}", state=state)
    if isinstance(condition, NumericCondition):
        return f"{condition.key} {condition.operator} {condition.value:g}"
    return tr("battle.condition.some", "conditions")


def _base_relative(battle_pool, base_pool):
    """``base_pool`` with each resource's current value as the battle left it, less what the
    build added on top (the build adds it back): a hero who ended on 900 / 1,000 health whose
    gear gave 400 of it is stored as 500 / 600."""
    from asteria.gameplay import ResourcePool

    pool = ResourcePool.from_data(base_pool.to_data())
    for name in tuple(pool.to_data()["values"]):
        if not battle_pool.contains(name):
            continue
        bonus = battle_pool.maximum(name) - pool.maximum(name)
        value = pool.get(name)
        current = min(value.maximum, max(value.minimum, battle_pool.current(name) - bonus))
        pool.set_current(name, current)
    return pool
