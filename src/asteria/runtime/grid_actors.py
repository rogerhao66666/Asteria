"""Grid movers: field characters that stand, turn and walk a whole cell at a time.

``GridMover2DComponent`` gives an entity (a townsperson, a guard) a grid behaviour:

* ``still`` - stands facing ``facing``;
* ``look_around`` - after each pause turns to a random direction (of ``look_facings`` when
  set: a guard who looks down and right in turn);
* ``wander`` / ``wander_vertical`` / ``wander_horizontal`` - after each pause turns to a random
  direction (of the allowed axis) and walks one cell that way when the cell is free and inside
  its range.

``range_x`` / ``range_y`` count cells from the cell it started on (0: no limit on that axis).
``pauses`` lists the seconds a pause may last (one is picked at random each time). With
``face_player`` the mover turns to the player when the player talks to it.

``GridMoverSystem`` moves them. A mover never walks into a wall, the player, a cell the player is
stepping into, or a cell another mover stands on or is stepping into; while it steps, it holds
both the cell it left and the one it walks to. The view animates it from its own ``facing`` and
movement, as it does any character.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType

from asteria.core import Component, Field, Transform, component_schema

GRID_BEHAVIOURS = ("still", "look_around", "wander", "wander_vertical", "wander_horizontal")
FACINGS = ("down", "up", "left", "right")
STEP = {"down": (0, 1), "up": (0, -1), "left": (-1, 0), "right": (1, 0)}
AXES = {
    "wander": FACINGS,
    "look_around": FACINGS,
    "wander_vertical": ("down", "up"),
    "wander_horizontal": ("left", "right"),
}


def parse_pauses(text):
    """``"0.5, 1, 2"`` -> ``(0.5, 1.0, 2.0)`` (an empty or bad list gives one second)."""
    values = []
    for part in str(text or "").replace(";", ",").split(","):
        try:
            value = float(part)
        except ValueError:
            continue
        if value >= 0:
            values.append(value)
    return tuple(values) or (1.0,)


@component_schema(
    type_name="asteria.GridMover2D",
    version=1,
    fields=(
        Field(
            "behaviour",
            str,
            "still",
            choices=GRID_BEHAVIOURS,
            tooltip="still, look_around, or wander one cell at a time (any axis, or one axis).",
        ),
        Field("facing", str, "down", choices=FACINGS, tooltip="The direction it faces now."),
        Field(
            "range_x",
            int,
            1,
            minimum=0,
            tooltip="Cells it may wander left or right of its start (0 = no limit).",
        ),
        Field(
            "range_y",
            int,
            1,
            minimum=0,
            tooltip="Cells it may wander up or down from its start (0 = no limit).",
        ),
        Field("grid_size", float, 16.0, minimum=1.0, tooltip="World units in one cell."),
        Field("walk_speed", float, 60.0, minimum=1.0, tooltip="World units walked a second."),
        Field(
            "pauses",
            str,
            "0.54, 1.07, 1.61, 2.14",
            tooltip="Seconds a pause between moves may last; one is picked at random.",
        ),
        Field(
            "face_player",
            bool,
            True,
            tooltip="Turn to face the player when the player talks to it.",
        ),
        Field(
            "look_facings",
            str,
            "",
            tooltip="The ways it turns between when it looks around ('down, right'; '' = all).",
        ),
    ),
)
class GridMover2DComponent(Component):
    def __init__(self):
        super().__init__()
        self.behaviour = "still"
        self.facing = "down"
        self.range_x = 1
        self.range_y = 1
        self.grid_size = 16.0
        self.walk_speed = 60.0
        self.pauses = "0.54, 1.07, 1.61, 2.14"
        self.face_player = True
        self.look_facings = ""


@component_schema(
    type_name="asteria.SightTrigger2D",
    version=1,
    fields=(
        Field(
            "range",
            int,
            3,
            minimum=0,
            tooltip="Cells it sees in the direction it faces (0 = it never notices anyone).",
        ),
        Field(
            "done_switch",
            str,
            "",
            tooltip="While this switch is on it no longer notices the player (beaten).",
        ),
        Field("music", str, "", tooltip="Music played when it notices the player."),
        Field("emote", str, "exclamation", tooltip="The mark shown over it when it notices."),
        Field("approach", bool, True, tooltip="It walks up to the player before its event."),
    ),
)
class SightTrigger2DComponent(Component):
    """A grid character that notices the player standing in front of it (within ``range``
    cells of a clear line, the way it faces): it shows its ``emote``, walks up and starts its
    own interaction event (a trainer's challenge). ``done_switch`` turns it off."""

    def __init__(self):
        super().__init__()
        self.range = 3
        self.done_switch = ""
        self.music = ""
        self.emote = "exclamation"
        self.approach = True


def line_of_sight(spec_range, facing, own_cell, target_cell, blocked):
    """The cells between ``own_cell`` and ``target_cell`` when the target stands in a clear
    line ahead (``facing``) within ``spec_range`` cells; None when it does not.
    ``blocked(cell)`` says whether a cell stops the look."""
    ox, oy = STEP.get(facing, (0, 1))
    dx, dy = target_cell[0] - own_cell[0], target_cell[1] - own_cell[1]
    distance = dx * ox + dy * oy
    if distance < 1 or distance > spec_range or (dx, dy) != (ox * distance, oy * distance):
        return None
    between = [(own_cell[0] + ox * n, own_cell[1] + oy * n) for n in range(1, distance)]
    if any(blocked(cell) for cell in between):
        return None
    return between


def _hold(holders, entity_id, mover, change=1):
    """Add (``change`` 1) or take away (-1) the cells ``mover`` stands on and steps into."""
    for cell in (mover.cell, mover.target):
        if cell is None:
            continue
        if change > 0:
            holders.setdefault(cell, []).append(entity_id)
        else:
            holders[cell].remove(entity_id)


@dataclass(slots=True)
class _Mover:
    home: tuple  # the cell it started on
    cell: tuple  # the cell it stands on (the one it left, while stepping)
    target: tuple | None = None  # the cell it is stepping into
    wait: float = 0.0


class GridMoverSystem:
    """Moves the scene's ``GridMover2DComponent`` entities.

    ``update(scene, dt, walls, reserved=())``: ``walls(x, y)`` says whether the cell centred at a
    point cannot be entered; ``reserved`` lists more cells (as ``(column, row)``) nobody may step
    into, such as the player's and the cell the player walks to.
    """

    def __init__(self, rng=None):
        self.rng = rng or random.Random(0)
        self.state = {}  # entity id -> _Mover

    @staticmethod
    def cell_of(spec, x, y):
        size = spec.grid_size
        return (int(x // size), int(y // size))

    def _mover(self, entity, spec, transform):
        mover = self.state.get(entity.id)
        if mover is None:
            cell = self.cell_of(spec, transform.x, transform.y)
            mover = self.state[entity.id] = _Mover(cell, cell)
            mover.wait = self.rng.choice(parse_pauses(spec.pauses))
        return mover

    def held_cells(self, exclude=None):
        """Every cell a mover stands on or steps into."""
        cells = set()
        for entity_id, mover in self.state.items():
            if entity_id == exclude:
                continue
            cells.add(mover.cell)
            if mover.target is not None:
                cells.add(mover.target)
        return cells

    def occupied(self, cell):
        return cell in self.held_cells()

    def face(self, entity, facing):
        spec = entity.try_get(GridMover2DComponent)
        if spec is not None and facing in STEP:
            spec.facing = facing

    def face_toward(self, entity, x, y):
        """Turn a mover that faces the player on a talk toward the point ``(x, y)``."""
        spec = entity.try_get(GridMover2DComponent)
        if spec is None or not spec.face_player or not entity.has(Transform):
            return
        t = entity.get(Transform)
        dx, dy = x - t.x, y - t.y
        if abs(dx) > abs(dy):
            spec.facing = "right" if dx > 0 else "left"
        elif dy:
            spec.facing = "down" if dy > 0 else "up"

    def update(self, scene, dt, walls, reserved=()):
        dt = max(0.0, float(dt))
        reserved = set(reserved)
        alive = set()
        # cell -> ids of the movers holding it (``held_cells`` once, not once per mover that
        # decides): made when first asked for, then kept current as movers step and choose
        holders = None
        for entity, spec, transform in scene.query(GridMover2DComponent, Transform):
            alive.add(entity.id)
            known = entity.id in self.state
            mover = self._mover(entity, spec, transform)
            if holders is not None and not known:
                _hold(holders, entity.id, mover)
            if mover.target is not None:
                if holders is not None:
                    _hold(holders, entity.id, mover, -1)
                self._walk(spec, mover, transform, dt)
                if holders is not None:
                    _hold(holders, entity.id, mover)
                continue
            if spec.behaviour == "still":
                continue
            mover.wait -= dt
            if mover.wait > 0:
                continue
            mover.wait = self.rng.choice(parse_pauses(spec.pauses))
            ways = AXES.get(spec.behaviour, FACINGS)
            if spec.behaviour == "look_around" and spec.look_facings:
                chosen = [f.strip() for f in spec.look_facings.split(",") if f.strip() in STEP]
                ways = tuple(chosen) or ways
            facing = self.rng.choice(ways)
            spec.facing = facing
            if spec.behaviour == "look_around":
                continue
            ox, oy = STEP[facing]
            cell = (mover.cell[0] + ox, mover.cell[1] + oy)
            if not self._inside(spec, mover, cell):
                continue
            size = spec.grid_size
            centre = (cell[0] * size + size / 2, cell[1] * size + size / 2)
            if cell in reserved:
                continue
            if holders is None:
                holders = {}
                for entity_id, held in self.state.items():
                    _hold(holders, entity_id, held)
            if any(owner != entity.id for owner in holders.get(cell, ())):
                continue
            if walls is not None and walls(*centre):
                continue
            mover.target = cell
            holders.setdefault(cell, []).append(entity.id)
        for entity_id in tuple(self.state):
            if entity_id not in alive:
                del self.state[entity_id]

    @staticmethod
    def _inside(spec, mover, cell):
        if spec.range_x and abs(cell[0] - mover.home[0]) > spec.range_x:
            return False
        if spec.range_y and abs(cell[1] - mover.home[1]) > spec.range_y:
            return False
        return True

    @staticmethod
    def _walk(spec, mover, transform, dt):
        size = spec.grid_size
        tx = mover.target[0] * size + size / 2
        ty = mover.target[1] * size + size / 2
        left = spec.walk_speed * dt
        dx, dy = tx - transform.x, ty - transform.y
        distance = abs(dx) + abs(dy)
        if distance <= left:
            transform.x, transform.y = tx, ty
            mover.cell, mover.target = mover.target, None
            return
        if dx:
            transform.x += left if dx > 0 else -left
        if dy:
            transform.y += left if dy > 0 else -left


__all__ = [
    "GRID_BEHAVIOURS",
    "GridMover2DComponent",
    "GridMoverSystem",
    "SightTrigger2DComponent",
    "line_of_sight",
    "parse_pauses",
]


# -- scripted routes ---------------------------------------------------------------------------
ROUTE_SPEEDS = {  # world units a second (a 16-unit cell in 16, 32, 8, 4 frames)
    "walk": 60.0,
    "walk_slow": 30.0,
    "walk_fast": 120.0,
    "walk_faster": 240.0,
    "run": 120.0,
    "ride": 120.0,
}
IN_PLACE = {"walk_in_place": 16, "walk_in_place_slow": 32, "walk_in_place_fast": 8,
            "walk_in_place_faster": 4}  # fmt: skip
FRAME = 1 / 59.7275


def parse_step(step):
    """``(kind, direction, amount)`` of a route step:

    * ``walk_<dir>`` / ``walk_slow_`` / ``walk_fast_`` / ``walk_faster_`` / ``run_<dir>`` - one
      cell at that pace (``("move", dir, speed)``);
    * ``face_<dir>`` - turn (``("face", dir, 0)``);
    * ``jump_<dir>`` / ``jump_2_<dir>`` - a hop of one or two cells (``("jump", dir, cells)``);
      ``jump_in_place_<dir>`` - a hop on the spot;
    * ``walk_in_place[_slow|_fast|_faster]_<dir>`` - steps on the spot facing that way;
    * ``delay:<seconds>``, ``emote:<key>``, ``hide``, ``show``, ``face_player``.
    """
    step = str(step).strip().lower()
    if step.startswith("delay:"):
        return ("delay", "", float(step.split(":", 1)[1]))
    if step.startswith("emote:"):
        return ("emote", step.split(":", 1)[1], 0.0)
    if step in ("hide", "show", "face_player"):
        return (step, "", 0.0)
    head, _, direction = step.rpartition("_")
    if direction not in STEP:
        raise ValueError(f"unknown route step: {step}")
    if head == "face":
        return ("face", direction, 0.0)
    if head == "jump":
        return ("jump", direction, 1.0)
    if head == "jump_2":
        return ("jump", direction, 2.0)
    if head == "jump_in_place":
        return ("jump", direction, 0.0)
    if head in IN_PLACE:
        return ("in_place", direction, IN_PLACE[head] * FRAME)
    if head in ROUTE_SPEEDS:
        return ("move", direction, ROUTE_SPEEDS[head])
    raise ValueError(f"unknown route step: {step}")


@dataclass(slots=True)
class _Route:
    steps: list
    current: tuple | None = None
    start: tuple = (0.0, 0.0)
    target: tuple = (0.0, 0.0)
    time: float = 0.0
    length: float = 0.0


class RouteRunner:
    """Scripted routes of grid characters (and the player): each entity walks its steps in
    order; ``done(entity_id)`` turns true when its route is over. ``update(dt, host)`` moves
    them: ``host`` answers ``transform(id)``, ``set_facing(id, dir)``, ``set_lift(id, h)``,
    ``set_hidden(id, bool)``, ``emote(id, key)`` and ``face_player(id)``."""

    JUMP_HEIGHT = 12.0

    def __init__(self):
        self.routes = {}

    def start(self, entity_id, steps):
        parsed = [parse_step(s) for s in steps]
        self.routes[str(entity_id)] = _Route(parsed)

    def done(self, entity_id=None):
        if entity_id is None:
            return not self.routes
        return str(entity_id) not in self.routes

    def update(self, dt, host):
        for entity_id in list(self.routes):
            route = self.routes[entity_id]
            left = dt
            while left > 0 and entity_id in self.routes:
                left = self._advance(entity_id, route, left, host)

    def _begin(self, entity_id, route, host):
        kind, direction, amount = route.steps.pop(0)
        transform = host.transform(entity_id)
        route.current, route.time = (kind, direction, amount), 0.0
        if transform is None:
            route.current = None
            return
        size = 16.0
        cx = int(transform.x // size) * size + size / 2
        cy = int(transform.y // size) * size + size / 2
        route.start = (cx, cy)
        ox, oy = STEP.get(direction, (0, 0))
        if kind in ("move", "jump", "in_place", "face"):
            host.set_facing(entity_id, direction)
        if kind == "move":
            route.target = (cx + ox * size, cy + oy * size)
            route.length = size / amount
        elif kind == "jump":
            cells = amount
            route.target = (cx + ox * size * cells, cy + oy * size * cells)
            route.length = (16 if cells <= 1 else 32) * FRAME * (2 if cells == 0 else 1)
        elif kind in ("in_place", "delay"):
            route.target = (cx, cy)
            route.length = amount
        else:
            route.length = 0.0
            if kind == "emote":
                host.emote(entity_id, direction)
            elif kind in ("hide", "show"):
                host.set_hidden(entity_id, kind == "hide")
            elif kind == "face_player":
                host.face_player(entity_id)

    def _advance(self, entity_id, route, dt, host):
        if route.current is None:
            if not route.steps:
                del self.routes[entity_id]
                return 0.0
            self._begin(entity_id, route, host)
            if route.current is None:
                return dt
        kind = route.current[0]
        spare = max(0.0, route.time + dt - route.length)
        route.time = min(route.length, route.time + dt)
        k = route.time / route.length if route.length else 1.0
        transform = host.transform(entity_id)
        if transform is not None and kind in ("move", "jump"):
            (x0, y0), (x1, y1) = route.start, route.target
            transform.x, transform.y = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
            if kind == "jump":
                from math import pi, sin

                host.set_lift(entity_id, self.JUMP_HEIGHT * sin(pi * k) if k < 1 else 0.0)
        if k >= 1.0:
            route.current = None
            return spare if spare > 0 else (dt if route.length == 0 else 0.0)
        return 0.0


@component_schema(
    type_name="asteria.SwitchVisibility2D",
    version=1,
    fields=(
        Field("hidden_switch", str, "", tooltip="The entity is gone while this switch is on."),
    ),
)
class SwitchVisibility2DComponent(Component):
    """Present only while ``hidden_switch`` is off (a person who has left, a truck moved
    away): events show or hide it by setting the switch."""

    def __init__(self):
        super().__init__()
        self.hidden_switch = ""


@component_schema(
    type_name="asteria.LookByVariable2D",
    version=1,
    fields=(
        Field("variable", str, "", tooltip="The event variable that picks the look."),
        Field(
            "looks",
            str,
            "",
            tooltip="value=sprite sheet|animations; ... (the look for each value).",
        ),
    ),
)
class LookByVariable2DComponent(Component):
    """A character whose picture follows an event variable (who the rival is): ``looks`` is
    ``"1=<sheet id>|<animation id>; 2=..."``."""

    def __init__(self):
        super().__init__()
        self.variable = ""
        self.looks = ""


def parse_looks(text):
    """``"1=a|b; 2=c|d"`` -> ``{"1": ("a", "b"), "2": ("c", "d")}``."""
    looks = {}
    for part in str(text or "").split(";"):
        value, _, look = part.partition("=")
        sheet, _, clips = look.partition("|")
        if value.strip() and sheet.strip():
            looks[value.strip()] = (sheet.strip(), clips.strip())
    return looks


@lru_cache(maxsize=256)
def _cached_looks(text):
    return MappingProxyType(parse_looks(text))


def looks_of(text):
    """``parse_looks`` of ``text``, read-only and parsed once per text (asked every frame)."""
    return _cached_looks(str(text or ""))
