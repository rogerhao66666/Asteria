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

from asteria import kernels
from asteria.core import Component, Field, System, Transform, component_schema, world_position
from asteria.core.columns import column_storage
from asteria.core.migration import component_migration

ALL_LAYERS = 0xFFFFFFFF
SHAPES = ("box", "circle", "slope_right", "slope_left")


@column_storage()
@component_schema(
    type_name="asteria.Collider2D",
    version=3,
    fields=(
        Field(
            "shape",
            str,
            "box",
            choices=SHAPES,
            tooltip="slope_right: solid below a line rising to the right across the box; "
            "slope_left: rising left.",
        ),
        Field("width", float, 16.0, minimum=0.0),
        Field("height", float, 16.0, minimum=0.0),
        Field("radius", float, 8.0, minimum=0.0),
        Field("offset_x", float, 0.0),
        Field("offset_y", float, 0.0),
        Field(
            "layer", int, 0, minimum=0, maximum=31, tooltip="Bit index of this collider's layer."
        ),
        Field(
            "mask",
            int,
            ALL_LAYERS,
            minimum=0,
            maximum=ALL_LAYERS,
            tooltip="Bitmask of layers it collides with.",
        ),
        Field("is_trigger", bool, False, label="Trigger"),
        Field(
            "one_way",
            bool,
            False,
            label="One-way platform",
            tooltip="Side view: blocks only from above.",
        ),
        Field(
            "ladder",
            bool,
            False,
            tooltip="A climbable area (side view); it never blocks movement.",
        ),
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
        self.one_way = False
        self.ladder = False
        self.enabled = True


@component_migration("asteria.Collider2D", from_version=1)
def _collider2d_v1_to_v2(fields):
    return fields  # v2 adds one_way (default False keeps v1 behaviour)


@component_migration("asteria.Collider2D", from_version=2)
def _collider2d_v2_to_v3(fields):
    return fields  # v3 adds slope shapes and ladder (default False)


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
    one_way: bool = False
    ladder: bool = False

    @property
    def bounds(self):
        return (
            self.cx - self.half_w,
            self.cy - self.half_h,
            self.cx + self.half_w,
            self.cy + self.half_h,
        )

    @property
    def slope(self):
        return self.shape in ("slope_right", "slope_left")

    def surface_y(self, x):
        """Top of the solid at ``x`` (slopes: the line across the box; other shapes: the top
        edge)."""
        x0, y0, x1, y1 = self.bounds
        if not self.slope or x1 <= x0:
            return y0
        t = min(1.0, max(0.0, (x - x0) / (x1 - x0)))
        if self.shape == "slope_left":
            t = 1.0 - t
        return y1 - t * (y1 - y0)

    def contains_point(self, x, y):
        x0, y0, x1, y1 = self.bounds
        if self.shape == "circle":
            return hypot(x - self.cx, y - self.cy) <= self.radius
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            return False
        return not self.slope or y >= self.surface_y(x) - 1e-9

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
        bool(collider.is_trigger) or bool(collider.ladder),  # ladders never block
        bool(getattr(collider, "one_way", False)),
        bool(collider.ladder),
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
                    key = (
                        (a.entity_id, b.entity_id)
                        if a.entity_id < b.entity_id
                        else (b.entity_id, a.entity_id)
                    )
                    if key not in pairs:
                        pairs[key] = (a, b) if key[0] == a.entity_id else (b, a)
        return tuple(pairs.values())


class CollisionWorld:
    """Collider snapshot of a scene with broad + narrow phase queries.

    Shapes are kept as columns (one list per field); ``ColliderShape`` objects are only made when
    something asks
    for them (``shapes``, point queries), so batched users (controllers, projectiles) never pay
    for them.
    """

    _FIELDS = (
        "ids",
        "kind",
        "cx",
        "cy",
        "hw",
        "hh",
        "radius",
        "bit",
        "mask",
        "trigger",
        "one_way",
        "ladder",
    )

    def __init__(self, shapes=(), cell_size=64.0):
        if cell_size <= 0:
            raise ValueError("cell_size must be positive")
        self.cell_size = float(cell_size)
        for name in self._FIELDS:
            setattr(self, "_" + name, [])
        self._row = {}
        self._shapes = None
        self._grid = None
        self._rows = None  # (cell -> [row], row -> [cell]): the row grid, kept up to date
        self._solid = None
        self._source = None  # what from_scene read, so follow() can update it in place
        self.parented = False  # some collider hangs under a parent transform (see move_shapes)
        self.stale = False  # positions changed in a way move_shapes could not follow: rebuild
        for shape in shapes:
            self._add(
                shape.entity_id,
                shape.shape,
                shape.cx,
                shape.cy,
                shape.half_w,
                shape.half_h,
                shape.radius,
                shape.layer_bit,
                shape.mask,
                shape.is_trigger,
                shape.one_way,
                shape.ladder,
            )

    def _add(
        self, entity_id, kind, cx, cy, hw, hh, radius, bit, mask, trigger, one_way, ladder=False
    ):
        if entity_id in self._row:  # same entity again: the later shape wins (dict semantics)
            i = self._row[entity_id]
            for name, value in zip(
                self._FIELDS,
                (entity_id, kind, cx, cy, hw, hh, radius, bit, mask, trigger, one_way, ladder),
                strict=True,
            ):
                getattr(self, "_" + name)[i] = value
            return
        self._rows = None
        self._row[entity_id] = len(self._ids)
        self._ids.append(entity_id)
        self._kind.append(kind)
        self._cx.append(cx)
        self._cy.append(cy)
        self._hw.append(hw)
        self._hh.append(hh)
        self._radius.append(radius)
        self._bit.append(bit)
        self._mask.append(mask)
        self._trigger.append(trigger)
        self._one_way.append(one_way)
        self._ladder.append(ladder)

    def _shape(self, i):
        return ColliderShape(
            self._ids[i],
            self._kind[i],
            self._cx[i],
            self._cy[i],
            self._hw[i],
            self._hh[i],
            self._radius[i],
            self._bit[i],
            self._mask[i],
            self._trigger[i],
            self._one_way[i],
            self._ladder[i],
        )

    @property
    def shapes(self):
        """``{entity_id: ColliderShape}`` (made on first use)."""
        if self._shapes is None:
            self._shapes = {self._ids[i]: self._shape(i) for i in range(len(self._ids))}
        return self._shapes

    def solid_columns(self):
        """Non-trigger shapes as ``(shapes, (x0, y0, x1, y1))`` for batched overlap tests
        (cached); ``shapes[j]``
        makes the ``ColliderShape`` of row ``j`` on demand."""
        if self._solid is None:
            rows = [i for i, trigger in enumerate(self._trigger) if not trigger]
            cx, cy, hw, hh = self._cx, self._cy, self._hw, self._hh
            columns = (
                [cx[i] - hw[i] for i in rows],
                [cy[i] - hh[i] for i in rows],
                [cx[i] + hw[i] for i in rows],
                [cy[i] + hh[i] for i in rows],
            )
            self._solid = (_ShapeRows(self, rows), columns)
        return self._solid

    def solid_extras(self):
        """Per solid row (same order as ``solid_columns``): ``cx, cy, radius, layer bit, one_way,
        circle`` lists and
        ``{entity_id: solid row}`` — what the batched blocking test needs."""
        shapes, _ = self.solid_columns()
        if getattr(shapes, "extras", None) is None:
            rows = shapes.rows
            shapes.extras = (
                [self._cx[i] for i in rows],
                [self._cy[i] for i in rows],
                [self._radius[i] for i in rows],
                [self._bit[i] for i in rows],
                [self._one_way[i] for i in rows],
                [self._kind[i] == "circle" for i in rows],
                {self._ids[i]: j for j, i in enumerate(rows)},
            )
        return shapes.extras

    def move_shapes(self, deltas):
        """Shift the shapes of entities that moved (``{entity_id: (dx, dy)}``) so the snapshot
        stays current.

        A collider under a moved parent cannot be followed here; the world is then marked
        ``stale``.
        """
        moved = []
        row, cx, cy = self._row, self._cx, self._cy
        for entity_id, (dx, dy) in deltas.items():
            i = row.get(entity_id)
            if i is not None and (dx or dy):
                cx[i] += dx
                cy[i] += dy
                moved.append(i)
        if deltas and self.parented:
            self.stale = True
        if moved:
            self._moved(moved)

    def _moved(self, rows):
        """Rows whose box changed: their cells are updated in the row grid (not rebuilt)."""
        self._grid = None
        self._solid = None
        self._shapes = None
        if self._rows is None:
            return
        if len(rows) * 2 > len(self._ids):  # most moved (a swarm): rebuilt when next needed
            self._rows = None
            return
        cells, where = self._rows
        for i in rows:
            new = self._cells_of(i)
            old = where[i]
            if new == old:
                continue
            for cell in old:
                members = cells[cell]
                members.remove(i)
                if not members:
                    del cells[cell]
            for cell in new:
                members = cells.setdefault(cell, [])
                members.append(i)
                if len(members) > 1 and members[-2] > i:
                    members.sort()  # rows in a cell stay in row (scene) order
            where[i] = new

    def _cells_of(self, i):
        size = self.cell_size
        x0, x1 = self._cx[i] - self._hw[i], self._cx[i] + self._hw[i]
        y0, y1 = self._cy[i] - self._hh[i], self._cy[i] + self._hh[i]
        return [
            (a, b)
            for a in range(floor(x0 / size), floor(x1 / size) + 1)
            for b in range(floor(y0 / size), floor(y1 / size) + 1)
        ]

    def _row_grid(self):
        """``(cells, where)``: the rows in each grid cell (in row order) and each row's cells;
        built once, then moved shapes only change their own cells."""
        if self._rows is None:
            cells, where = {}, []
            for i in range(len(self._ids)):
                keys = self._cells_of(i)
                where.append(keys)
                for key in keys:
                    cells.setdefault(key, []).append(i)
            self._rows = (cells, where)
        return self._rows

    def query_box(self, bounds):
        """Shapes whose grid cells meet ``bounds`` (as ``grid.query``: each once, in the order
        cells and rows are met)."""
        cells, _ = self._row_grid()
        size = self.cell_size
        x0, y0, x1, y1 = bounds
        seen = {}
        for a in range(floor(x0 / size), floor(x1 / size) + 1):
            for b in range(floor(y0 / size), floor(y1 / size) + 1):
                for i in cells.get((a, b), ()):
                    if i not in seen:
                        seen[i] = None
        made = self.shapes
        ids = self._ids
        return tuple(made[ids[i]] for i in seen)

    @property
    def grid(self):
        """Spatial hash for point and area queries (built on first use)."""
        if self._grid is None:
            self._grid = SpatialHash(self.cell_size)
            for shape in self.shapes.values():
                self._grid.insert(shape)
        return self._grid

    def candidate_pairs(self):
        """Pairs of shapes whose bounds overlap or touch (the active kernel's broad phase),
        ``a.entity_id <
        b.entity_id`` in each, in a stable order."""
        shapes = tuple(self.shapes.values())
        bounds = [s.bounds for s in shapes]
        columns = [[b[k] for b in bounds] for k in range(4)] if bounds else [[], [], [], []]
        pairs = []
        for i, j in kernels.active().aabb_pairs(*columns, self.cell_size):
            a, b = shapes[i], shapes[j]
            pairs.append((a, b) if a.entity_id < b.entity_id else (b, a))
        return tuple(pairs)

    @classmethod
    def from_scene(cls, scene, cell_size=64.0):
        """Snapshot of the scene's enabled colliders, in scene order, read straight from column
        storage."""
        colliders, transforms = scene.columns(Collider2DComponent), scene.columns(Transform)
        world = cls((), cell_size)
        if colliders is None or transforms is None:
            return world
        owners = colliders.components
        placed = transforms.components
        live = []
        for slot in colliders.slots():
            collider = owners[slot]
            entity = collider._entity
            transform = placed[slot] if slot < len(placed) else None
            if (
                transform is None
                or not collider.enabled
                or not entity.enabled
                or entity._destroy_requested
            ):
                continue
            live.append((entity._order, slot, entity, collider, transform))
        live.sort(key=lambda row: row[0])
        slots = [row[1] for row in live]
        kinds = [row[3].shape for row in live]
        world._source = (
            scene,
            colliders,
            transforms,
            colliders.version,
            transforms.version,
            len(colliders.slots()),
            [(row[2], row[3]) for row in live],
            slots,
            [kind == "circle" for kind in kinds],
        )
        cx, cy, hw, hh = kernels.active().collider_columns(
            transforms.data, colliders.data, slots, [kind == "circle" for kind in kinds]
        )
        data = colliders.data
        radius, layer, mask = data["radius"], data["layer"], data["mask"]
        trigger, one_way, ladder = data["is_trigger"], data["one_way"], data["ladder"]
        add = world._add
        for k, (_, slot, entity, collider, transform) in enumerate(live):
            if transform.parent_id:  # under a parent: the full transform chain
                world.parented = True
                shape = shape_of(entity, collider)
                add(
                    shape.entity_id,
                    shape.shape,
                    shape.cx,
                    shape.cy,
                    shape.half_w,
                    shape.half_h,
                    shape.radius,
                    shape.layer_bit,
                    shape.mask,
                    shape.is_trigger,
                    shape.one_way,
                    shape.ladder,
                )
                continue
            add(
                entity.id,
                kinds[k],
                cx[k],
                cy[k],
                hw[k],
                hh[k],
                radius[slot],
                1 << int(layer[slot]),
                int(mask[slot]),
                bool(trigger[slot]) or bool(ladder[slot]),  # ladders never block
                bool(one_way[slot]),
                bool(ladder[slot]),
            )
        return world

    def follow(self, scene):
        """Bring this snapshot up to date with ``scene`` in place: moved and resized colliders
        are updated (each only in its own grid cells). Returns False - rebuild with
        ``from_scene`` - when that cannot be done exactly: another scene, colliders or
        transforms added or removed, one enabled, disabled or being destroyed, one under a
        parent, or a layer, mask or kind changed. Rebuilding the whole world twice a frame was
        most of a field frame with many foes."""
        source = self._source
        if source is None or self.parented or self.stale:
            return False
        owner, colliders, transforms, cv, tv, count, live, slots, circles = source
        if (
            owner is not scene
            or scene.columns(Collider2DComponent) is not colliders
            or scene.columns(Transform) is not transforms
            or colliders.version != cv
            or transforms.version != tv
            or len(colliders.slots()) != count
        ):
            return False
        if not all(c.enabled and e.enabled and not e._destroy_requested for e, c in live):
            return False
        if count != len(live):  # some collider was left out: it must still be left out
            members = {id(c) for _, c in live}
            for slot in colliders.slots():
                collider = colliders.components[slot]
                entity = collider._entity
                if id(collider) not in members and (
                    collider.enabled and entity.enabled and not entity._destroy_requested
                ):
                    return False
        data = colliders.data
        # the settings (whole lists compared at once: a loop per collider was the cost)
        radius, layer, mask = data["radius"], data["layer"], data["mask"]
        trigger, one_way, ladder = data["is_trigger"], data["one_way"], data["ladder"]
        if (
            [radius[s] for s in slots] != self._radius
            or [1 << int(layer[s]) for s in slots] != self._bit
            or [int(mask[s]) for s in slots] != self._mask
            or [bool(trigger[s]) or bool(ladder[s]) for s in slots] != self._trigger
            or [bool(one_way[s]) for s in slots] != self._one_way
            or [bool(ladder[s]) for s in slots] != self._ladder
            or [c.shape for _, c in live] != self._kind
        ):
            return False
        cx, cy, hw, hh = (
            list(v.tolist() if hasattr(v, "tolist") else v)
            for v in kernels.active().collider_columns(transforms.data, data, slots, circles)
        )
        if cx == self._cx and cy == self._cy and hw == self._hw and hh == self._hh:
            return True  # nothing moved
        old_x, old_y, old_w, old_h = self._cx, self._cy, self._hw, self._hh
        changed = [
            k
            for k in range(len(slots))
            if cx[k] != old_x[k] or cy[k] != old_y[k] or hw[k] != old_w[k] or hh[k] != old_h[k]
        ]
        self._cx, self._cy, self._hw, self._hh = cx, cy, hw, hh
        self._moved(changed)
        return True

    def contacts(self):
        result = []
        for a, b in self.candidate_pairs():
            if a.interacts_with(b):
                contact = overlap(a, b)
                if contact is not None:
                    result.append(contact)
        return tuple(result)

    def query_point(self, x, y, *, mask=ALL_LAYERS, solid_only=True, exclude=()):
        """Ids of the shapes containing the point, read straight from the columns (no shape
        objects: AI steps ask this tens of thousands of times a second)."""
        cells, _ = self._row_grid()
        size = self.cell_size
        rows = cells.get((floor(x / size), floor(y / size)))
        if not rows:
            return ()
        ids, kind, trigger, bit = self._ids, self._kind, self._trigger, self._bit
        cx, cy, hw, hh = self._cx, self._cy, self._hw, self._hh
        hits = []
        for i in rows:
            if (solid_only and trigger[i]) or not (mask & bit[i]) or ids[i] in exclude:
                continue
            shape = kind[i]
            if shape == "circle":
                if hypot(x - cx[i], y - cy[i]) <= self._radius[i]:
                    hits.append(ids[i])
            elif cx[i] - hw[i] <= x <= cx[i] + hw[i] and cy[i] - hh[i] <= y <= cy[i] + hh[i]:
                if shape not in ("slope_right", "slope_left") or self._shape(i).contains_point(
                    x, y
                ):
                    hits.append(ids[i])
        return tuple(hits)

    def ladder_at(self, x0, y0, x1, y1, *, exclude=()):
        """A ladder shape overlapping the box, or ``None``."""
        for shape in self.query_box((x0, y0, x1, y1)):
            if shape.ladder and shape.entity_id not in exclude:
                sx0, sy0, sx1, sy1 = shape.bounds
                if x0 <= sx1 and sx0 <= x1 and y0 <= sy1 and sy0 <= y1:
                    return shape
        return None

    def blocking_query(self, *, mask=ALL_LAYERS, exclude=()):
        """Object with ``collides_world_point`` for CharacterController2D.move."""
        return _BlockingQuery(self, mask, exclude)


class _ShapeRows:
    """Sequence view of selected world rows; each ``ColliderShape`` is made when first indexed."""

    __slots__ = ("world", "rows", "_made", "extras")

    def __init__(self, world, rows):
        self.world, self.rows, self._made, self.extras = world, rows, {}, None

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, j):
        shape = self._made.get(j)
        if shape is None:
            shape = self._made[j] = self.world._shape(self.rows[j])
        return shape


class _BlockingQuery:
    __slots__ = ("world", "mask", "exclude")

    def __init__(self, world, mask, exclude):
        self.world, self.mask, self.exclude = world, mask, exclude

    def collides_world_point(self, x, y):
        return bool(self.world.query_point(x, y, mask=self.mask, exclude=self.exclude))


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
