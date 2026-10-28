from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite

from .stats import StatBlock
from .tags import TagSet, normalize_tag


def _number(value, *, name="value"):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


class ModifierOperation(str, Enum):
    ADD = "add"
    MULTIPLY = "multiply"
    OVERRIDE = "override"


@dataclass(frozen=True, slots=True)
class StatModifier:
    """One deterministic transformation of a named stat.

    Evaluation order is:
      1. ADD
      2. MULTIPLY
      3. OVERRIDE

    Within an operation, modifiers are ordered by (priority, modifier_id).
    The highest ordered applicable OVERRIDE therefore wins.
    """

    modifier_id: str
    stat: str
    operation: ModifierOperation
    value: float
    priority: int = 0
    required_tags: tuple[str, ...] = ()
    blocked_tags: tuple[str, ...] = ()

    def __init__(
        self,
        modifier_id,
        stat,
        operation,
        value,
        *,
        priority=0,
        required_tags=(),
        blocked_tags=(),
    ):
        modifier_id = str(modifier_id).strip()
        stat = str(stat).strip()
        if not modifier_id:
            raise ValueError("modifier_id is required")
        if not stat:
            raise ValueError("modifier stat is required")
        object.__setattr__(self, "modifier_id", modifier_id)
        object.__setattr__(self, "stat", stat)
        object.__setattr__(self, "operation", ModifierOperation(operation))
        object.__setattr__(self, "value", _number(value))
        object.__setattr__(self, "priority", int(priority))
        object.__setattr__(
            self,
            "required_tags",
            tuple(sorted({normalize_tag(x) for x in required_tags})),
        )
        object.__setattr__(
            self,
            "blocked_tags",
            tuple(sorted({normalize_tag(x) for x in blocked_tags})),
        )

    def applies(self, tags: TagSet | None = None):
        tags = tags or TagSet()
        return tags.contains_all(self.required_tags) and not tags.contains_any(self.blocked_tags)

    def to_data(self):
        return {
            "modifier_id": self.modifier_id,
            "stat": self.stat,
            "operation": self.operation.value,
            "value": self.value,
            "priority": self.priority,
            "required_tags": list(self.required_tags),
            "blocked_tags": list(self.blocked_tags),
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "modifier_id",
            "stat",
            "operation",
            "value",
            "priority",
            "required_tags",
            "blocked_tags",
        }
        if set(data) != expected:
            raise ValueError("invalid stat modifier")
        if not isinstance(data["required_tags"], list):
            raise TypeError("required_tags must be a list")
        if not isinstance(data["blocked_tags"], list):
            raise TypeError("blocked_tags must be a list")
        return cls(
            data["modifier_id"],
            data["stat"],
            data["operation"],
            data["value"],
            priority=data["priority"],
            required_tags=data["required_tags"],
            blocked_tags=data["blocked_tags"],
        )


class _ModifierTable(dict):
    """modifier id -> StatModifier, remembering its ordered views until it next changes.

    The views live on the table itself, so anything sharing the table (a shallow copy of the
    set) shares them too, and every dict mutation drops them.
    """

    views = None  # (all modifiers in order, {stat: modifiers of that stat in order})

    def _changed(self):
        self.views = None

    def __setitem__(self, key, value):
        self._changed()
        super().__setitem__(key, value)

    def __delitem__(self, key):
        self._changed()
        super().__delitem__(key)

    def pop(self, *args):
        self._changed()
        return super().pop(*args)

    def popitem(self):
        self._changed()
        return super().popitem()

    def setdefault(self, key, default=None):
        self._changed()
        return super().setdefault(key, default)

    def update(self, *args, **kwargs):
        self._changed()
        super().update(*args, **kwargs)

    def clear(self):
        self._changed()
        super().clear()

    def __ior__(self, other):
        self._changed()
        return super().__ior__(other)

    def ordered(self):
        views = self.views
        if views is None:
            ordered = tuple(sorted(self.values(), key=lambda m: (m.priority, m.modifier_id)))
            by_stat = {}
            for modifier in ordered:
                by_stat.setdefault(modifier.stat, []).append(modifier)
            views = self.views = (
                ordered,
                {stat: tuple(items) for stat, items in by_stat.items()},
            )
        return views


@dataclass(slots=True)
class ModifierSet:
    _modifiers: dict[str, StatModifier] = field(default_factory=_ModifierTable)

    def __init__(self, modifiers=()):
        self._modifiers = _ModifierTable()
        for modifier in modifiers:
            self.add(modifier)

    def add(self, modifier: StatModifier):
        if not isinstance(modifier, StatModifier):
            raise TypeError("modifier must be StatModifier")
        if modifier.modifier_id in self._modifiers:
            raise ValueError(f"duplicate modifier ID: {modifier.modifier_id}")
        self._modifiers[modifier.modifier_id] = modifier
        return modifier

    def replace(self, modifier: StatModifier):
        if not isinstance(modifier, StatModifier):
            raise TypeError("modifier must be StatModifier")
        self._modifiers[modifier.modifier_id] = modifier
        return modifier

    def remove(self, modifier_id):
        return self._modifiers.pop(str(modifier_id))

    def _ordered(self):
        table = self._modifiers
        if not isinstance(table, _ModifierTable):  # a plain dict was assigned: no caching
            ordered = tuple(sorted(table.values(), key=lambda m: (m.priority, m.modifier_id)))
            return ordered, None
        return table.ordered()

    def modifiers(self):
        return self._ordered()[0]

    def for_stat(self, stat, *, tags=None):
        stat = str(stat)
        tags = tags or TagSet()
        ordered, by_stat = self._ordered()
        if by_stat is None:
            return tuple(m for m in ordered if m.stat == stat and m.applies(tags))
        return tuple(m for m in by_stat.get(stat, ()) if m.applies(tags))

    def evaluate(self, stat, base_value, *, tags=None):
        value = _number(base_value, name=str(stat))
        modifiers = self.for_stat(stat, tags=tags)

        for modifier in modifiers:
            if modifier.operation == ModifierOperation.ADD:
                value += modifier.value

        for modifier in modifiers:
            if modifier.operation == ModifierOperation.MULTIPLY:
                value *= modifier.value

        overrides = [m for m in modifiers if m.operation == ModifierOperation.OVERRIDE]
        if overrides:
            value = overrides[-1].value

        return _number(value, name=str(stat))

    def evaluate_block(self, base: StatBlock, *, tags=None):
        if not isinstance(base, StatBlock):
            raise TypeError("base must be StatBlock")
        names = set(base.names())
        names.update(m.stat for m in self._modifiers.values())
        return StatBlock(
            {name: self.evaluate(name, base.get(name), tags=tags) for name in sorted(names)}
        )

    def to_data(self):
        return {
            "schema": "asteria.modifier_set",
            "version": 1,
            "modifiers": [m.to_data() for m in self.modifiers()],
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"schema", "version", "modifiers"}:
            raise ValueError("invalid modifier set")
        if data["schema"] != "asteria.modifier_set" or data["version"] != 1:
            raise ValueError("unsupported modifier set")
        if not isinstance(data["modifiers"], list):
            raise TypeError("modifiers must be a list")
        return cls(StatModifier.from_data(raw) for raw in data["modifiers"])
