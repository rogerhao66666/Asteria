"""Heights on a grid map: walls of height, one-way edges, bridges (runtime/grid_heights.py)."""

from __future__ import annotations

from asteria.runtime.grid_heights import GridHeights, compatible


def heights_of(cells, over=()):
    def keys_at(x, y):
        return cells.get((int(x // 16), int(y // 16)), ())

    return GridHeights(keys_at, over=over)


def test_a_person_does_not_step_onto_another_height():
    map_ = heights_of({(0, 0): ("tag:height_3",), (1, 0): ("tag:height_4",)})
    assert map_.stopped((0, 0), (1, 0), 3)
    assert not map_.stopped((0, 0), (1, 0), 4)


def test_height_zero_lets_anybody_on_and_off():
    map_ = heights_of(
        {(0, 0): ("tag:height_3",), (1, 0): ("tag:height_0",), (2, 0): ("tag:height_4",)}
    )
    assert not map_.stopped((0, 0), (1, 0), 3)
    height, drawn = map_.stepped((0, 0), (1, 0), 3, 3)
    assert (height, drawn) == (0, 3)  # stairs: free to go on, still drawn as it was
    assert not map_.stopped((1, 0), (2, 0), height)
    assert map_.stepped((1, 0), (2, 0), height, drawn) == (4, 4)


def test_a_crossing_keeps_the_height_it_was_entered_with():
    map_ = heights_of(
        {(0, 0): ("tag:height_4",), (2, 0): ("tag:height_3",), (3, 0): ("tag:height_4",)}
    )
    assert not map_.stopped((0, 0), (1, 0), 4)  # no height tag on (1, 0)
    assert map_.stepped((0, 0), (1, 0), 4, 4) == (4, 4)
    assert map_.stepped((1, 0), (2, 0), 4, 4) == (4, 4)  # leaving it keeps it too
    assert map_.stopped((1, 0), (2, 0), 4)


def test_a_one_way_edge_stops_both_sides_of_it():
    map_ = heights_of({(0, 0): ("tag:block_right",), (0, 2): ("tag:block_up",)})
    assert map_.stopped((0, 0), (1, 0), 0)  # cannot leave that way
    assert map_.stopped((1, 0), (0, 0), 0)  # nor come in over that same edge
    assert not map_.stopped((0, 1), (0, 0), 0)  # the other edges are open
    assert map_.stopped((0, 2), (0, 1), 0)  # cannot leave upward
    assert map_.stopped((0, 1), (0, 2), 0)  # nor come in over that same edge
    assert not map_.stopped((0, 3), (0, 2), 0)  # the other edge is open


def test_a_map_without_the_tags_changes_nothing():
    map_ = heights_of({})
    assert not map_.stopped((0, 0), (1, 0), 3)
    assert map_.placed((0, 0)) == (0, 0)
    assert map_.stepped((0, 0), (1, 0), 0, 0) == (0, 0)


def test_people_at_different_heights_pass_each_other():
    assert not compatible(3, 4)
    assert compatible(3, 3) and compatible(0, 4) and compatible(3, 0)
