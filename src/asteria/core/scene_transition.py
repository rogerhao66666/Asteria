"""Scene changes with optional fade, carrying persistent entities (ASTERIA_SPEC §8 Scene)."""

from __future__ import annotations

from dataclasses import dataclass

from .component import Component
from .metadata import component_schema


@component_schema(type_name="asteria.Persistent", version=1, fields=())
class PersistentComponent(Component):
    """Marks an entity that moves to the next scene on Application.change_scene."""


@dataclass(frozen=True, slots=True)
class SceneTransition:
    fade_out: float = 0.25
    fade_in: float = 0.25
    color: tuple[int, int, int] = (0, 0, 0)

    def __post_init__(self):
        if self.fade_out < 0 or self.fade_in < 0:
            raise ValueError("fade durations must be >= 0")


@dataclass(slots=True)
class _ActiveTransition:
    target: object
    spec: SceneTransition
    phase: str = "out"
    elapsed: float = 0.0


def carry_persistent_entities(old_scene, new_scene):
    """Move every entity with PersistentComponent from ``old_scene`` to ``new_scene``."""
    if old_scene is None or old_scene is new_scene:
        return ()
    moved = tuple(e for e in old_scene.entities() if e.has(PersistentComponent))
    for entity in moved:
        old_scene.detach_entity(entity)
        if new_scene.get_entity(entity.id) is None:
            new_scene.add_entity(entity)
    return moved
