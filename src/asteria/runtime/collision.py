"""2D collision: colliders, layers/masks, spatial-hash broad phase, triggers (ASTERIA_SPEC §8).

Colliders are axis-aligned boxes or circles placed at the entity's world
position (Transform hierarchy aware) plus an offset. Two colliders interact
when each one's ``layer`` bit is in the other's ``mask``. Solid colliders
block movement (``CollisionWorld.collides_world_point`` lets the existing
``CharacterController2D`` use them like a tile map); triggers only report
enter / stay / exit.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, hypot

from asteria.core import Component, Field, System, Transform, component_schema, world_position

ALL_LAYERS = 0xFFFFFFFF


@component_schema(
    type_name="asteria.Collider2D",
    version=1,
    fields=(
        Field("shape", str, "box", choices=("box", "circle")),
        Field("width", float, 16.0, minimum=0.0),
        Field("height", float, 16.0, minimum=0.0),
        Field("radius", float, 8.0, minimum=0.0),
        Field("offset_x", float, 0.0),
        Field("offset_y", float, 0.0),
        Field("layer", int, 0, minimum=0, maximum=31, tooltip="Bit index of this collider's layer."),
        Field("mask", int, ALL_LAYERS, minimum=0, maximum=ALL_LAYERS, tooltip="Bitmask of layers it collides with."),
        Field("is_trigger", bool, False, label="Trigger"),
        Field("enabled", bool, True),
    ),
)
class Collider2DComponent(Component):
    def __init__(self):
        super().__init__()
        self.shape = "box"
        self.width = 16.0
        self.height = 16.0
        self.radius = 8.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.layer = 0
        self.mask = ALL_LAYERS
        self.is_trigger = False
        self.enabled = True


@dataclass(frozen=True, slots=True)
class ColliderShape:
    entity_id: str
    shape: str
    cx: float
    cy: float
    half_w: float
    half_h: float
    radius: float
    layer_bit: int
    mask: int
    is_trigger: bool

    @property
    def bounds(self):
        return (self.cx - self.half_w, self.cy - self.half_h, self.cx + self.half_w, self.cy + self.half_h)

    def interacts_with(self, other):
        return bool(self.mask & other.layer_bit) and bool(other.mask & self.layer_bit)


@dataclass(frozen=True, slots=True)
class Contact:
    a: str
    b: str
    normal: tuple[float, float]  # from a toward b
    depth: float


def shape_of(entity, collider):
    x, y = world_position(entity)
    cx, cy = x + collider.offset_x, y + collider.offset_y
    if collider.shape == "circle":
        half_w = half_h = collider.radius
    else:
        half_w, half_h = collider.width / 2, collider.height / 2
    return ColliderShape(
        entity.id,
        collider.shape,
        cx,
        cy,
        half_w,
        half_h,
        collider.radius,
        1 << int(collider.layer),
        int(collider.mask),
        bool(collider.is_trigger),
    )


def _box_box(a, b):
    dx, dy = b.cx - a.cx, b.cy - a.cy
    ox = a.half_w + b.half_w - abs(dx)
    oy = a.half_h + b.half_h - abs(dy)
    if ox <= 0 or oy <= 0:
        return None
    if ox < oy:
        return ((1.0 if dx >= 0 else -1.0, 0.0), ox)
    return ((0.0, 1.0 if dy >= 0 else -1.0), oy)


def _circle_circle(a, b):
    dx, dy = b.cx - a.cx, b.cy - a.cy
    dist = hypot(dx, dy)
    depth = a.radius + b.radius - dist
    if depth <= 0:
        return None
    return ((dx / dist, dy / dist) if dist else (1.0, 0.0), depth)


def _box_circle(box, circle):
    nx = min(max(circle.cx, box.cx - box.half_w), box.cx + box.half_w)
    ny = min(max(circle.cy, box.cy - box.half_h), box.cy + box.half_h)
    dx, dy = circle.cx - nx, circle.cy - ny
    dist = hypot(dx, dy)
    if dist >= circle.radius:
        return None
    if dist == 0:  # centre inside the box: push out along the shallow axis
        return _box_box(
            box,
            ColliderShape(
                circle.entity_id,
                "box",
                circle.cx,
                circle.cy,
                circle.radius,
                circle.radius,
                circle.radius,
                circle.layer_bit,
                circle.mask,
                circle.is_trigger,
            ),
        )
    return ((dx / dist, dy / dist), circle.radius - dist)


def overlap(a, b):
    """Contact normal/depth from ``a`` toward ``b``, or None."""
    if a.shape == "circle" and b.shape == "circle":
        result = _circle_circle(a, b)
    elif a.shape == "circle":
        result = _box_circle(b, a)
        result = None if result is None else ((-result[0][0], -result[0][1]), result[1])
    elif b.shape == "circle":
        result = _box_circle(a, b)
    else:
        result = _box_box(a, b)
    return None if result is None else Contact(a.entity_id, b.entity_id, result[0], result[1])


class SpatialHash:
    """Uniform-grid broad phase over shape bounds."""

    def __init__(self, cell_size=64.0):
        if cell_size <= 0:
            raise ValueError("cell_size must be positive")
        self.cell_size = float(cell_size)
        self._cells: dict[tuple[int, int], list[ColliderShape]] = {}

    def _cells_for(self, bounds):
        x0, y0, x1, y1 = bounds
        size = self.cell_size
        for cx in range(floor(x0 / size), floor(x1 / size) + 1):
            for cy in range(floor(y0 / size), floor(y1 / size) + 1):
                yield (cx, cy)

    def insert(self, shape):
        for cell in self._cells_for(shape.bounds):
            self._cells.setdefault(cell, []).append(shape)

    def query(self, bounds):
        seen = {}
        for cell in self._cells_for(bounds):
            for shape in self._cells.get(cell, ()):
                seen[shape.entity_id] = shape
        return tuple(seen.values())

    def candidate_pairs(self):
        pairs = {}
        for shapes in self._cells.values():
            for i, a in enumerate(shapes):
                for b in shapes[i + 1 :]:
                    key = (a.entity_id, b.entity_id) if a.entity_id < b.entity_id else (b.entity_id, a.entity_id)
                    if key not in pairs:
                        pairs[key] = (a, b) if key[0] == a.entity_id else (b, a)
        return tuple(pairs.values())


class CollisionWorld:
    """Collider snapshot of a scene with broad + narrow phase queries."""

    def __init__(self, shapes=(), cell_size=64.0):
        self.shapes = {s.entity_id: s for s in shapes}
        self.grid = SpatialHash(cell_size)
        for shape in self.shapes.values():
            self.grid.insert(shape)

    @classmethod
    def from_scene(cls, scene, cell_size=64.0):
        return cls(
            (shape_of(e, c) for e, c in scene.query(Collider2DComponent) if c.enabled and e.has(Transform)),
            cell_size,
        )

    def contacts(self):
        result = []
        for a, b in self.grid.candidate_pairs():
            if a.interacts_with(b):
                contact = overlap(a, b)
                if contact is not None:
                    result.append(contact)
        return tuple(result)

    def query_point(self, x, y, *, mask=ALL_LAYERS, solid_only=True, exclude=()):
        probe = ColliderShape("__probe__", "box", x, y, 0.0, 0.0, 0.0, ALL_LAYERS, mask, False)
        hits = []
        for shape in self.grid.query(probe.bounds):
            if shape.entity_id in exclude or (solid_only and shape.is_trigger) or not (mask & shape.layer_bit):
                continue
            x0, y0, x1, y1 = shape.bounds
            if shape.shape == "circle":
                inside = hypot(x - shape.cx, y - shape.cy) <= shape.radius
            else:
                inside = x0 <= x <= x1 and y0 <= y <= y1
            if inside:
                hits.append(shape.entity_id)
        return tuple(hits)

    def blocking_query(self, *, mask=ALL_LAYERS, exclude=()):
        """Object with ``collides_world_point`` for CharacterController2D.move."""
        world = self

        class _Query:
            def collides_world_point(self, x, y):
                return bool(world.query_point(x, y, mask=mask, exclude=exclude))

        return _Query()


class CombinedQuery:
    """Blocks movement when any of the given queries (tile map, collision world, ...) does."""

    def __init__(self, *queries):
        self.queries = tuple(q for q in queries if q is not None)

    def collides_world_point(self, x, y):
        return any(q.collides_world_point(x, y) for q in self.queries)


class CollisionSystem(System):
    """Rebuilds the collision world each update and reports contacts and trigger events.

    ``trigger_events`` holds ``(kind, trigger_id, other_id)`` tuples for this
    update, with kind in {"enter", "stay", "exit"}; ``listeners`` are called
    with each event.
    """

    order = 50

    def __init__(self, cell_size=64.0):
        self.cell_size = cell_size
        self.world = CollisionWorld()
        self.contacts: tuple[Contact, ...] = ()
        self.trigger_events: list[tuple[str, str, str]] = []
        self.listeners = []
        self._active_triggers: set[tuple[str, str]] = set()

    def update(self, scene, dt):
        self.world = CollisionWorld.from_scene(scene, self.cell_size)
        self.contacts = self.world.contacts()
        current = set()
        for contact in self.contacts:
            a, b = self.world.shapes[contact.a], self.world.shapes[contact.b]
            if a.is_trigger:
                current.add((a.entity_id, b.entity_id))
            if b.is_trigger:
                current.add((b.entity_id, a.entity_id))
        events = [("enter", t, o) for t, o in sorted(current - self._active_triggers)]
        events += [("stay", t, o) for t, o in sorted(current & self._active_triggers)]
        events += [("exit", t, o) for t, o in sorted(self._active_triggers - current)]
        self._active_triggers = current
        self.trigger_events = events
        for event in events:
            for listener in tuple(self.listeners):
                listener(*event)
