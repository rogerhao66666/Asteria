"""Reference kernels in plain Python - always available; every other kernel set must match these."""

from __future__ import annotations

from math import floor

NAME = "python"

# column order of a particle row
FIELDS = ("px", "py", "vx", "vy", "life", "max_life", "size_k", "angle", "spin")


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
