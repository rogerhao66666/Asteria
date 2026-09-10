from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from .states import StateRuntime
from .stats import ResourcePool, StatBlock
from .tags import TagSet, normalize_tag


class ConditionSubject(str, Enum):
    SOURCE = "source"
    TARGET = "target"


class ConditionValueKind(str, Enum):
    STAT = "stat"
    RESOURCE_CURRENT = "resource_current"
    RESOURCE_MAX = "resource_max"
    RESOURCE_RATIO = "resource_ratio"


_COMPARATORS = {"==", "!=", "<", "<=", ">", ">="}


def _compare(current, operator, expected):
    if operator not in _COMPARATORS:
        raise ValueError(f"unsupported comparator: {operator}")
    try:
        if operator == "==":
            return current == expected
        if operator == "!=":
            return current != expected
        if operator == "<":
            return current < expected
        if operator == "<=":
            return current <= expected
        if operator == ">":
            return current > expected
        return current >= expected
    except TypeError:
        return False


@dataclass(frozen=True, slots=True)
class GameplaySubject:
    stats: StatBlock
    resources: ResourcePool
    tags: TagSet
    states: StateRuntime | None = None


@dataclass(frozen=True, slots=True)
class GameplayConditionContext:
    source: GameplaySubject
    target: GameplaySubject | None = None


class GameplayCondition:
    def evaluate(self, context: GameplayConditionContext) -> bool:
        raise NotImplementedError

    def to_data(self):
        raise NotImplementedError


def _subject(context, subject):
    subject = ConditionSubject(subject)
    if subject == ConditionSubject.SOURCE:
        return context.source
    if context.target is None:
        return None
    return context.target


@dataclass(frozen=True, slots=True)
class NumericCondition(GameplayCondition):
    subject: ConditionSubject
    kind: ConditionValueKind
    key: str
    operator: str
    value: float

    def __init__(self, subject, kind, key, operator, value):
        key = str(key).strip()
        if not key:
            raise ValueError("condition key is required")
        operator = str(operator)
        if operator not in _COMPARATORS:
            raise ValueError(f"unsupported comparator: {operator}")
        value = float(value)
        if not isfinite(value):
            raise ValueError("condition value must be finite")
        object.__setattr__(self, "subject", ConditionSubject(subject))
        object.__setattr__(self, "kind", ConditionValueKind(kind))
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "operator", operator)
        object.__setattr__(self, "value", value)

    def evaluate(self, context):
        subject = _subject(context, self.subject)
        if subject is None:
            return False

        if self.kind == ConditionValueKind.STAT:
            current = subject.stats.get(self.key)
        elif self.kind == ConditionValueKind.RESOURCE_CURRENT:
            current = subject.resources.current(self.key)
        elif self.kind == ConditionValueKind.RESOURCE_MAX:
            current = subject.resources.maximum(self.key)
        elif self.kind == ConditionValueKind.RESOURCE_RATIO:
            resource = subject.resources.get(self.key)
            current = resource.normalized
        else:
            raise ValueError(f"unsupported condition kind: {self.kind}")
        return _compare(current, self.operator, self.value)

    def to_data(self):
        return {
            "type": "numeric",
            "subject": self.subject.value,
            "kind": self.kind.value,
            "key": self.key,
            "operator": self.operator,
            "value": self.value,
        }

    @classmethod
    def from_data(cls, data):
        expected = {"type", "subject", "kind", "key", "operator", "value"}
        if set(data) != expected or data["type"] != "numeric":
            raise ValueError("invalid numeric condition")
        return cls(
            data["subject"],
            data["kind"],
            data["key"],
            data["operator"],
            data["value"],
        )


@dataclass(frozen=True, slots=True)
class TagCondition(GameplayCondition):
    subject: ConditionSubject
    tag: str
    present: bool = True

    def __init__(self, subject, tag, present=True):
        object.__setattr__(self, "subject", ConditionSubject(subject))
        object.__setattr__(self, "tag", normalize_tag(tag))
        object.__setattr__(self, "present", bool(present))

    def evaluate(self, context):
        subject = _subject(context, self.subject)
        if subject is None:
            return False
        current = subject.tags.contains(self.tag)
        return current if self.present else not current

    def to_data(self):
        return {
            "type": "tag",
            "subject": self.subject.value,
            "tag": self.tag,
            "present": self.present,
        }

    @classmethod
    def from_data(cls, data):
        expected = {"type", "subject", "tag", "present"}
        if set(data) != expected or data["type"] != "tag":
            raise ValueError("invalid tag condition")
        return cls(data["subject"], data["tag"], data["present"])


@dataclass(frozen=True, slots=True)
class StateCondition(GameplayCondition):
    subject: ConditionSubject
    state_id: str
    present: bool = True
    minimum_stacks: int = 1

    def __init__(self, subject, state_id, present=True, minimum_stacks=1):
        state_id = str(state_id).strip()
        if not state_id:
            raise ValueError("state_id is required")
        minimum_stacks = int(minimum_stacks)
        if minimum_stacks < 1:
            raise ValueError("minimum_stacks must be >= 1")
        object.__setattr__(self, "subject", ConditionSubject(subject))
        object.__setattr__(self, "state_id", state_id)
        object.__setattr__(self, "present", bool(present))
        object.__setattr__(self, "minimum_stacks", minimum_stacks)

    def evaluate(self, context):
        subject = _subject(context, self.subject)
        if subject is None or subject.states is None:
            return not self.present
        active = subject.states.get(self.state_id)
        matched = active is not None and active.stacks >= self.minimum_stacks
        return matched if self.present else not matched

    def to_data(self):
        return {
            "type": "state",
            "subject": self.subject.value,
            "state_id": self.state_id,
            "present": self.present,
            "minimum_stacks": self.minimum_stacks,
        }

    @classmethod
    def from_data(cls, data):
        expected = {"type", "subject", "state_id", "present", "minimum_stacks"}
        if set(data) != expected or data["type"] != "state":
            raise ValueError("invalid state condition")
        return cls(
            data["subject"],
            data["state_id"],
            data["present"],
            data["minimum_stacks"],
        )


class ConditionGroupMode(str, Enum):
    ALL = "all"
    ANY = "any"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ConditionGroup(GameplayCondition):
    mode: ConditionGroupMode
    conditions: tuple[GameplayCondition, ...]

    def __init__(self, conditions=(), *, mode=ConditionGroupMode.ALL):
        conditions = tuple(conditions)
        if any(not isinstance(x, GameplayCondition) for x in conditions):
            raise TypeError("conditions must be GameplayCondition values")
        object.__setattr__(self, "mode", ConditionGroupMode(mode))
        object.__setattr__(self, "conditions", conditions)

    def evaluate(self, context):
        values = [condition.evaluate(context) for condition in self.conditions]
        if self.mode == ConditionGroupMode.ALL:
            return all(values)
        if self.mode == ConditionGroupMode.ANY:
            return any(values)
        return not any(values)

    def to_data(self):
        return {
            "type": "group",
            "mode": self.mode.value,
            "conditions": [serialize_condition(x) for x in self.conditions],
        }

    @classmethod
    def from_data(cls, data):
        expected = {"type", "mode", "conditions"}
        if set(data) != expected or data["type"] != "group":
            raise ValueError("invalid condition group")
        if not isinstance(data["conditions"], list):
            raise TypeError("conditions must be a list")
        return cls(
            [deserialize_condition(x) for x in data["conditions"]],
            mode=data["mode"],
        )


def serialize_condition(condition):
    if not isinstance(condition, GameplayCondition):
        raise TypeError("condition must be GameplayCondition")
    return condition.to_data()


def deserialize_condition(data):
    condition_type = data.get("type")
    if condition_type == "numeric":
        return NumericCondition.from_data(data)
    if condition_type == "tag":
        return TagCondition.from_data(data)
    if condition_type == "state":
        return StateCondition.from_data(data)
    if condition_type == "group":
        return ConditionGroup.from_data(data)
    raise ValueError(f"unknown gameplay condition type: {condition_type}")
