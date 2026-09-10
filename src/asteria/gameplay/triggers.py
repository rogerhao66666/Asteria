from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .conditions import (
    ConditionGroup,
    GameplayCondition,
    GameplayConditionContext,
)
from .effects import Effect, EffectApplicationResult, apply_effect


class TriggerEvent(str, Enum):
    MANUAL = "manual"
    ON_HIT = "on_hit"
    ON_DAMAGED = "on_damaged"
    ON_DEFEAT = "on_defeat"
    ON_RESOURCE_CHANGED = "on_resource_changed"
    ON_STATE_APPLIED = "on_state_applied"
    ON_STATE_REMOVED = "on_state_removed"
    ON_EQUIP = "on_equip"
    ON_UNEQUIP = "on_unequip"


@dataclass(frozen=True, slots=True)
class GameplayTrigger:
    trigger_id: str
    event: str
    conditions: GameplayCondition
    effects: tuple[Effect, ...] = ()

    def __init__(
        self,
        trigger_id,
        event,
        *,
        conditions=None,
        effects=(),
    ):
        trigger_id = str(trigger_id).strip()
        if not trigger_id:
            raise ValueError("trigger_id is required")
        effects = tuple(effects)
        if any(not isinstance(effect, Effect) for effect in effects):
            raise TypeError("effects must be Effect values")
        if conditions is None:
            conditions = ConditionGroup(())
        if not isinstance(conditions, GameplayCondition):
            raise TypeError("conditions must be GameplayCondition")
        object.__setattr__(self, "trigger_id", trigger_id)
        event = str(event.value if isinstance(event, TriggerEvent) else event).strip()
        if not event:
            raise ValueError("trigger event is required")
        object.__setattr__(self, "event", event)
        object.__setattr__(self, "conditions", conditions)
        object.__setattr__(self, "effects", effects)

    def to_data(self):
        from .conditions import serialize_condition

        return {
            "schema": "asteria.gameplay_trigger",
            "version": 1,
            "trigger_id": self.trigger_id,
            "event": self.event,
            "conditions": serialize_condition(self.conditions),
            "effects": [effect.to_data() for effect in self.effects],
        }

    @classmethod
    def from_data(cls, data):
        from .conditions import deserialize_condition

        expected = {"schema", "version", "trigger_id", "event", "conditions", "effects"}
        if set(data) != expected:
            raise ValueError("invalid gameplay trigger")
        if data["schema"] != "asteria.gameplay_trigger" or data["version"] != 1:
            raise ValueError("unsupported gameplay trigger")
        return cls(
            data["trigger_id"],
            data["event"],
            conditions=deserialize_condition(data["conditions"]),
            effects=[Effect.from_data(x) for x in data["effects"]],
        )


@dataclass(frozen=True, slots=True)
class TriggerExecutionResult:
    trigger_id: str
    fired: bool
    effect_results: tuple[EffectApplicationResult, ...] = ()


class TriggerRuntime:
    """Deterministic dispatcher for authored gameplay triggers."""

    def __init__(self, triggers=()):
        self._triggers = {}
        for trigger in triggers:
            self.register(trigger)

    def register(self, trigger):
        if not isinstance(trigger, GameplayTrigger):
            raise TypeError("trigger must be GameplayTrigger")
        if trigger.trigger_id in self._triggers:
            raise ValueError(f"duplicate trigger: {trigger.trigger_id}")
        self._triggers[trigger.trigger_id] = trigger
        return trigger

    def triggers(self):
        return tuple(self._triggers[key] for key in sorted(self._triggers))

    def dispatch(
        self,
        event,
        context: GameplayConditionContext,
        *,
        effect_target=None,
    ):
        event = str(event.value if isinstance(event, TriggerEvent) else event).strip()
        if not event:
            raise ValueError("trigger event is required")
        results = []

        for trigger in self.triggers():
            if trigger.event != event:
                continue
            if not trigger.conditions.evaluate(context):
                results.append(TriggerExecutionResult(trigger.trigger_id, False))
                continue

            target = effect_target or context.target or context.source
            effect_results = tuple(
                apply_effect(
                    effect,
                    target.stats,
                    target.resources,
                    target.tags,
                )
                for effect in trigger.effects
            )
            results.append(
                TriggerExecutionResult(
                    trigger.trigger_id,
                    True,
                    effect_results,
                )
            )
        return tuple(results)
