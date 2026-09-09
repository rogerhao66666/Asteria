from dataclasses import dataclass

from asteria.core import Transform

from .commands import CommandTransaction
from .editing import build_set_component_field_command


@dataclass(frozen=True, slots=True)
class GridSnap:
    enabled: bool = True
    size: float = 16.0

    def snap(self, value):
        if not self.enabled or self.size <= 0:
            return float(value)
        return round(float(value) / self.size) * self.size

    def point(self, x, y):
        return self.snap(x), self.snap(y)


@dataclass(frozen=True, slots=True)
class SelectionRect:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def left(self):
        return min(self.x1, self.x2)

    @property
    def right(self):
        return max(self.x1, self.x2)

    @property
    def top(self):
        return min(self.y1, self.y2)

    @property
    def bottom(self):
        return max(self.y1, self.y2)

    def contains(self, x, y):
        return self.left <= x <= self.right and self.top <= y <= self.bottom


def entities_in_screen_rect(markers, rect):
    return tuple(m.entity for m in markers if rect.contains(m.screen_x, m.screen_y))


def build_move_entities_command(entities, delta_world_x, delta_world_y, snap=None):
    entities = tuple(entities)
    if not entities:
        raise ValueError("No entities to move")
    snap = snap or GridSnap(False)
    tx = CommandTransaction("Move Entities")
    for entity in entities:
        transform = entity.try_get(Transform)
        if transform is None:
            continue
        nx, ny = snap.point(transform.x + delta_world_x, transform.y + delta_world_y)
        if nx != transform.x:
            tx.add(build_set_component_field_command(transform, "x", nx))
        if ny != transform.y:
            tx.add(build_set_component_field_command(transform, "y", ny))
    if not tx.commands:
        raise ValueError("No movable Transform components")
    return tx
