"""A sprite sheet may say how tall its character really is (``body_height``), so health bars and
command menus sit on the body instead of on empty room in the frame."""

import pytest

from asteria.runtime.battle_visuals import member_body_height


def test_frame_height_is_the_default():
    assert member_body_height({}, 96, 1.0) == 96.0
    assert member_body_height(None, 96, 2.0) == 48.0


def test_body_height_overrides_the_frame():
    assert member_body_height({"body_height": 60}, 96, 1.0) == 60.0
    assert member_body_height({"body_height": 60}, 96, 2.0) == 30.0


def test_a_bad_body_height_falls_back_to_the_frame():
    for bad in (0, -5, "tall", None):
        assert member_body_height({"body_height": bad}, 96, 1.0) == pytest.approx(96.0)
