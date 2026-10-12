"""Weather particles (VFX-03): rain, snow, leaves and dust drawn into the world layer.

The simulation is backend-neutral and deterministic (seeded per scene); it runs on both the
pygame and the GPU presenter paths (it is drawn into the world layer before lighting and
post-processing). Particles live in screen space and are shifted by the camera's movement,
so they stay put in the world while the camera pans. Storage, motion and drawing are the active compute
kernel's ``WeatherStore`` (D21); ``max_particles`` caps the cost.
"""

from __future__ import annotations

import math
import random

from asteria import kernels

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
        self._particles = kernels.active().WeatherStore()
        self._last_camera = None
        self.time = 0.0

    @property
    def count(self):
        return len(self._particles)

    x = property(lambda self: self._particles.column("x"))
    y = property(lambda self: self._particles.column("y"))
    vy = property(lambda self: self._particles.column("vy"))
    size = property(lambda self: self._particles.column("size"))
    phase = property(lambda self: self._particles.column("phase"))

    def _new_particle(self, *, top=False):
        lo, hi = _KINDS[self.kind][0]
        smin, smax = _KINDS[self.kind][1]
        return (
            self.rng.uniform(-40, self.width + 40),
            self.rng.uniform(-60, -4) if top else self.rng.uniform(-20, self.height),
            self.rng.uniform(lo, hi),
            self.rng.uniform(smin, smax),
            self.rng.uniform(0, math.tau),
        )

    def update(self, dt, kind, intensity, max_particles, wind=0.0, camera=None, scale=1.0):
        """Advance ``dt`` seconds. ``camera`` = current view centre in world units (pans the particles)."""
        dt = max(0.0, float(dt))
        self.time += dt
        particles = self._particles
        if kind not in _KINDS:
            self.kind = "none"
            particles.truncate(0)
            return
        if kind != self.kind:
            self.kind = kind
            particles.truncate(0)
        target = int(max(0, max_particles) * max(0.0, min(1.0, intensity)) * _KINDS[kind][3])
        if len(particles) < target:
            particles.add([self._new_particle() for _ in range(target - len(particles))])
        particles.truncate(target)
        shift_x = shift_y = 0.0
        if camera is not None:
            if self._last_camera is not None:
                shift_x = (self._last_camera[0] - camera[0]) * scale
                shift_y = (self._last_camera[1] - camera[1]) * scale
            self._last_camera = camera
        sway = kind in ("snow", "leaves", "dust")
        for index, fell_out in particles.step(dt, wind, self.time, sway, shift_x, shift_y, self.width, self.height):
            particles.set_row(index, self._new_particle(top=fell_out))

    def draw(self, pg, surface, wind=0.0):
        if self.kind == "none" or not len(self._particles):
            return 0
        layer = getattr(self, "_layer", None)
        if layer is None or layer.get_size() != surface.get_size():
            layer = self._layer = pg.Surface(surface.get_size(), pg.SRCALPHA)
        self._particles.draw(pg, layer, self.kind, _KINDS[self.kind][2], wind, self.time)
        surface.blit(layer, (0, 0))
        return len(self._particles)
