"""D23: the native (C++) kernel set gives exactly the python reference results - the returned
values and the column buffers it writes in place; without the compiled library the engine keeps
working on numpy."""

import copy
import math
import random
from array import array

import pytest

from asteria import kernels
from asteria.kernels import _python as py


def _native():
    try:
        from asteria.kernels import _native
    except ImportError:
        pytest.skip("native kernels not built (python -m asteria.kernels.build_native)")
    return _native


def _same(a, b):
    """Equal, treating nan as equal to nan, element by element."""
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def _boxes(rng, n, spread=500.0, size=40.0):
    x = [rng.uniform(-spread, spread) for _ in range(n)]
    y = [rng.uniform(-spread, spread) for _ in range(n)]
    w = [rng.choice([0.0, rng.uniform(0, size)]) for _ in range(n)]
    h = [rng.choice([0.0, rng.uniform(0, size)]) for _ in range(n)]
    return (
        x,
        y,
        [a + b for a, b in zip(x, w, strict=True)],
        [a + b for a, b in zip(y, h, strict=True)],
    )


def _doubles(rng, n, low=-50.0, high=50.0, zeros=0.2):
    return array("d", [0.0 if rng.random() < zeros else rng.uniform(low, high) for _ in range(n)])


# -- broad phase ----------------------------------------------------------------------------
def test_native_cross_pairs_and_self_pairs_match_the_reference_exactly():
    native = _native()
    rng = random.Random(7)
    for _ in range(150):
        a, b = _boxes(rng, rng.randint(0, 60)), _boxes(rng, rng.randint(0, 60))
        cell = rng.choice([8.0, 64.0, 300.0])
        for touching in (False, True):
            expected = py.aabb_cross_pairs(a, b, cell, touching)
            assert native.aabb_cross_pairs(a, b, cell, touching) == expected
        assert native.aabb_pairs(*a, cell) == py.aabb_pairs(*a, cell)


def test_native_handles_edges_touching_negative_cells_and_many_results():
    native = _native()
    a = ([0.0, -64.0], [0.0, -64.0], [10.0, -1.0], [10.0, -1.0])
    b = ([10.0, -1.0], [10.0, -1.0], [20.0, 0.0], [20.0, 0.0])
    for touching in (False, True):
        assert native.aabb_cross_pairs(a, b, 64.0, touching) == py.aabb_cross_pairs(
            a, b, 64.0, touching
        )
    n = 120  # every box overlaps every other: more results than the first buffer guess
    pile = ([0.0] * n, [0.0] * n, [5.0] * n, [5.0] * n)
    assert len(native.aabb_cross_pairs(pile, pile, 64.0)) == n * n
    assert len(native.aabb_pairs(*pile, 64.0)) == n * (n - 1) // 2
    with pytest.raises(ValueError):
        native.aabb_pairs(*pile, 0)


# -- stores ---------------------------------------------------------------------------------
def test_native_particles_and_weather_match_frame_by_frame():
    native = _native()
    rng = random.Random(3)
    rows = [
        (
            rng.uniform(-90, 90),
            rng.uniform(-90, 90),
            rng.uniform(-40, 40),
            rng.uniform(-40, 40),
            rng.uniform(0, 0.5),
            rng.uniform(0.3, 2.0),
            rng.uniform(0.5, 2.0),
            rng.uniform(0, 6),
            rng.uniform(-3, 3),
        )
        for _ in range(300)
    ]
    ref, fast = py.ParticleStore(), native.ParticleStore()
    ref.add(rows)
    fast.add(rows)
    for frame in range(90):
        ref.step(1 / 60, 0.0, 30.0, 0.98)
        fast.step(1 / 60, 0.0, 30.0, 0.98)
        assert len(ref) == len(fast)
        if frame % 7 == 0:
            ref.shift(1.5, -2.0)
            fast.shift(1.5, -2.0)
        colors = ((255, 0, 0, 255), (0, 0, 255, 0))
        assert fast.views(2, 4, *colors, 1.0) == ref.views(2, 4, *colors, 1.0)
    assert 0 < len(ref) < 300
    rows = [
        (
            rng.uniform(-80, 400),
            rng.uniform(-30, 300),
            rng.uniform(60, 260),
            rng.uniform(1, 4),
            rng.uniform(0, 6),
        )
        for _ in range(250)
    ]
    ref, fast = py.WeatherStore(), native.WeatherStore()
    ref.add(rows)
    fast.add(rows)
    for frame in range(60):
        args = (1 / 60, 40.0, frame / 60, frame % 2 == 0, 0.5, -0.25, 320, 180)
        assert fast.step(*args) == ref.step(*args)
        for name in py.WEATHER_FIELDS:
            assert fast.column(name) == ref.column(name)
    fast.truncate(100)  # a non-contiguous view must still work
    ref.truncate(100)
    assert fast.step(1 / 60, 0.0, 1.0, True, 0, 0, 320, 180) == ref.step(
        1 / 60, 0.0, 1.0, True, 0, 0, 320, 180
    )


def test_native_projectiles_match_the_reference_step_by_step():
    native = _native()
    rng = random.Random(7)
    rows = [
        (
            rng.uniform(-200, 200),
            rng.uniform(-200, 200),
            rng.uniform(-150, 150),
            rng.uniform(-150, 150),
            rng.choice((0.0, 400.0)),
            0.0,
            rng.uniform(0.2, 4.0),
            rng.uniform(1, 6),
            rng.uniform(1, 6),
            rng.choice((0.0, 0.0, 3.0, 8.0)),
            uid,
        )
        for uid in range(400)
    ]
    ref, fast = py.ProjectileStore(), native.ProjectileStore()
    ref.add(rows)
    fast.add(rows)
    for frame in range(150):
        dt = 1 / 60 if frame % 5 else 1 / 30
        n = len(ref)
        tx = [float("nan") if k % 3 == 0 else 50.0 * (k % 7) - 150.0 for k in range(n)]
        ty = [float("nan") if k % 3 == 0 else -20.0 * (k % 5) for k in range(n)]
        if frame % 11 == 0 and n:
            tx[0], ty[0] = ref.x[0], ref.y[0]  # a target exactly on the projectile
        ref.step(dt, tx if frame % 4 else None, ty if frame % 4 else None)
        fast.step(dt, tx if frame % 4 else None, ty if frame % 4 else None)
        for name in py.PROJECTILE_FIELDS:
            assert fast.column(name) == ref.column(name), f"{name} differs at frame {frame}"
        assert fast.expired() == ref.expired()
        alive = [i for i in range(len(ref)) if i not in set(ref.expired())]
        ref.keep(alive)
        fast.keep(alive)
    assert 0 < len(ref) < 400


# -- columns by slot ------------------------------------------------------------------------
def _controller_columns(rng, n):
    return {
        "intent_x": _doubles(rng, n, -1.5, 1.5),
        "intent_y": _doubles(rng, n, -1.5, 1.5),
        "control_lock": array("d", [rng.choice([0.0, 0.0, 0.01, 0.2, 1.0]) for _ in range(n)]),
        "jump": array("b", [rng.choice([0, 1]) for _ in range(n)]),
        "speed": _doubles(rng, n, 10, 90),
        "speed_override": _doubles(rng, n, 0, 150, zeros=0.7),
        "push_x": _doubles(rng, n, -200, 200),
        "push_y": _doubles(rng, n, -200, 200),
        "knockback_decay": array("d", [rng.choice([4.0, 8.0, 12.0]) for _ in range(n)]),
        "half_width": _doubles(rng, n, 2, 9, zeros=0),
        "half_height": _doubles(rng, n, 2, 9, zeros=0),
    }


def test_native_column_kernels_match_and_write_the_same_buffers():
    native = _native()
    rng = random.Random(11)
    n = 90
    for _ in range(25):
        transform = {"x": _doubles(rng, n, -300, 300), "y": _doubles(rng, n, -300, 300)}
        collider = {
            "offset_x": _doubles(rng, n),
            "offset_y": _doubles(rng, n),
            "width": _doubles(rng, n, 1, 40, zeros=0),
            "height": _doubles(rng, n, 1, 40, zeros=0),
            "radius": _doubles(rng, n, 1, 20, zeros=0),
        }
        slots = sorted(rng.sample(range(n), rng.randint(0, n)))
        circle = [rng.random() < 0.4 for _ in slots]
        assert native.collider_columns(transform, collider, slots, circle) == py.collider_columns(
            transform, collider, slots, circle
        )
        c_py, c_nat = _controller_columns(rng, n), None
        c_nat = copy.deepcopy(c_py)
        dt = rng.choice([1 / 60, 1 / 30, 0.0167])
        got = native.topdown_prepare(c_nat, slots, dt)
        want = py.topdown_prepare(c_py, slots, dt)
        assert _same(list(map(list, got)), list(map(list, want)))
        assert c_nat == c_py  # the lock countdown and the cleared jumps were written alike
        mx, my = want[2], want[3]
        got_boxes = native.moved_boxes(c_nat, transform, slots, mx, my)
        want_boxes = py.moved_boxes(c_py, transform, slots, mx, my)
        assert [list(map(float, g)) for g in got_boxes] == [list(w) for w in want_boxes]
        values = [rng.uniform(-3, 3) for _ in slots]
        a, b = array("d", transform["x"]), array("d", transform["x"])
        native.add_to_column(a, slots, values)
        py.add_to_column(b, slots, values)
        assert a == b
        native.decay_push(c_nat, slots, dt, 0.5)
        py.decay_push(c_py, slots, dt, 0.5)
        assert c_nat == c_py
        hurt = {
            "offset_x": _doubles(rng, n),
            "offset_y": _doubles(rng, n),
            "width": _doubles(rng, n, 1, 30, zeros=0),
            "height": _doubles(rng, n, 1, 30, zeros=0),
            "follow_facing": array("b", [rng.choice([0, 1]) for _ in range(n)]),
        }
        codes = [rng.randrange(4) for _ in slots]
        assert native.box_columns(transform, hurt, slots, codes) == py.box_columns(
            transform, hurt, slots, codes
        )
        dx = [rng.choice([0.0, rng.uniform(-1, 1), 1e-12]) for _ in range(40)]
        dy = [rng.choice([0.0, rng.uniform(-1, 1), -1e-12]) for _ in range(40)]
        cur = [rng.randrange(4) for _ in range(40)]
        held = [rng.random() < 0.3 for _ in range(40)]
        assert native.facing_codes(dx, dy, cur, held) == py.facing_codes(dx, dy, cur, held)


def test_native_blocked_rows_match_the_reference():
    native = _native()
    rng = random.Random(5)
    for _ in range(60):
        nm, nw = rng.randint(1, 30), rng.randint(1, 30)
        boxes = _boxes(rng, nm, 100, 20)
        cx = [rng.uniform(-100, 100) for _ in range(nw)]
        cy = [rng.uniform(-100, 100) for _ in range(nw)]
        radius = [rng.uniform(1, 25) for _ in range(nw)]
        pairs = sorted({(rng.randrange(nm), rng.randrange(nw)) for _ in range(80)})
        args = (
            boxes,
            (cx, cy, radius),
            pairs,
            [rng.choice([0xFFFFFFFF, 1, 2, 3]) for _ in range(nm)],
            [rng.choice([-1, rng.randrange(nw)]) for _ in range(nm)],
            [rng.choice([1, 2, 4]) for _ in range(nw)],
            [rng.random() < 0.3 for _ in range(nw)],
            [rng.random() < 0.4 for _ in range(nw)],
        )
        assert native.blocked_rows(*args) == py.blocked_rows(*args)
    assert native.blocked_rows(boxes, ([], [], []), [], [], [], [], [], []) == []


def test_native_field_ai_matches_the_reference():
    native = _native()
    rng = random.Random(9)
    n = 70
    for _ in range(40):

        def columns():
            return (
                {
                    "mode_code": array("q", [rng.choice([0, 1, 2, 3, 4, 5]) for _ in range(n)]),
                    "home_x": _doubles(rng, n, -200, 200),
                    "home_y": _doubles(rng, n, -200, 200),
                    "detect_radius": _doubles(rng, n, 10, 120),
                    "lose_radius": _doubles(rng, n, 60, 220),
                    "arrive_distance": _doubles(rng, n, 0, 12),
                },
                {"x": _doubles(rng, n, -200, 200), "y": _doubles(rng, n, -200, 200)},
                {
                    "intent_x": _doubles(rng, n),
                    "intent_y": _doubles(rng, n),
                    "speed": _doubles(rng, n, 10, 80, zeros=0.1),
                },
            )

        state = random.getstate()
        f1, t1, c1 = columns()
        random.setstate(state)
        f2, t2, c2 = copy.deepcopy((f1, t1, c1))
        slots = sorted(rng.sample(range(n), rng.randint(0, n)))
        behaviour = [rng.choice([0, 1, 2, 3, 4, 5]) for _ in slots]
        tx = [rng.choice([float("nan"), rng.uniform(-200, 200)]) for _ in slots]
        ty = [rng.uniform(-200, 200) for _ in slots]
        has = [rng.random() < 0.7 for _ in slots]
        dt = rng.choice([1 / 60, 1 / 30])
        want = py.fieldai_step(f1, t1, c1, slots, behaviour, tx, ty, has, dt)
        got = native.fieldai_step(f2, t2, c2, slots, behaviour, tx, ty, has, dt)
        assert got == want
        for left, right in zip((f1, t1, c1), (f2, t2, c2), strict=True):
            for name in left:
                assert _same(list(left[name]), list(right[name])), name


def test_native_falls_back_to_numpy_for_unexpected_column_types():
    native = _native()
    ints = lambda *v: array("q", v)  # noqa: E731 - int columns, not the float ones C++ reads
    transform = {"x": ints(1, 2), "y": ints(3, 4)}
    collider = {k: ints(1, 2) for k in ("offset_x", "offset_y", "width", "height", "radius")}
    assert native.collider_columns(transform, collider, [0, 1], [False, True]) == (
        py.collider_columns(transform, collider, [0, 1], [False, True])
    )


def test_the_native_set_is_selectable_and_never_required():
    names = kernels.available()
    assert "python" in names
    if "native" in names:
        previous = kernels.use("native")
        try:
            assert kernels.active().NAME == "native"
        finally:
            kernels.use(previous)
    with pytest.raises(ValueError):
        kernels.use("nope")
