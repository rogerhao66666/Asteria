from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from asteria.core.lifecycle import LifecycleHookBus

from .runner import EventRunner


@dataclass(frozen=True, slots=True)
class LifecycleEventBinding:
    """Run ``event_program_id`` when ``hook_name`` fires (battle events use ``rpg.battle.*`` hooks).

    ``conditions`` (all must hold) can read switches, variables, locals and
    host providers such as ``battle`` (``round``, ``hp_ratio:<member or enemy id>``).
    ``once`` runs it at most once per hook bus lifetime (one battle).
    """

    hook_name: str
    event_program_id: str
    source_entity_id: str = ""
    conditions: tuple = ()
    once: bool = False

    def __init__(self, hook_name, event_program_id, *, source_entity_id="", conditions=(), once=False):
        from .conditions import EventCondition

        hook_name = str(hook_name).strip()
        event_program_id = str(event_program_id).strip()
        if not hook_name or not event_program_id:
            raise ValueError("hook_name and event_program_id are required")
        conditions = tuple(conditions)
        if any(not isinstance(x, EventCondition) for x in conditions):
            raise TypeError("conditions must contain EventCondition values")
        object.__setattr__(self, "hook_name", hook_name)
        object.__setattr__(self, "event_program_id", event_program_id)
        object.__setattr__(self, "source_entity_id", str(source_entity_id))
        object.__setattr__(self, "conditions", conditions)
        object.__setattr__(self, "once", bool(once))

    def to_data(self):
        data = {
            "hook_name": self.hook_name,
            "event_program_id": self.event_program_id,
            "source_entity_id": self.source_entity_id,
        }
        if self.conditions or self.once:
            data["conditions"] = [x.to_data() for x in self.conditions]
            data["once"] = self.once
        return data

    @classmethod
    def from_data(cls, data):
        from .conditions import EventCondition

        base = {"hook_name", "event_program_id", "source_entity_id"}
        if set(data) not in (base, base | {"conditions", "once"}):
            raise ValueError("invalid lifecycle event binding")
        return cls(
            data["hook_name"],
            data["event_program_id"],
            source_entity_id=data["source_entity_id"],
            conditions=[EventCondition.from_data(x) for x in data.get("conditions", ())],
            once=data.get("once", False),
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
        self._fired = set()
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
            if binding.once and id(binding) in self._fired:
                continue
            try:
                ready = all(c.evaluate(self.runner.context) for c in binding.conditions)
            except (ValueError, KeyError):
                ready = False
            if not ready:
                continue
            if binding.once:
                self._fired.add(id(binding))
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
