"""numpy kernels - the reference arithmetic on whole arrays (same operations, same order, same results)."""

from __future__ import annotations

import numpy as np

from asteria.kernels._python import FIELDS, PROJECTILE_FIELDS, WEATHER_FIELDS, _turn_cosines

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
        return list(zip(px.tolist(), py.tolist(), size.tolist(), colors, angle.tolist(), strict=True))


class WeatherStore:
    """Weather particles as arrays. Drawing stamps each particle's shape: pygame truncates coordinates to whole
    pixels, so a line, ellipse or dot depends only on whole-pixel sizes - each distinct shape is drawn once by
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
    """Same pairs as the reference, found by sort-and-sweep along the wider axis (``cell_size`` is unused)."""
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


def aabb_cross_pairs(a, b, cell_size=64.0):
    """Same pairs as the reference: a grid join (cells of ``a`` matched to sorted cells of ``b``)."""
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
    j = b_row[np.repeat(lo, counts) + np.arange(total) - np.repeat(np.cumsum(counts) - counts, counts)]
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
