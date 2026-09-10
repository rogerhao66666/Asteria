from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from asteria.core.lifecycle import LifecycleHookBus

from .runner import EventRunner


@dataclass(frozen=True, slots=True)
class LifecycleEventBinding:
    hook_name: str
    event_program_id: str
    source_entity_id: str = ""

    def __init__(self, hook_name, event_program_id, *, source_entity_id=""):
        hook_name = str(hook_name).strip()
        event_program_id = str(event_program_id).strip()
        if not hook_name or not event_program_id:
            raise ValueError("hook_name and event_program_id are required")
        object.__setattr__(self, "hook_name", hook_name)
        object.__setattr__(self, "event_program_id", event_program_id)
        object.__setattr__(self, "source_entity_id", str(source_entity_id))

    def to_data(self):
        return {
            "hook_name": self.hook_name,
            "event_program_id": self.event_program_id,
            "source_entity_id": self.source_entity_id,
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"hook_name", "event_program_id", "source_entity_id"}:
            raise ValueError("invalid lifecycle event binding")
        return cls(
            data["hook_name"],
            data["event_program_id"],
            source_entity_id=data["source_entity_id"],
        )


class LifecycleEventBridge:
    """Optional adapter from lifecycle hooks to the Phase 5 EventRunner.

    The producer never knows about Event VM. Busy runners queue programs rather
    than replacing active dialogue/cutscenes.
    """

    def __init__(self, hooks, runner, bindings=()):
        if not isinstance(hooks, LifecycleHookBus):
            raise TypeError("hooks must be LifecycleHookBus")
        if not isinstance(runner, EventRunner):
            raise TypeError("runner must be EventRunner")
        self.hooks = hooks
        self.runner = runner
        self._bindings = {}
        self._pending = deque()
        for binding in bindings:
            self.bind(binding)

    def bind(self, binding):
        if not isinstance(binding, LifecycleEventBinding):
            raise TypeError("binding must be LifecycleEventBinding")
        bucket = self._bindings.setdefault(binding.hook_name, [])
        if not bucket:
            self.hooks.subscribe(binding.hook_name, self._on_hook)
        bucket.append(binding)
        return binding

    def _on_hook(self, event):
        for binding in self._bindings.get(event.name, ()):
            self._pending.append((binding, event))
        self.pump()

    def pump(self):
        if self.runner.busy or not self._pending:
            return None
        binding, event = self._pending.popleft()
        source = binding.source_entity_id or event.source
        return self.runner.start(
            binding.event_program_id,
            source_entity_id=source,
            local_scope_id=source,
        )

    def pending_count(self):
        return len(self._pending)
