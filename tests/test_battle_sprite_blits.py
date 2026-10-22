"""Battle sprites are scaled and flipped once per frame size and only their visible part is
drawn: the screen gets the same pixels as blitting the whole frame every time."""

import random
from types import SimpleNamespace

import pygame
import pytest

from asteria.runtime.battle_presentation_adapters import PygameTextureDrawer


def _old_blit(host, image, x, y, width, height, scale, flip_x, opacity, blend, rotation, tint):
    """``PygameTextureDrawer.blit_region`` as it was, from the frame's subsurface on."""
    pg = host.pg
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    if image.get_size() != size:
        image = pg.transform.scale(image, size)
    if flip_x:
        image = pg.transform.flip(image, True, False)
    if tint:
        image = image.copy()
        image.fill((*tint, 255), special_flags=pg.BLEND_RGBA_MULT)
    position = (round(x * scale), round(y * scale))
    if rotation:
        centre = (x * scale + size[0] / 2, y * scale + size[1] / 2)
        image = pg.transform.rotate(image, -rotation)
        position = (
            round(centre[0] - image.get_width() / 2),
            round(centre[1] - image.get_height() / 2),
        )
    if opacity < 1.0 and blend == "add":
        level = max(0, min(255, int(opacity * 255)))
        image = image.copy()
        image.fill((level, level, level), special_flags=pg.BLEND_RGB_MULT)
    elif opacity < 1.0:
        image = image.copy()
        image.set_alpha(max(0, min(255, int(opacity * 255))))
    flags = pg.BLEND_RGB_ADD if blend == "add" else 0
    host.screen.blit(image, position, special_flags=flags)


def _sheet(seed):
    """Two 24x20 frames: a figure with soft edges and a faint rim inside transparent margins,
    then nothing."""
    rng = random.Random(seed)
    sheet = pygame.Surface((48, 20), pygame.SRCALPHA)
    for y in range(20):
        for x in range(24):
            inside = 5 <= x < 19 and 3 <= y < 17
            rim = 4 <= x < 20 and 2 <= y < 18
            alpha = rng.choice((255, 255, 128, 40)) if inside else (3 if rim else 0)
            colour = (rng.randrange(256), rng.randrange(256), rng.randrange(256))
            sheet.set_at((x, y), (*colour, alpha) if alpha else (0, 0, 0, 0))
    return sheet


def _screen():
    screen = pygame.Surface((160, 120), pygame.SRCALPHA)
    for y in range(0, 120, 8):
        pygame.draw.rect(screen, (y * 2, 90, 255 - y * 2, 255), (0, y, 160, 8))
    return screen


CASES = [  # x, y, width, height, flip, opacity, blend, rotation, tint
    (10, 12, 24, 20, False, 1.0, "normal", 0.0, None),
    (10.4, 12.6, 33, 27, True, 1.0, "normal", 0.0, None),
    (70, 40, 13, 11, False, 0.5, "normal", 0.0, (255, 120, 60)),
    (60, 30, 30, 25, True, 0.25, "normal", 0.0, None),
    (20, 50, 24, 20, False, 0.6, "add", 0.0, None),
    (90, 60, 26, 22, True, 1.0, "normal", 30.0, (200, 200, 255)),
]


@pytest.mark.parametrize("scale", [1.0, 2.6666666666666665])
@pytest.mark.parametrize("frame", [(0, 0, 24, 20), (24, 0, 24, 20)])
def test_sprite_blits_put_the_same_pixels_on_the_screen(scale, frame):
    sheets = {"hero": _sheet(3)}
    new = SimpleNamespace(pg=pygame, screen=_screen())
    old = SimpleNamespace(pg=pygame, screen=_screen())
    resolver = SimpleNamespace(generated_image=lambda asset_id: sheets[asset_id])
    drawer = PygameTextureDrawer(new, resolver, scale)
    for turn in range(3):  # the second and third draws come from the cache
        if turn == 2:
            sheets["hero"] = _sheet(4)  # a new picture under the same id is drawn anew
        for x, y, w, h, flip, opacity, blend, rotation, tint in CASES:
            drawer.blit_region(
                "hero",
                frame,
                x,
                y,
                w,
                h,
                flip_x=flip,
                opacity=opacity,
                blend=blend,
                rotation_deg=rotation,
                tint=tint,
            )
            image = sheets["hero"].subsurface(pygame.Rect(*frame))
            _old_blit(old, image, x, y, w, h, scale, flip, opacity, blend, rotation, tint)
            assert pygame.image.tobytes(new.screen, "RGBA") == pygame.image.tobytes(
                old.screen, "RGBA"
            ), (turn, x, y)
    assert drawer.draw_count == 3 * len(CASES)


def test_the_sprite_cache_starts_over_past_its_pixel_budget():
    sheets = {"hero": _sheet(5)}
    host = SimpleNamespace(pg=pygame, screen=_screen())
    drawer = PygameTextureDrawer(host, SimpleNamespace(generated_image=sheets.get), 1.0)
    drawer.SPRITE_PIXELS = 2_000
    for width in range(30, 60):  # a zooming camera: a new size every frame
        drawer.blit_region("hero", (0, 0, 24, 20), 0, 0, width, width)
        assert drawer._sprite_pixels <= drawer.SPRITE_PIXELS
    assert 0 < len(drawer._sprites) < 30


def test_panels_drawn_from_the_kept_layer_match_a_fresh_drawing():
    from asteria.platform.pygame_battle_ui import PygameBattleUiBackend

    kept = PygameBattleUiBackend(_screen(), scale=2.6666666666666665)
    panels = [  # x, y, width, height, fill, border, radius, border width
        (3, 4, 30, 12, (20, 30, 60, 200), (240, 220, 160), 4, 1),
        (3, 4, 30, 12, (20, 30, 60, 200), (240, 220, 160), 4, 0),
        (10.5, 20.2, 18, 9, (200, 40, 40), (0, 0, 0, 90), 0, 2),
        (3, 4, 30, 12, (20, 30, 60, 120), (240, 220, 160), 4, 1),
    ]
    for _ in range(2):  # the second time every panel comes from the kept layers
        for x, y, w, h, fill, border, radius, width in panels:
            fresh = PygameBattleUiBackend(kept.screen.copy(), scale=kept.scale)
            panel = SimpleNamespace(x=x, y=y, width=w, height=h)
            for backend in (kept, fresh):
                backend.draw_panel(
                    panel, fill=fill, border=border, radius=radius, border_width=width
                )
            assert pygame.image.tobytes(kept.screen, "RGBA") == pygame.image.tobytes(
                fresh.screen, "RGBA"
            )
    assert len(kept._panel_layers) == len(panels)
