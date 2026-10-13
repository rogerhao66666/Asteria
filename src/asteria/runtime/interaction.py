from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from asteria.core import Transform, world_position

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
        actor_x, actor_y = world_position(actor)
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
            if getattr(interaction, "trigger", "action") != "action":
                continue  # touch interactions start by walking in (TouchTriggerController)

            ex, ey = world_position(entity)
            dx = ex - actor_x
            dy = ey - actor_y
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


class TouchTriggerController:
    """Touch interactions (``trigger == "touch"``): fire once when the actor walks into range.

    The interaction re-arms after the actor leaves its range, so standing on a
    door does not loop. ``arm(scene, actor)`` marks everything currently in
    range as already touched (used after a transfer so the destination door
    does not send the player straight back).
    """

    def __init__(self):
        self._inside = set()

    def reset(self):
        self._inside.clear()

    def _touching(self, scene, actor):
        from .components2d import Interaction2DComponent

        ax, ay = world_position(actor)
        for entity in scene.entities():
            if entity is actor or not entity.enabled:
                continue
            interaction = entity.try_get(Interaction2DComponent)
            if interaction is None or entity.try_get(Transform) is None:
                continue
            if (
                not interaction.enabled
                or not interaction.event_program_id
                or interaction.trigger != "touch"
            ):
                continue
            ex, ey = world_position(entity)
            if hypot(ex - ax, ey - ay) <= interaction.range:
                yield entity, interaction

    def arm(self, scene, actor):
        self._inside = {entity.id for entity, _ in self._touching(scene, actor)}

    def step(self, scene, actor):
        touching = list(self._touching(scene, actor))
        fresh = [(e, i) for e, i in touching if e.id not in self._inside]
        self._inside = {e.id for e, _ in touching}
        if not fresh:
            return None
        entity, interaction = min(fresh, key=lambda item: item[0].id)
        return InteractionTrigger(
            entity.id, interaction.event_program_id, interaction.local_scope_id or entity.id
        )
