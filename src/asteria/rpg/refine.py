"""Weapon refinement (+N): spend currency to raise an item's refine level for stat bonuses.

Project data says which equipment can be refined, the level cap, the bonus each level adds, what
each attempt costs, how likely it is to work at every level and what a failure does:
``keep`` (nothing), ``drop`` (lose a level), ``break`` (the item is broken until repaired) or
``destroy`` (the item is gone). ``safe_until`` is the level up to which attempts never fail.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import ceil, isfinite

from asteria.gameplay.modifiers import ModifierOperation, StatModifier

ON_FAIL = ("keep", "drop", "break", "destroy")


def _text(value):
    return str(value or "").strip()


def _fail(message):
    raise ValueError(message)


def _non_negative(value, label):
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and >= 0")
    return value


@dataclass(frozen=True, slots=True)
class RefineResult:
    outcome: str  # "success" | "failure" | "protected" (a protection item kept the level)
    old_level: int
    new_level: int
    cost: float
    destroyed: bool = False


@dataclass(frozen=True, slots=True)
class RefineRules:
    """``bonuses``: stat -> amount added per refine level (``multiply`` makes it a factor per
    level). ``success``: chance per attempt by current level (the last value repeats)."""

    rules_id: str
    max_level: int = 10
    equipment_tags: tuple[str, ...] = ()
    bonuses: tuple[tuple[str, float], ...] = ()
    operation: str = "add"
    currency: str = ""
    base_cost: float = 0.0
    cost_growth: float = 0.0
    success: tuple[float, ...] = (1.0,)
    on_fail: str = "keep"
    safe_until: int = 0
    # materials: items every attempt uses up (``{item_id: count}``, ores, catalysts...);
    # protect_item: an item that, used on an attempt, keeps the level when the roll fails
    materials: tuple[tuple[str, int], ...] = ()
    protect_item: str = ""

    def __init__(
        self,
        rules_id,
        *,
        max_level=10,
        equipment_tags=(),
        bonuses=None,
        operation="add",
        currency="",
        base_cost=0.0,
        cost_growth=0.0,
        success=(1.0,),
        on_fail="keep",
        safe_until=0,
        materials=None,
        protect_item="",
    ):
        s = object.__setattr__
        s(self, "rules_id", _text(rules_id) or _fail("rules_id is required"))
        max_level = int(max_level)
        if max_level < 1:
            raise ValueError("max_level must be >= 1")
        s(self, "max_level", max_level)
        s(self, "equipment_tags", tuple(sorted({_text(t) for t in equipment_tags if _text(t)})))
        pairs = [(_text(k), float(v)) for k, v in dict(bonuses or {}).items() if _text(k)]
        if any(not isfinite(v) for _, v in pairs):
            raise ValueError("bonuses must be finite")
        s(self, "bonuses", tuple(sorted(pairs)))
        s(self, "operation", ModifierOperation(operation).value)
        s(self, "currency", _text(currency))
        s(self, "base_cost", _non_negative(base_cost, "base_cost"))
        s(self, "cost_growth", _non_negative(cost_growth, "cost_growth"))
        chances = tuple(float(x) for x in success) or (1.0,)
        if any(not 0.0 <= x <= 1.0 for x in chances):
            raise ValueError("success chances must be between 0 and 1")
        s(self, "success", chances)
        if on_fail not in ON_FAIL:
            raise ValueError(f"on_fail must be one of {ON_FAIL}")
        s(self, "on_fail", on_fail)
        s(self, "safe_until", max(0, int(safe_until)))
        needs = [(_text(k), int(v)) for k, v in dict(materials or {}).items() if _text(k)]
        if any(v < 1 for _, v in needs):
            raise ValueError("material counts must be >= 1")
        s(self, "materials", tuple(sorted(needs)))
        s(self, "protect_item", _text(protect_item))

    def eligible(self, item):
        if not self.equipment_tags:
            return True
        return bool(set(self.equipment_tags) & set(item.tags()))

    def cost(self, level):
        """Price of the attempt that starts from ``level``."""
        return float(ceil(self.base_cost + self.cost_growth * int(level)))

    def chance(self, level):
        level = int(level)
        if level < self.safe_until:
            return 1.0
        return self.success[min(level, len(self.success) - 1)]

    def modifiers(self, level, source):
        """Stat modifiers granted by ``level`` (stored on the item, so saves need no rules)."""
        if level <= 0:
            return ()
        op = ModifierOperation(self.operation)
        result = []
        for stat, amount in self.bonuses:
            value = amount * level if op == ModifierOperation.ADD else amount**level
            result.append(StatModifier(f"refine:{source}:{stat}", stat, op, value))
        return tuple(result)

    def apply_level(self, item, level):
        item.refine_level = int(level)
        item.refine_modifiers = self.modifiers(level, item.instance_id)

    def attempt(self, item, rng=None):
        """Roll one refine attempt on ``item`` (cost is the caller's to charge); an item that
        is destroyed is flagged on the result for the caller to remove."""
        rng = rng or random.Random()
        old = item.refine_level
        cost = self.cost(old)
        if rng.random() < self.chance(old):
            self.apply_level(item, old + 1)
            return RefineResult("success", old, old + 1, cost)
        destroyed = False
        if self.on_fail == "drop" and old > 0:
            self.apply_level(item, old - 1)
        elif self.on_fail == "break":
            item.max_durability = max(item.max_durability, 1.0)
            item.durability = 0.0
        elif self.on_fail == "destroy":
            destroyed = True
        return RefineResult("failure", old, item.refine_level, cost, destroyed)

    def to_data(self):
        return {
            "schema": "asteria.rpg.refine_rules",
            "version": 1,
            "rules_id": self.rules_id,
            "max_level": self.max_level,
            "equipment_tags": list(self.equipment_tags),
            "bonuses": dict(self.bonuses),
            "operation": self.operation,
            "currency": self.currency,
            "base_cost": self.base_cost,
            "cost_growth": self.cost_growth,
            "success": list(self.success),
            "on_fail": self.on_fail,
            "safe_until": self.safe_until,
            "materials": dict(self.materials),
            "protect_item": self.protect_item,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.refine_rules" or data.get("version") != 1:
            raise ValueError("unsupported refine rules")
        return cls(
            data["rules_id"],
            max_level=data.get("max_level", 10),
            equipment_tags=data.get("equipment_tags", ()),
            bonuses=data.get("bonuses"),
            operation=data.get("operation", "add"),
            currency=data.get("currency", ""),
            base_cost=data.get("base_cost", 0.0),
            cost_growth=data.get("cost_growth", 0.0),
            success=data.get("success", (1.0,)),
            on_fail=data.get("on_fail", "keep"),
            safe_until=data.get("safe_until", 0),
            materials=data.get("materials"),
            protect_item=data.get("protect_item", ""),
        )
