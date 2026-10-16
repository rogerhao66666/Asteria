"""Combatants can step toward a foe and back during an action (the ``move`` motion channel)."""

import pytest
from test_battle_presentation_runtime import _runtime

from asteria.runtime import Camera2D


def _hero_x(runtime):
    frame = runtime.build_frame(Camera2D())
    return frame.combatant_draws[0].screen_x


def test_move_goes_toward_the_target_and_returns():
    runtime = _runtime()
    start = _hero_x(runtime)
    runtime.start_move("hero", target_id="mimic", gap=40.0, duration=0.2)
    runtime.update(0.1)
    halfway = _hero_x(runtime)
    runtime.update(0.2)
    arrived = _hero_x(runtime)
    assert start < halfway < arrived
    # the hero stands 40 world units from the foe's anchor (232) at the end
    assert arrived - start == pytest.approx((232 - 40) - 72, abs=1.0)
    runtime.start_move("hero", duration=0.2)  # no target: back to where it stands
    runtime.update(0.3)
    assert _hero_x(runtime) == pytest.approx(start, abs=0.01)


def test_nothing_moves_without_a_move_beat():
    runtime = _runtime()
    start = _hero_x(runtime)
    runtime.update(1.0)
    assert _hero_x(runtime) == start


def test_default_stop_is_the_edge_of_the_foes_sprite():
    runtime = _runtime()
    start = _hero_x(runtime)
    runtime.start_move("hero", target_id="mimic", duration=0.1)
    runtime.update(0.2)
    # mimic's frame is 32 wide: half of it plus a small margin short of its anchor
    assert _hero_x(runtime) - start == pytest.approx((232 - (16 + 8)) - 72, abs=1.0)
