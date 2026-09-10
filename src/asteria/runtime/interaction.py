from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from asteria.core import Transform

_FACING_VECTORS = {
    "up": (0.0, -1.0),
    "down": (0.0, 1.0),
    "left": (-1.0, 0.0),
    "right": (1.0, 0.0),
}


@dataclass(frozen=True, slots=True)
class InteractionCandidate:
    entity: object
    component: object
    distance: float


@dataclass(frozen=True, slots=True)
class InteractionTrigger:
    """Backend-neutral request to start an event program."""

    source_entity_id: str
    event_program_id: str
    local_scope_id: str


class InteractionQuery:
    """Find interactable entities from canonical scene/entity data."""

    def __init__(self, *, facing_dot_threshold: float = 0.25):
        threshold = float(facing_dot_threshold)
        if threshold < -1.0 or threshold > 1.0:
            raise ValueError("facing_dot_threshold must be between -1 and 1")
        self.facing_dot_threshold = threshold

    def candidates(self, scene, actor, facing: str):
        actor_transform = actor.get(Transform)
        facing_vector = _FACING_VECTORS.get(str(facing).lower())
        if facing_vector is None:
            raise ValueError(f"unsupported facing: {facing}")

        from .components2d import Interaction2DComponent

        result = []
        for entity in scene.entities():
            if entity is actor or not entity.enabled:
                continue
            interaction = entity.try_get(Interaction2DComponent)
            transform = entity.try_get(Transform)
            if interaction is None or transform is None:
                continue
            if not interaction.enabled or not interaction.event_program_id:
                continue

            dx = transform.x - actor_transform.x
            dy = transform.y - actor_transform.y
            distance = hypot(dx, dy)
            if distance > interaction.range:
                continue

            if interaction.require_facing and distance > 1e-12:
                nx, ny = dx / distance, dy / distance
                dot = nx * facing_vector[0] + ny * facing_vector[1]
                if dot < self.facing_dot_threshold:
                    continue

            result.append(InteractionCandidate(entity, interaction, distance))

        result.sort(key=lambda item: (item.distance, item.entity.id))
        return tuple(result)

    def nearest(self, scene, actor, facing: str):
        items = self.candidates(scene, actor, facing)
        return items[0] if items else None


class InteractionController:
    """Edge-triggered action-button interaction coordinator."""

    def __init__(self, *, action="interact", query=None):
        self.action = str(action)
        self.query = query or InteractionQuery()
        self._was_down = False

    def reset(self):
        self._was_down = False

    def step(self, input_snapshot, scene, actor, facing: str):
        down = float(input_snapshot.actions.get(self.action, 0.0)) > 0.0
        pressed = down and not self._was_down
        self._was_down = down
        if not pressed:
            return None

        candidate = self.query.nearest(scene, actor, facing)
        if candidate is None:
            return None

        component = candidate.component
        scope_id = component.local_scope_id or candidate.entity.id
        return InteractionTrigger(
            source_entity_id=candidate.entity.id,
            event_program_id=component.event_program_id,
            local_scope_id=scope_id,
        )
