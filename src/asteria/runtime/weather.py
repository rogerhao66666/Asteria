"""Weather particles (VFX-03): rain, snow, leaves and dust drawn into the world layer.

The simulation is backend-neutral and deterministic (seeded per scene); it runs on both the
pygame and the GPU presenter paths (it is drawn into the world layer before lighting and
post-processing). Particles live in screen space and are shifted by the camera's movement,
so they stay put in the world while the camera pans. Storage is a fixed set of flat lists
reused every frame (no per-frame allocation once warmed up); ``max_particles`` caps the cost.
"""

from __future__ import annotations

import math
import random

_KINDS = {
    #          speed (px/s)   size     colour             count share
    "rain": ((520.0, 760.0), (8, 16), (170, 190, 230, 150), 1.0),
    "snow": ((40.0, 90.0), (2, 4), (245, 248, 255, 220), 0.8),
    "leaves": ((50.0, 110.0), (4, 7), (196, 120, 48, 230), 0.25),
    "dust": ((8.0, 24.0), (1, 2), (230, 220, 190, 120), 0.5),
}


class WeatherSystem:
    def __init__(self, width, height, *, seed="weather"):
        self.width, self.height = int(width), int(height)
        self.rng = random.Random(seed)
        self.kind = "none"
        self.x, self.y, self.vy, self.size, self.phase = [], [], [], [], []
        self._last_camera = None
        self.time = 0.0

    @property
    def count(self):
        return len(self.x)

    def _spawn(self, index=None, *, top=False):
        lo, hi = _KINDS[self.kind][0]
        smin, smax = _KINDS[self.kind][1]
        values = (
            self.rng.uniform(-40, self.width + 40),
            self.rng.uniform(-60, -4) if top else self.rng.uniform(-20, self.height),
            self.rng.uniform(lo, hi),
            self.rng.uniform(smin, smax),
            self.rng.uniform(0, math.tau),
        )
        if index is None:
            for store, value in zip((self.x, self.y, self.vy, self.size, self.phase), values, strict=True):
                store.append(value)
        else:
            self.x[index], self.y[index], self.vy[index], self.size[index], self.phase[index] = values

    def update(self, dt, kind, intensity, max_particles, wind=0.0, camera=None, scale=1.0):
        """Advance ``dt`` seconds. ``camera`` = current view centre in world units (pans the particles)."""
        dt = max(0.0, float(dt))
        self.time += dt
        if kind not in _KINDS:
            self.kind = "none"
            for store in (self.x, self.y, self.vy, self.size, self.phase):
                store.clear()
            return
        if kind != self.kind:
            self.kind = kind
            for store in (self.x, self.y, self.vy, self.size, self.phase):
                store.clear()
        target = int(max(0, max_particles) * max(0.0, min(1.0, intensity)) * _KINDS[kind][3])
        while len(self.x) < target:
            self._spawn()
        del self.x[target:], self.y[target:], self.vy[target:], self.size[target:], self.phase[target:]
        shift_x = shift_y = 0.0
        if camera is not None:
            if self._last_camera is not None:
                shift_x = (self._last_camera[0] - camera[0]) * scale
                shift_y = (self._last_camera[1] - camera[1]) * scale
            self._last_camera = camera
        sway = kind in ("snow", "leaves", "dust")
        for i in range(len(self.x)):
            drift = math.sin(self.time * 1.7 + self.phase[i]) * 18.0 if sway else 0.0
            self.x[i] += (wind + drift) * dt + shift_x
            self.y[i] += self.vy[i] * dt + shift_y
            if self.y[i] > self.height + 20 or self.x[i] < -60 or self.x[i] > self.width + 60:
                self._spawn(i, top=self.y[i] > self.height + 20)

    def draw(self, pg, surface, wind=0.0):
        if self.kind == "none" or not self.x:
            return 0
        color = _KINDS[self.kind][2]
        layer = getattr(self, "_layer", None)
        if layer is None or layer.get_size() != surface.get_size():
            layer = self._layer = pg.Surface(surface.get_size(), pg.SRCALPHA)
        layer.fill((0, 0, 0, 0))
        if self.kind == "rain":
            slant = wind / 700.0
            for x, y, length in zip(self.x, self.y, self.size, strict=True):
                pg.draw.line(layer, color, (x, y), (x - slant * length * 3, y - length * 2), 1)
        elif self.kind == "leaves":
            for x, y, s, ph in zip(self.x, self.y, self.size, self.phase, strict=True):
                w = s * (0.5 + 0.5 * abs(math.sin(self.time * 3 + ph)))
                pg.draw.ellipse(layer, color, (x, y, max(1, w * 2), s))
        else:
            for x, y, s in zip(self.x, self.y, self.size, strict=True):
                pg.draw.circle(layer, color, (int(x), int(y)), int(s))
        surface.blit(layer, (0, 0))
        return len(self.x)
