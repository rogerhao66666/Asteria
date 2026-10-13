"""Weighted and guaranteed drop tables (RPG-04, ASTERIA_SPEC §23 loot).

A ``DropTable`` is referenced by an enemy reward (``RewardDefinition.drop_table_id``)
and rolled on victory, alongside the reward's independent ``loot`` chances:

* ``rolls`` weighted picks from ``entries`` (``weight``, quantity ``minimum``..``maximum``,
  ``rarity`` label, ``required_switch``); ``nothing_weight`` is the weight of "no drop"
* ``guaranteed`` entries always drop
* ``pity`` rules: after ``after_misses`` consecutive tables rolled without the item,
  the next roll gives it for sure; the counter lives in the save (world counters
  ``pity:<table>:<item>``), so pity survives save/load
* ``luck`` (difficulty / luck modifiers) multiplies the weight of entries whose rarity
  is not ``common`` by (1 + luck x ``luck_weight_bonus``)
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

RARITIES = ("common", "uncommon", "rare", "epic", "legendary")


def _num(value, label, *, minimum=0.0):
    value = float(value)
    if not isfinite(value) or value < minimum:
        raise ValueError(f"{label} must be a number >= {minimum}")
    return value


@dataclass(frozen=True, slots=True)
class DropEntry:
    item_id: str
    weight: float = 1.0
    minimum: int = 1
    maximum: int = 1
    rarity: str = "common"
    required_switch: str = ""

    def __post_init__(self):
        if not str(self.item_id).strip():
            raise ValueError("drop entry item_id is required")
        object.__setattr__(self, "weight", _num(self.weight, "weight"))
        if int(self.minimum) < 0 or int(self.maximum) < int(self.minimum):
            raise ValueError("invalid drop quantity")
        object.__setattr__(self, "minimum", int(self.minimum))
        object.__setattr__(self, "maximum", int(self.maximum))
        if not str(self.rarity).strip():
            raise ValueError(
                "rarity is required (any authored rarity id; RARITIES are the defaults)"
            )

    def to_data(self):
        return {
            "item_id": self.item_id,
            "weight": self.weight,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "rarity": self.rarity,
            "required_switch": self.required_switch,
        }


@dataclass(frozen=True, slots=True)
class PityRule:
    item_id: str
    after_misses: int = 10

    def __post_init__(self):
        if not str(self.item_id).strip() or int(self.after_misses) < 1:
            raise ValueError("pity rule needs an item and after_misses >= 1")
        object.__setattr__(self, "after_misses", int(self.after_misses))

    def to_data(self):
        return {"item_id": self.item_id, "after_misses": self.after_misses}


@dataclass(frozen=True, slots=True)
class DropTable:
    table_id: str
    display_name: str = ""
    rolls: int = 1
    nothing_weight: float = 0.0
    entries: tuple = ()
    guaranteed: tuple = ()  # DropEntry (weight ignored)
    pity: tuple = ()  # PityRule
    luck_weight_bonus: float = 0.0

    def __post_init__(self):
        if not str(self.table_id).strip():
            raise ValueError("table_id is required")
        if int(self.rolls) < 0:
            raise ValueError("rolls must be >= 0")
        object.__setattr__(self, "rolls", int(self.rolls))
        object.__setattr__(self, "nothing_weight", _num(self.nothing_weight, "nothing_weight"))
        object.__setattr__(
            self, "luck_weight_bonus", _num(self.luck_weight_bonus, "luck_weight_bonus")
        )
        object.__setattr__(self, "entries", tuple(_entry(x) for x in self.entries))
        object.__setattr__(self, "guaranteed", tuple(_entry(x) for x in self.guaranteed))
        object.__setattr__(
            self,
            "pity",
            tuple(x if isinstance(x, PityRule) else PityRule(**dict(x)) for x in self.pity),
        )

    def item_ids(self):
        return {e.item_id for e in (*self.entries, *self.guaranteed)} | {
            p.item_id for p in self.pity
        }

    def to_data(self):
        return {
            "schema": "asteria.rpg.drop_table",
            "version": 1,
            "table_id": self.table_id,
            "display_name": self.display_name,
            "rolls": self.rolls,
            "nothing_weight": self.nothing_weight,
            "entries": [x.to_data() for x in self.entries],
            "guaranteed": [x.to_data() for x in self.guaranteed],
            "pity": [x.to_data() for x in self.pity],
            "luck_weight_bonus": self.luck_weight_bonus,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.drop_table" or data.get("version") != 1:
            raise ValueError("unsupported drop table")
        values = {k: v for k, v in data.items() if k not in ("schema", "version")}
        return cls(**values)


def _entry(value):
    return value if isinstance(value, DropEntry) else DropEntry(**dict(value))


def roll_drop_table(table, rng, *, counters=None, luck=0.0, switches=None):
    """Items ``{item_id: quantity}`` from one roll of ``table``; updates pity ``counters`` in
    place."""
    counters = {} if counters is None else counters
    items = {}

    def give(entry):
        amount = rng.randint(entry.minimum, entry.maximum)
        if amount:
            items[entry.item_id] = items.get(entry.item_id, 0) + amount

    for entry in table.guaranteed:
        if not entry.required_switch or (switches is not None and switches(entry.required_switch)):
            give(entry)
    pool = [
        e
        for e in table.entries
        if not e.required_switch or (switches is not None and switches(e.required_switch))
    ]
    for _ in range(table.rolls):
        weights = [
            e.weight * (1.0 + luck * table.luck_weight_bonus if e.rarity != "common" else 1.0)
            for e in pool
        ]
        total = sum(weights) + table.nothing_weight
        if total <= 0:
            break
        pick = rng.random() * total
        for entry, weight in zip(pool, weights, strict=True):
            if pick < weight:
                give(entry)
                break
            pick -= weight
    by_id = {e.item_id: e for e in (*table.entries, *table.guaranteed)}
    for rule in table.pity:
        key = f"pity:{table.table_id}:{rule.item_id}"
        if rule.item_id in items:
            counters[key] = 0.0
            continue
        misses = counters.get(key, 0.0) + 1
        if misses >= rule.after_misses:
            give(by_id.get(rule.item_id, DropEntry(rule.item_id)))
            misses = 0.0
        counters[key] = float(misses)
    return items
