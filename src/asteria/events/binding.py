from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .conditions import EventCondition
from .scheduler import EventScheduleMode, ScheduledEventSpec


class EventTriggerKind(str, Enum):
    ACTION = "action"
    AUTORUN = "autorun"
    PARALLEL = "parallel"


@dataclass(frozen=True, slots=True)
class EventTriggerCondition:
    condition: EventCondition

    def evaluate(self, context) -> bool:
        return self.condition.evaluate(context)

    def to_data(self):
        return {"condition": self.condition.to_data()}

    @classmethod
    def from_data(cls, data):
        if set(data) != {"condition"}:
            raise ValueError("invalid event trigger condition")
        return cls(EventCondition.from_data(data["condition"]))


@dataclass(frozen=True, slots=True)
class EventBinding:
    """Canonical scene/entity -> event program binding."""

    binding_id: str
    entity_id: str
    program_id: str
    trigger: EventTriggerKind = EventTriggerKind.ACTION
    enabled: bool = True
    conditions: tuple[EventTriggerCondition, ...] = ()
    local_scope_id: str = ""

    def __init__(
        self,
        binding_id: str,
        entity_id: str,
        program_id: str,
        *,
        trigger: EventTriggerKind = EventTriggerKind.ACTION,
        enabled: bool = True,
        conditions=(),
        local_scope_id: str = "",
    ):
        binding_id = str(binding_id).strip()
        entity_id = str(entity_id).strip()
        program_id = str(program_id).strip()
        if not binding_id:
            raise ValueError("binding_id is required")
        if not entity_id:
            raise ValueError("entity_id is required")
        if not program_id:
            raise ValueError("program_id is required")
        trigger = EventTriggerKind(trigger)
        conds = tuple(conditions)
        if any(not isinstance(c, EventTriggerCondition) for c in conds):
            raise TypeError("conditions must be EventTriggerCondition values")

        object.__setattr__(self, "binding_id", binding_id)
        object.__setattr__(self, "entity_id", entity_id)
        object.__setattr__(self, "program_id", program_id)
        object.__setattr__(self, "trigger", trigger)
        object.__setattr__(self, "enabled", bool(enabled))
        object.__setattr__(self, "conditions", conds)
        object.__setattr__(self, "local_scope_id", str(local_scope_id))

    def is_active(self, context) -> bool:
        return self.enabled and all(c.evaluate(context) for c in self.conditions)

    def to_scheduler_spec(self):
        if self.trigger == EventTriggerKind.ACTION:
            raise ValueError("action bindings are foreground interactions")
        mode = (
            EventScheduleMode.AUTORUN
            if self.trigger == EventTriggerKind.AUTORUN
            else EventScheduleMode.PARALLEL
        )
        return ScheduledEventSpec(
            event_id=self.binding_id,
            program_id=self.program_id,
            mode=mode,
            source_entity_id=self.entity_id,
            local_scope_id=self.local_scope_id or self.entity_id,
            enabled=self.enabled,
        )

    def to_data(self):
        return {
            "binding_id": self.binding_id,
            "entity_id": self.entity_id,
            "program_id": self.program_id,
            "trigger": self.trigger.value,
            "enabled": self.enabled,
            "conditions": [c.to_data() for c in self.conditions],
            "local_scope_id": self.local_scope_id,
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "binding_id",
            "entity_id",
            "program_id",
            "trigger",
            "enabled",
            "conditions",
            "local_scope_id",
        }
        if set(data) != expected:
            raise ValueError("invalid event binding")
        if not isinstance(data["conditions"], list):
            raise TypeError("event binding conditions must be a list")
        return cls(
            data["binding_id"],
            data["entity_id"],
            data["program_id"],
            trigger=EventTriggerKind(data["trigger"]),
            enabled=data["enabled"],
            conditions=[EventTriggerCondition.from_data(x) for x in data["conditions"]],
            local_scope_id=data["local_scope_id"],
        )


@dataclass(slots=True)
class SceneEventBindings:
    """Canonical collection for scene-level event bindings."""

    bindings: dict[str, EventBinding] = field(default_factory=dict)

    def add(self, binding: EventBinding):
        if binding.binding_id in self.bindings:
            raise ValueError(f"duplicate event binding ID: {binding.binding_id}")
        self.bindings[binding.binding_id] = binding
        return binding

    def replace(self, binding: EventBinding):
        self.bindings[binding.binding_id] = binding
        return binding

    def remove(self, binding_id: str):
        return self.bindings.pop(str(binding_id))

    def for_entity(self, entity_id: str):
        entity_id = str(entity_id)
        return tuple(b for b in self.bindings.values() if b.entity_id == entity_id)

    def active_for_entity(self, entity_id: str, context):
        return tuple(b for b in self.for_entity(entity_id) if b.is_active(context))

    def scheduled_specs(self, context):
        specs = []
        for binding in self.bindings.values():
            if binding.trigger == EventTriggerKind.ACTION:
                continue
            if not binding.is_active(context):
                continue
            specs.append(binding.to_scheduler_spec())
        return tuple(specs)

    def to_data(self):
        return {
            "schema": "asteria.scene_event_bindings",
            "version": 1,
            "bindings": [b.to_data() for b in self.bindings.values()],
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"schema", "version", "bindings"}:
            raise ValueError("invalid scene event bindings")
        if data["schema"] != "asteria.scene_event_bindings" or data["version"] != 1:
            raise ValueError("unsupported scene event bindings")
        if not isinstance(data["bindings"], list):
            raise TypeError("bindings must be a list")
        result = cls()
        for raw in data["bindings"]:
            result.add(EventBinding.from_data(raw))
        return result
