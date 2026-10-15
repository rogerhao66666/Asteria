"""Grid pathfinding (Godot's navigation, for tile and top-down maps).

``NavGrid`` lays a grid over a rectangle of the world; a cell is blocked when ``blocked(x, y)``
(tiles, solid colliders, restricted areas...) is true at its centre. ``find_path`` is A* with an
octile distance that never cuts a blocked corner and returns smoothed world waypoints.
``PathFollower`` walks an entity along a path.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from math import floor, hypot, sqrt

_STRAIGHT = ((1, 0), (-1, 0), (0, 1), (0, -1))
_DIAGONAL = ((1, 1), (1, -1), (-1, 1), (-1, -1))
ROOT2 = sqrt(2.0)


@dataclass(frozen=True, slots=True)
class NavBounds:
    x0: float
    y0: float
    x1: float
    y1: float


class NavGrid:
    def __init__(self, bounds, cell_size, blocked, *, diagonal=True, margin=0.0):
        if not cell_size > 0:
            raise ValueError("cell_size must be positive")
        self.bounds = NavBounds(*(float(v) for v in bounds))
        if self.bounds.x1 <= self.bounds.x0 or self.bounds.y1 <= self.bounds.y0:
            raise ValueError("bounds must have a positive size")
        self.cell = float(cell_size)
        self.diagonal = bool(diagonal)
        self._blocked = blocked
        self.margin = max(0.0, float(margin))  # an agent's radius: the cell edges are probed too
        self.columns = max(1, int(-(-(self.bounds.x1 - self.bounds.x0) // self.cell)))
        self.rows = max(1, int(-(-(self.bounds.y1 - self.bounds.y0) // self.cell)))
        self._cache = {}

    # -- cells ---------------------------------------------------------------------------------
    def cell_of(self, x, y):
        return (
            floor((x - self.bounds.x0) / self.cell),
            floor((y - self.bounds.y0) / self.cell),
        )

    def center(self, cx, cy):
        return (
            self.bounds.x0 + (cx + 0.5) * self.cell,
            self.bounds.y0 + (cy + 0.5) * self.cell,
        )

    def inside(self, cx, cy):
        return 0 <= cx < self.columns and 0 <= cy < self.rows

    def _clamp(self, cell):
        return (min(max(cell[0], 0), self.columns - 1), min(max(cell[1], 0), self.rows - 1))

    def is_blocked(self, cx, cy, extra=()):
        if not self.inside(cx, cy) or (cx, cy) in extra:
            return True
        key = (cx, cy)
        value = self._cache.get(key)
        if value is None:
            x, y = self.center(cx, cy)
            probes = [(x, y)]
            if self.margin:
                m = min(self.margin, self.cell / 2)
                probes += [(x - m, y), (x + m, y), (x, y - m), (x, y + m)]
            value = self._cache[key] = any(self._blocked(px, py) for px, py in probes)
        return value

    def clear_cache(self):
        """Forget what was learned about blocked cells (call after the world changed)."""
        self._cache.clear()

    def nearest_free(self, cx, cy, extra=(), radius=8):
        """The free cell closest to ``(cx, cy)`` within ``radius`` cells, or ``None``."""
        if not self.is_blocked(cx, cy, extra):
            return (cx, cy)
        best, best_distance = None, None
        for ring in range(1, radius + 1):
            for dx in range(-ring, ring + 1):
                for dy in range(-ring, ring + 1):
                    if max(abs(dx), abs(dy)) != ring or self.is_blocked(cx + dx, cy + dy, extra):
                        continue
                    distance = hypot(dx, dy)
                    if best_distance is None or distance < best_distance:
                        best, best_distance = (cx + dx, cy + dy), distance
            if best is not None:
                return best
        return None

    # -- search --------------------------------------------------------------------------------
    def find_path(self, start, goal, *, extra_blocked=(), max_nodes=20000, snap_goal=True):
        """World waypoints from ``start`` to ``goal`` (both ``(x, y)``), or ``None`` if there is no
        way. A blocked goal is moved to the nearest free cell when ``snap_goal``."""
        extra = frozenset(extra_blocked)
        begin = self.nearest_free(*self._clamp(self.cell_of(*start)), extra, radius=2)
        target = self.cell_of(*goal)
        if snap_goal:
            target = self.nearest_free(*self._clamp(target), extra)  # off the map: nearest edge
        elif self.is_blocked(*target, extra):
            target = None
        if begin is None or target is None:
            return None
        if begin == target:
            return [self._point(begin, target, goal)]
        cells = self._astar(begin, target, extra, max_nodes)
        if cells is None:
            return None
        cells = self._smooth(cells, extra)
        points = [self.center(*c) for c in cells[1:]]
        points[-1] = self._point(cells[-1], target, goal)
        return points

    def _point(self, cell, target, goal):
        """The final waypoint: the exact goal when its own cell is free, else the cell centre."""
        if self.cell_of(*goal) == cell:
            return (float(goal[0]), float(goal[1]))
        return self.center(*cell)

    def _heuristic(self, a, b):
        dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
        return (dx + dy) + (ROOT2 - 2.0) * min(dx, dy)

    def _neighbours(self, cell, extra):
        cx, cy = cell
        for dx, dy in _STRAIGHT:
            if not self.is_blocked(cx + dx, cy + dy, extra):
                yield (cx + dx, cy + dy), 1.0
        if self.diagonal:
            for dx, dy in _DIAGONAL:
                if self.is_blocked(cx + dx, cy + dy, extra):
                    continue
                if self.is_blocked(cx + dx, cy, extra) or self.is_blocked(cx, cy + dy, extra):
                    continue  # no cutting a blocked corner
                yield (cx + dx, cy + dy), ROOT2

    def _astar(self, begin, target, extra, max_nodes):
        open_heap = [(self._heuristic(begin, target), 0, begin)]
        cost, came, closed, serial = {begin: 0.0}, {}, set(), 0
        while open_heap and len(closed) < max_nodes:
            _, _, cell = heapq.heappop(open_heap)
            if cell in closed:
                continue
            if cell == target:
                path = [cell]
                while cell in came:
                    cell = came[cell]
                    path.append(cell)
                return path[::-1]
            closed.add(cell)
            for neighbour, step in self._neighbours(cell, extra):
                new_cost = cost[cell] + step
                if neighbour in closed or new_cost >= cost.get(neighbour, float("inf")):
                    continue
                cost[neighbour], came[neighbour] = new_cost, cell
                serial += 1
                heapq.heappush(
                    open_heap, (new_cost + self._heuristic(neighbour, target), serial, neighbour)
                )
        return None

    def line_clear(self, a, b, extra=()):
        """True when the straight run between two cells crosses no blocked cell."""
        (x0, y0), (x1, y1) = a, b
        steps = max(abs(x1 - x0), abs(y1 - y0), 1) * 2
        for i in range(steps + 1):
            t = i / steps
            cx, cy = floor(x0 + 0.5 + (x1 - x0) * t), floor(y0 + 0.5 + (y1 - y0) * t)
            if self.is_blocked(cx, cy, extra):
                return False
        return True

    def _smooth(self, cells, extra):
        """Drop waypoints that a straight, clear line makes unnecessary."""
        if len(cells) < 3:
            return cells
        result, anchor = [cells[0]], 0
        for i in range(2, len(cells)):
            if not self.line_clear(cells[anchor], cells[i], extra):
                anchor = i - 1
                result.append(cells[anchor])
        result.append(cells[-1])
        return result


class PathFollower:
    """Moves a point along waypoints at ``speed``; ``step`` returns the new position."""

    def __init__(self, waypoints, speed):
        if not speed > 0:
            raise ValueError("speed must be positive")
        self.waypoints = list(waypoints)
        self.speed = float(speed)

    @property
    def done(self):
        return not self.waypoints

    def step(self, x, y, dt):
        remaining = self.speed * max(0.0, float(dt))
        while self.waypoints and remaining > 0:
            tx, ty = self.waypoints[0]
            distance = hypot(tx - x, ty - y)
            if distance <= remaining:
                x, y = tx, ty
                remaining -= distance
                self.waypoints.pop(0)
            else:
                x += (tx - x) / distance * remaining
                y += (ty - y) / distance * remaining
                remaining = 0.0
        return x, y
