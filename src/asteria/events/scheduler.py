from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .context import EventContext
from .registry import EventProgramRegistry
from .runner import EventRunner
from .world_commands import WorldCommandRouter


class EventScheduleMode(str, Enum):
    AUTORUN = "autorun"
    PARALLEL = "parallel"


@dataclass(frozen=True, slots=True)
class ScheduledEventSpec:
    event_id: str
    program_id: str
    mode: EventScheduleMode
    source_entity_id: str = ""
    local_scope_id: str = ""
    enabled: bool = True

    def __post_init__(self):
        if not str(self.event_id).strip():
            raise ValueError("scheduled event_id is required")
        if not str(self.program_id).strip():
            raise ValueError("scheduled program_id is required")


@dataclass(slots=True)
class ScheduledEventInstance:
    spec: ScheduledEventSpec
    runner: EventRunner


@dataclass(slots=True)
class EventScheduler:
    registry: EventProgramRegistry
    context: EventContext = field(default_factory=EventContext)
    world_commands: WorldCommandRouter | None = None
    _specs: dict[str, ScheduledEventSpec] = field(default_factory=dict)
    _instances: dict[str, ScheduledEventInstance] = field(default_factory=dict)

    def add(self, spec: ScheduledEventSpec):
        if spec.event_id in self._specs:
            raise ValueError(f"duplicate scheduled event ID: {spec.event_id}")
        self._specs[spec.event_id] = spec
        return spec

    def replace(self, spec: ScheduledEventSpec):
        self._specs[spec.event_id] = spec
        self._instances.pop(spec.event_id, None)
        return spec

    def remove(self, event_id: str):
        self._instances.pop(str(event_id), None)
        return self._specs.pop(str(event_id))

    def specs(self):
        return tuple(self._specs.values())

    def instance(self, event_id: str):
        return self._instances.get(str(event_id))

    @property
    def autorun_busy(self):
        return any(
            inst.spec.mode == EventScheduleMode.AUTORUN and inst.runner.busy
            for inst in self._instances.values()
        )

    def can_start_foreground(self):
        return not self.autorun_busy

    def _ensure_instance(self, spec: ScheduledEventSpec):
        inst = self._instances.get(spec.event_id)
        if inst is None:
            runner = EventRunner(
                self.registry, context=self.context, world_commands=self.world_commands
            )
            runner.start(
                spec.program_id,
                source_entity_id=spec.source_entity_id,
                local_scope_id=spec.local_scope_id,
            )
            inst = ScheduledEventInstance(spec, runner)
            self._instances[spec.event_id] = inst
        return inst

    def update(self, dt: float = 0.0):
        """Advance scheduled events.

        Autorun policy:
        - starts automatically while enabled
        - considered blocking while busy
        - does not immediately restart again in the same update after completion

        Parallel policy:
        - starts automatically while enabled
        - updates independently
        - does not block foreground interaction
        """
        outputs = {}
        completed = []

        for event_id, spec in tuple(self._specs.items()):
            if not spec.enabled:
                continue
            inst = self._ensure_instance(spec)
            outputs[event_id] = inst.runner.update(dt)
            if (
                inst.runner.vm is not None
                and inst.runner.vm.completed
                and not inst.runner.call_stack
            ):
                completed.append(event_id)

        for event_id in completed:
            # completion resets runtime instance; if still enabled, it may start
            # again on the next scheduler update (autorun/parallel loop semantics)
            self._instances.pop(event_id, None)

        return outputs

    def stop(self, event_id: str):
        inst = self._instances.get(str(event_id))
        if inst is None:
            return False
        inst.runner.stop()
        self._instances.pop(str(event_id), None)
        return True

    def stop_all(self):
        for inst in tuple(self._instances.values()):
            inst.runner.stop()
        self._instances.clear()

    def snapshot(self):
        return {
            "schema": "asteria.event_scheduler",
            "version": 1,
            "instances": {
                event_id: inst.runner.snapshot()
                for event_id, inst in self._instances.items()
                if inst.runner.snapshot() is not None
            },
        }

    def restore(self, data):
        if set(data) != {"schema", "version", "instances"}:
            raise ValueError("invalid event scheduler snapshot")
        if data["schema"] != "asteria.event_scheduler" or data["version"] != 1:
            raise ValueError("unsupported event scheduler snapshot")
        if not isinstance(data["instances"], dict):
            raise TypeError("scheduler instances must be a dict")

        self._instances.clear()
        for event_id, runner_data in data["instances"].items():
            spec = self._specs.get(event_id)
            if spec is None:
                raise KeyError(
                    f"snapshot references unknown scheduled event: {event_id}"
                )
            runner = EventRunner(
                self.registry, context=self.context, world_commands=self.world_commands
            )
            runner.restore(runner_data)
            self._instances[event_id] = ScheduledEventInstance(spec, runner)
