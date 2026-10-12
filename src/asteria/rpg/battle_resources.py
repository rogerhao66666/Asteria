from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from asteria.core.lifecycle import emit_hook


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _number(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


class BattleResourceStartMode(str, Enum):
    FIXED = "fixed"
    CURRENT = "current"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"


class BattleResourceEndMode(str, Enum):
    PERSIST = "persist"
    RESTORE_INITIAL = "restore_initial"
    RESET_TO_START = "reset_to_start"


@dataclass(frozen=True, slots=True)
class BattleResourceRule:
    trigger: str
    amount: float

    def __init__(self, trigger, amount):
        object.__setattr__(self, "trigger", _id(trigger, "trigger"))
        object.__setattr__(self, "amount", _number(amount, "amount"))

    def to_data(self):
        return {"trigger": self.trigger, "amount": self.amount}

    @classmethod
    def from_data(cls, data):
        if set(data) != {"trigger", "amount"}:
            raise ValueError("invalid battle resource rule")
        return cls(data["trigger"], data["amount"])


@dataclass(frozen=True, slots=True)
class BattleResourceDefinition:
    """Project-defined combat resource/gauge policy.

    `resource_id` may bind to an existing GameplaySubject resource with the same
    key (HP/MP/etc.) or define a combat-only gauge. Nothing here assigns semantic
    meaning to names such as MP, rage, stagger, combo, boost, or guard.
    """

    resource_id: str
    minimum: float | None = None
    maximum: float | None = None
    start_mode: BattleResourceStartMode = BattleResourceStartMode.CURRENT
    start_value: float | None = None
    end_mode: BattleResourceEndMode = BattleResourceEndMode.PERSIST
    overflow_limit: float | None = None
    rules: tuple[BattleResourceRule, ...] = ()
    # A member whose own subject carries this resource uses its maximum instead of ``maximum`` (e.g. every
    # enemy its own shield count); the others use ``maximum``. Left out of the data while False.
    subject_maximum: bool = False
    OPTIONAL_DATA = {"subject_maximum": False}

    SCHEMA = "asteria.rpg.battle_resource"
    VERSION = 1

    def __init__(
        self,
        resource_id,
        *,
        minimum=None,
        maximum=None,
        start_mode=BattleResourceStartMode.CURRENT,
        start_value=None,
        end_mode=BattleResourceEndMode.PERSIST,
        overflow_limit=None,
        rules=(),
        subject_maximum=False,
    ):
        resource_id = _id(resource_id, "resource_id")
        minimum = None if minimum is None else _number(minimum, "minimum")
        maximum = None if maximum is None else _number(maximum, "maximum")
        if minimum is not None and maximum is not None and maximum < minimum:
            raise ValueError("maximum must be >= minimum")
        start_mode = BattleResourceStartMode(start_mode)
        start_value = None if start_value is None else _number(start_value, "start_value")
        if start_mode == BattleResourceStartMode.FIXED and start_value is None:
            raise ValueError("fixed start mode requires start_value")
        end_mode = BattleResourceEndMode(end_mode)
        overflow_limit = None if overflow_limit is None else _number(overflow_limit, "overflow_limit")
        if overflow_limit is not None and maximum is not None and overflow_limit < maximum:
            raise ValueError("overflow_limit must be >= maximum")
        normalized_rules = tuple(x if isinstance(x, BattleResourceRule) else BattleResourceRule(**x) for x in rules)
        object.__setattr__(self, "resource_id", resource_id)
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)
        object.__setattr__(self, "start_mode", start_mode)
        object.__setattr__(self, "start_value", start_value)
        object.__setattr__(self, "end_mode", end_mode)
        object.__setattr__(self, "overflow_limit", overflow_limit)
        object.__setattr__(self, "rules", normalized_rules)
        object.__setattr__(self, "subject_maximum", bool(subject_maximum))

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "resource_id": self.resource_id,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "start_mode": self.start_mode.value,
            "start_value": self.start_value,
            "end_mode": self.end_mode.value,
            "overflow_limit": self.overflow_limit,
            "rules": [x.to_data() for x in self.rules],
            **({"subject_maximum": True} if self.subject_maximum else {}),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported battle resource definition")
        return cls(
            data["resource_id"],
            minimum=data.get("minimum"),
            maximum=data.get("maximum"),
            start_mode=data.get("start_mode", BattleResourceStartMode.CURRENT.value),
            start_value=data.get("start_value"),
            end_mode=data.get("end_mode", BattleResourceEndMode.PERSIST.value),
            overflow_limit=data.get("overflow_limit"),
            rules=[BattleResourceRule.from_data(x) for x in data.get("rules", ())],
            subject_maximum=data.get("subject_maximum", False),
        )


@dataclass(slots=True)
class BattleResourceValue:
    current: float
    minimum: float
    maximum: float
    overflow_limit: float
    initial: float
    start_value: float
    bound_to_subject: bool = False

    def __post_init__(self):
        self.minimum = _number(self.minimum, "minimum")
        self.maximum = _number(self.maximum, "maximum")
        self.overflow_limit = _number(self.overflow_limit, "overflow_limit")
        if self.maximum < self.minimum:
            raise ValueError("maximum must be >= minimum")
        if self.overflow_limit < self.maximum:
            raise ValueError("overflow_limit must be >= maximum")
        self.initial = self.clamp(self.initial)
        self.start_value = self.clamp(self.start_value)
        self.current = self.clamp(self.current)

    def clamp(self, value):
        value = _number(value, "current")
        return max(self.minimum, min(self.overflow_limit, value))

    @property
    def full(self):
        return self.current >= self.maximum

    @property
    def overflow(self):
        return max(0.0, self.current - self.maximum)

    @property
    def normalized(self):
        span = self.maximum - self.minimum
        if span <= 0:
            return 0.0
        return max(0.0, min(1.0, (self.current - self.minimum) / span))

    def to_data(self):
        return {
            "current": self.current,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "overflow_limit": self.overflow_limit,
            "initial": self.initial,
            "start_value": self.start_value,
            "bound_to_subject": self.bound_to_subject,
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "current",
            "minimum",
            "maximum",
            "overflow_limit",
            "initial",
            "start_value",
            "bound_to_subject",
        }
        if set(data) != expected:
            raise ValueError("invalid battle resource value")
        return cls(**data)


@dataclass(frozen=True, slots=True)
class BattleResourceChange:
    member_id: str
    resource_id: str
    before: float
    after: float
    requested_delta: float
    applied_delta: float
    trigger: str | None = None


class BattleResourceRuntime:
    """Combat-scoped resource runtime for arbitrary gauges.

    Existing GameplaySubject resources are mirrored when compatible. Combat-only
    gauges remain local. Lifecycle trigger rules are explicit and deterministic;
    event names are project-defined strings rather than a closed engine enum.
    """

    SCHEMA = "asteria.rpg.battle_resource_runtime"
    VERSION = 1

    def __init__(self, definitions=(), members=(), *, hooks=None):
        definitions = tuple(definitions)
        members = tuple(members)
        self.definitions = {}
        for definition in definitions:
            if not isinstance(definition, BattleResourceDefinition):
                raise TypeError("definitions must contain BattleResourceDefinition values")
            if definition.resource_id in self.definitions:
                raise ValueError(f"duplicate battle resource definition: {definition.resource_id}")
            self.definitions[definition.resource_id] = definition
        self.members = {m.member_id: m for m in members}
        if len(self.members) != len(members):
            raise ValueError("duplicate battle resource member id")
        self.hooks = hooks
        self.values: dict[str, dict[str, BattleResourceValue]] = {}
        for member_id, member in self.members.items():
            self.values[member_id] = {}
            for definition in definitions:
                self.values[member_id][definition.resource_id] = self._initialize_value(member, definition)

    def register_member(self, member):
        if member.member_id in self.members:
            raise ValueError(f"duplicate battle resource member id: {member.member_id}")
        self.members[member.member_id] = member
        self.values[member.member_id] = {
            definition.resource_id: self._initialize_value(member, definition)
            for definition in self.definitions.values()
        }
        return member.member_id

    def _initialize_value(self, member, definition):
        pool = member.subject.resources
        bound = pool.contains(definition.resource_id)
        if bound:
            subject_value = pool.get(definition.resource_id)
            minimum = subject_value.minimum if definition.minimum is None else definition.minimum
            own = definition.maximum is None or definition.subject_maximum
            maximum = subject_value.maximum if own else definition.maximum
            current = subject_value.current
        else:
            if definition.minimum is None:
                minimum = 0.0
            else:
                minimum = definition.minimum
            if definition.maximum is None:
                raise ValueError(f"combat-only resource requires maximum: {definition.resource_id}")
            maximum = definition.maximum
            current = maximum
        if maximum < minimum:
            raise ValueError(f"invalid bounds for battle resource: {definition.resource_id}")
        overflow_limit = definition.overflow_limit
        if overflow_limit is None:
            overflow_limit = maximum
        elif overflow_limit < maximum:
            raise ValueError("overflow_limit must be >= maximum")
        if definition.start_mode == BattleResourceStartMode.CURRENT:
            start = current
        elif definition.start_mode == BattleResourceStartMode.MINIMUM:
            start = minimum
        elif definition.start_mode == BattleResourceStartMode.MAXIMUM:
            start = maximum
        else:
            start = definition.start_value
        value = BattleResourceValue(
            start,
            minimum,
            maximum,
            overflow_limit,
            current,
            start,
            bound,
        )
        self._sync_member(member, definition.resource_id, value)
        return value

    def _sync_member(self, member, resource_id, value):
        if value.bound_to_subject:
            # Gameplay ResourcePool is bounded by logical maximum; overflow is a
            # combat-layer concept and intentionally does not corrupt persistent data.
            member.subject.resources.set_current(resource_id, max(value.minimum, min(value.maximum, value.current)))

    def get(self, member_id, resource_id):
        member_id = _id(member_id, "member_id")
        resource_id = _id(resource_id, "resource_id")
        try:
            return self.values[member_id][resource_id]
        except KeyError as exc:
            raise KeyError(f"unknown battle resource: {member_id}/{resource_id}") from exc

    def current(self, member_id, resource_id):
        return self.get(member_id, resource_id).current

    def change(self, member_id, resource_id, delta, *, trigger=None):
        member_id = _id(member_id, "member_id")
        resource_id = _id(resource_id, "resource_id")
        delta = _number(delta, "delta")
        value = self.get(member_id, resource_id)
        before = value.current
        value.current = value.clamp(value.current + delta)
        self._sync_member(self.members[member_id], resource_id, value)
        result = BattleResourceChange(
            member_id,
            resource_id,
            before,
            value.current,
            delta,
            value.current - before,
            None if trigger is None else str(trigger),
        )
        if result.applied_delta != 0:
            emit_hook(
                self.hooks,
                "rpg.battle_resource.changed",
                source=member_id,
                data={"change": result},
            )
            if before < value.maximum <= value.current:
                emit_hook(
                    self.hooks,
                    "rpg.battle_resource.full",
                    source=member_id,
                    data={"resource_id": resource_id, "value": value.current},
                )
            if before > value.minimum >= value.current:
                emit_hook(
                    self.hooks,
                    "rpg.battle_resource.empty",
                    source=member_id,
                    data={"resource_id": resource_id, "value": value.current},
                )
            if before <= value.maximum < value.current:
                emit_hook(
                    self.hooks,
                    "rpg.battle_resource.overflowed",
                    source=member_id,
                    data={"resource_id": resource_id, "overflow": value.overflow},
                )
        return result

    def spend(self, member_id, resource_id, amount, *, trigger=None):
        amount = _number(amount, "amount")
        if amount < 0:
            raise ValueError("spend amount must be >= 0")
        value = self.get(member_id, resource_id)
        if value.current - amount < value.minimum:
            return False
        self.change(member_id, resource_id, -amount, trigger=trigger)
        return True

    def restore(self, member_id, resource_id, amount, *, trigger=None):
        amount = _number(amount, "amount")
        if amount < 0:
            raise ValueError("restore amount must be >= 0")
        return self.change(member_id, resource_id, amount, trigger=trigger)

    def apply_trigger(self, trigger, member_ids=None):
        trigger = _id(trigger, "trigger")
        if member_ids is None:
            member_ids = tuple(self.members)
        changes = []
        for member_id in tuple(member_ids):
            for definition in self.definitions.values():
                for rule in definition.rules:
                    if rule.trigger == trigger:
                        changes.append(
                            self.change(
                                member_id,
                                definition.resource_id,
                                rule.amount,
                                trigger=trigger,
                            )
                        )
        return tuple(changes)

    def finish(self):
        """Apply end-of-battle persistence policy once BattleRuntime finishes."""
        for member_id, member_values in self.values.items():
            member = self.members[member_id]
            for resource_id, value in member_values.items():
                definition = self.definitions[resource_id]
                if definition.end_mode == BattleResourceEndMode.RESTORE_INITIAL:
                    value.current = value.initial
                elif definition.end_mode == BattleResourceEndMode.RESET_TO_START:
                    value.current = value.start_value
                self._sync_member(member, resource_id, value)
        emit_hook(self.hooks, "rpg.battle_resource.finished", data={"runtime": self})

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "values": {
                member_id: {resource_id: value.to_data() for resource_id, value in member_values.items()}
                for member_id, member_values in self.values.items()
            },
        }

    def restore_from_data(self, data):
        if data.get("schema") != self.SCHEMA or data.get("version") != self.VERSION:
            raise ValueError("unsupported battle resource runtime snapshot")
        raw_values = data.get("values")
        if set(raw_values or {}) != set(self.values):
            raise ValueError("battle resource member set mismatch")
        rebuilt = {}
        for member_id, member_values in self.values.items():
            raw_member = raw_values[member_id]
            if set(raw_member) != set(member_values):
                raise ValueError("battle resource definition set mismatch")
            rebuilt[member_id] = {
                resource_id: BattleResourceValue.from_data(raw_member[resource_id]) for resource_id in member_values
            }
        self.values = rebuilt
        for member_id, member_values in self.values.items():
            for resource_id, value in member_values.items():
                self._sync_member(self.members[member_id], resource_id, value)
        return self
