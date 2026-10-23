"""One way to resize a sprite, and one cache for the resized copies.

Every pygame drawer in the engine (the battle drawer, the field view, the playtest runtime's
field sprites and pictures, the generic texture backend) resizes frames through ``resized``:
nearest neighbour for pixel art, bilinear (``smooth=True``) for painted or rendered pictures
(a sprite sheet's ``scaling`` metadata, see ``graphics.sprites``). ``ScaledImageCache`` keeps
the copies a drawer makes every frame (a walking character, the NPCs of a map) under a pixel
budget, so a picture is resized once per size, not once per frame.

The module takes the pygame module as an argument instead of importing it: the engine never
imports pygame at module level (tests and the editor run without a display).
"""

from __future__ import annotations


def resized(pg, image, size, *, smooth=False):
    """``image`` at ``size`` (a ``(width, height)`` of ints, at least 1 x 1).

    The same surface comes back when the size already matches. ``smooth`` blends the pixels
    (``pygame.transform.smoothscale``, which needs a 24- or 32-bit surface: an 8-bit one is
    converted first); otherwise the pixels stay a sharp grid (``pygame.transform.scale``)."""
    size = (max(1, int(size[0])), max(1, int(size[1])))
    if image.get_size() == size:
        return image
    if not smooth:
        return pg.transform.scale(image, size)
    if image.get_bitsize() < 24:
        image = image.convert_alpha()
    return pg.transform.smoothscale(image, size)


class ScaledImageCache:
    """Resized copies by key, dropped all at once past a pixel budget.

    ``get(key, make)`` returns the copy kept under ``key`` or stores what ``make()`` returns.
    The budget counts the pixels of the kept copies (4 bytes each); when a new copy would
    exceed it the cache starts over - a zooming camera asks for a new size every frame, and
    keeping every size would only grow."""

    def __init__(self, budget_pixels=6_000_000):
        self.budget_pixels = int(budget_pixels)
        self._images = {}
        self.pixels = 0

    def __len__(self):
        return len(self._images)

    def __contains__(self, key):
        return key in self._images

    def get(self, key, make):
        image = self._images.get(key)
        if image is None:
            image = make()
            width, height = image.get_size()
            cost = width * height
            if self.pixels + cost > self.budget_pixels:
                self.clear()
            self._images[key] = image
            self.pixels += cost
        return image

    def pop(self, key):
        image = self._images.pop(key, None)
        if image is not None:
            width, height = image.get_size()
            self.pixels -= width * height
        return image

    def clear(self):
        self._images.clear()
        self.pixels = 0
