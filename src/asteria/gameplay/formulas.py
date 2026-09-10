from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from .stats import ResourcePool, StatBlock
from .tags import TagSet, normalize_tag


def _number(value, *, name="value"):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


class ValueSource(str, Enum):
    CONSTANT = "constant"
    SOURCE_STAT = "source_stat"
    TARGET_STAT = "target_stat"
    SOURCE_RESOURCE_CURRENT = "source_resource_current"
    SOURCE_RESOURCE_MAX = "source_resource_max"
    TARGET_RESOURCE_CURRENT = "target_resource_current"
    TARGET_RESOURCE_MAX = "target_resource_max"


@dataclass(frozen=True, slots=True)
class FormulaTerm:
    source: ValueSource
    key: str = ""
    coefficient: float = 1.0

    def __init__(self, source, key="", coefficient=1.0):
        source = ValueSource(source)
        key = str(key).strip()
        if source != ValueSource.CONSTANT and not key:
            raise ValueError("formula term key is required")
        if source == ValueSource.CONSTANT and key:
            raise ValueError("constant formula term cannot have a key")
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "coefficient", _number(coefficient))

    @classmethod
    def constant(cls, value):
        return cls(ValueSource.CONSTANT, coefficient=value)

    def to_data(self):
        return {
            "source": self.source.value,
            "key": self.key,
            "coefficient": self.coefficient,
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"source", "key", "coefficient"}:
            raise ValueError("invalid formula term")
        return cls(data["source"], data["key"], data["coefficient"])


@dataclass(frozen=True, slots=True)
class FormulaCondition:
    required_source_tags: tuple[str, ...] = ()
    blocked_source_tags: tuple[str, ...] = ()
    required_target_tags: tuple[str, ...] = ()
    blocked_target_tags: tuple[str, ...] = ()

    def __init__(
        self,
        *,
        required_source_tags=(),
        blocked_source_tags=(),
        required_target_tags=(),
        blocked_target_tags=(),
    ):
        for name, values in (
            ("required_source_tags", required_source_tags),
            ("blocked_source_tags", blocked_source_tags),
            ("required_target_tags", required_target_tags),
            ("blocked_target_tags", blocked_target_tags),
        ):
            object.__setattr__(
                self,
                name,
                tuple(sorted({normalize_tag(v) for v in values})),
            )

    def matches(self, source_tags, target_tags):
        return (
            source_tags.contains_all(self.required_source_tags)
            and not source_tags.contains_any(self.blocked_source_tags)
            and target_tags.contains_all(self.required_target_tags)
            and not target_tags.contains_any(self.blocked_target_tags)
        )

    def to_data(self):
        return {
            "required_source_tags": list(self.required_source_tags),
            "blocked_source_tags": list(self.blocked_source_tags),
            "required_target_tags": list(self.required_target_tags),
            "blocked_target_tags": list(self.blocked_target_tags),
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "required_source_tags",
            "blocked_source_tags",
            "required_target_tags",
            "blocked_target_tags",
        }
        if set(data) != expected:
            raise ValueError("invalid formula condition")
        return cls(**data)


@dataclass(frozen=True, slots=True)
class ConditionalMultiplier:
    multiplier: float
    condition: FormulaCondition

    def __init__(self, multiplier, condition):
        if not isinstance(condition, FormulaCondition):
            raise TypeError("condition must be FormulaCondition")
        object.__setattr__(self, "multiplier", _number(multiplier))
        object.__setattr__(self, "condition", condition)

    def to_data(self):
        return {
            "multiplier": self.multiplier,
            "condition": self.condition.to_data(),
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"multiplier", "condition"}:
            raise ValueError("invalid conditional multiplier")
        return cls(data["multiplier"], FormulaCondition.from_data(data["condition"]))


@dataclass(frozen=True, slots=True)
class FormulaContext:
    source_stats: StatBlock
    source_resources: ResourcePool
    source_tags: TagSet
    target_stats: StatBlock
    target_resources: ResourcePool
    target_tags: TagSet


@dataclass(frozen=True, slots=True)
class ValueFormula:
    """GUI-friendly generic value formula.

    The canonical model deliberately uses a small list of typed terms instead
    of an arbitrary expression language. Beginner, standard and advanced GUI
    layers can therefore generate/edit the same data safely.
    """

    terms: tuple[FormulaTerm, ...] = ()
    multipliers: tuple[ConditionalMultiplier, ...] = ()
    minimum: float | None = None
    maximum: float | None = None

    def __init__(self, terms=(), *, multipliers=(), minimum=None, maximum=None):
        terms = tuple(terms)
        multipliers = tuple(multipliers)
        if any(not isinstance(x, FormulaTerm) for x in terms):
            raise TypeError("terms must be FormulaTerm values")
        if any(not isinstance(x, ConditionalMultiplier) for x in multipliers):
            raise TypeError("multipliers must be ConditionalMultiplier values")
        minimum = None if minimum is None else _number(minimum, name="minimum")
        maximum = None if maximum is None else _number(maximum, name="maximum")
        if minimum is not None and maximum is not None and maximum < minimum:
            raise ValueError("formula maximum must be >= minimum")
        object.__setattr__(self, "terms", terms)
        object.__setattr__(self, "multipliers", multipliers)
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)

    @classmethod
    def constant(cls, value, **kwargs):
        return cls([FormulaTerm.constant(value)], **kwargs)

    def evaluate(self, context: FormulaContext):
        if not isinstance(context, FormulaContext):
            raise TypeError("context must be FormulaContext")

        value = 0.0
        for term in self.terms:
            value += self._term_value(term, context) * term.coefficient

        for conditional in self.multipliers:
            if conditional.condition.matches(context.source_tags, context.target_tags):
                value *= conditional.multiplier

        if self.minimum is not None:
            value = max(self.minimum, value)
        if self.maximum is not None:
            value = min(self.maximum, value)
        return _number(value)

    @staticmethod
    def _term_value(term, context):
        if term.source == ValueSource.CONSTANT:
            return 1.0
        if term.source == ValueSource.SOURCE_STAT:
            return context.source_stats.get(term.key)
        if term.source == ValueSource.TARGET_STAT:
            return context.target_stats.get(term.key)
        if term.source == ValueSource.SOURCE_RESOURCE_CURRENT:
            return context.source_resources.current(term.key)
        if term.source == ValueSource.SOURCE_RESOURCE_MAX:
            return context.source_resources.maximum(term.key)
        if term.source == ValueSource.TARGET_RESOURCE_CURRENT:
            return context.target_resources.current(term.key)
        if term.source == ValueSource.TARGET_RESOURCE_MAX:
            return context.target_resources.maximum(term.key)
        raise ValueError(f"unsupported formula source: {term.source}")

    def to_data(self):
        return {
            "schema": "asteria.value_formula",
            "version": 1,
            "terms": [term.to_data() for term in self.terms],
            "multipliers": [m.to_data() for m in self.multipliers],
            "minimum": self.minimum,
            "maximum": self.maximum,
        }

    @classmethod
    def from_data(cls, data):
        expected = {"schema", "version", "terms", "multipliers", "minimum", "maximum"}
        if set(data) != expected:
            raise ValueError("invalid value formula")
        if data["schema"] != "asteria.value_formula" or data["version"] != 1:
            raise ValueError("unsupported value formula")
        return cls(
            [FormulaTerm.from_data(x) for x in data["terms"]],
            multipliers=[
                ConditionalMultiplier.from_data(x) for x in data["multipliers"]
            ],
            minimum=data["minimum"],
            maximum=data["maximum"],
        )


class FormulaBuilder:
    """Progressive-authoring helper; produces the same canonical ValueFormula."""

    def __init__(self):
        self._terms = []
        self._multipliers = []
        self._minimum = None
        self._maximum = None

    def constant(self, value):
        self._terms.append(FormulaTerm.constant(value))
        return self

    def source_stat(self, key, coefficient=1.0):
        self._terms.append(FormulaTerm("source_stat", key, coefficient))
        return self

    def target_stat(self, key, coefficient=1.0):
        self._terms.append(FormulaTerm("target_stat", key, coefficient))
        return self

    def source_resource_current(self, key, coefficient=1.0):
        self._terms.append(FormulaTerm("source_resource_current", key, coefficient))
        return self

    def source_resource_max(self, key, coefficient=1.0):
        self._terms.append(FormulaTerm("source_resource_max", key, coefficient))
        return self

    def target_resource_current(self, key, coefficient=1.0):
        self._terms.append(FormulaTerm("target_resource_current", key, coefficient))
        return self

    def target_resource_max(self, key, coefficient=1.0):
        self._terms.append(FormulaTerm("target_resource_max", key, coefficient))
        return self

    def multiply_when(self, multiplier, condition):
        self._multipliers.append(ConditionalMultiplier(multiplier, condition))
        return self

    def clamp(self, *, minimum=None, maximum=None):
        self._minimum = minimum
        self._maximum = maximum
        return self

    def build(self):
        return ValueFormula(
            self._terms,
            multipliers=self._multipliers,
            minimum=self._minimum,
            maximum=self._maximum,
        )
