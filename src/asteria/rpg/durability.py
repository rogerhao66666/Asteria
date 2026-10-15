"""Equipment durability: gear wears with use, breaks, and is repaired for a price.

Project data says which equipment wears out, how fast per event (``attack``, ``hit`` or any name
the game emits) and for which slots, and what a repair costs. A broken item stays equipped but
contributes nothing (``EquipmentLoadout.working``) until it is repaired; ``on_break="destroy"``
removes it instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite

ON_BREAK = ("disable", "destroy")


def _text(value):
    return str(value or "").strip()


def _positive(value, label):
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be finite and > 0")
    return value


@dataclass(frozen=True, slots=True)
class WearEvent:
    """``slots`` lose ``amount`` durability each time ``event`` happens to their wearer."""

    event: str
    slots: tuple[str, ...]
    amount: float = 1.0

    def __init__(self, event, slots, amount=1.0):
        event = _text(event)
        slots = tuple(sorted({_text(x) for x in slots if _text(x)}))
        if not event or not slots:
            raise ValueError("a wear event needs a name and at least one slot")
        object.__setattr__(self, "event", event)
        object.__setattr__(self, "slots", slots)
        object.__setattr__(self, "amount", _positive(amount, "amount"))


@dataclass(frozen=True, slots=True)
class DurabilityRules:
    """``max_durability``: equipment id -> points (``default_max`` for any other; 0 = does not
    wear). ``repair_currency`` / ``repair_cost_per_point`` price a repair (0 = free)."""

    rules_id: str
    max_durability: tuple[tuple[str, float], ...] = ()
    default_max: float = 0.0
    wear: tuple[WearEvent, ...] = ()
    on_break: str = "disable"
    repair_currency: str = ""
    repair_cost_per_point: float = 0.0

    def __init__(
        self,
        rules_id,
        *,
        max_durability=None,
        default_max=0.0,
        wear=(),
        on_break="disable",
        repair_currency="",
        repair_cost_per_point=0.0,
    ):
        s = object.__setattr__
        s(self, "rules_id", _text(rules_id) or _fail("rules_id is required"))
        values = []
        for equipment_id, points in dict(max_durability or {}).items():
            values.append((_text(equipment_id), _positive(points, "max_durability")))
        s(self, "max_durability", tuple(sorted(values)))
        default_max = float(default_max)
        if not isfinite(default_max) or default_max < 0:
            raise ValueError("default_max must be finite and >= 0")
        s(self, "default_max", default_max)
        wear = tuple(wear)
        if any(not isinstance(x, WearEvent) for x in wear):
            raise TypeError("wear must be WearEvent values")
        s(self, "wear", wear)
        if on_break not in ON_BREAK:
            raise ValueError(f"on_break must be one of {ON_BREAK}")
        s(self, "on_break", on_break)
        s(self, "repair_currency", _text(repair_currency))
        cost = float(repair_cost_per_point)
        if not isfinite(cost) or cost < 0:
            raise ValueError("repair_cost_per_point must be finite and >= 0")
        s(self, "repair_cost_per_point", cost)

    def max_for(self, equipment_id):
        return dict(self.max_durability).get(str(equipment_id), self.default_max)

    # -- instances -----------------------------------------------------------------------------
    def ensure(self, item):
        """Give a new instance its durability (full) when this equipment wears out."""
        top = self.max_for(item.equipment.equipment_id)
        if top > 0 and item.durability is None:
            item.durability, item.max_durability = top, top
        return item

    def apply_wear(self, loadout, event):
        """Wear the items in the loadout for ``event``; returns the items that just broke."""
        broke = []
        for rule in self.wear:
            if rule.event != event:
                continue
            for slot_id in rule.slots:
                if slot_id not in loadout.slot_ids():
                    continue
                for index, item in reversed(list(enumerate(loadout.equipped(slot_id)))):
                    self.ensure(item)
                    if item.durability is None or item.broken:
                        continue
                    item.durability = max(0.0, item.durability - rule.amount)
                    if item.broken:
                        broke.append(item)
                        if self.on_break == "destroy":
                            loadout.unequip(slot_id, index)
        return tuple(broke)

    def repair_cost(self, item, amount=None):
        """Price of restoring ``amount`` points (default: all the way) as ``(currency, cost)``."""
        if item.durability is None:
            return self.repair_currency, 0.0
        missing = item.max_durability - item.durability
        points = missing if amount is None else min(missing, max(0.0, float(amount)))
        return self.repair_currency, float(ceil(points * self.repair_cost_per_point))

    def repair(self, item, amount=None):
        """Restore durability; returns the points restored."""
        if item.durability is None:
            return 0.0
        missing = item.max_durability - item.durability
        points = missing if amount is None else min(missing, max(0.0, float(amount)))
        item.durability += points
        return points

    def to_data(self):
        return {
            "schema": "asteria.rpg.durability_rules",
            "version": 1,
            "rules_id": self.rules_id,
            "max_durability": dict(self.max_durability),
            "default_max": self.default_max,
            "wear": [
                {"event": w.event, "slots": list(w.slots), "amount": w.amount} for w in self.wear
            ],
            "on_break": self.on_break,
            "repair_currency": self.repair_currency,
            "repair_cost_per_point": self.repair_cost_per_point,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.durability_rules" or data.get("version") != 1:
            raise ValueError("unsupported durability rules")
        return cls(
            data["rules_id"],
            max_durability=data.get("max_durability"),
            default_max=data.get("default_max", 0.0),
            wear=tuple(WearEvent(**x) for x in data.get("wear", ())),
            on_break=data.get("on_break", "disable"),
            repair_currency=data.get("repair_currency", ""),
            repair_cost_per_point=data.get("repair_cost_per_point", 0.0),
        )


def _fail(message):
    raise ValueError(message)
