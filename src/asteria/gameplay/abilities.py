from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from .conditions import (
    ConditionGroup,
    GameplayCondition,
    GameplayConditionContext,
    GameplaySubject,
    deserialize_condition,
    serialize_condition,
)
from .effects import Effect, EffectApplicationResult, apply_effect
from .formulas import FormulaContext, ValueFormula
from .stats import ResourcePool, StatBlock
from .tags import TagSet, normalize_tag


class AbilityTargetMode(str, Enum):
    SELF = "self"
    SELECTED = "selected"


@dataclass(frozen=True, slots=True)
class AbilityTarget:
    target_id: str
    subject: GameplaySubject

    def __init__(self, target_id, subject):
        target_id = str(target_id).strip()
        if not target_id:
            raise ValueError("target_id is required")
        if not isinstance(subject, GameplaySubject):
            raise TypeError("subject must be GameplaySubject")
        object.__setattr__(self, "target_id", target_id)
        object.__setattr__(self, "subject", subject)


@dataclass(frozen=True, slots=True)
class TargetingRule:
    minimum_targets: int = 1
    maximum_targets: int = 1
    allow_self: bool = False
    required_tags: tuple[str, ...] = ()
    blocked_tags: tuple[str, ...] = ()

    def __init__(
        self,
        *,
        minimum_targets=1,
        maximum_targets=1,
        allow_self=False,
        required_tags=(),
        blocked_tags=(),
    ):
        minimum_targets = int(minimum_targets)
        maximum_targets = int(maximum_targets)
        if minimum_targets < 0:
            raise ValueError("minimum_targets must be >= 0")
        if maximum_targets < minimum_targets:
            raise ValueError("maximum_targets must be >= minimum_targets")
        object.__setattr__(self, "minimum_targets", minimum_targets)
        object.__setattr__(self, "maximum_targets", maximum_targets)
        object.__setattr__(self, "allow_self", bool(allow_self))
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

    def validate(
        self,
        source: AbilityTarget,
        targets: tuple[AbilityTarget, ...],
    ) -> tuple[str, ...]:
        errors = []
        if len(targets) < self.minimum_targets:
            errors.append("too_few_targets")
        if len(targets) > self.maximum_targets:
            errors.append("too_many_targets")

        seen = set()
        for target in targets:
            if target.target_id in seen:
                errors.append(f"duplicate_target:{target.target_id}")
                continue
            seen.add(target.target_id)

            if not self.allow_self and target.target_id == source.target_id:
                errors.append(f"self_target_not_allowed:{target.target_id}")
            if not target.subject.tags.contains_all(self.required_tags):
                errors.append(f"missing_required_tags:{target.target_id}")
            if target.subject.tags.contains_any(self.blocked_tags):
                errors.append(f"blocked_tags:{target.target_id}")
        return tuple(errors)

    def to_data(self):
        return {
            "minimum_targets": self.minimum_targets,
            "maximum_targets": self.maximum_targets,
            "allow_self": self.allow_self,
            "required_tags": list(self.required_tags),
            "blocked_tags": list(self.blocked_tags),
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "minimum_targets",
            "maximum_targets",
            "allow_self",
            "required_tags",
            "blocked_tags",
        }
        if set(data) != expected:
            raise ValueError("invalid targeting rule")
        return cls(**data)


@dataclass(frozen=True, slots=True)
class AbilityCost:
    resource: str
    amount: ValueFormula

    def __init__(self, resource, amount):
        resource = str(resource).strip()
        if not resource:
            raise ValueError("cost resource is required")
        if isinstance(amount, (int, float)):
            amount = ValueFormula.constant(amount)
        if not isinstance(amount, ValueFormula):
            raise TypeError("amount must be ValueFormula or number")
        object.__setattr__(self, "resource", resource)
        object.__setattr__(self, "amount", amount)

    def to_data(self):
        return {
            "resource": self.resource,
            "amount": self.amount.to_data(),
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"resource", "amount"}:
            raise ValueError("invalid ability cost")
        return cls(data["resource"], ValueFormula.from_data(data["amount"]))


@dataclass(frozen=True, slots=True)
class AbilityEffect:
    mode: AbilityTargetMode
    effect: Effect

    def __init__(self, mode, effect):
        if not isinstance(effect, Effect):
            raise TypeError("effect must be Effect")
        object.__setattr__(self, "mode", AbilityTargetMode(mode))
        object.__setattr__(self, "effect", effect)

    def to_data(self):
        return {"mode": self.mode.value, "effect": self.effect.to_data()}

    @classmethod
    def from_data(cls, data):
        if set(data) != {"mode", "effect"}:
            raise ValueError("invalid ability effect")
        return cls(data["mode"], Effect.from_data(data["effect"]))


@dataclass(frozen=True, slots=True)
class AbilityDefinition:
    ability_id: str
    targeting: TargetingRule
    costs: tuple[AbilityCost, ...] = ()
    conditions: GameplayCondition | None = None
    effects: tuple[AbilityEffect, ...] = ()
    tags: tuple[str, ...] = ()

    def __init__(
        self,
        ability_id,
        *,
        targeting=None,
        costs=(),
        conditions=None,
        effects=(),
        tags=(),
    ):
        ability_id = str(ability_id).strip()
        if not ability_id:
            raise ValueError("ability_id is required")
        if targeting is None:
            targeting = TargetingRule()
        if not isinstance(targeting, TargetingRule):
            raise TypeError("targeting must be TargetingRule")
        costs = tuple(costs)
        effects = tuple(effects)
        if any(not isinstance(x, AbilityCost) for x in costs):
            raise TypeError("costs must be AbilityCost values")
        if any(not isinstance(x, AbilityEffect) for x in effects):
            raise TypeError("effects must be AbilityEffect values")
        if conditions is None:
            conditions = ConditionGroup(())
        if not isinstance(conditions, GameplayCondition):
            raise TypeError("conditions must be GameplayCondition")
        object.__setattr__(self, "ability_id", ability_id)
        object.__setattr__(self, "targeting", targeting)
        object.__setattr__(self, "costs", costs)
        object.__setattr__(self, "conditions", conditions)
        object.__setattr__(self, "effects", effects)
        object.__setattr__(
            self, "tags", tuple(sorted({normalize_tag(x) for x in tags}))
        )

    def to_data(self):
        return {
            "schema": "asteria.ability_definition",
            "version": 1,
            "ability_id": self.ability_id,
            "targeting": self.targeting.to_data(),
            "costs": [x.to_data() for x in self.costs],
            "conditions": serialize_condition(self.conditions),
            "effects": [x.to_data() for x in self.effects],
            "tags": list(self.tags),
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "schema",
            "version",
            "ability_id",
            "targeting",
            "costs",
            "conditions",
            "effects",
            "tags",
        }
        if set(data) != expected:
            raise ValueError("invalid ability definition")
        if data["schema"] != "asteria.ability_definition" or data["version"] != 1:
            raise ValueError("unsupported ability definition")
        return cls(
            data["ability_id"],
            targeting=TargetingRule.from_data(data["targeting"]),
            costs=[AbilityCost.from_data(x) for x in data["costs"]],
            conditions=deserialize_condition(data["conditions"]),
            effects=[AbilityEffect.from_data(x) for x in data["effects"]],
            tags=data["tags"],
        )


class AbilityRegistry:
    def __init__(self, definitions=()):
        self._definitions = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition):
        if not isinstance(definition, AbilityDefinition):
            raise TypeError("definition must be AbilityDefinition")
        if definition.ability_id in self._definitions:
            raise ValueError(f"duplicate ability: {definition.ability_id}")
        self._definitions[definition.ability_id] = definition
        return definition

    def get(self, ability_id):
        return self._definitions.get(str(ability_id))

    def require(self, ability_id):
        try:
            return self._definitions[str(ability_id)]
        except KeyError as exc:
            raise KeyError(f"unknown ability: {ability_id}") from exc

    def ids(self):
        return tuple(sorted(self._definitions))


@dataclass(frozen=True, slots=True)
class AbilityExecutionResult:
    ability_id: str
    executed: bool
    errors: tuple[str, ...] = ()
    spent_resources: tuple[tuple[str, float], ...] = ()
    effect_results: tuple[tuple[str, EffectApplicationResult], ...] = ()


def _formula_context(source: GameplaySubject, target: GameplaySubject | None):
    if target is None:
        target = source
    return FormulaContext(
        source.stats,
        source.resources,
        source.tags,
        target.stats,
        target.resources,
        target.tags,
    )


def _clone_subject(subject: GameplaySubject):
    return GameplaySubject(
        StatBlock.from_data(subject.stats.to_data()),
        ResourcePool.from_data(subject.resources.to_data()),
        TagSet.from_data(subject.tags.to_data()),
        subject.states,
    )


def _commit_subject(staged: GameplaySubject, actual: GameplaySubject):
    actual.stats._values = dict(staged.stats._values)
    actual.resources._values = {
        key: type(value).from_data(value.to_data())
        for key, value in staged.resources._values.items()
    }
    actual.tags._tags = set(staged.tags._tags)


class AbilityRuntime:
    """Turn/realtime-neutral ability validation and atomic execution.

    Spatial queries, animation timing, cooldown scheduling and input are
    intentionally outside this foundation.
    """

    def __init__(self, registry: AbilityRegistry):
        if not isinstance(registry, AbilityRegistry):
            raise TypeError("registry must be AbilityRegistry")
        self.registry = registry

    def execute(
        self,
        ability_id,
        source: AbilityTarget,
        targets=(),
        *,
        prepaid_costs=None,
        value_transform=None,
    ):
        """Validate, pay costs and apply effects atomically.

        ``value_transform(target_id, operation, value)`` (optional) adjusts each
        operation value an effect applies to a selected target. It returns the
        value for the target, or ``(target_value, source_value)`` to route part
        of it back to the source as a delta of the same resource (reflection).
        """
        definition = self.registry.require(ability_id)
        targets = tuple(targets)
        if any(not isinstance(x, AbilityTarget) for x in targets):
            raise TypeError("targets must be AbilityTarget values")

        errors = list(definition.targeting.validate(source, targets))
        condition_target = targets[0].subject if targets else None
        if not definition.conditions.evaluate(
            GameplayConditionContext(source.subject, condition_target)
        ):
            errors.append("conditions_failed")

        evaluated_costs = []
        formula_context = _formula_context(source.subject, condition_target)
        for cost in definition.costs:
            try:
                amount = float(cost.amount.evaluate(formula_context))
            except (KeyError, ValueError) as exc:
                errors.append(f"cost_formula_failed:{cost.resource}:{exc}")
                continue
            if not isfinite(amount) or amount < 0.0:
                errors.append(f"invalid_cost:{cost.resource}")
                continue
            if not source.subject.resources.contains(cost.resource):
                errors.append(f"missing_resource:{cost.resource}")
                continue
            available = (
                source.subject.resources.current(cost.resource)
                - source.subject.resources.get(cost.resource).minimum
            )
            if prepaid_costs is None and available < amount:
                errors.append(f"insufficient_resource:{cost.resource}")
            evaluated_costs.append((cost.resource, amount))

        if errors:
            return AbilityExecutionResult(definition.ability_id, False, tuple(errors))

        # One staged subject per stable target ID so cost/effects are atomic.
        actual_by_id = {source.target_id: source.subject}
        for target in targets:
            actual_by_id[target.target_id] = target.subject
        staged_by_id = {
            target_id: _clone_subject(subject)
            for target_id, subject in actual_by_id.items()
        }

        staged_source = staged_by_id[source.target_id]
        if prepaid_costs is None:
            for resource, amount in evaluated_costs:
                if not staged_source.resources.spend(resource, amount):
                    return AbilityExecutionResult(
                        definition.ability_id,
                        False,
                        (f"insufficient_resource:{resource}",),
                    )
        else:
            normalized_prepaid = tuple((str(r), float(a)) for r, a in prepaid_costs)
            if normalized_prepaid != tuple(evaluated_costs):
                return AbilityExecutionResult(
                    definition.ability_id, False, ("prepaid_cost_mismatch",)
                )

        effect_results = []
        for ability_effect in definition.effects:
            if ability_effect.mode == AbilityTargetMode.SELF:
                result = apply_effect(
                    ability_effect.effect,
                    staged_source.stats,
                    staged_source.resources,
                    staged_source.tags,
                    formula_context=_formula_context(staged_source, staged_source),
                )
                effect_results.append((source.target_id, result))
            else:
                for target in targets:
                    staged_target = staged_by_id[target.target_id]
                    reflected = []
                    transform = None
                    if value_transform is not None:
                        def transform(operation, value, _target_id=target.target_id, _reflected=reflected):
                            routed = value_transform(_target_id, operation, value)
                            if isinstance(routed, tuple):
                                routed, back = routed
                                if back:
                                    _reflected.append((operation.target, float(back)))
                            return routed
                    result = apply_effect(
                        ability_effect.effect,
                        staged_target.stats,
                        staged_target.resources,
                        staged_target.tags,
                        formula_context=_formula_context(staged_source, staged_target),
                        value_transform=transform,
                    )
                    effect_results.append((target.target_id, result))
                    for resource, amount in reflected:
                        if staged_source.resources.contains(resource):
                            staged_source.resources.change(resource, amount)
        for target_id in sorted(staged_by_id):
            _commit_subject(staged_by_id[target_id], actual_by_id[target_id])

        return AbilityExecutionResult(
            definition.ability_id,
            True,
            spent_resources=tuple(evaluated_costs),
            effect_results=tuple(effect_results),
        )
