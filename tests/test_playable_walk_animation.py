from asteria.runtime.playable_test_runtime import (
    field_player_render_size,
    walking_pattern_index,
    walking_row_index,
)


def test_moving_walk_uses_rpg_maker_cycle_without_skipping_the_return_pose():
    assert [walking_pattern_index(step) for step in range(0, 40, 8)] == [0, 1, 2, 1, 0]


def test_walk_facing_uses_the_native_mv_row_order_for_eye_colors():
    assert walking_row_index("down") == 0
    assert walking_row_index("left") == 1
    assert walking_row_index("right") == 2
    assert walking_row_index("up") == 3
    assert walking_row_index("unknown") == 0


def test_field_render_preserves_custom_48px_square_character_aspect_ratio():
    assert field_player_render_size((48, 48)) == (64, 64)


def test_field_render_keeps_native_mv_character_height_at_existing_scale():
    assert field_player_render_size((32, 48)) == (64, 96)
