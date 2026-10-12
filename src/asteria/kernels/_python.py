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


def collider_columns(transform, collider, slots, circle):
    """World boxes of colliders from column storage: ``(cx, cy, half_w, half_h)`` lists for ``slots``.

    ``transform`` / ``collider`` map column names to slot-indexed arrays; ``circle[k]`` marks circle colliders.
    """
    tx, ty = transform["x"], transform["y"]
    ox, oy, w, h, r = (
        collider["offset_x"],
        collider["offset_y"],
        collider["width"],
        collider["height"],
        collider["radius"],
    )
    cx = [tx[s] + ox[s] for s in slots]
    cy = [ty[s] + oy[s] for s in slots]
    hw = [r[s] if c else w[s] / 2 for s, c in zip(slots, circle, strict=True)]
    hh = [r[s] if c else h[s] / 2 for s, c in zip(slots, circle, strict=True)]
    return cx, cy, hw, hh


# -- top-down character controllers on column storage (D22-C2) ------------------------------------------------------
def topdown_prepare(c, slots, dt):
    """Lock countdown, intent normalising and this step's move for top-down controllers.

    ``c`` maps controller column names to slot-indexed arrays. Locked controllers ignore intent (and jump). Returns
    ``(dx, dy, move_x, move_y, locked)`` lists: the normalised intent and ``(intent * speed + push) * dt``.
    """
    ix, iy, lock, jump = c["intent_x"], c["intent_y"], c["control_lock"], c["jump"]
    speed, override, px, py = c["speed"], c["speed_override"], c["push_x"], c["push_y"]
    out_dx, out_dy, out_mx, out_my, out_locked = [], [], [], [], []
    for s in slots:
        dx, dy = ix[s], iy[s]
        locked = lock[s] > 0.0
        if locked:
            remaining = lock[s] - dt
            lock[s] = 0.0 if remaining < 1e-9 else remaining  # float steps (30 x 1/60 is not exactly 0.5)
            dx = dy = 0.0
            jump[s] = 0
        mag = math.sqrt(dx * dx + dy * dy)
        if mag > 1.0:
            dx, dy = dx / mag, dy / mag
        out_dx.append(dx)
        out_dy.append(dy)
        v = override[s] if override[s] > 0.0 else speed[s]
        out_mx.append((dx * v + px[s]) * dt)
        out_my.append((dy * v + py[s]) * dt)
        out_locked.append(locked)
    return out_dx, out_dy, out_mx, out_my, out_locked


def moved_boxes(c, t, slots, move_x, move_y):
    """Boxes ``(x0, y0, x1, y1)`` of controllers at their position plus ``(move_x, move_y)``."""
    tx, ty, hw, hh = t["x"], t["y"], c["half_width"], c["half_height"]
    x = [tx[s] + mx for s, mx in zip(slots, move_x, strict=True)]
    y = [ty[s] + my for s, my in zip(slots, move_y, strict=True)]
    return (
        [v - hw[s] for v, s in zip(x, slots, strict=True)],
        [v - hh[s] for v, s in zip(y, slots, strict=True)],
        [v + hw[s] for v, s in zip(x, slots, strict=True)],
        [v + hh[s] for v, s in zip(y, slots, strict=True)],
    )


def add_to_column(column, slots, values):
    """``column[slot] += value`` for each pair."""
    for s, v in zip(slots, values, strict=True):
        column[s] += v


def _decay_factors(decays, dt):
    return {d: math.exp(-d * dt) for d in set(decays)}


def decay_push(c, slots, dt, epsilon):
    """Outside pushes fade by ``knockback_decay`` per second; slower than ``epsilon`` they stop."""
    px, py, decay = c["push_x"], c["push_y"], c["knockback_decay"]
    factors = _decay_factors([decay[s] for s in slots if px[s] or py[s]], dt)
    for s in slots:
        if not (px[s] or py[s]):
            continue
        keep = factors[decay[s]]
        x, y = px[s] * keep, py[s] * keep
        px[s] = 0.0 if abs(x) < epsilon else x
        py[s] = 0.0 if abs(y) < epsilon else y


def box_columns(t, b, slots, codes):
    """Hit / hurt boxes ``(x0, y0, x1, y1)`` from column storage, turned with the facing ``codes`` (0 down, 1 up,
    2 left, 3 right) where ``follow_facing`` is set: authored for facing right, mirrored left, a quarter turn
    down / up."""
    tx, ty = t["x"], t["y"]
    bx, by, bw, bh, follow = b["offset_x"], b["offset_y"], b["width"], b["height"], b["follow_facing"]
    x0, y0, x1, y1 = [], [], [], []
    for s, code in zip(slots, codes, strict=True):
        ox, oy, w, h = bx[s], by[s], bw[s], bh[s]
        if follow[s]:
            if code == 2:
                ox = -ox
            elif code == 0:
                ox, oy, w, h = -oy, ox, h, w
            elif code == 1:
                ox, oy, w, h = oy, -ox, h, w
        cx, cy = tx[s] + ox, ty[s] + oy
        x0.append(cx - w / 2)
        y0.append(cy - h / 2)
        x1.append(cx + w / 2)
        y1.append(cy + h / 2)
    return x0, y0, x1, y1


def blocked_rows(boxes, walls, pairs, mover_mask, mover_row, wall_bit, wall_one_way, wall_circle):
    """Movers (rows of ``boxes``) blocked by a wall among candidate ``pairs`` ``(mover, wall)``.

    A wall blocks unless it is the mover's own shape (``mover_row``), a one-way platform, outside the mover's layer
    mask, or a circle the box does not reach. ``walls`` = ``(cx, cy, radius)`` columns. Returns sorted mover rows.
    """
    x0, y0, x1, y1 = boxes
    cx, cy, radius = walls
    blocked = set()
    for i, j in pairs:
        if i in blocked or j == mover_row[i] or wall_one_way[j] or not (mover_mask[i] & wall_bit[j]):
            continue
        if wall_circle[j]:
            nx = min(max(cx[j], x0[i]), x1[i])
            ny = min(max(cy[j], y0[i]), y1[i])
            if math.sqrt((nx - cx[j]) * (nx - cx[j]) + (ny - cy[j]) * (ny - cy[j])) > radius[j]:
                continue
        blocked.add(i)
    return sorted(blocked)


def facing_codes(dx, dy, current, locked):
    """Top-down facing codes (0 down, 1 up, 2 left, 3 right) after moving by ``(dx, dy)``; standing still or
    locked keeps ``current``."""
    out = []
    for x, y, code, held in zip(dx, dy, current, locked, strict=True):
        if held:
            out.append(code)
        elif abs(x) >= abs(y) and x > 1e-9:
            out.append(3)
        elif abs(x) >= abs(y) and x < -1e-9:
            out.append(2)
        elif y > 1e-9:
            out.append(0)
        elif y < -1e-9:
            out.append(1)
        else:
            out.append(code)
    return out


# -- field AI on column storage (D22 A4) ---------------------------------------------------------------------------
# mode / behaviour codes: 0 idle, 1 patrol, 2 wander, 3 chase, 4 flee, 5 return
def fieldai_step(f, t, c, slots, behaviour, target_x, target_y, has_target, dt):
    """React (detect / lose the target) and steer chase, flee and return for AI entities with controllers.

    Writes ``f["mode_code"]`` and the controllers' intents; returns the rows (indexes into ``slots``) whose mode is
    patrol or wander, which the caller steers itself.
    """
    mode, hx, hy = f["mode_code"], f["home_x"], f["home_y"]
    detect, lose, arrive = f["detect_radius"], f["lose_radius"], f["arrive_distance"]
    x, y = t["x"], t["y"]
    ix, iy, speed = c["intent_x"], c["intent_y"], c["speed"]
    rest = []
    for k, s in enumerate(slots):
        ix[s] = iy[s] = 0.0
        b, m = behaviour[k], mode[s]
        if b in (3, 4) and has_target[k]:
            dxt, dyt = target_x[k] - x[s], target_y[k] - y[s]
            distance = math.sqrt(dxt * dxt + dyt * dyt)
            if m in (3, 4):
                if distance > lose[s]:
                    m = 5
            elif distance <= detect[s]:
                m = b
        if m in (3, 4) and not has_target[k]:
            m = 5  # the target is gone: go home
        if m in (3, 4, 5):
            away = m == 4
            gx, gy = (hx[s], hy[s]) if m == 5 else (target_x[k], target_y[k])
            dx, dy = gx - x[s], gy - y[s]
            if away:
                dx, dy = -dx, -dy
            d = math.sqrt(dx * dx + dy * dy)
            if d <= (0.0 if away else arrive[s]):
                if m == 5:
                    m = 0
            else:
                scale = 1.0 if away else min(1.0, d / max(speed[s] * dt, 1e-9))
                ix[s] = dx / d * scale
                iy[s] = dy / d * scale
        elif b in (1, 2):
            m = b
            rest.append(k)
        else:
            m = 0
        mode[s] = m
    return rest
