"""pygame (L0) rendering of a scene environment (VFX-02 fallback, proposal §7).

On the pygame backend the world layer gets an approximate light map (ambient fill plus cached
radial gradients added per light, multiplied over the world) and a flat fog overlay. Bloom,
colour grading, screen shaders, normal maps and shadows need the GPU; they are skipped here
and listed by ``unsupported(env)`` so the profiler / debugger can report them. Gameplay is
never affected.
"""

from __future__ import annotations

GPU_ONLY = ("bloom", "grade", "vignette", "screen_shader")


def unsupported(env):
    missing = [e.effect_id for e in env.post if e.enabled and e.effect_id in GPU_ONLY]
    if env.lighting and any(model.casts_shadow for model, _, _ in env.lights) and env.casters:
        missing.append("shadows")
    return missing


class PygameEnvironmentRenderer:
    def __init__(self, pg):
        self.pg = pg
        self.time = 0.0
        self._gradients = {}
        self._light = None
        self._fog = None

    def _gradient(self, radius, color):
        key = (int(radius), tuple(int(c * 255) for c in color))
        image = self._gradients.get(key)
        if image is None:
            pg = self.pg
            size = max(2, int(radius) * 2)
            image = pg.Surface((size, size))
            image.fill((0, 0, 0))
            steps = 96  # fine steps: no visible rings
            for i in range(steps, 0, -1):  # concentric discs approximate (1 - d/r)^2
                t = i / steps
                fall = (1 - t) ** 2
                c = tuple(min(255, int(255 * channel * fall)) for channel in color)
                pg.draw.circle(image, c, (size // 2, size // 2), max(1, int(radius * t)))
            if len(self._gradients) > 64:
                self._gradients.clear()
            self._gradients[key] = image
        return image

    def apply(self, world, env):
        pg = self.pg
        size = world.get_size()
        if env.lighting:
            if self._light is None or self._light.get_size() != size:
                self._light = pg.Surface(size)
            ambient = tuple(
                min(255, int(255 * c * env.ambient.intensity)) for c in env.ambient.color
            )
            self._light.fill(ambient)
            for model, _height, _flicker in env.lights:
                color = tuple(c * model.intensity for c in model.color)
                image = self._gradient(model.radius, tuple(min(1.0, c) for c in color))
                self._light.blit(
                    image,
                    (int(model.x - image.get_width() / 2), int(model.y - image.get_height() / 2)),
                    special_flags=pg.BLEND_RGB_ADD,
                )
            world.blit(self._light, (0, 0), special_flags=pg.BLEND_RGB_MULT)
        for x0, y0, x1, y1, amplitude, wavelength, speed, tint, strength in env.water:
            self._water(world, (x0, y0, x1, y1), amplitude, wavelength, speed, tint, strength)
        if env.fog is not None and env.fog.density > 0:
            if self._fog is None or self._fog.get_size() != size:
                self._fog = pg.Surface(size, pg.SRCALPHA)
            self._fog.fill(
                (
                    *(int(c * 255) for c in env.fog.color),
                    int(255 * min(1.0, env.fog.density * 0.8)),
                )
            )
            world.blit(self._fog, (0, 0))

    def _water(self, world, rect, amplitude, wavelength, speed, tint, strength):
        """Ripple by shifting 2-pixel rows sideways, then tint (cheap CPU approximation of the GPU
        pass)."""
        import math

        pg = self.pg
        x0, y0, x1, y1 = (int(v) for v in rect)
        area = pg.Rect(x0, y0, max(0, x1 - x0), max(0, y1 - y0)).clip(world.get_rect())
        if area.width <= 0 or area.height <= 0:
            return
        source = world.subsurface(area).copy()
        for row in range(0, area.height, 2):
            shift = int(
                math.sin((area.y + row) / max(1.0, wavelength) * math.tau + self.time * speed)
                * amplitude
            )
            world.blit(source, (area.x + shift, area.y + row), (0, row, area.width, 2))
        if strength > 0:
            veil = pg.Surface(area.size, pg.SRCALPHA)
            veil.fill((*(int(c * 255) for c in tint), int(255 * strength * 0.6)))
            world.blit(veil, area.topleft)
