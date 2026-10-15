"""Grid pathfinding: shortest routes around walls, smoothing, snapping and path following."""

import pytest

from asteria.runtime.navigation import NavGrid, PathFollower

CELL = 10.0


def _grid(walls=(), size=10, **options):
    blocked_cells = set(walls)

    def blocked(x, y):
        return (int(x // CELL), int(y // CELL)) in blocked_cells

    return NavGrid((0, 0, size * CELL, size * CELL), CELL, blocked, **options), blocked_cells


def _length(points, start):
    total, last = 0.0, start
    for p in points:
        total += ((p[0] - last[0]) ** 2 + (p[1] - last[1]) ** 2) ** 0.5
        last = p
    return total


def test_an_open_field_gives_a_straight_path():
    grid, _ = _grid()
    path = grid.find_path((5, 5), (95, 5))
    assert path == [(95.0, 5.0)]  # smoothing leaves just the goal


def test_the_path_goes_around_a_wall():
    wall = {(5, y) for y in range(0, 8)}
    grid, _ = _grid(wall)
    path = grid.find_path((5, 45), (95, 45))
    assert path is not None and path[-1] == (95.0, 45.0)
    assert any(py > 75 for _, py in path)  # it goes through the gap at the bottom
    # no waypoint inside a wall cell, and no straight leg crosses one
    assert not any((int(px // CELL), int(py // CELL)) in wall for px, py in path)
    last = (5, 45)
    for p in path:
        assert grid.line_clear(grid.cell_of(*last), grid.cell_of(*p)), (last, p)
        last = p


def test_no_way_through_returns_none():
    wall = {(5, y) for y in range(10)}
    grid, _ = _grid(wall)
    assert grid.find_path((5, 5), (95, 5)) is None


def test_no_corner_cutting_between_two_diagonal_walls():
    walls = {(1, 0), (0, 1)}  # the only way from (0,0) to (1,1) would squeeze between them
    grid, _ = _grid(walls, size=3)
    assert grid.find_path((5, 5), (15, 15)) is None


def test_diagonals_can_be_switched_off():
    grid, _ = _grid(diagonal=False)
    path = grid.find_path((5, 5), (25, 25))
    assert path == [(25.0, 25.0)]  # smoothing still straightens an open field
    assert grid.diagonal is False


def test_a_blocked_goal_snaps_to_the_nearest_free_cell_or_fails_without_snapping():
    grid, walls = _grid({(5, 5)})
    path = grid.find_path((5, 5), (55, 55))
    assert path is not None and grid.cell_of(*path[-1]) != (5, 5)
    assert grid.find_path((5, 5), (55, 55), snap_goal=False) is None


def test_extra_blocked_cells_are_avoided_for_one_search_only():
    grid, _ = _grid(size=5)
    detour = grid.find_path((5, 25), (45, 25), extra_blocked={(2, 2)})
    assert any(py != 25 for _, py in detour)
    assert grid.find_path((5, 25), (45, 25)) == [(45.0, 25.0)]


def test_start_and_goal_in_one_cell_and_outside_the_map():
    grid, _ = _grid()
    assert grid.find_path((52, 52), (58, 54)) == [(58.0, 54.0)]
    assert grid.find_path((5, 5), (500, 500)) is not None  # outside: snapped to the nearest edge
    assert grid.find_path((5, 5), (500, 500), snap_goal=False) is None


def test_max_nodes_gives_up_on_huge_searches():
    wall = {(5, y) for y in range(0, 9)}
    grid, _ = _grid(wall)
    assert grid.find_path((5, 5), (95, 5), max_nodes=3) is None


def test_agent_margin_keeps_clear_of_walls():
    grid, _ = _grid({(3, 3)}, size=7, margin=4.0)
    assert grid.is_blocked(3, 3)
    snug, _ = _grid({(3, 3)}, size=7)
    assert snug.find_path((5, 35), (65, 35)) is not None


def test_changing_the_world_needs_a_cache_clear():
    state = {"wall": False}
    grid = NavGrid((0, 0, 30, 10), 10, lambda x, y: state["wall"] and x > 10 and x < 20)
    assert grid.find_path((5, 5), (25, 5)) is not None
    state["wall"] = True
    assert grid.find_path((5, 5), (25, 5)) is not None  # still remembers the old answer
    grid.clear_cache()
    assert grid.find_path((5, 5), (25, 5)) is None


def test_follower_walks_the_waypoints_at_its_speed():
    follower = PathFollower([(10.0, 0.0), (10.0, 10.0)], speed=10.0)
    x, y = follower.step(0.0, 0.0, 0.5)
    assert (x, y) == (5.0, 0.0) and not follower.done
    x, y = follower.step(x, y, 1.0)  # 10 units: 5 to the corner, 5 up
    assert (x, y) == (10.0, 5.0)
    x, y = follower.step(x, y, 1.0)
    assert (x, y) == (10.0, 10.0) and follower.done
    assert follower.step(x, y, 1.0) == (10.0, 10.0)


def test_validation():
    with pytest.raises(ValueError):
        NavGrid((0, 0, 10, 10), 0, lambda x, y: False)
    with pytest.raises(ValueError):
        NavGrid((0, 0, 0, 10), 5, lambda x, y: False)
    with pytest.raises(ValueError):
        PathFollower([], 0)
