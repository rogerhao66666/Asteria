"""One resize helper for every drawer (``graphics.scaling``): the same pixels pygame gives,
sharp or blended as asked, and a cache that resizes a field sprite once per size."""

from pathlib import Path
from types import SimpleNamespace

import pygame
import pytest

from asteria.graphics.scaling import ScaledImageCache, resized


def _picture(width=12, height=10):
    image = pygame.Surface((width, height), pygame.SRCALPHA)
    for y in range(height):
        for x in range(width):
            if 2 <= x < width - 2 and 1 <= y < height - 1:
                image.set_at((x, y), (20 * x, 25 * y, 120, 255 if x % 2 else 90))
    return image


def test_resized_matches_pygame_and_keeps_an_unchanged_size():
    image = _picture()
    assert resized(pygame, image, (12, 10)) is image
    sharp = resized(pygame, image, (30, 25))
    assert pygame.image.tobytes(sharp, "RGBA") == pygame.image.tobytes(
        pygame.transform.scale(image, (30, 25)), "RGBA"
    )
    soft = resized(pygame, image, (30, 25), smooth=True)
    assert pygame.image.tobytes(soft, "RGBA") == pygame.image.tobytes(
        pygame.transform.smoothscale(image, (30, 25)), "RGBA"
    )
    assert pygame.image.tobytes(sharp, "RGBA") != pygame.image.tobytes(soft, "RGBA")
    assert resized(pygame, image, (0, -3)).get_size() == (1, 1)  # never an empty surface
    paletted = pygame.Surface((4, 4), depth=8)  # smoothscale needs 24/32 bits: converted
    pygame.display.init()
    pygame.display.set_mode((8, 8))
    assert resized(pygame, paletted, (8, 8), smooth=True).get_size() == (8, 8)


def test_the_cache_resizes_once_per_key_and_starts_over_past_its_budget():
    cache = ScaledImageCache(budget_pixels=2_000)
    calls = []

    def make(size):
        def build():
            calls.append(size)
            return pygame.Surface(size)

        return build

    first = cache.get("a", make((20, 20)))
    assert cache.get("a", make((20, 20))) is first and calls == [(20, 20)]
    assert "a" in cache and len(cache) == 1 and cache.pixels == 400
    cache.get("b", make((30, 30)))  # 400 + 900 fits
    assert len(cache) == 2 and cache.pixels == 1300
    cache.get("c", make((30, 30)))  # 1300 + 900 would pass 2000: start over
    assert len(cache) == 1 and "c" in cache and cache.pixels == 900
    assert cache.pop("c").get_size() == (30, 30) and cache.pixels == 0
    assert cache.pop("missing") is None
    cache.get("d", make((5, 5)))
    cache.clear()
    assert len(cache) == 0 and cache.pixels == 0


def test_the_field_resizes_a_walker_and_the_townsfolk_once_per_size(runtime):
    """The playtest field keeps the resized player step and each NPC picture, and drops them
    with the pictures when a scope is unloaded."""
    from asteria.graphics import scaling

    runtime._ui_mode = "field"
    runtime._frame([], 0.03)
    runtime._frame([], 0.03)
    count = {"n": 0}
    original = scaling.resized

    def counting(pg, image, size, *, smooth=False):
        count["n"] += 1
        return original(pg, image, size, smooth=smooth)

    import asteria.runtime.playtest.field_view as module

    module.resized = counting
    try:
        for _ in range(5):  # nothing moves: every picture is already resized and kept
            runtime._frame([], 0.03)
        assert count["n"] == 0 and len(runtime._scaled) >= 1
        runtime._scaled.clear()
        runtime._frame([], 0.03)
        assert count["n"] >= 1  # cleared: the next frame resizes again
    finally:
        module.resized = original


@pytest.mark.parametrize("backend_name", ["PygameRuntimeBackend", "PygameTextureBackend"])
def test_the_texture_backends_draw_through_the_helper(backend_name):
    from asteria.assets import TextureResource
    from asteria.platform import pygame_backend

    backend = pygame_backend.__dict__[backend_name].__new__(pygame_backend.__dict__[backend_name])
    backend.pg = pygame
    backend.screen = pygame.Surface((40, 30), pygame.SRCALPHA)
    picture = _picture()
    texture = TextureResource("t", 12, 10, picture)
    command = SimpleNamespace(
        source=(0, 0, 12, 10),
        width=24,
        height=20,
        flip_x=True,
        opacity=0.5,
        screen_x=3,
        screen_y=4,
    )
    backend.draw_texture(texture, command)
    wanted = pygame.Surface((40, 30), pygame.SRCALPHA)
    image = pygame.transform.flip(pygame.transform.scale(picture, (24, 20)), True, False)
    image.set_alpha(127)
    wanted.blit(image, (3, 4))
    assert pygame.image.tobytes(backend.screen, "RGBA") == pygame.image.tobytes(wanted, "RGBA")
    assert Path(pygame_backend.__file__).name == "pygame_backend.py"
