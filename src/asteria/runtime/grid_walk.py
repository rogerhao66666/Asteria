"""Grid walking for the field: the player moves a whole cell at a time, as in tile-based handheld
RPGs.

Standing still, a short press of a direction only turns the player to face it; holding it (or
pressing the direction already faced) starts a step to the next cell when that cell is free.
A step always ends on the centre of a cell, and the next direction is read only there, so the
player never stands between cells. Holding the run action steps at ``run_speed``.

A project turns it on with the playtest manifest's ``field.movement: "grid"`` and may set
``field.grid_size`` (16), ``field.walk_speed`` (60 world units a second: one 16-unit cell in
16 frames), ``field.run_speed`` (120), ``field.run_action`` ("run") and ``field.turn_time``
(seconds a press must last before a standing player walks instead of only turning, 0.1).

A ledge: when the cell ahead cannot be entered but ``ledge(x, y, facing)`` says it is a ledge
that may be jumped that way, the player hops over it to the cell beyond (when that one is free),
at walking pace, rising up to ``field.jump_height`` (12) world units; ``lift`` is the height
above the ground at the moment, for the view to draw the player raised.
"""

from __future__ import annotations

from math import pi, sin

FACING_STEP = {"down": (0, 1), "up": (0, -1), "left": (-1, 0), "right": (1, 0)}


class GridWalker:
    def __init__(self, settings=None):
        settings = dict(settings or {})
        self.size = float(settings.get("grid_size", 16.0))
        self.walk_speed = float(settings.get("walk_speed", 60.0))
        self.run_speed = float(settings.get("run_speed", 120.0))
        self.run_action = str(settings.get("run_action", "run"))
        self.turn_time = float(settings.get("turn_time", 0.1))
        self.jump_height = float(settings.get("jump_height", 12.0))
        self.jump = None  # (start x, start y, length) while hopping a ledge
        self.lift = 0.0  # height above the ground now (a ledge hop)
        self.target = None  # the cell centre being walked to
        self.held = 0.0  # how long the current direction has been held while standing
        self.held_direction = None
        self.pressed_facing = None  # the facing when that direction was first pressed

    def centre(self, x, y):
        """The centre of the cell holding ``(x, y)``."""
        size = self.size
        return (int(x // size) * size + size / 2, int(y // size) * size + size / 2)

    @staticmethod
    def direction(dx, dy):
        if not dx and not dy:
            return None
        if abs(dx) > abs(dy):
            return "right" if dx > 0 else "left"
        return "down" if dy > 0 else "up"

    def step(self, transform, facing, dx, dy, dt, blocked, *, running=False, ledge=None):
        """Advance by ``dt``; returns ``(facing, moving)``. ``blocked(x, y)`` says whether the
        cell centred at a point cannot be entered; ``ledge(x, y, facing)`` whether that cell is
        a ledge that may be jumped going ``facing``."""
        wanted = self.direction(dx, dy)
        if self.target is None:
            cx, cy = self.centre(transform.x, transform.y)
            transform.x, transform.y = cx, cy  # a player never rests between cells
            if wanted is None:
                self.held, self.held_direction, self.pressed_facing = 0.0, None, None
                return facing, False
            if wanted != self.held_direction:
                self.held_direction, self.held, self.pressed_facing = wanted, 0.0, facing
            else:
                self.held += dt
            if wanted != self.pressed_facing and self.held < self.turn_time:
                return wanted, False  # a press away from the facing: a tap turns on the spot
            ox, oy = FACING_STEP[wanted]
            tx, ty = cx + ox * self.size, cy + oy * self.size
            if blocked(tx, ty):
                beyond = (tx + ox * self.size, ty + oy * self.size)
                if ledge is None or not ledge(tx, ty, wanted) or blocked(*beyond):
                    return wanted, False  # walking into a wall: the player only faces it
                self.jump = (cx, cy, 2 * self.size)  # a ledge: hop over it
                tx, ty = beyond
            self.target = (tx, ty)
            facing = wanted
        speed = self.walk_speed if self.jump or not running else self.run_speed
        tx, ty = self.target
        left = speed * dt
        distance = abs(tx - transform.x) + abs(ty - transform.y)
        if distance <= left:
            transform.x, transform.y = tx, ty
            self.target = None
            self.lift = 0.0
            if self.jump is not None:  # landed: a hop always ends standing
                self.jump = None
                return facing, True
            # still holding a direction: carry the rest of this frame into the next step
            if wanted is not None:
                spare = (left - distance) / speed if speed else 0.0
                self.held = self.turn_time
                self.held_direction, self.pressed_facing = wanted, wanted
                if spare > 0:
                    return self.step(transform, facing, dx, dy, spare, blocked, running=running)
            return facing, True
        ox, oy = FACING_STEP[facing]
        transform.x += ox * left
        transform.y += oy * left
        if self.jump is not None:
            sx, sy, length = self.jump
            done = (abs(transform.x - sx) + abs(transform.y - sy)) / length
            self.lift = self.jump_height * sin(pi * min(1.0, done))
        return facing, True


__all__ = ["GridWalker", "FACING_STEP"]
