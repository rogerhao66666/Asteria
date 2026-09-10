from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite


def _finite_number(value, *, name="value"):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


@dataclass(slots=True)
class StatBlock:
    """Generic named numeric stats with stable string keys.

    This layer intentionally knows nothing about RPG-specific names such as
    strength, attack, agility, or defense. Games define their own keys.
    """

    _values: dict[str, float] = field(default_factory=dict)

    def __init__(self, values=None):
        self._values = {}
        for name, value in dict(values or {}).items():
            self.set(name, value)

    def names(self):
        return tuple(self._values)

    def contains(self, name):
        return str(name) in self._values

    def get(self, name, default=0.0):
        return float(self._values.get(str(name), default))

    def require(self, name):
        key = str(name)
        if key not in self._values:
            raise KeyError(f"unknown stat: {key}")
        return self._values[key]

    def set(self, name, value):
        key = str(name).strip()
        if not key:
            raise ValueError("stat name is required")
        self._values[key] = _finite_number(value, name=key)
        return self._values[key]

    def add(self, name, delta):
        return self.set(name, self.get(name) + _finite_number(delta))

    def remove(self, name):
        return self._values.pop(str(name))

    def to_data(self):
        return {
            "schema": "asteria.stat_block",
            "version": 1,
            "values": dict(self._values),
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"schema", "version", "values"}:
            raise ValueError("invalid stat block")
        if data["schema"] != "asteria.stat_block" or data["version"] != 1:
            raise ValueError("unsupported stat block")
        if not isinstance(data["values"], dict):
            raise TypeError("stat values must be an object")
        return cls(data["values"])

    def replace_from(self, other):
        """Replace contents from another validated StatBlock."""
        if not isinstance(other, StatBlock):
            raise TypeError("other must be StatBlock")
        self._values = dict(other._values)
        return self

    def replace_from_data(self, data):
        return self.replace_from(type(self).from_data(data))


@dataclass(slots=True)
class ResourceValue:
    current: float
    maximum: float
    minimum: float = 0.0

    def __post_init__(self):
        self.minimum = _finite_number(self.minimum, name="minimum")
        self.maximum = _finite_number(self.maximum, name="maximum")
        if self.maximum < self.minimum:
            raise ValueError("resource maximum must be >= minimum")
        self.current = self.clamp(self.current)

    def clamp(self, value):
        value = _finite_number(value, name="current")
        return max(self.minimum, min(self.maximum, value))

    @property
    def normalized(self):
        span = self.maximum - self.minimum
        return 0.0 if span <= 0.0 else (self.current - self.minimum) / span

    @property
    def empty(self):
        return self.current <= self.minimum

    @property
    def full(self):
        return self.current >= self.maximum

    def set_current(self, value):
        self.current = self.clamp(value)
        return self.current

    def change(self, delta):
        return self.set_current(self.current + _finite_number(delta))

    def set_maximum(self, value, *, preserve_ratio=False):
        old_ratio = self.normalized
        value = _finite_number(value, name="maximum")
        if value < self.minimum:
            raise ValueError("resource maximum must be >= minimum")
        self.maximum = value
        if preserve_ratio:
            self.current = self.minimum + old_ratio * (self.maximum - self.minimum)
        else:
            self.current = self.clamp(self.current)
        return self.maximum

    def to_data(self):
        return {
            "current": self.current,
            "maximum": self.maximum,
            "minimum": self.minimum,
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"current", "maximum", "minimum"}:
            raise ValueError("invalid resource value")
        return cls(data["current"], data["maximum"], data["minimum"])


@dataclass(slots=True)
class ResourcePool:
    """Named bounded resources such as HP, MP, stamina, guard or custom meters."""

    _values: dict[str, ResourceValue] = field(default_factory=dict)

    def define(self, name, maximum, *, current=None, minimum=0.0, replace=False):
        key = str(name).strip()
        if not key:
            raise ValueError("resource name is required")
        if key in self._values and not replace:
            raise ValueError(f"resource already exists: {key}")
        if current is None:
            current = maximum
        self._values[key] = ResourceValue(current, maximum, minimum)
        return self._values[key]

    def names(self):
        return tuple(self._values)

    def contains(self, name):
        return str(name) in self._values

    def get(self, name):
        try:
            return self._values[str(name)]
        except KeyError as exc:
            raise KeyError(f"unknown resource: {name}") from exc

    def current(self, name):
        return self.get(name).current

    def maximum(self, name):
        return self.get(name).maximum

    def set_current(self, name, value):
        return self.get(name).set_current(value)

    def change(self, name, delta):
        return self.get(name).change(delta)

    def spend(self, name, amount):
        amount = _finite_number(amount, name="amount")
        if amount < 0:
            raise ValueError("spend amount must be >= 0")
        resource = self.get(name)
        if resource.current - amount < resource.minimum:
            return False
        resource.change(-amount)
        return True

    def restore(self, name, amount):
        amount = _finite_number(amount, name="amount")
        if amount < 0:
            raise ValueError("restore amount must be >= 0")
        return self.get(name).change(amount)

    def to_data(self):
        return {
            "schema": "asteria.resource_pool",
            "version": 1,
            "values": {name: value.to_data() for name, value in self._values.items()},
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"schema", "version", "values"}:
            raise ValueError("invalid resource pool")
        if data["schema"] != "asteria.resource_pool" or data["version"] != 1:
            raise ValueError("unsupported resource pool")
        if not isinstance(data["values"], dict):
            raise TypeError("resource values must be an object")
        result = cls()
        for name, raw in data["values"].items():
            key = str(name).strip()
            if not key:
                raise ValueError("resource name is required")
            result._values[key] = ResourceValue.from_data(raw)
        return result

    def replace_from(self, other):
        """Replace contents from another validated ResourcePool."""
        if not isinstance(other, ResourcePool):
            raise TypeError("other must be ResourcePool")
        rebuilt = type(self).from_data(other.to_data())
        self._values = rebuilt._values
        return self

    def replace_from_data(self, data):
        return self.replace_from(type(self).from_data(data))
