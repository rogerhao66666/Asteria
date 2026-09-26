import pytest

from asteria.graphics.character_placement import (
    CharacterPlacement,
    frame_rect_at_standing_point,
    integer_preview_scale,
    standing_point_for_cell,
)


def test_standard_actor_fills_one_cell_from_bottom_center():
    standing = standing_point_for_cell(0, 0)
    placement = CharacterPlacement((48, 48))

    assert standing == (24.0, 48.0)
    assert frame_rect_at_standing_point(standing, placement) == (0.0, 0.0, 48.0, 48.0)


def test_large_actor_preserves_native_size_at_same_standing_point():
    standing = standing_point_for_cell(0, 0)
    placement = CharacterPlacement((96, 96))

    assert frame_rect_at_standing_point(standing, placement) == (-24.0, -48.0, 72.0, 48.0)


def test_object_character_semantics_remain_explicit():
    regular = CharacterPlacement((48, 48))
    object_character = CharacterPlacement((48, 48), object_character=True)

    assert regular.object_character is False
    assert object_character.object_character is True
    assert object_character.pivot == (0.5, 1.0)


def test_preview_scale_is_integer_and_never_stretches():
    assert integer_preview_scale((48, 48), (288, 250)) == 5
    assert integer_preview_scale((96, 96), (48, 48)) == 1
    with pytest.raises(ValueError, match="dimensions"):
        integer_preview_scale((0, 48), (288, 288))


def test_custom_tile_size_uses_bottom_center_standing_point():
    assert standing_point_for_cell(2, 3, tile_size=(32, 24)) == (80.0, 96.0)
