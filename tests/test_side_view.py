"""ASTERIA_SPEC §20 (D22 A5): side-view feel — coyote time, jump buffer, short hops, drop-through
platforms,
slopes and ladders; every option defaults to the earlier behaviour."""

import pytest

from asteria.core import ComponentRegistry, Entity, Scene, Transform, deserialize_component
from asteria.runtime.character_control import (
    CharacterController2DComponent,
    CharacterControllerSystem,
    PlayerInput2DComponent,
    PlayerInputSystem,
    register_character_components,
)
from asteria.runtime.collision import Collider2DComponent
from asteria.runtime.input import InputSnapshot

DT = 1 / 60


def _set(component, **fields):
    for k, v in fields.items():
        setattr(component, k, v)
    return component


class Stage:
    def __init__(self):
        self.scene = Scene("Stage")
        self.input = {}
        self.scene.scheduler.add(PlayerInputSystem(lambda: InputSnapshot(dict(self.input))))
        self.scene.scheduler.add(CharacterControllerSystem())

    def solid(self, x, y, w, h, **fields):
        e = self.scene.add_entity(Entity("Solid"))
        e.add_component(Transform(x, y))
        e.add_component(_set(Collider2DComponent(), width=w, height=h, **fields))
        return e

    def hero(self, x, y, **fields):
        e = self.scene.add_entity(Entity("Hero"))
        e.add_component(Transform(x, y))
        e.add_component(_set(CharacterController2DComponent(), mode="side", speed=80.0, **fields))
        e.add_component(PlayerInput2DComponent())
        return e

    def run(self, seconds):
        ys = []
        for _ in range(max(1, round(seconds / DT))):
            self.scene.update(DT)
            ys.append(self.y)
        return ys

    @property
    def y(self):
        return self._hero.get(Transform).y

    def c(self):
        return self._hero.get(CharacterController2DComponent)


def _stage_with_ledge(**fields):
    s = Stage()
    s.solid(0, 20, 100, 8)  # floor from x -50 to 50, top at y 16
    s._hero = s.hero(40, 7.9, **fields)
    s.run(0.1)
    assert s.c().grounded
    return s


@pytest.mark.parametrize(("coyote", "jumps"), [(0.0, False), (0.15, True)])
def test_coyote_time_allows_a_late_jump_after_walking_off(coyote, jumps):
    s = _stage_with_ledge(coyote_time=coyote)
    s.input["move_right"] = 1.0
    while s.c().grounded:
        s.scene.update(DT)
    s.run(0.05)  # just past the edge
    s.input = {"jump": 1.0}
    s.scene.update(DT)
    s.input = {}
    assert (s.c().velocity_y < -100) is jumps


@pytest.mark.parametrize(("buffer", "jumps"), [(0.0, False), (0.2, True)])
def test_a_jump_pressed_just_before_landing_is_remembered(buffer, jumps):
    s = Stage()
    s.solid(0, 20, 200, 8)
    s._hero = s.hero(0, -20, jump_buffer=buffer)
    while s.y < 7.9 - 3:  # falling, a few units above the floor
        s.scene.update(DT)
    s.input = {"jump": 1.0}
    s.scene.update(DT)
    s.input = {}
    s.run(0.15)
    assert (min(s.run(0.3)) < -10) is jumps


def test_releasing_jump_early_makes_a_short_hop():
    heights = []
    for hold in (0.05, 0.6):
        s = _stage_with_ledge(jump_cut=0.4)
        s._hero.get(Transform).x = 0
        s.input = {"jump": 1.0}
        apex = min(s.run(hold))
        s.input = {}
        apex = min([apex, *s.run(0.8)])
        heights.append(7.9 - apex)
    assert heights[0] < heights[1] * 0.6
    s = _stage_with_ledge()  # jump_cut 1: the earlier behaviour, full height either way
    s._hero.get(Transform).x = 0
    s.input = {"jump": 1.0}
    s.run(0.05)
    s.input = {}
    assert 7.9 - min(s.run(0.8)) == pytest.approx(heights[1], abs=1.0)


def test_down_and_jump_drops_through_a_one_way_platform():
    for drop, expect_below in ((True, True), (False, False)):
        s = Stage()
        s.solid(0, 100, 300, 8)  # ground
        s.solid(0, 20, 100, 4, one_way=True)  # a thin platform, top at 18
        s._hero = s.hero(0, 9.9, drop_through=drop)
        s.run(0.1)
        assert s.c().grounded and s.y < 12
        s.input = {"move_down": 1.0, "jump": 1.0}
        s.scene.update(DT)
        s.input = {}
        s.run(0.6)
        assert (s.y > 50) is expect_below


def test_walking_up_and_down_a_slope_follows_the_surface():
    s = Stage()
    s.solid(-100, 20, 200, 8)  # flat floor x -200..0, top 16
    s.solid(50, 0, 100, 40, shape="slope_right")  # ramp x 0..100 rising from y 20 to y -20
    s.solid(150, -16, 100, 8)  # upper floor x 100..200, top -20 (flush with the ramp top)
    s._hero = s.hero(-40, 7.9)
    s.run(0.1)
    s.input = {"move_right": 1.0}
    ys = s.run(2.0)
    assert s._hero.get(Transform).x > 90 and min(ys) < -10  # climbed the ramp
    s.input = {"move_left": 1.0}
    grounded = 0
    for _ in range(90):
        s.scene.update(DT)
        grounded += s.c().grounded
    assert (
        s._hero.get(Transform).x < 20 and grounded > 80
    )  # walked down without bouncing into the air


def test_ladders_are_climbed_without_gravity_and_never_block():
    s = Stage()
    s.solid(0, 20, 300, 8)
    s.solid(40, -40, 16, 120, ladder=True)  # ladder from y -100 to 20
    s._hero = s.hero(0, 7.9)
    s.run(0.1)
    s.input = {"move_right": 1.0}
    s.run(0.6)
    assert s._hero.get(Transform).x > 40  # walking through the ladder: it does not block
    s._hero.get(Transform).x = 40
    s.input = {"move_up": 1.0}
    s.run(1.0)
    assert s.c().climbing and s.y < -40
    s.input = {}
    y = s.y
    s.run(0.5)
    assert s.y == pytest.approx(y)  # holding on: no gravity
    s.input = {"jump": 1.0}
    s.scene.update(DT)
    s.input = {}
    assert not s.c().climbing


def test_old_controllers_and_colliders_load_with_the_earlier_behaviour():
    registry = register_character_components(ComponentRegistry())
    registry.register(Collider2DComponent)
    c = deserialize_component(
        {"type": "asteria.CharacterController2D", "version": 2, "fields": {"mode": "side"}},
        registry,
    )
    assert (c.coyote_time, c.jump_buffer, c.jump_cut, c.drop_through) == (0.0, 0.0, 1.0, False)
    collider = deserialize_component(
        {"type": "asteria.Collider2D", "version": 2, "fields": {"one_way": True}}, registry
    )
    assert collider.one_way and not collider.ladder and collider.shape == "box"


def test_a_side_view_character_has_its_feet_at_the_bottom_of_its_box():
    from asteria.runtime.character_control import feet_y

    side = Entity("Side")
    side.add_component(_set(CharacterController2DComponent(), mode="side", half_height=7.0))
    top = Entity("Top")
    top.add_component(_set(CharacterController2DComponent(), mode="topdown", half_height=7.0))
    assert feet_y(side, 100.0) == 107.0  # the box's bottom rests on the floor
    assert feet_y(top, 100.0) == 100.0  # top-down: the place is the feet
    assert feet_y(Entity("Prop"), 100.0) == 100.0
