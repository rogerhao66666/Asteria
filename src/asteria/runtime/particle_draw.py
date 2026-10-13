"""Draw particle systems (VFX-01) on a pygame surface - the field and the battle use the same
drawer.

Shapes go to one reusable layer per blend mode (``alpha`` or ``add``); only the area particles
touched
is cleared and composited, so an effect costs what it covers, not the whole screen.
"""

from __future__ import annotations

import math


class ParticleDrawer:
    def __init__(self, pg):
        self.pg = pg
        self._layers = {}
        self._images = {}

    def _layer(self, blend, size):
        layer = self._layers.get(blend)
        if layer is None or layer.get_size() != size:
            if blend == "add":
                layer = self.pg.Surface(size)
                layer.fill((0, 0, 0))
            else:
                layer = self.pg.Surface(size, self.pg.SRCALPHA)
                layer.fill((0, 0, 0, 0))
            self._layers[blend] = layer
        return layer

    def draw(self, surface, systems, to_screen, pixels_per_unit, *, image=None):
        """``systems``: ParticleSystems; ``to_screen(x, y)`` -> screen point; ``pixels_per_unit``:
        screen pixels per
        world unit (zoom included); ``image(image_id)`` -> pygame surface or None (image
        particles)."""
        pg = self.pg
        size = surface.get_size()
        dirty = {"alpha": [], "add": []}
        drawn = 0
        for system in systems:
            definition = system.definition
            blend = definition.blend
            layer = self._layer(blend, size)
            source = (
                image(definition.image)
                if definition.particle == "image" and image is not None
                else None
            )
            for p in system.views():
                alpha = p.color[3]
                if alpha <= 0:
                    continue
                sx, sy = to_screen(p.x, p.y)
                radius = max(0.5, p.size * pixels_per_unit / 2)
                if blend == "add":
                    k = alpha / 255.0
                    color = (int(p.color[0] * k), int(p.color[1] * k), int(p.color[2] * k))
                else:
                    color = p.color
                if source is not None:
                    rect = self._blit_image(surface, source, sx, sy, radius, p.angle, alpha, blend)
                    drawn += 1
                    continue
                kind = definition.particle
                if kind == "square" or kind == "image":
                    rect = pg.draw.polygon(layer, color, _square(sx, sy, radius, p.angle))
                elif kind == "spark":
                    width = max(1, round(radius / 3))
                    a = math.radians(p.angle)
                    dx, dy = math.cos(a) * radius * 1.6, math.sin(a) * radius * 1.6
                    rect = pg.draw.line(
                        layer, color, (sx - dx, sy - dy), (sx + dx, sy + dy), width
                    )
                    rect = rect.union(
                        pg.draw.line(layer, color, (sx + dy, sy - dx), (sx - dy, sy + dx), width)
                    )
                else:
                    rect = pg.draw.circle(
                        layer, color, (round(sx), round(sy)), max(1, round(radius))
                    )
                dirty[blend].append(rect)
                drawn += 1
        for blend, rects in dirty.items():
            if not rects:
                continue
            area = rects[0].unionall(rects[1:]).clip(surface.get_rect())
            layer = self._layers[blend]
            if blend == "add":
                surface.blit(layer, area.topleft, area, special_flags=pg.BLEND_RGB_ADD)
                layer.fill((0, 0, 0), area)
            else:
                surface.blit(layer, area.topleft, area)
                layer.fill((0, 0, 0, 0), area)
        return drawn

    def _blit_image(self, surface, source, sx, sy, radius, angle, alpha, blend):
        pg = self.pg
        side = max(1, round(radius * 2))
        key = (id(source), side, round(angle) % 360 if angle else 0)
        image = self._images.get(key)
        if image is None:
            w, h = source.get_size()
            k = side / max(w, h)
            image = pg.transform.scale(source, (max(1, round(w * k)), max(1, round(h * k))))
            if angle:
                image = pg.transform.rotate(image, -key[2])
            if len(self._images) > 512:
                self._images.clear()
            self._images[key] = image
        rect = image.get_rect(center=(round(sx), round(sy)))
        if blend == "add":
            lit = image.copy()
            lit.fill((alpha, alpha, alpha), special_flags=pg.BLEND_RGB_MULT)
            return surface.blit(lit, rect, special_flags=pg.BLEND_RGB_ADD)
        image.set_alpha(alpha)
        return surface.blit(image, rect)


def _square(x, y, radius, angle):
    a = math.radians(angle + 45)
    r = radius * math.sqrt(2)
    return [
        (x + math.cos(a + k * math.pi / 2) * r, y + math.sin(a + k * math.pi / 2) * r)
        for k in range(4)
    ]
