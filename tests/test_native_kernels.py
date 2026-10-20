"""D23: the native (C++) kernel set gives exactly the python reference results - the returned
values and the column buffers it writes in place - with numpy installed and without it (an
exported game on a plain Python); without the compiled library the engine keeps working on numpy
or python."""

import copy
import math
import os
import random
import subprocess
import sys
from array import array
from pathlib import Path

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


def test_native_falls_back_for_unexpected_column_types():
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


def test_native_blocked_boxes_match_cross_pairs_then_blocked_rows():
    """The fused broad phase + blocking test gives the rows the two separate steps give."""
    native = _native()
    try:
        from asteria.kernels import _numpy as npk
    except ImportError:  # the run without numpy
        npk = None

    rng = random.Random(8)
    for _ in range(80):
        nm, nw = rng.randint(0, 40), rng.randint(0, 40)
        boxes = _boxes(rng, nm, 120, 30)
        solids = _boxes(rng, nw, 120, 30)
        walls = (
            [(a + b) / 2 for a, b in zip(solids[0], solids[2], strict=True)],
            [(a + b) / 2 for a, b in zip(solids[1], solids[3], strict=True)],
            [rng.uniform(1, 20) for _ in range(nw)],
        )
        args = (
            boxes,
            solids,
            walls,
            rng.choice([8.0, 32.0, 64.0]),
            [rng.choice([0xFFFFFFFF, 1, 2, 3]) for _ in range(nm)],
            [rng.choice([-1, rng.randrange(nw)]) if nw else -1 for _ in range(nm)],
            [rng.choice([1, 2, 4]) for _ in range(nw)],
            [rng.random() < 0.3 for _ in range(nw)],
            [rng.random() < 0.4 for _ in range(nw)],
        )
        pairs = py.aabb_cross_pairs(boxes, solids, args[3], touching=True)
        expected = py.blocked_rows(boxes, walls, pairs, *args[4:]) if pairs else []
        assert py.blocked_boxes(*args) == expected
        if npk is not None:
            assert npk.blocked_boxes(*args) == expected
        assert native.blocked_boxes(*args) == expected


def test_native_stores_follow_the_reference_through_every_method():
    """Rows written, kept (any order, negative = from the end), cut and read back alike."""
    native = _native()
    rng = random.Random(4)
    rows = [tuple(rng.uniform(-50, 50) for _ in py.PROJECTILE_FIELDS) for _ in range(30)]
    ref, fast = py.ProjectileStore(), native.ProjectileStore()
    for store in (ref, fast):
        store.add(rows)
        store.add([])
        store.set_velocity(-1, 3.5, -2)
        store.set_values(0, x=1.25, gravity=7, uid=99)
        store.keep([5, 0, -1, 7, 7, 29])
    for name in py.PROJECTILE_FIELDS:
        assert fast.column(name) == ref.column(name), name
    assert [list(map(float, c)) for c in fast.boxes()] == list(map(list, ref.boxes()))
    assert fast.expired() == ref.expired()
    for store in (ref, fast):
        with pytest.raises(IndexError):
            store.keep([6])
        with pytest.raises(IndexError):
            store.set_values(6, x=0.0)
    with pytest.raises(ValueError):
        fast.add([(1.0, 2.0)])
    fast.keep([])
    assert len(fast) == 0 and fast.boxes()[0] is not None and fast.expired() == []
    fast.step(1 / 60, [], [])
    weather = [tuple(rng.uniform(0, 100) for _ in py.WEATHER_FIELDS) for _ in range(12)]
    ref, fast = py.WeatherStore(), native.WeatherStore()
    for store in (ref, fast):
        store.add(weather)
        store.set_row(-2, (1.0, 2.0, 3.0, 4.0, 5.0))
        store.truncate(50)
        store.truncate(9)
    for name in py.WEATHER_FIELDS:
        assert fast.column(name) == ref.column(name), name
    fast.truncate(0)
    assert len(fast) == 0 and fast.step(1 / 60, 0, 0, True, 0, 0, 10, 10) == []
    particles = native.ParticleStore()
    particles.shift(1.0, 1.0)  # empty: nothing to move
    particles.step(1 / 60, 0.0, 0.0, 1.0)
    assert len(particles) == 0 and particles.views(1, 2, (0,) * 4, (0,) * 4, 1.0) == []


def test_native_kernels_accept_numpy_columns_and_odd_values():
    """Inputs the engine may hand over: numpy columns, iterators, float flags and indices."""
    native = _native()
    a = ([0.0, 3.0], [0.0, 3.0], [4.0, 9.0], [4.0, 9.0])
    want = py.aabb_pairs(*a, 8.0)
    assert native.aabb_pairs(*(iter(c) for c in a), 8.0) == want
    try:
        import numpy as np
    except ImportError:
        np = None
    if np is not None:
        assert native.aabb_pairs(*(np.asarray(c) for c in a), 8.0) == want
        assert native.aabb_pairs(*(np.asarray(c)[::-1][::-1] for c in a), 8.0) == want
    held = [0.5, 0, 2, -1]
    args = ([1.0, 1.0, 0.0, 0.0], [0.0] * 4, [0.0, 1.0, 2.0, 3.0], held)
    assert native.facing_codes(*args) == py.facing_codes(*args)
    walls = ([5.0], [5.0], [1.0])
    boxes = ([0.0], [0.0], [10.0], [10.0])
    for flags in ([0.5], [2], [True], [0]):
        call = (boxes, walls, [(0, 0)], [1], [-1], [1], [0], flags)
        assert native.blocked_rows(*call) == py.blocked_rows(*call)


_WITHOUT_NUMPY = """
import sys
sys.modules["numpy"] = None  # import numpy now fails, as on a Python without it
import pytest
from asteria import kernels
from asteria.kernels import _native
assert _native.np is None and _native._fallback.NAME == "python"
assert kernels.available()[0] == "native", kernels.available()
sys.exit(pytest.main(["-q", "-p", "no:cacheprovider", sys.argv[1], "-k", "not without_numpy"]))
"""


def test_native_kernels_match_the_reference_without_numpy():
    """This whole file again in a Python where numpy cannot be imported."""
    _native()
    result = subprocess.run(
        [sys.executable, "-c", _WITHOUT_NUMPY, __file__],
        capture_output=True,
        text=True,
        check=False,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert " passed" in result.stdout and "skipped" not in result.stdout, result.stdout


@pytest.mark.skipif(sys.platform != "darwin", reason="universal binaries are a macOS thing")
def test_the_macos_library_is_universal():
    native = _native()
    if not Path("/usr/bin/lipo").is_file():
        pytest.skip("no lipo")
    info = subprocess.run(
        ["/usr/bin/lipo", "-archs", str(native._path)], capture_output=True, text=True
    )
    archs = set(info.stdout.split())
    if archs == {"arm64"} or archs == {"x86_64"}:
        pytest.skip(f"built for this machine only ({info.stdout.strip()}): no universal compiler")
    assert {"arm64", "x86_64"} <= archs, info.stdout + info.stderr
    if Path("/usr/bin/vtool").is_file() and not os.environ.get("MACOSX_DEPLOYMENT_TARGET"):
        build = subprocess.run(
            ["/usr/bin/vtool", "-show-build", str(native._path)], capture_output=True, text=True
        )
        mins = [line.split()[1] for line in build.stdout.splitlines() if "minos" in line]
        assert mins and all(m == "11.0" for m in mins), build.stdout  # loads on older Macs


def test_the_build_falls_back_to_this_machine_when_universal_fails(monkeypatch):
    from asteria.kernels import build_native

    commands = []

    def run(command, **_):
        commands.append(command)
        failed = "-arch" in command
        return subprocess.CompletedProcess(command, 1 if failed else 0, "", "")

    monkeypatch.setattr(build_native.subprocess, "run", run)
    build_native.build(verbose=False, universal=True)
    assert len(commands) == 2 and "-arch" in commands[0] and "-arch" not in commands[1]
    commands.clear()
    build_native.build(verbose=False, universal=False)
    assert len(commands) == 1 and "-arch" not in commands[0]


_FROM_PYZ = """
import sys, zipfile
from pathlib import Path
sys.modules["numpy"] = None  # the player's Python has no numpy
pyz = Path(sys.argv[1])
main = {"__name__": "packaged_game", "__file__": str(pyz / "__main__.py")}
exec(zipfile.ZipFile(pyz).read("__main__.py"), main)
target = main["unpack"](pyz)
sys.path.insert(0, str(target / "engine"))
from asteria import kernels
from asteria.kernels import _native, _python
assert Path(_native._path).is_relative_to(target), _native._path
a = ([0.0, 3.0], [0.0, 3.0], [4.0, 9.0], [4.0, 9.0])
assert _native.aabb_pairs(*a, 8.0) == _python.aabb_pairs(*a, 8.0)
print(kernels.available()[0])
"""


def test_an_exported_pyz_loads_the_native_library_after_unpacking(tmp_path):
    _native()
    from asteria.project_tools import _copy_engine, build_pyz

    _copy_engine(tmp_path / "game" / "engine")
    pyz = build_pyz(tmp_path / "game", tmp_path / "out" / "Game.pyz", name="KernelCheck")
    home = tmp_path / "home"
    env = {**os.environ, "HOME": str(home), "LOCALAPPDATA": str(home)}
    env.pop("XDG_CACHE_HOME", None)
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-I", "-c", _FROM_PYZ, str(pyz)],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.split() == ["native"], result.stdout
