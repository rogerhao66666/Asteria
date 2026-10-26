"""D87: menus fit a small window, bodies block with their feet box, walks keep pace with the
ground, figures stand on their feet, and the play-test hint panel never hides the map."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from asteria.runtime.collision import box_blocked
from asteria.runtime.playtest.menu_fit import MenuFitMixin, fitted_size
from asteria.runtime.pointer import Hotspot

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


def test_fitted_size_keeps_the_window_shape_and_at_least_the_design():
    assert fitted_size((960, 540), (1280, 720)) == (1280, 720)
    assert fitted_size((960, 640), (1280, 720)) == (1280, 853)
    assert fitted_size((1920, 1080), (1280, 720)) == (1920, 1080)  # big enough: as it is
    assert fitted_size((960, 540), (0, 0)) == (960, 540)  # [0, 0]: fitting is off


class _Host(MenuFitMixin):
    def __init__(self, pg, menu_size=None):
        self.pg = pg
        self.width, self.height = 960, 540
        self.screen = pg.Surface((960, 540))
        self.manifest = {"render": {"menu_size": menu_size}} if menu_size else {}
        self.pointer = SimpleNamespace(drawn=[Hotspot((0, 0, 5, 5))])


@pytest.fixture
def pg(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    import pygame

    pygame.init()
    yield pygame


def test_a_fitted_menu_draws_big_and_its_clicks_shrink_with_it(pg):
    host = _Host(pg)
    with host.menu_fit():
        assert (host.width, host.height) == (1280, 720)
        assert host.screen.get_size() == (1280, 720)
        host.screen.fill((255, 0, 0), (1180, 620, 100, 100))  # the far corner
        host.pointer.drawn.append(Hotspot((1180, 620, 100, 100)))
        with host.window_drawing():  # the map behind the menu: the window itself
            assert host.screen.get_size() == (960, 540)
    assert (host.width, host.height) == (960, 540)
    assert host.pointer.drawn[0].rect == (0, 0, 5, 5)  # drawn before: left alone
    assert host.pointer.drawn[1].rect == (885, 465, 75, 75)
    red, green, _blue, _alpha = host.screen.get_at((950, 530))
    assert red > 240 and green < 10  # the corner is in the window (smoothed)


def test_menu_size_zero_turns_the_fitting_off(pg):
    host = _Host(pg, [0, 0])
    with host.menu_fit():
        assert (host.width, host.height) == (960, 540)


class _Wall:
    def collides_world_point(self, x, y):
        return x >= 100.0


def test_a_feet_box_blocks_where_a_point_would_slip_in():
    wall = _Wall()
    assert not box_blocked(wall, 95.0, 0.0, None)  # a point 5 short of the wall
    assert box_blocked(wall, 95.0, 0.0, (7.0, 4.0, 0.0, 0.0))  # a body 14 wide touches it
    assert not box_blocked(wall, 93.0, 0.0, (7.0, 4.0, 0.0, 0.0))  # just touching: free


def test_a_walk_plays_as_far_as_the_figure_moves():
    from asteria.runtime.tile_scene_view import _Animated

    keys = [SimpleNamespace(duration=0.1, frame_index=i) for i in range(8)]
    walk = SimpleNamespace(keyframes=keys, loop=True)
    idle = SimpleNamespace(keyframes=keys[:1], loop=True)
    clips = SimpleNamespace(clips={"walk_down": walk, "idle_down": idle})
    figure = _Animated(clips)
    figure.update(0.1, (0.0, 0.0), "down", False, stride=24.0)
    for step in range(1, 7):  # 6 px a frame: a quarter of the 24 px stride
        figure.update(0.1, (0.0, 6.0 * step), "down", False, stride=24.0)
    # 36 px walked = 1.5 strides = 1.2 s of the 0.8 s clip, whatever the clock says
    assert figure.time == pytest.approx(1.2)
    clock = _Animated(clips)
    clock.update(0.1, (0.0, 0.0), "down", False)
    for step in range(1, 7):
        clock.update(0.1, (0.0, 6.0 * step), "down", False)
    assert clock.time == pytest.approx(0.6)  # without a stride: by the clock


def test_feet_pivot_finds_the_lowest_opaque_row():
    from PIL import Image

    from asteria.graphics.character_placement import feet_pivot_y

    image = Image.new("RGBA", (96, 48))
    image.paste((255, 255, 255, 255), (10, 4, 30, 40))  # feet end on row 39
    image.paste((255, 255, 255, 255), (58, 10, 70, 38))
    assert feet_pivot_y(image, [(0, 0, 48, 48), (48, 0, 48, 48)]) == round(40 / 48, 4)
    assert feet_pivot_y(Image.new("RGBA", (48, 48)), [(0, 0, 48, 48)]) == 1.0


# -- the Full Verification demo ------------------------------------------------------------------
def _project():
    return json.loads((DEMO / "project.asteria.json").read_text(encoding="utf-8"))


def _entities(node):
    if isinstance(node, dict):
        if isinstance(node.get("components"), list):
            yield node
        for value in node.values():
            yield from _entities(value)
    elif isinstance(node, list):
        for value in node:
            yield from _entities(value)


def test_the_demo_house_and_props_block_and_people_are_body_wide():
    data = _project()
    named = {}
    for entity in _entities(data["scenes"]):
        named.setdefault(entity.get("name"), []).append(entity)
    for name in ("Roger's House", "Hall of Heroes", "Victory Banner", "Old Cache", "Sealed Vault"):
        types = {c["type"] for e in named[name] for c in e["components"]}
        assert "asteria.Collider2D" in types, name
    widths = {
        c["fields"]["width"]
        for e in _entities(data["scenes"])
        for c in e["components"]
        if c["type"] == "asteria.Collider2D" and c["fields"]["height"] == 8.0
    }
    assert 10.0 not in widths and 14.0 in widths
    strides = {
        c["fields"].get("stride")
        for e in _entities(data["scenes"])
        for c in e["components"]
        if c["type"] == "asteria.Animator2D"
    }
    assert strides == {24.0}


def test_the_demo_warrior_stands_on_its_feet_and_the_settings_are_set():
    sheet = json.loads(
        (DEMO / "playable_assets/lucifer/world/look_hero_warrior_sheet.json").read_text()
    )
    pivots = {f["pivot_y"] for f in sheet["frames"]}
    assert pivots == {0.8542}
    manifest = json.loads((DEMO / "playable_test_manifest.json").read_text())
    assert manifest["field"]["walk_speed"] == 48.0
    assert manifest["render"]["menu_size"] == [1280, 720]


def test_the_patch_is_safe_to_run_again():
    sys.path.insert(0, str(DEMO))
    import trial_d87

    data = _project()
    before = json.dumps(data, indent=2)
    trial_d87.patch_project(data)
    trial_d87.patch_menu_pages(data)
    assert json.dumps(data, indent=2) == before
