"""numpy kernels - the reference arithmetic on whole arrays (same operations, same order, same
results)."""

from __future__ import annotations

import math

import numpy as np

from asteria.kernels._python import (
    FIELDS,
    PROJECTILE_FIELDS,
    WEATHER_FIELDS,
    _decay_factors,
    _turn_cosines,
)

NAME = "numpy"


class ParticleStore:
    def __init__(self):
        self._data = np.empty((len(FIELDS), 0))

    def __len__(self):
        return self._data.shape[1]

    def add(self, rows):
        rows = list(rows)
        if rows:
            self._data = np.concatenate((self._data, np.array(rows, dtype=float).T), axis=1)

    def step(self, dt, gx, gy, keep):
        px, py, vx, vy, life, max_life, _size_k, angle, spin = self._data
        vx += gx * dt
        vx *= keep
        vy += gy * dt
        vy *= keep
        px += vx * dt
        py += vy * dt
        life += dt
        angle += spin * dt
        alive = life < max_life
        if not alive.all():
            self._data = self._data[:, alive]

    def shift(self, dx, dy):
        self._data[0] += dx
        self._data[1] += dy

    def views(self, size_from, size_to, color_from, color_to, scale):
        px, py, _vx, _vy, life, max_life, size_k, angle, _spin = self._data
        t = life / max_life
        size = np.maximum((size_from + (size_to - size_from) * t) * size_k * scale, 0.0)
        c0 = np.asarray(color_from, dtype=float)
        c1 = np.asarray(color_to, dtype=float)
        colors = map(tuple, (c0 + (c1 - c0) * t[:, None]).astype(np.int64).tolist())
        return list(
            zip(px.tolist(), py.tolist(), size.tolist(), colors, angle.tolist(), strict=True)
        )


class WeatherStore:
    """Weather particles as arrays. Drawing stamps each particle's shape: pygame truncates
    coordinates to whole
    pixels, so a line, ellipse or dot depends only on whole-pixel sizes - each distinct shape is
    drawn once by
    pygame itself and then copied to every particle that has it, giving the reference's pixels."""

    def __init__(self):
        self._data = np.empty((len(WEATHER_FIELDS), 0))
        self._stamps = {}

    def __len__(self):
        return self._data.shape[1]

    def column(self, name):
        return self._data[WEATHER_FIELDS.index(name)].tolist()

    def add(self, rows):
        rows = list(rows)
        if rows:
            self._data = np.concatenate((self._data, np.array(rows, dtype=float).T), axis=1)

    def set_row(self, index, row):
        self._data[:, index] = row

    def truncate(self, count):
        self._data = self._data[:, :count]

    def step(self, dt, wind, time, sway, shift_x, shift_y, width, height):
        x, y, vy, _size, phase = self._data
        drift = np.sin(time * 1.7 + phase) * 18.0 if sway else 0.0
        x += (wind + drift) * dt + shift_x
        y += vy * dt + shift_y
        fell = y > height + 20
        left = np.flatnonzero(fell | (x < -60) | (x > width + 60))
        return list(zip(left.tolist(), fell[left].tolist(), strict=True))

    def _stamp(self, pg, kind, key):
        stamp = self._stamps.get((kind, key))
        if stamp is None:
            pad = max(abs(key[0]), abs(key[1])) + 4
            surface = pg.Surface((pad * 2 + 1, pad * 2 + 1), pg.SRCALPHA)
            surface.fill((0, 0, 0, 0))
            white = (255, 255, 255, 255)
            if kind == "rain":
                pg.draw.line(surface, white, (pad, pad), (pad + key[0], pad + key[1]), 1)
            elif kind == "leaves":
                pg.draw.ellipse(surface, white, (pad, pad, key[0], key[1]))
            else:
                pg.draw.circle(surface, white, (pad, pad), key[0])
            dx, dy = np.nonzero(pg.surfarray.array_alpha(surface))
            stamp = self._stamps[(kind, key)] = (dx - pad, dy - pad)
        return stamp

    def draw(self, pg, layer, kind, color, wind, time):
        x, y, _vy, size, phase = self._data
        layer.fill((*color[:3], 0))
        if not len(self):
            return
        ax, ay = np.trunc(x).astype(np.int64), np.trunc(y).astype(np.int64)
        if kind == "rain":
            slant = wind / 700.0
            k0 = np.trunc(x - slant * size * 3).astype(np.int64) - ax
            k1 = np.trunc(y - size * 2).astype(np.int64) - ay
        elif kind == "leaves":
            w = size * (0.5 + 0.5 * np.abs(np.sin(time * 3 + phase)))
            k0 = np.trunc(np.maximum(1, w * 2)).astype(np.int64)
            k1 = np.trunc(size).astype(np.int64)
        else:
            k0 = np.trunc(size).astype(np.int64)
            k1 = np.zeros_like(k0)
        # group particles by shape: one sort of a packed (k0, k1) key
        packed = (k0 + (1 << 20)) * (1 << 21) + (k1 + (1 << 20))
        order = np.argsort(packed)
        ranked = packed[order]
        starts = np.flatnonzero(np.diff(ranked)) + 1
        xs, ys = [], []
        for members in np.split(order, starts):
            first = members[0]
            dx, dy = self._stamp(pg, kind, (int(k0[first]), int(k1[first])))
            xs.append((ax[members][:, None] + dx[None, :]).ravel())
            ys.append((ay[members][:, None] + dy[None, :]).ravel())
        px, py = np.concatenate(xs), np.concatenate(ys)
        width, height = layer.get_size()
        inside = (px >= 0) & (px < width) & (py >= 0) & (py < height)
        alpha = pg.surfarray.pixels_alpha(layer)
        alpha[px[inside], py[inside]] = color[3]
        del alpha  # unlock the surface


def aabb_pairs(x0, y0, x1, y1, cell_size=64.0):
    """Same pairs as the reference, found by sort-and-sweep along the wider axis (``cell_size`` is
    unused)."""
    if cell_size <= 0:
        raise ValueError("cell_size must be positive")
    n = len(x0)
    if n < 2:
        return []
    a0, a1 = np.asarray(x0, dtype=float), np.asarray(x1, dtype=float)
    b0, b1 = np.asarray(y0, dtype=float), np.asarray(y1, dtype=float)
    if a1.max() - a0.min() < b1.max() - b0.min():
        a0, a1, b0, b1 = b0, b1, a0, a1
    order = np.argsort(a0, kind="stable")
    start = np.arange(1, n + 1)
    # boxes after i in sweep order that start before i ends overlap it on the sweep axis
    counts = np.maximum(np.searchsorted(a0[order], a1[order], side="right") - start, 0)
    total = int(counts.sum())
    if not total:
        return []
    first = np.repeat(np.arange(n), counts)
    second = first + 1 + np.arange(total) - np.repeat(np.cumsum(counts) - counts, counts)
    i, j = order[first], order[second]
    hit = (b0[i] <= b1[j]) & (b0[j] <= b1[i])
    lo, hi = np.minimum(i[hit], j[hit]), np.maximum(i[hit], j[hit])
    ranked = np.lexsort((hi, lo))
    return list(zip(lo[ranked].tolist(), hi[ranked].tolist(), strict=True))


def _cells(x0, y0, x1, y1, cell_size):
    """(row, cell key) for every grid cell each box covers."""
    cx0, cx1 = np.floor(x0 / cell_size).astype(np.int64), np.floor(x1 / cell_size).astype(np.int64)
    cy0, cy1 = np.floor(y0 / cell_size).astype(np.int64), np.floor(y1 / cell_size).astype(np.int64)
    w, h = cx1 - cx0 + 1, cy1 - cy0 + 1
    counts = w * h
    row = np.repeat(np.arange(len(x0)), counts)
    k = np.arange(int(counts.sum())) - np.repeat(np.cumsum(counts) - counts, counts)
    cx = cx0[row] + k % w[row]
    cy = cy0[row] + k // w[row]
    return row, (cx << 32) ^ (cy & 0xFFFFFFFF)


def aabb_cross_pairs(a, b, cell_size=64.0, touching=False):
    """Same pairs as the reference: a grid join (cells of ``a`` matched to sorted cells of
    ``b``)."""
    if cell_size <= 0:
        raise ValueError("cell_size must be positive")
    ax0, ay0, ax1, ay1 = (np.asarray(v, dtype=float) for v in a)
    bx0, by0, bx1, by1 = (np.asarray(v, dtype=float) for v in b)
    if not len(ax0) or not len(bx0):
        return []
    a_row, a_key = _cells(ax0, ay0, ax1, ay1, cell_size)
    b_row, b_key = _cells(bx0, by0, bx1, by1, cell_size)
    order = np.argsort(b_key, kind="stable")
    b_row, b_key = b_row[order], b_key[order]
    lo = np.searchsorted(b_key, a_key, side="left")
    counts = np.searchsorted(b_key, a_key, side="right") - lo
    total = int(counts.sum())
    if not total:
        return []
    i = np.repeat(a_row, counts)
    j = b_row[
        np.repeat(lo, counts) + np.arange(total) - np.repeat(np.cumsum(counts) - counts, counts)
    ]
    if touching:
        hit = (ax0[i] <= bx1[j]) & (bx0[j] <= ax1[i]) & (ay0[i] <= by1[j]) & (by0[j] <= ay1[i])
    else:
        hit = (ax0[i] < bx1[j]) & (bx0[j] < ax1[i]) & (ay0[i] < by1[j]) & (by0[j] < ay1[i])
    code = np.unique(i[hit] * len(bx0) + j[hit])
    return list(zip((code // len(bx0)).tolist(), (code % len(bx0)).tolist(), strict=True))


class ProjectileStore:
    _INDEX = {name: k for k, name in enumerate(PROJECTILE_FIELDS)}

    def __init__(self):
        self._data = np.empty((len(PROJECTILE_FIELDS), 0))

    def __len__(self):
        return self._data.shape[1]

    def column(self, name):
        return self._data[self._INDEX[name]].tolist()

    def add(self, rows):
        rows = list(rows)
        if rows:
            self._data = np.concatenate((self._data, np.array(rows, dtype=float).T), axis=1)

    def set_velocity(self, index, vx, vy):
        self._data[2, index], self._data[3, index] = float(vx), float(vy)

    def set_values(self, index, **values):
        for name, value in values.items():
            self._data[self._INDEX[name], index] = float(value)

    def keep(self, indices):
        self._data = self._data[:, np.asarray(indices, dtype=np.int64)]

    def step(self, dt, target_x=None, target_y=None):
        x, y, vx, vy, gravity, age, _life, _hw, _hh, turn, _uid = self._data
        if target_x is not None and len(x):
            tx, ty = np.asarray(target_x, dtype=float), np.asarray(target_y, dtype=float)
            rot = _turn_cosines(turn.tolist(), dt)
            c = np.ones_like(turn)
            s = np.zeros_like(turn)
            for t, (ct, st) in rot.items():
                c[turn == t], s[turn == t] = ct, st
            dx, dy = tx - x, ty - y
            dist = np.sqrt(dx * dx + dy * dy)
            speed = np.sqrt(vx * vx + vy * vy)
            live = (turn > 0) & (tx == tx) & (dist != 0.0) & (speed != 0.0)
            with np.errstate(divide="ignore", invalid="ignore"):
                aim = live & ((vx * dx + vy * dy) / (speed * dist) >= c)
                aim_vx, aim_vy = dx / dist * speed, dy / dist * speed
            turning = live & ~aim
            s = np.where(vx * dy - vy * dx > 0, s, -s)
            rot_vx, rot_vy = vx * c - vy * s, vx * s + vy * c
            new_vx = np.where(aim, aim_vx, np.where(turning, rot_vx, vx))
            new_vy = np.where(aim, aim_vy, np.where(turning, rot_vy, vy))
            vx[:], vy[:] = new_vx, new_vy
        vy += gravity * dt
        x += vx * dt
        y += vy * dt
        age += dt

    def boxes(self):
        x, y, hw, hh = self._data[0], self._data[1], self._data[7], self._data[8]
        return (x - hw, y - hh, x + hw, y + hh)

    def expired(self):
        return np.flatnonzero(self._data[5] >= self._data[6]).tolist()


_DTYPES = {"d": np.float64, "q": np.int64, "b": np.int8}


def _view(column):
    """Zero-copy (writable) numpy view of an ``array.array`` column."""
    return np.frombuffer(column, dtype=_DTYPES[column.typecode])


def collider_columns(transform, collider, slots, circle):
    if not len(slots):
        return [], [], [], []
    idx = np.asarray(slots, dtype=np.int64)
    flag = np.asarray(circle, dtype=bool)
    cx = _view(transform["x"])[idx] + _view(collider["offset_x"])[idx]
    cy = _view(transform["y"])[idx] + _view(collider["offset_y"])[idx]
    r = _view(collider["radius"])[idx]
    hw = np.where(flag, r, _view(collider["width"])[idx] / 2)
    hh = np.where(flag, r, _view(collider["height"])[idx] / 2)
    return cx.tolist(), cy.tolist(), hw.tolist(), hh.tolist()


def topdown_prepare(c, slots, dt):
    idx = np.asarray(slots, dtype=np.int64)
    if not len(idx):
        return [], [], [], [], []
    lock = _view(c["control_lock"])
    dx = _view(c["intent_x"])[idx].copy()
    dy = _view(c["intent_y"])[idx].copy()
    held = lock[idx]
    locked = held > 0.0
    remaining = held - dt
    lock[idx] = np.where(locked, np.where(remaining < 1e-9, 0.0, remaining), held)
    dx[locked] = 0.0
    dy[locked] = 0.0
    jump = _view(c["jump"])
    jump[idx[locked]] = 0
    mag = np.sqrt(dx * dx + dy * dy)
    big = mag > 1.0
    dx[big] /= mag[big]
    dy[big] /= mag[big]
    override = _view(c["speed_override"])[idx]
    speed = np.where(override > 0.0, override, _view(c["speed"])[idx])
    mx = (dx * speed + _view(c["push_x"])[idx]) * dt
    my = (dy * speed + _view(c["push_y"])[idx]) * dt
    return dx.tolist(), dy.tolist(), mx.tolist(), my.tolist(), locked.tolist()


def moved_boxes(c, t, slots, move_x, move_y):
    idx = np.asarray(slots, dtype=np.int64)
    x = _view(t["x"])[idx] + np.asarray(move_x, dtype=float)
    y = _view(t["y"])[idx] + np.asarray(move_y, dtype=float)
    hw, hh = _view(c["half_width"])[idx], _view(c["half_height"])[idx]
    return (x - hw, y - hh, x + hw, y + hh)


def add_to_column(column, slots, values):
    if len(slots):
        view = _view(column)
        idx = np.asarray(slots, dtype=np.int64)
        view[idx] = view[idx] + np.asarray(values, dtype=float)


def decay_push(c, slots, dt, epsilon):
    idx = np.asarray(slots, dtype=np.int64)
    if not len(idx):
        return
    px, py, decay = _view(c["push_x"]), _view(c["push_y"]), _view(c["knockback_decay"])
    x, y = px[idx], py[idx]
    moving = (x != 0.0) | (y != 0.0)
    if not moving.any():
        return
    idx, x, y = idx[moving], x[moving], y[moving]
    d = decay[idx]
    factors = _decay_factors(d.tolist(), dt)
    keep = np.empty_like(d)
    for value, factor in factors.items():
        keep[d == value] = factor
    x, y = x * keep, y * keep
    px[idx] = np.where(np.abs(x) < epsilon, 0.0, x)
    py[idx] = np.where(np.abs(y) < epsilon, 0.0, y)


def box_columns(t, b, slots, codes):
    if not len(slots):
        return [], [], [], []
    idx = np.asarray(slots, dtype=np.int64)
    code = np.asarray(codes, dtype=np.int64)
    ox, oy = _view(b["offset_x"])[idx], _view(b["offset_y"])[idx]
    w, h = _view(b["width"])[idx], _view(b["height"])[idx]
    follow = _view(b["follow_facing"])[idx] != 0
    left, down, up = follow & (code == 2), follow & (code == 0), follow & (code == 1)
    turned = down | up
    nox = np.where(left, -ox, np.where(down, -oy, np.where(up, oy, ox)))
    noy = np.where(down, ox, np.where(up, -ox, oy))
    nw, nh = np.where(turned, h, w), np.where(turned, w, h)
    cx, cy = _view(t["x"])[idx] + nox, _view(t["y"])[idx] + noy
    return (
        (cx - nw / 2).tolist(),
        (cy - nh / 2).tolist(),
        (cx + nw / 2).tolist(),
        (cy + nh / 2).tolist(),
    )


def blocked_rows(boxes, walls, pairs, mover_mask, mover_row, wall_bit, wall_one_way, wall_circle):
    if not len(pairs):
        return []
    p = np.asarray(pairs, dtype=np.int64)
    i, j = p[:, 0], p[:, 1]
    x0, y0, x1, y1 = (np.asarray(c, dtype=float) for c in boxes)
    cx, cy, radius = (np.asarray(c, dtype=float) for c in walls)
    ok = (j != np.asarray(mover_row, dtype=np.int64)[i]) & ~np.asarray(wall_one_way, dtype=bool)[j]
    ok &= (
        np.asarray(mover_mask, dtype=np.int64)[i] & np.asarray(wall_bit, dtype=np.int64)[j]
    ) != 0
    circle = np.asarray(wall_circle, dtype=bool)[j]
    if circle.any():
        nx = np.minimum(np.maximum(cx[j], x0[i]), x1[i])
        ny = np.minimum(np.maximum(cy[j], y0[i]), y1[i])
        far = np.sqrt((nx - cx[j]) * (nx - cx[j]) + (ny - cy[j]) * (ny - cy[j])) > radius[j]
        ok &= ~(circle & far)
    return np.unique(i[ok]).tolist()


def blocked_boxes(
    boxes, solids, walls, cell_size, mover_mask, mover_row, wall_bit, wall_one_way, wall_circle
):
    pairs = aabb_cross_pairs(boxes, solids, cell_size, touching=True)
    if not len(pairs):
        return []
    return blocked_rows(
        boxes, walls, pairs, mover_mask, mover_row, wall_bit, wall_one_way, wall_circle
    )


def facing_codes(dx, dy, current, locked):
    x, y = np.asarray(dx, dtype=float), np.asarray(dy, dtype=float)
    code = np.asarray(current, dtype=np.int64)
    horizontal = np.abs(x) >= np.abs(y)
    out = np.where(
        horizontal & (x > 1e-9),
        3,
        np.where(horizontal & (x < -1e-9), 2, np.where(y > 1e-9, 0, np.where(y < -1e-9, 1, code))),
    )
    return np.where(np.asarray(locked, dtype=bool), code, out).tolist()


def fieldai_step(f, t, c, slots, behaviour, target_x, target_y, has_target, dt):
    if not len(slots):
        return []
    idx = np.asarray(slots, dtype=np.int64)
    mode_col = _view(f["mode_code"])
    m = mode_col[idx].copy()
    b = np.asarray(behaviour, dtype=np.int64)
    tx, ty = np.asarray(target_x, dtype=float), np.asarray(target_y, dtype=float)
    has = np.asarray(has_target, dtype=bool)
    x, y = _view(t["x"])[idx], _view(t["y"])[idx]
    detect, lose = _view(f["detect_radius"])[idx], _view(f["lose_radius"])[idx]
    arrive, speed = _view(f["arrive_distance"])[idx], _view(c["speed"])[idx]
    hx, hy = _view(f["home_x"])[idx], _view(f["home_y"])[idx]
    with np.errstate(invalid="ignore"):
        dxt, dyt = tx - x, ty - y
        distance = np.sqrt(dxt * dxt + dyt * dyt)
    reacting = ((b == 3) | (b == 4)) & has
    busy = (m == 3) | (m == 4)
    m = np.where(reacting & busy & (distance > lose), 5, m)
    m = np.where(reacting & ~busy & (distance <= detect), b, m)
    m = np.where(((m == 3) | (m == 4)) & ~has, 5, m)
    steer = (m == 3) | (m == 4) | (m == 5)
    away = m == 4
    gx, gy = np.where(m == 5, hx, tx), np.where(m == 5, hy, ty)
    with np.errstate(invalid="ignore", divide="ignore"):
        dx, dy = gx - x, gy - y
        dx, dy = np.where(away, -dx, dx), np.where(away, -dy, dy)
        d = np.sqrt(dx * dx + dy * dy)
        arrived = d <= np.where(away, 0.0, arrive)
        scale = np.where(away, 1.0, np.minimum(1.0, d / np.maximum(speed * dt, 1e-9)))
        move = steer & ~arrived
        ix = np.where(move, dx / d * scale, 0.0)
        iy = np.where(move, dy / d * scale, 0.0)
    m = np.where(steer & arrived & (m == 5), 0, m)
    wanders = ~steer & ((b == 1) | (b == 2))
    m = np.where(wanders, b, np.where(steer, m, 0))
    mode_col[idx] = m
    _view(c["intent_x"])[idx] = ix
    _view(c["intent_y"])[idx] = iy
    return np.flatnonzero(wanders).tolist()


def _hypot(a, b):
    """``math.hypot`` per row: numpy's hypot can round the last bit differently."""
    return np.fromiter(map(math.hypot, a.tolist(), b.tolist()), dtype=float, count=len(a))


def fieldai_free_step(
    f, t, slots, behaviour, target_x, target_y, has_target, goal_x, goal_y, has_goal, dt
):
    n = len(slots)
    if not n:
        return [], [], []
    idx = np.asarray(slots, dtype=np.int64)
    mode_col = _view(f["mode_code"])
    m = mode_col[idx].copy()
    b = np.asarray(behaviour, dtype=np.int64)
    tx, ty = np.asarray(target_x, dtype=float), np.asarray(target_y, dtype=float)
    has = np.asarray(has_target, dtype=bool)
    x, y = _view(t["x"])[idx], _view(t["y"])[idx]
    detect, lose = _view(f["detect_radius"])[idx], _view(f["lose_radius"])[idx]
    arrive, speed = _view(f["arrive_distance"])[idx], _view(f["speed"])[idx]
    hx, hy = _view(f["home_x"])[idx], _view(f["home_y"])[idx]
    with np.errstate(invalid="ignore", divide="ignore"):
        distance = _hypot(tx - x, ty - y)
        reacting = ((b == 3) | (b == 4)) & has
        busy = (m == 3) | (m == 4)
        m = np.where(reacting & busy & (distance > lose), 5, m)
        m = np.where(reacting & ~busy & (distance <= detect), b, m)
        m = np.where(((m == 3) | (m == 4)) & ~has, 5, m)
        chasing, home = (m == 3) | (m == 4), m == 5
        patrols = ~chasing & ~home & ((b == 1) | (b == 2))
        m = np.where(patrols, b, np.where(chasing | home, m, 0))
        steer = chasing | home | (patrols & np.asarray(has_goal, dtype=bool))
        away = m == 4
        gx = np.where(home, hx, np.where(chasing, tx, np.asarray(goal_x, dtype=float)))
        gy = np.where(home, hy, np.where(chasing, ty, np.asarray(goal_y, dtype=float)))
        dx, dy = gx - x, gy - y
        dx, dy = np.where(away, -dx, dx), np.where(away, -dy, dy)
        d = _hypot(dx, dy)
        arrived = steer & (d <= np.where(away, 0.0, arrive))
        m = np.where(arrived & home, 0, m)
        moving = steer & ~arrived & (dt > 0)
        step = speed * dt
        land = ~away & (step > d)
        dx, dy = np.where(land, dx * d / step, dx), np.where(land, dy * d / step, dy)
        ux, uy = dx / d, dy / d
        long = np.flatnonzero(moving & (ux * ux + uy * uy > 1.0))
        for k in long.tolist():  # CharacterController2D.move's ``** 0.5`` (libm pow), per row
            magnitude = (ux[k] * ux[k] + uy[k] * uy[k]).item() ** 0.5
            if magnitude > 1.0:
                ux[k], uy[k] = ux[k] / magnitude, uy[k] / magnitude
        mx = np.where(moving, ux * speed * dt, 0.0)
        my = np.where(moving, uy * speed * dt, 0.0)
    mode_col[idx] = m
    code = np.where(arrived, 2, np.where(moving, 1, 0))
    return code.tolist(), mx.tolist(), my.tolist()


def points_blocked(px, py, solids, walls, shapes, wall_bit, cell_size, mask, skip_start, skip):
    n, nw = len(px), len(solids[0])
    if not n or not nw:
        return []
    px, py = np.asarray(px, dtype=float), np.asarray(py, dtype=float)
    x0, y0, x1, y1 = (np.asarray(c, dtype=float) for c in solids)
    cx, cy, radius = (np.asarray(c, dtype=float) for c in walls)
    kind = np.asarray(shapes, dtype=np.int64)
    # candidates: the point's grid cell is one of the wall's cells, the layers meet, not skipped
    gx, gy = np.floor(px / cell_size), np.floor(py / cell_size)
    near = (
        (np.floor(x0 / cell_size) <= gx[:, None])
        & (gx[:, None] <= np.floor(x1 / cell_size))
        & (np.floor(y0 / cell_size) <= gy[:, None])
        & (gy[:, None] <= np.floor(y1 / cell_size))
        & ((np.asarray(mask, dtype=np.int64)[:, None] & np.asarray(wall_bit, dtype=np.int64)) != 0)
    )
    starts = np.asarray(skip_start, dtype=np.int64)
    if len(skip):
        near[np.repeat(np.arange(n), np.diff(starts)), np.asarray(skip, dtype=np.int64)] = False
    i, j = np.nonzero(near)
    if not len(i):
        return []
    x, y, k = px[i], py[i], kind[j]
    hit = (x0[j] <= x) & (x <= x1[j]) & (y0[j] <= y) & (y <= y1[j])
    slope = hit & (k > 1)
    if slope.any():
        with np.errstate(invalid="ignore", divide="ignore"):
            wide = x1[j] > x0[j]
            rise = (x - x0[j]) / (x1[j] - x0[j])
            rise = np.where(rise > 0.0, rise, 0.0)
            rise = np.where(rise < 1.0, rise, 1.0)
            rise = np.where(k == 3, 1.0 - rise, rise)
            top = np.where(wide, y1[j] - rise * (y1[j] - y0[j]), y0[j])
        hit &= ~slope | (y >= top - 1e-9)
    round_ = np.flatnonzero(k == 1)
    if len(round_):
        reach = _hypot(x[round_] - cx[j[round_]], y[round_] - cy[j[round_]])
        hit[round_] = reach <= radius[j[round_]]
    return np.unique(i[hit]).tolist()
