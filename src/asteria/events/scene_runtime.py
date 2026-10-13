from __future__ import annotations

from dataclasses import dataclass

from .binding import EventTriggerKind, SceneEventBindings
from .context import EventContext
from .scheduler import EventScheduler


@dataclass(slots=True)
class SceneEventRuntime:
    bindings: SceneEventBindings
    scheduler: EventScheduler
    context: EventContext

    @classmethod
    def build(cls, bindings, registry, *, context=None, world_commands=None, sequence_host=None):
        context = context or EventContext()
        scheduler = EventScheduler(
            registry, context=context, world_commands=world_commands, sequence_host=sequence_host
        )
        runtime = cls(bindings, scheduler, context)
        runtime.refresh_scheduled_bindings()
        return runtime

    def refresh_scheduled_bindings(self):
        desired = {spec.event_id: spec for spec in self.bindings.scheduled_specs(self.context)}
        existing = {spec.event_id: spec for spec in self.scheduler.specs()}

        for event_id in tuple(existing):
            if event_id not in desired:
                self.scheduler.remove(event_id)

        for event_id, spec in desired.items():
            if event_id in existing:
                if existing[event_id] != spec:
                    self.scheduler.replace(spec)
            else:
                self.scheduler.add(spec)

    def action_binding_for_entity(self, entity_id: str):
        active = [
            b
            for b in self.bindings.active_for_entity(entity_id, self.context)
            if b.trigger == EventTriggerKind.ACTION
        ]
        if not active:
            return None
        active.sort(key=lambda b: b.binding_id)
        return active[0]

    def update(self, dt=0.0):
        self.refresh_scheduled_bindings()
        return self.scheduler.update(dt)
