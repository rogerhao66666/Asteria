from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from math import isfinite

from asteria.core.lifecycle import emit_hook
from asteria.gameplay import GameplaySubject, normalize_tag


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


def _tags(values):
    return tuple(sorted({normalize_tag(x) for x in values}))


def _coefficients(values, label):
    result = {}
    for key, coefficient in dict(values or {}).items():
        result[_id(key, label)] = _number(coefficient, label)
    return dict(sorted(result.items()))


class InteractionDisposition(str, Enum):
    """Where a resolved magnitude should go; names do not imply elements."""

    NORMAL = "normal"
    NULLIFY = "nullify"
    ABSORB = "absorb"
    REFLECT = "reflect"


@dataclass(frozen=True, slots=True)
class InteractionRule:
    """Tag-driven value interaction rule.

    A rule can describe elemental weakness/resistance, armor, species bonuses,
    airborne-vs-ranged interactions, guard states, or project-specific rules.
    Stat names and tags remain project vocabulary.
    """

    rule_id: str
    source_tags_all: tuple[str, ...] = ()
    source_tags_any: tuple[str, ...] = ()
    target_tags_all: tuple[str, ...] = ()
    target_tags_any: tuple[str, ...] = ()
    blocked_source_tags: tuple[str, ...] = ()
    blocked_target_tags: tuple[str, ...] = ()
    flat_delta: float = 0.0
    multiplier: float = 1.0
    source_stat_terms: dict[str, float] = None
    target_stat_terms: dict[str, float] = None
    disposition: InteractionDisposition = InteractionDisposition.NORMAL
    outcome_tags: tuple[str, ...] = ()
    priority: int = 0

    SCHEMA = "asteria.rpg.interaction_rule"
    VERSION = 1

    def __init__(
        self,
        rule_id,
        *,
        source_tags_all=(),
        source_tags_any=(),
        target_tags_all=(),
        target_tags_any=(),
        blocked_source_tags=(),
        blocked_target_tags=(),
        flat_delta=0.0,
        multiplier=1.0,
        source_stat_terms=None,
        target_stat_terms=None,
        disposition=InteractionDisposition.NORMAL,
        outcome_tags=(),
        priority=0,
    ):
        multiplier = _number(multiplier, "multiplier")
        if multiplier < 0:
            raise ValueError("multiplier must be >= 0")
        object.__setattr__(self, "rule_id", _id(rule_id, "rule_id"))
        object.__setattr__(self, "source_tags_all", _tags(source_tags_all))
        object.__setattr__(self, "source_tags_any", _tags(source_tags_any))
        object.__setattr__(self, "target_tags_all", _tags(target_tags_all))
        object.__setattr__(self, "target_tags_any", _tags(target_tags_any))
        object.__setattr__(self, "blocked_source_tags", _tags(blocked_source_tags))
        object.__setattr__(self, "blocked_target_tags", _tags(blocked_target_tags))
        object.__setattr__(self, "flat_delta", _number(flat_delta, "flat_delta"))
        object.__setattr__(self, "multiplier", multiplier)
        object.__setattr__(self, "source_stat_terms", _coefficients(source_stat_terms, "source stat"))
        object.__setattr__(self, "target_stat_terms", _coefficients(target_stat_terms, "target stat"))
        object.__setattr__(self, "disposition", InteractionDisposition(disposition))
        object.__setattr__(self, "outcome_tags", _tags(outcome_tags))
        object.__setattr__(self, "priority", int(priority))

    def matches(self, source_tags, target_tags):
        source_tags = set(source_tags)
        target_tags = set(target_tags)
        if not set(self.source_tags_all).issubset(source_tags):
            return False
        if self.source_tags_any and not set(self.source_tags_any).intersection(source_tags):
            return False
        if not set(self.target_tags_all).issubset(target_tags):
            return False
        if self.target_tags_any and not set(self.target_tags_any).intersection(target_tags):
            return False
        if set(self.blocked_source_tags).intersection(source_tags):
            return False
        if set(self.blocked_target_tags).intersection(target_tags):
            return False
        return True

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "rule_id": self.rule_id,
            "source_tags_all": list(self.source_tags_all),
            "source_tags_any": list(self.source_tags_any),
            "target_tags_all": list(self.target_tags_all),
            "target_tags_any": list(self.target_tags_any),
            "blocked_source_tags": list(self.blocked_source_tags),
            "blocked_target_tags": list(self.blocked_target_tags),
            "flat_delta": self.flat_delta,
            "multiplier": self.multiplier,
            "source_stat_terms": dict(self.source_stat_terms),
            "target_stat_terms": dict(self.target_stat_terms),
            "disposition": self.disposition.value,
            "outcome_tags": list(self.outcome_tags),
            "priority": self.priority,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported interaction rule")
        return cls(
            data["rule_id"],
            source_tags_all=data.get("source_tags_all", ()),
            source_tags_any=data.get("source_tags_any", ()),
            target_tags_all=data.get("target_tags_all", ()),
            target_tags_any=data.get("target_tags_any", ()),
            blocked_source_tags=data.get("blocked_source_tags", ()),
            blocked_target_tags=data.get("blocked_target_tags", ()),
            flat_delta=data.get("flat_delta", 0),
            multiplier=data.get("multiplier", 1),
            source_stat_terms=data.get("source_stat_terms", {}),
            target_stat_terms=data.get("target_stat_terms", {}),
            disposition=data.get("disposition", "normal"),
            outcome_tags=data.get("outcome_tags", ()),
            priority=data.get("priority", 0),
        )


@dataclass(frozen=True, slots=True)
class OutcomeCheckDefinition:
    """Generic probability check used for hit/crit/block/parry/etc."""

    check_id: str
    base_chance: float
    source_stat_terms: dict[str, float] = None
    target_stat_terms: dict[str, float] = None
    minimum_chance: float = 0.0
    maximum_chance: float = 1.0
    required_source_tags: tuple[str, ...] = ()
    required_target_tags: tuple[str, ...] = ()
    success_tags: tuple[str, ...] = ()
    failure_tags: tuple[str, ...] = ()

    SCHEMA = "asteria.rpg.outcome_check"
    VERSION = 1

    def __init__(
        self,
        check_id,
        base_chance,
        *,
        source_stat_terms=None,
        target_stat_terms=None,
        minimum_chance=0.0,
        maximum_chance=1.0,
        required_source_tags=(),
        required_target_tags=(),
        success_tags=(),
        failure_tags=(),
    ):
        minimum_chance = _number(minimum_chance, "minimum_chance")
        maximum_chance = _number(maximum_chance, "maximum_chance")
        if not 0 <= minimum_chance <= maximum_chance <= 1:
            raise ValueError("chance bounds must satisfy 0 <= min <= max <= 1")
        object.__setattr__(self, "check_id", _id(check_id, "check_id"))
        object.__setattr__(self, "base_chance", _number(base_chance, "base_chance"))
        object.__setattr__(self, "source_stat_terms", _coefficients(source_stat_terms, "source stat"))
        object.__setattr__(self, "target_stat_terms", _coefficients(target_stat_terms, "target stat"))
        object.__setattr__(self, "minimum_chance", minimum_chance)
        object.__setattr__(self, "maximum_chance", maximum_chance)
        object.__setattr__(self, "required_source_tags", _tags(required_source_tags))
        object.__setattr__(self, "required_target_tags", _tags(required_target_tags))
        object.__setattr__(self, "success_tags", _tags(success_tags))
        object.__setattr__(self, "failure_tags", _tags(failure_tags))

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "check_id": self.check_id,
            "base_chance": self.base_chance,
            "source_stat_terms": dict(self.source_stat_terms),
            "target_stat_terms": dict(self.target_stat_terms),
            "minimum_chance": self.minimum_chance,
            "maximum_chance": self.maximum_chance,
            "required_source_tags": list(self.required_source_tags),
            "required_target_tags": list(self.required_target_tags),
            "success_tags": list(self.success_tags),
            "failure_tags": list(self.failure_tags),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported outcome check")
        return cls(
            data["check_id"],
            data["base_chance"],
            source_stat_terms=data.get("source_stat_terms", {}),
            target_stat_terms=data.get("target_stat_terms", {}),
            minimum_chance=data.get("minimum_chance", 0),
            maximum_chance=data.get("maximum_chance", 1),
            required_source_tags=data.get("required_source_tags", ()),
            required_target_tags=data.get("required_target_tags", ()),
            success_tags=data.get("success_tags", ()),
            failure_tags=data.get("failure_tags", ()),
        )


@dataclass(frozen=True, slots=True)
class OutcomeCheckResult:
    check_id: str
    applicable: bool
    success: bool | None
    chance: float | None
    roll: float | None
    outcome_tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValueResolutionResult:
    base_value: float
    resolved_value: float
    disposition: InteractionDisposition
    matched_rules: tuple[str, ...]
    outcome_tags: tuple[str, ...]
    trace: tuple[tuple[str, float, float], ...]


@dataclass(frozen=True, slots=True)
class OutcomeResolutionResult:
    checks: tuple[OutcomeCheckResult, ...]
    value: ValueResolutionResult

    @property
    def outcome_tags(self):
        tags = set(self.value.outcome_tags)
        for check in self.checks:
            tags.update(check.outcome_tags)
        return tuple(sorted(tags))


class InteractionResolver:
    """Deterministic tag/stat interaction resolver; mutation-free and explainable."""

    def __init__(self, rules=(), checks=(), *, hooks=None):
        self.rules = {}
        for rule in rules:
            if not isinstance(rule, InteractionRule):
                raise TypeError("rules must contain InteractionRule values")
            if rule.rule_id in self.rules:
                raise ValueError(f"duplicate interaction rule: {rule.rule_id}")
            self.rules[rule.rule_id] = rule
        self.checks = {}
        for check in checks:
            if not isinstance(check, OutcomeCheckDefinition):
                raise TypeError("checks must contain OutcomeCheckDefinition values")
            if check.check_id in self.checks:
                raise ValueError(f"duplicate outcome check: {check.check_id}")
            self.checks[check.check_id] = check
        self.hooks = hooks

    @staticmethod
    def _stat(subject, name):
        try:
            return subject.stats.get(name)
        except KeyError:
            return 0.0

    def resolve_value(self, base_value, source: GameplaySubject, target: GameplaySubject, *, action_tags=()):
        if not isinstance(source, GameplaySubject) or not isinstance(target, GameplaySubject):
            raise TypeError("source and target must be GameplaySubject")
        base_value = _number(base_value, "base_value")
        source_tags = set(source.tags.values()) | set(_tags(action_tags))
        target_tags = set(target.tags.values())
        matches = [r for r in self.rules.values() if r.matches(source_tags, target_tags)]
        matches.sort(key=lambda r: (-r.priority, r.rule_id))
        value = base_value
        trace = []
        outcome_tags = set()
        disposition = InteractionDisposition.NORMAL
        disposition_priority = None
        for rule in matches:
            before = value
            value += rule.flat_delta
            value += sum(self._stat(source, k) * c for k, c in rule.source_stat_terms.items())
            value += sum(self._stat(target, k) * c for k, c in rule.target_stat_terms.items())
            value *= rule.multiplier
            value = max(0.0, value)
            trace.append((rule.rule_id, before, value))
            outcome_tags.update(rule.outcome_tags)
            if rule.disposition != InteractionDisposition.NORMAL and disposition_priority is None:
                disposition = rule.disposition
                disposition_priority = rule.priority
        if disposition == InteractionDisposition.NULLIFY:
            value = 0.0
        result = ValueResolutionResult(
            base_value,
            value,
            disposition,
            tuple(r.rule_id for r in matches),
            tuple(sorted(outcome_tags)),
            tuple(trace),
        )
        emit_hook(self.hooks, "rpg.battle.interaction_resolved", data={"result": result})
        return result

    def resolve(
        self, base_value, source: GameplaySubject, target: GameplaySubject, *, action_tags=(), check_ids=(), rng=None
    ):
        """Resolve probability outcomes first, then feed their tags into value rules.

        This is how projects compose hit/evade, crit, block, parry and custom
        checks without hardcoding their meaning. For example, a failed `hit`
        check may emit `outcome.evade`, and a normal InteractionRule matching
        that tag can NULLIFY the value.
        """
        rng = rng or random.Random()
        checks = tuple(self.check(check_id, source, target, action_tags=action_tags, rng=rng) for check_id in check_ids)
        combined = set(_tags(action_tags))
        for check in checks:
            combined.update(check.outcome_tags)
        value = self.resolve_value(base_value, source, target, action_tags=combined)
        result = OutcomeResolutionResult(checks, value)
        emit_hook(self.hooks, "rpg.battle.outcome_resolved", data={"result": result})
        return result

    def check(self, check_id, source: GameplaySubject, target: GameplaySubject, *, action_tags=(), rng=None):
        definition = self.checks[_id(check_id, "check_id")]
        source_tags = set(source.tags.values()) | set(_tags(action_tags))
        target_tags = set(target.tags.values())
        applicable = set(definition.required_source_tags).issubset(source_tags) and set(
            definition.required_target_tags
        ).issubset(target_tags)
        if not applicable:
            return OutcomeCheckResult(definition.check_id, False, None, None, None, ())
        chance = definition.base_chance
        chance += sum(self._stat(source, k) * c for k, c in definition.source_stat_terms.items())
        chance += sum(self._stat(target, k) * c for k, c in definition.target_stat_terms.items())
        chance = max(definition.minimum_chance, min(definition.maximum_chance, chance))
        rng = rng or random.Random()
        roll = float(rng.random())
        success = roll < chance
        tags = definition.success_tags if success else definition.failure_tags
        result = OutcomeCheckResult(definition.check_id, True, success, chance, roll, tags)
        emit_hook(self.hooks, "rpg.battle.outcome_check", data={"result": result})
        return result
