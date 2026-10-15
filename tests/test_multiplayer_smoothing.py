"""Client-side smoothing: snapshot interpolation and input prediction with reconciliation."""

import pytest

from asteria.multiplayer.smoothing import InputPredictor, SnapshotInterpolator


def test_samples_blend_the_two_snapshots_around_the_delayed_time():
    view = SnapshotInterpolator(delay=0.1)
    view.push(0.0, {"a": (0, 0)})
    view.push(0.1, {"a": (10, 0)})
    view.push(0.2, {"a": (10, 20)})
    assert view.sample(0.15)["a"] == pytest.approx((5.0, 0.0))  # 0.05 into the first span
    assert view.sample(0.25)["a"] == pytest.approx((10.0, 10.0))


def test_before_the_first_snapshot_it_holds_and_unknown_ids_just_appear():
    view = SnapshotInterpolator(delay=0.1)
    assert view.sample(5.0) == {}
    view.push(1.0, {"a": (1, 1)})
    assert view.sample(0.0) == {"a": (1.0, 1.0)}
    view.push(2.0, {"a": (3, 1), "b": (9, 9)})
    mid = view.sample(1.6)  # b was not in the first snapshot: it is simply there
    assert mid["a"] == pytest.approx((2.0, 1.0)) and mid["b"] == (9.0, 9.0)


def test_extrapolation_is_limited_and_then_holds():
    view = SnapshotInterpolator(delay=0.0, max_extrapolation=0.2)
    view.push(0.0, {"a": (0, 0)})
    view.push(1.0, {"a": (10, 0)})
    assert view.sample(1.1)["a"] == pytest.approx((11.0, 0.0))
    assert view.sample(9.0)["a"] == pytest.approx((12.0, 0.0))  # capped at 0.2 s ahead
    flat = SnapshotInterpolator(delay=0.0, max_extrapolation=0.0)
    flat.push(0.0, {"a": (0, 0)})
    flat.push(1.0, {"a": (10, 0)})
    assert flat.sample(5.0)["a"] == (10.0, 0.0)


def test_old_or_duplicate_snapshots_are_ignored_and_capacity_is_bounded():
    view = SnapshotInterpolator(capacity=3)
    assert view.push(1.0, {"a": (0, 0)}) and not view.push(1.0, {"a": (5, 5)})
    assert not view.push(0.5, {"a": (5, 5)})
    for t in range(2, 10):
        view.push(float(t), {"a": (t, 0)})
    assert len(view._snapshots) == 3
    with pytest.raises(ValueError):
        SnapshotInterpolator(capacity=1)


def test_prediction_moves_at_once_and_a_correct_server_changes_nothing():
    mover = InputPredictor((0, 0), speed=10)
    for sequence in range(1, 4):
        mover.apply_local(sequence, 1, 0, 0.1)
    assert mover.position == pytest.approx((3.0, 0.0)) and mover.pending == 3
    error = mover.reconcile((1.0, 0.0), acked_sequence=1)  # the server agrees about input 1
    assert error == pytest.approx(0.0) and mover.pending == 2
    assert mover.position == pytest.approx((3.0, 0.0)) and mover.corrections == 0


def test_a_server_that_disagrees_pulls_the_player_and_replays_pending_inputs():
    mover = InputPredictor((0, 0), speed=10)
    for sequence in range(1, 5):
        mover.apply_local(sequence, 1, 0, 0.1)
    error = mover.reconcile((0.5, 0.0), acked_sequence=2)  # the server stopped it short (a wall)
    assert mover.pending == 2
    assert mover.position == pytest.approx((2.5, 0.0))  # 0.5 + two replayed steps of 1.0
    assert error == pytest.approx(1.5) and mover.corrections == 1


def test_diagonals_are_not_faster_and_the_pending_queue_is_capped():
    mover = InputPredictor((0, 0), speed=10, max_pending=3)
    mover.apply_local(1, 1, 1, 1.0)
    assert mover.position == pytest.approx((10 / 2**0.5, 10 / 2**0.5))
    for sequence in range(2, 10):
        mover.apply_local(sequence, 0, 0, 0.1)
    assert mover.pending == 3
