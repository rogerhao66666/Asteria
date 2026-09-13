from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from asteria.core.lifecycle import emit_hook
from asteria.gameplay import normalize_tag


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


class GaugeRecipient(str, Enum):
    SOURCE = "source"
    TARGET = "target"


class GaugeThresholdComparison(str, Enum):
    AT_OR_BELOW = "at_or_below"
    AT_OR_ABOVE = "at_or_above"


@dataclass(frozen=True, slots=True)
class GaugeImpactRule:
    """Map a project-defined battle trigger/outcome to a gauge delta.

    The engine does not assign meaning to trigger names, resource names, or
    outcome tags. A rule can describe stagger damage, guard pressure, combo
    gain, poise loss, heat buildup, morale, or any other project mechanic.
    """

    impact_id: str
    resource_id: str
    trigger: str
    recipient: GaugeRecipient = GaugeRecipient.TARGET
    delta: float = 0.0
    value_scale: float = 0.0
    required_outcome_tags_all: tuple[str, ...] = ()
    required_outcome_tags_any: tuple[str, ...] = ()
    blocked_outcome_tags: tuple[str, ...] = ()
    priority: int = 0

    SCHEMA = "asteria.rpg.gauge_impact_rule"
    VERSION = 1

    def __init__(
        self,
        impact_id,
        resource_id,
        trigger,
        *,
        recipient=GaugeRecipient.TARGET,
        delta=0.0,
        value_scale=0.0,
        required_outcome_tags_all=(),
        required_outcome_tags_any=(),
        blocked_outcome_tags=(),
        priority=0,
    ):
        object.__setattr__(self, "impact_id", _id(impact_id, "impact_id"))
        object.__setattr__(self, "resource_id", _id(resource_id, "resource_id"))
        object.__setattr__(self, "trigger", _id(trigger, "trigger"))
        object.__setattr__(self, "recipient", GaugeRecipient(recipient))
        object.__setattr__(self, "delta", _number(delta, "delta"))
        object.__setattr__(self, "value_scale", _number(value_scale, "value_scale"))
        object.__setattr__(self, "required_outcome_tags_all", _tags(required_outcome_tags_all))
        object.__setattr__(self, "required_outcome_tags_any", _tags(required_outcome_tags_any))
        object.__setattr__(self, "blocked_outcome_tags", _tags(blocked_outcome_tags))
        object.__setattr__(self, "priority", int(priority))

    def matches(self, trigger, outcome_tags):
        if self.trigger != str(trigger):
            return False
        tags = set(_tags(outcome_tags))
        if not set(self.required_outcome_tags_all).issubset(tags):
            return False
        if self.required_outcome_tags_any and not set(self.required_outcome_tags_any).intersection(tags):
            return False
        if set(self.blocked_outcome_tags).intersection(tags):
            return False
        return True

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "impact_id": self.impact_id,
            "resource_id": self.resource_id,
            "trigger": self.trigger,
            "recipient": self.recipient.value,
            "delta": self.delta,
            "value_scale": self.value_scale,
            "required_outcome_tags_all": list(self.required_outcome_tags_all),
            "required_outcome_tags_any": list(self.required_outcome_tags_any),
            "blocked_outcome_tags": list(self.blocked_outcome_tags),
            "priority": self.priority,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported gauge impact rule")
        return cls(
            data["impact_id"], data["resource_id"], data["trigger"],
            recipient=data.get("recipient", "target"), delta=data.get("delta", 0),
            value_scale=data.get("value_scale", 0),
            required_outcome_tags_all=data.get("required_outcome_tags_all", ()),
            required_outcome_tags_any=data.get("required_outcome_tags_any", ()),
            blocked_outcome_tags=data.get("blocked_outcome_tags", ()),
            priority=data.get("priority", 0),
        )


@dataclass(frozen=True, slots=True)
class GaugeThresholdRule:
    """Consequence when a gauge crosses a project-defined boundary.

    Consequences intentionally reuse existing battle primitives: optional state
    application, timeline movement, resource reset, and lifecycle trigger.
    Nothing here knows what "break", "stagger", "guard", or "poise" means.
    """

    threshold_id: str
    resource_id: str
    comparison: GaugeThresholdComparison
    threshold: float
    state_id: str | None = None
    timeline_shift: float = 0.0
    reset_to: float | None = None
    emit_trigger: str | None = None
    include_cast_in_shift: bool = True
    priority: int = 0

    SCHEMA = "asteria.rpg.gauge_threshold_rule"
    VERSION = 1

    def __init__(
        self,
        threshold_id,
        resource_id,
        comparison,
        threshold,
        *,
        state_id=None,
        timeline_shift=0.0,
        reset_to=None,
        emit_trigger=None,
        include_cast_in_shift=True,
        priority=0,
    ):
        object.__setattr__(self, "threshold_id", _id(threshold_id, "threshold_id"))
        object.__setattr__(self, "resource_id", _id(resource_id, "resource_id"))
        object.__setattr__(self, "comparison", GaugeThresholdComparison(comparison))
        object.__setattr__(self, "threshold", _number(threshold, "threshold"))
        object.__setattr__(self, "state_id", None if state_id is None else _id(state_id, "state_id"))
        object.__setattr__(self, "timeline_shift", _number(timeline_shift, "timeline_shift"))
        object.__setattr__(self, "reset_to", None if reset_to is None else _number(reset_to, "reset_to"))
        object.__setattr__(self, "emit_trigger", None if emit_trigger is None else _id(emit_trigger, "emit_trigger"))
        object.__setattr__(self, "include_cast_in_shift", bool(include_cast_in_shift))
        object.__setattr__(self, "priority", int(priority))

    def crossed(self, before, after):
        before = float(before)
        after = float(after)
        if self.comparison == GaugeThresholdComparison.AT_OR_BELOW:
            return before > self.threshold and after <= self.threshold
        return before < self.threshold and after >= self.threshold

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "threshold_id": self.threshold_id,
            "resource_id": self.resource_id,
            "comparison": self.comparison.value,
            "threshold": self.threshold,
            "state_id": self.state_id,
            "timeline_shift": self.timeline_shift,
            "reset_to": self.reset_to,
            "emit_trigger": self.emit_trigger,
            "include_cast_in_shift": self.include_cast_in_shift,
            "priority": self.priority,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported gauge threshold rule")
        return cls(
            data["threshold_id"], data["resource_id"], data["comparison"], data["threshold"],
            state_id=data.get("state_id"), timeline_shift=data.get("timeline_shift", 0),
            reset_to=data.get("reset_to"), emit_trigger=data.get("emit_trigger"),
            include_cast_in_shift=data.get("include_cast_in_shift", True),
            priority=data.get("priority", 0),
        )


@dataclass(frozen=True, slots=True)
class GaugeCompositionDefinition:
    composition_id: str
    impacts: tuple[GaugeImpactRule, ...] = ()
    thresholds: tuple[GaugeThresholdRule, ...] = ()

    SCHEMA = "asteria.rpg.gauge_composition"
    VERSION = 1

    def __init__(self, composition_id, *, impacts=(), thresholds=()):
        impacts = tuple(x if isinstance(x, GaugeImpactRule) else GaugeImpactRule(**x) for x in impacts)
        thresholds = tuple(x if isinstance(x, GaugeThresholdRule) else GaugeThresholdRule(**x) for x in thresholds)
        impact_ids = [x.impact_id for x in impacts]
        threshold_ids = [x.threshold_id for x in thresholds]
        if len(set(impact_ids)) != len(impact_ids):
            raise ValueError("duplicate gauge impact id")
        if len(set(threshold_ids)) != len(threshold_ids):
            raise ValueError("duplicate gauge threshold id")
        object.__setattr__(self, "composition_id", _id(composition_id, "composition_id"))
        object.__setattr__(self, "impacts", tuple(sorted(impacts, key=lambda x: (-x.priority, x.impact_id))))
        object.__setattr__(self, "thresholds", tuple(sorted(thresholds, key=lambda x: (-x.priority, x.threshold_id))))

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "composition_id": self.composition_id,
            "impacts": [x.to_data() for x in self.impacts],
            "thresholds": [x.to_data() for x in self.thresholds],
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported gauge composition")
        return cls(
            data["composition_id"],
            impacts=[GaugeImpactRule.from_data(x) for x in data.get("impacts", ())],
            thresholds=[GaugeThresholdRule.from_data(x) for x in data.get("thresholds", ())],
        )


@dataclass(frozen=True, slots=True)
class GaugeThresholdResult:
    threshold_id: str
    member_id: str
    resource_id: str
    before: float
    after: float
    state_applied: bool = False
    timeline_shift: float = 0.0
    reset_to: float | None = None
    emitted_trigger: str | None = None


@dataclass(frozen=True, slots=True)
class GaugeCompositionResult:
    composition_id: str
    source_id: str
    target_id: str
    trigger: str
    matched_impact_ids: tuple[str, ...]
    changes: tuple[object, ...]
    thresholds: tuple[GaugeThresholdResult, ...]


class BattleGaugeCompositionRuntime:
    """Glue layer that composes resources, outcome tags, states and timeline.

    The runtime deliberately exposes mechanism rather than a named BreakSystem.
    Project data decides whether a composition represents break, stagger, guard,
    poise, heat, combo pressure, or something else.
    """

    def __init__(self, definitions=(), *, hooks=None):
        self.definitions = {}
        for definition in definitions:
            if not isinstance(definition, GaugeCompositionDefinition):
                raise TypeError("definitions must contain GaugeCompositionDefinition values")
            if definition.composition_id in self.definitions:
                raise ValueError(f"duplicate gauge composition: {definition.composition_id}")
            self.definitions[definition.composition_id] = definition
        self.hooks = hooks

    def apply(self, battle, composition_id, source_id, target_id, *, trigger, outcome_tags=(), value=0.0, rng=None):
        composition = self.definitions[str(composition_id)]
        source_id = _id(source_id, "source_id")
        target_id = _id(target_id, "target_id")
        trigger = _id(trigger, "trigger")
        value = _number(value, "value")
        outcome_tags = _tags(outcome_tags)
        changes = []
        threshold_results = []
        matched_impact_ids = []

        # Aggregate all matching contributions to the same member/resource before
        # threshold evaluation. This makes one logical impact deterministic and
        # prevents multiple rules in the same event from spuriously crossing the
        # same threshold more than once.
        aggregated = {}
        for impact in composition.impacts:
            if not impact.matches(trigger, outcome_tags):
                continue
            member_id = source_id if impact.recipient == GaugeRecipient.SOURCE else target_id
            delta = impact.delta + abs(value) * impact.value_scale
            if delta == 0:
                continue
            key = (member_id, impact.resource_id)
            aggregated[key] = aggregated.get(key, 0.0) + delta
            matched_impact_ids.append(impact.impact_id)

        for (member_id, resource_id), delta in sorted(aggregated.items()):
            change = battle.battle_resources.change(
                member_id, resource_id, delta,
                trigger=f"gauge.{composition.composition_id}",
            )
            changes.append(change)
            for threshold in composition.thresholds:
                if threshold.resource_id != resource_id:
                    continue
                if not threshold.crossed(change.before, change.after):
                    continue
                state_applied = False
                if threshold.state_id is not None:
                    state_result = battle.apply_state(threshold.state_id, source_id, member_id, rng=rng)
                    state_applied = bool(state_result.applied)
                if threshold.timeline_shift != 0:
                    battle.shift_timeline(
                        member_id, threshold.timeline_shift,
                        include_cast=threshold.include_cast_in_shift,
                    )
                if threshold.emit_trigger is not None:
                    battle.battle_resources.apply_trigger(threshold.emit_trigger, [member_id])
                    battle.battle_states.apply_trigger(threshold.emit_trigger, [battle.member(member_id)])
                    emit_hook(
                        self.hooks, threshold.emit_trigger, source=member_id,
                        data={"composition_id": composition.composition_id, "threshold_id": threshold.threshold_id},
                    )
                if threshold.reset_to is not None:
                    current = battle.battle_resources.current(member_id, threshold.resource_id)
                    battle.battle_resources.change(
                        member_id, threshold.resource_id, threshold.reset_to - current,
                        trigger=f"gauge.{composition.composition_id}.{threshold.threshold_id}.reset",
                    )
                threshold_result = GaugeThresholdResult(
                    threshold.threshold_id, member_id, threshold.resource_id,
                    change.before, change.after, state_applied, threshold.timeline_shift,
                    threshold.reset_to, threshold.emit_trigger,
                )
                threshold_results.append(threshold_result)
                emit_hook(
                    self.hooks, "rpg.battle.gauge_threshold_crossed", source=member_id,
                    data={"composition_id": composition.composition_id, "result": threshold_result},
                )

        result = GaugeCompositionResult(
            composition.composition_id, source_id, target_id, trigger,
            tuple(matched_impact_ids), tuple(changes), tuple(threshold_results),
        )
        emit_hook(
            self.hooks, "rpg.battle.gauge_composed", source=source_id,
            data={"result": result},
        )
        return result
