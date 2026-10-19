"""Derived stats: one stat computed from others, written as project data.

A rule reads ``stat = base + sum(coefficient x source stat)`` and adds the result to whatever the
stat already has (gear, jobs, trees, passives). Rules run in ``order`` (then by id), so a later
rule may read a stat an earlier one derived. ``minimum`` keeps the stat at or above a floor and
``maximum`` caps it (0 = no cap). ``applies_to`` picks who uses it: party ``actors``, ``enemies``
or ``all``. Typical use: points in Strength / Dexterity / Intellect / Luck that become attack,
defence, accuracy, evasion and critical rate.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

APPLIES_TO = ("actors", "enemies", "all")


def _number(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


@dataclass(frozen=True, slots=True)
class DerivedStatRule:
    stat_id: str
    display_name: str = ""
    terms: dict[str, float] = None  # source stat -> coefficient
    base: float = 0.0
    minimum: float = 0.0
    maximum: float = 0.0  # 0 = no cap
    applies_to: str = "actors"
    order: int = 0
    description: str = ""

    SCHEMA = "asteria.rpg.derived_stat"
    VERSION = 1

    def __init__(
        self,
        stat_id,
        display_name="",
        *,
        terms=None,
        base=0.0,
        minimum=0.0,
        maximum=0.0,
        applies_to="actors",
        order=0,
        description="",
    ):
        stat_id = str(stat_id).strip()
        if not stat_id:
            raise ValueError("stat_id is required")
        terms = {str(k).strip(): _number(v, "coefficient") for k, v in dict(terms or {}).items()}
        if "" in terms:
            raise ValueError("a term needs a stat")
        if stat_id in terms:
            raise ValueError(f"{stat_id} cannot read itself")
        if applies_to not in APPLIES_TO:
            raise ValueError(f"applies_to must be one of {', '.join(APPLIES_TO)}")
        minimum, maximum = _number(minimum, "minimum"), _number(maximum, "maximum")
        if maximum and maximum < minimum:
            raise ValueError("maximum must be >= minimum (or 0 for no cap)")
        s = object.__setattr__
        s(self, "stat_id", stat_id)
        s(self, "display_name", str(display_name or stat_id))
        s(self, "terms", dict(sorted(terms.items())))
        s(self, "base", _number(base, "base"))
        s(self, "minimum", minimum)
        s(self, "maximum", maximum)
        s(self, "applies_to", applies_to)
        s(self, "order", int(order))
        s(self, "description", str(description or ""))

    def applies(self, side):
        return self.applies_to == "all" or self.applies_to == side

    def amount(self, stats):
        """What the rule adds to its stat, read from ``stats`` (a StatBlock)."""
        return self.base + sum(c * stats.get(k, 0.0) for k, c in self.terms.items())

    def formula_text(self):
        """``power = 2 x str + 0.5 x dex`` - for menus and the editor."""
        parts = [f"{c:g} x {k}" for k, c in self.terms.items()]
        if self.base or not parts:
            parts.insert(0, f"{self.base:g}")
        text = f"{self.stat_id} += " + " + ".join(parts)
        if self.maximum:
            text += f" (at most {self.maximum:g})"
        return text

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "stat_id": self.stat_id,
            "display_name": self.display_name,
            "terms": dict(self.terms),
            "base": self.base,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "applies_to": self.applies_to,
            "order": self.order,
            "description": self.description,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported derived stat")
        return cls(
            data["stat_id"],
            data.get("display_name", ""),
            terms=data.get("terms", {}),
            base=data.get("base", 0.0),
            minimum=data.get("minimum", 0.0),
            maximum=data.get("maximum", 0.0),
            applies_to=data.get("applies_to", "actors"),
            order=data.get("order", 0),
            description=data.get("description", ""),
        )


def apply_derived_stats(stats, rules, *, side="actors"):
    """Add every applicable rule's amount to ``stats`` (a StatBlock, changed in place); returns
    ``((stat_id, amount), ...)`` in the order applied."""
    applied = []
    for rule in sorted(rules, key=lambda r: (r.order, r.stat_id)):
        if not rule.applies(side):
            continue
        amount = rule.amount(stats)
        value = max(rule.minimum, stats.get(rule.stat_id, 0.0) + amount)
        if rule.maximum:
            value = min(rule.maximum, value)
        stats.set(rule.stat_id, value)
        applied.append((rule.stat_id, amount))
    return tuple(applied)
