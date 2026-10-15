"""Screen pictures: show, move with tweens, sprite-sheet cells, click hit-testing, saving."""

import pytest

from asteria.events.context import EventContext
from asteria.runtime.pictures import PictureManager

SIZE = lambda picture: (64, 32)  # noqa: E731  (a 64x32 image for every picture)


def _manager():
    return PictureManager(EventContext())


def test_show_get_and_erase():
    pictures = _manager()
    pictures.show("logo", "img_logo", 10, 20, scale=2, opacity=0.5, layer=3)
    picture = pictures.get("logo")
    assert (picture.x, picture.y, picture.scale, picture.opacity, picture.layer) == (
        10,
        20,
        2,
        0.5,
        3,
    )
    assert pictures.ids() == ("logo",) and pictures.exists("logo")
    pictures.erase("logo")
    assert pictures.get("logo") is None and not pictures.context.variables
    pictures.erase("never_shown")  # harmless


def test_showing_again_replaces_everything():
    pictures = _manager()
    pictures.show("p", "a", click_event="old")
    pictures.show("p", "b", 5, 5)
    assert pictures.get("p").asset_id == "b" and pictures.get("p").click_event == ""


def test_pictures_are_ordered_by_layer_then_id():
    pictures = _manager()
    pictures.show("b", "x", layer=1)
    pictures.show("a", "x", layer=1)
    pictures.show("top", "x", layer=9)
    pictures.show("bottom", "x", layer=-1)
    assert [p.picture_id for p in pictures.pictures()] == ["bottom", "a", "b", "top"]


def test_move_is_instant_without_a_duration_and_tweens_with_one():
    pictures = _manager()
    pictures.show("p", "a", 0, 0)
    pictures.move("p", x=100, opacity=0.0)
    assert pictures.get("p").x == 100 and pictures.get("p").opacity == 0.0
    pictures.move("p", x=0, y=50, duration=2.0)
    assert pictures.get("p").x == 100  # the tween starts where it was
    pictures.update(1.0)
    assert pictures.get("p").x == pytest.approx(50) and pictures.get("p").y == pytest.approx(25)
    pictures.update(1.5)
    assert pictures.get("p").x == 0 and pictures.get("p").y == 50
    assert pictures._tweens == {}


def test_easing_shapes_the_tween_and_the_saved_value_is_the_end():
    pictures = _manager()
    pictures.show("p", "a", 0, 0)
    pictures.move("p", x=10, duration=1.0, easing="ease_in")
    pictures.update(0.5)
    assert pictures.get("p").x == pytest.approx(2.5)
    restored = PictureManager(EventContext.from_data(pictures.context.to_data()))
    assert restored.get("p").x == 10  # a save in the middle loads at the end


def test_sprite_sheet_cells():
    pictures = _manager()
    pictures.show("sheet", "a", columns=4, rows=2, frame=5)
    picture = pictures.get("sheet")
    assert picture.cell(64, 32) == (16, 16, 16, 16)  # frame 5: column 1, row 1
    pictures.set_frame("sheet", 9)  # wraps around the 8 cells
    assert pictures.get("sheet").cell(64, 32) == (16, 0, 16, 16)
    assert pictures.get("sheet").rect(64, 32) == (0, 0, 16, 16)


def test_hit_test_finds_the_topmost_clickable_picture():
    pictures = _manager()
    pictures.show("back", "a", 0, 0, click_event="back_ev", layer=0)
    pictures.show("front", "b", 32, 0, click_event="front_ev", layer=1)
    pictures.show("decor", "c", 0, 0, layer=5)  # no click event: never hit
    pictures.show("ghost", "d", 0, 0, click_event="ghost_ev", opacity=0.0, layer=6)
    assert pictures.hit_test(40, 10, SIZE).picture_id == "front"
    assert pictures.hit_test(10, 10, SIZE).picture_id == "back"
    assert pictures.hit_test(200, 10, SIZE) is None
    assert pictures.hit_test(10, 10, lambda p: None) is None  # unknown size: skipped
    pictures.move("back", x=1000)
    assert pictures.hit_test(10, 10, SIZE) is None


def test_scale_changes_the_clickable_area():
    pictures = _manager()
    pictures.show("p", "a", 0, 0, scale=2.0, click_event="ev")
    assert pictures.hit_test(100, 50, SIZE) is not None  # 64x32 at 2x covers up to 128x64
    assert pictures.hit_test(130, 50, SIZE) is None


def test_validation():
    pictures = _manager()
    for args in (("", "a"), ("a.b", "a"), ("p", "")):
        with pytest.raises(ValueError):
            pictures.show(*args)
    with pytest.raises(ValueError):
        pictures.show("p", "a", scale=0)
    with pytest.raises(ValueError):
        pictures.show("p", "a", columns=0)
    with pytest.raises(KeyError):
        pictures.move("ghost", x=1)
    pictures.show("p", "a")
    with pytest.raises(ValueError):
        pictures.move("p", x=1, easing="bounce")
    with pytest.raises(ValueError):
        pictures.move("p", scale=-1)
