"""Reference kernels in plain Python - always available; every other kernel set must match these."""

from __future__ import annotations

import math
from math import floor

NAME = "python"

# column order of a particle row
FIELDS = ("px", "py", "vx", "vy", "life", "max_life", "size_k", "angle", "spin")
# column order of a weather particle row
WEATHER_FIELDS = ("x", "y", "vy", "size", "phase")
# column order of a projectile row (turn = homing turn rate, radians per second; uid = caller's id)
PROJECTILE_FIELDS = ("x", "y", "vx", "vy", "gravity", "age", "life", "hw", "hh", "turn", "uid")


class ParticleStore:
    def __init__(self):
        self.px, self.py, self.vx, self.vy = [], [], [], []
        self.life, self.max_life, self.size_k, self.angle, self.spin = [], [], [], [], []

    def __len__(self):
        return len(self.px)

    def add(self, rows):
        """Append particles; each row holds the ``FIELDS`` values in order."""
        columns = [getattr(self, name) for name in FIELDS]
        for row in rows:
            for column, value in zip(columns, row, strict=True):
                column.append(value)

    def step(self, dt, gx, gy, keep):
        """Gravity, drag (``keep`` = velocity kept), motion, ageing and spin; drops expired particles."""
        px, py, vx, vy, life, angle, spin = self.px, self.py, self.vx, self.vy, self.life, self.angle, self.spin
        for i in range(len(px)):
            vx[i] = (vx[i] + gx * dt) * keep
            vy[i] = (vy[i] + gy * dt) * keep
            px[i] += vx[i] * dt
            py[i] += vy[i] * dt
            life[i] += dt
            angle[i] += spin[i] * dt
        alive = [i for i in range(len(px)) if life[i] < self.max_life[i]]
        if len(alive) != len(px):
            for name in FIELDS:
                values = getattr(self, name)
                setattr(self, name, [values[i] for i in alive])

    def shift(self, dx, dy):
        self.px = [p + dx for p in self.px]
        self.py = [p + dy for p in self.py]

    def views(self, size_from, size_to, color_from, color_to, scale):
        """``(x, y, size, (r, g, b, a), angle)`` per particle, interpolated over each particle's life."""
        s0, s1, c0, c1 = size_from, size_to, color_from, color_to
        out = []
        for i in range(len(self.px)):
            t = self.life[i] / self.max_life[i]
            size = (s0 + (s1 - s0) * t) * self.size_k[i] * scale
            color = tuple(int(c0[k] + (c1[k] - c0[k]) * t) for k in range(4))
            out.append((self.px[i], self.py[i], max(0.0, size), color, self.angle[i]))
        return out


class WeatherStore:
    """Screen-space weather particles (rain, snow, leaves, dust)."""

    def __init__(self):
        self.x, self.y, self.vy, self.size, self.phase = [], [], [], [], []

    def __len__(self):
        return len(self.x)

    def column(self, name):
        return list(getattr(self, name))

    def add(self, rows):
        columns = [getattr(self, name) for name in WEATHER_FIELDS]
        for row in rows:
            for column, value in zip(columns, row, strict=True):
                column.append(value)

    def set_row(self, index, row):
        for name, value in zip(WEATHER_FIELDS, row, strict=True):
            getattr(self, name)[index] = value

    def truncate(self, count):
        for name in WEATHER_FIELDS:
            del getattr(self, name)[count:]

    def step(self, dt, wind, time, sway, shift_x, shift_y, width, height):
        """Fall, wind, sway (``sway``: sideways sine drift) and camera shift. Returns ``(index, fell_out)`` for
        each particle that left the screen, in index order (``fell_out``: below the bottom edge)."""
        x, y, vy, phase = self.x, self.y, self.vy, self.phase
        left = []
        for i in range(len(x)):
            drift = math.sin(time * 1.7 + phase[i]) * 18.0 if sway else 0.0
            x[i] += (wind + drift) * dt + shift_x
            y[i] += vy[i] * dt + shift_y
            if y[i] > height + 20 or x[i] < -60 or x[i] > width + 60:
                left.append((i, y[i] > height + 20))
        return left

    def draw(self, pg, layer, kind, color, wind, time):
        """Draw every particle on ``layer`` (cleared first): rain as slanted lines, leaves as flapping
        ellipses, snow and dust as dots."""
        layer.fill((0, 0, 0, 0))
        if kind == "rain":
            slant = wind / 700.0
            for x, y, length in zip(self.x, self.y, self.size, strict=True):
                pg.draw.line(layer, color, (x, y), (x - slant * length * 3, y - length * 2), 1)
        elif kind == "leaves":
            for x, y, s, ph in zip(self.x, self.y, self.size, self.phase, strict=True):
                w = s * (0.5 + 0.5 * abs(math.sin(time * 3 + ph)))
                pg.draw.ellipse(layer, color, (x, y, max(1, w * 2), s))
        else:
            for x, y, s in zip(self.x, self.y, self.size, strict=True):
                pg.draw.circle(layer, color, (int(x), int(y)), int(s))


def aabb_pairs(x0, y0, x1, y1, cell_size=64.0):
    """Pairs ``(i, j)``, ``i < j``, whose boxes overlap or touch, sorted; a uniform grid finds the candidates."""
    if cell_size <= 0:
        raise ValueError("cell_size must be positive")
    cells = {}
    for i in range(len(x0)):
        for cx in range(floor(x0[i] / cell_size), floor(x1[i] / cell_size) + 1):
            for cy in range(floor(y0[i] / cell_size), floor(y1[i] / cell_size) + 1):
                cells.setdefault((cx, cy), []).append(i)
    pairs = set()
    for members in cells.values():
        for k, i in enumerate(members):
            for j in members[k + 1 :]:
                if x0[i] <= x1[j] and x0[j] <= x1[i] and y0[i] <= y1[j] and y0[j] <= y1[i]:
                    pairs.add((i, j) if i < j else (j, i))
    return sorted(pairs)


def aabb_cross_pairs(a, b, cell_size=64.0, touching=False):
    """Pairs ``(i, j)`` where box ``a[i]`` overlaps box ``b[j]``, sorted. Touching edges count only with
    ``touching``.

    ``a`` and ``b`` are ``(x0, y0, x1, y1)`` column tuples. A uniform grid over ``b`` finds the candidates.
    """
    if cell_size <= 0:
        raise ValueError("cell_size must be positive")
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    cells = {}
    for j in range(len(bx0)):
        for cx in range(floor(bx0[j] / cell_size), floor(bx1[j] / cell_size) + 1):
            for cy in range(floor(by0[j] / cell_size), floor(by1[j] / cell_size) + 1):
                cells.setdefault((cx, cy), []).append(j)
    pairs = set()
    for i in range(len(ax0)):
        for cx in range(floor(ax0[i] / cell_size), floor(ax1[i] / cell_size) + 1):
            for cy in range(floor(ay0[i] / cell_size), floor(ay1[i] / cell_size) + 1):
                for j in cells.get((cx, cy), ()):
                    if touching:
                        hit = ax0[i] <= bx1[j] and bx0[j] <= ax1[i] and ay0[i] <= by1[j] and by0[j] <= ay1[i]
                    else:
                        hit = ax0[i] < bx1[j] and bx0[j] < ax1[i] and ay0[i] < by1[j] and by0[j] < ay1[i]
                    if hit:
                        pairs.add((i, j))
    return sorted(pairs)


def _turn_cosines(turns, dt):
    """cos / sin of each distinct per-step turn angle, computed once with ``math`` (shared by every kernel set)."""
    return {t: (math.cos(t * dt), math.sin(t * dt)) for t in set(turns) if t > 0}


class ProjectileStore:
    """Projectile columns: homing, gravity, motion, ageing; boxes for hit tests."""

    def __init__(self):
        for name in PROJECTILE_FIELDS:
            setattr(self, name, [])

    def __len__(self):
        return len(self.x)

    def column(self, name):
        return list(getattr(self, name))

    def add(self, rows):
        """Append projectiles; each row holds the ``PROJECTILE_FIELDS`` values in order."""
        columns = [getattr(self, name) for name in PROJECTILE_FIELDS]
        for row in rows:
            for column, value in zip(columns, row, strict=True):
                column.append(float(value))

    def set_velocity(self, index, vx, vy):
        self.vx[index], self.vy[index] = float(vx), float(vy)

    def set_values(self, index, **values):
        """Overwrite named columns of one row (e.g. ``x``, ``y``, ``gravity``)."""
        for name, value in values.items():
            getattr(self, name)[index] = float(value)

    def keep(self, indices):
        """Keep only the rows at ``indices`` (ascending)."""
        for name in PROJECTILE_FIELDS:
            values = getattr(self, name)
            setattr(self, name, [values[i] for i in indices])

    def step(self, dt, target_x=None, target_y=None):
        """Homing toward ``target_x/y`` (``nan`` = no target; at most ``turn * dt`` per step, no trig on rows),
        then gravity, motion and ageing."""
        x, y, vx, vy = self.x, self.y, self.vx, self.vy
        if target_x is not None:
            rot = _turn_cosines(self.turn, dt)
            for i in range(len(x)):
                tx, ty, turn = target_x[i], target_y[i], self.turn[i]
                if turn <= 0 or tx != tx:
                    continue
                dx, dy = tx - x[i], ty - y[i]
                dist = math.sqrt(dx * dx + dy * dy)
                speed = math.sqrt(vx[i] * vx[i] + vy[i] * vy[i])
                if dist == 0.0 or speed == 0.0:
                    continue
                c, s = rot[turn]
                if (vx[i] * dx + vy[i] * dy) / (speed * dist) >= c:
                    vx[i], vy[i] = dx / dist * speed, dy / dist * speed  # within this step's turn: aim straight
                else:
                    s = s if vx[i] * dy - vy[i] * dx > 0 else -s
                    vx[i], vy[i] = vx[i] * c - vy[i] * s, vx[i] * s + vy[i] * c
        for i in range(len(x)):
            vy[i] += self.gravity[i] * dt
            x[i] += vx[i] * dt
            y[i] += vy[i] * dt
            self.age[i] += dt

    def boxes(self):
        x, y, hw, hh = self.x, self.y, self.hw, self.hh
        n = range(len(x))
        return (
            [x[i] - hw[i] for i in n],
            [y[i] - hh[i] for i in n],
            [x[i] + hw[i] for i in n],
            [y[i] + hh[i] for i in n],
        )

    def expired(self):
        return [i for i in range(len(self.x)) if self.age[i] >= self.life[i]]
