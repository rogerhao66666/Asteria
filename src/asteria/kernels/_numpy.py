"""numpy kernels - the reference arithmetic on whole arrays (same operations, same order, same results)."""

from __future__ import annotations

import numpy as np

from asteria.kernels._python import FIELDS

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
