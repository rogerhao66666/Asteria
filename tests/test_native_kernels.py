"""D23: the native (C++) kernel set gives exactly the python reference results; without the
compiled library the engine keeps working on numpy."""

import random

import pytest

from asteria import kernels
from asteria.kernels import _python


def _native():
    try:
        from asteria.kernels import _native
    except ImportError:
        pytest.skip("native kernels not built (python -m asteria.kernels.build_native)")
    return _native


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


def test_native_cross_pairs_match_the_reference_exactly():
    native = _native()
    rng = random.Random(7)
    for _ in range(150):
        a, b = _boxes(rng, rng.randint(0, 60)), _boxes(rng, rng.randint(0, 60))
        for touching in (False, True):
            cell = rng.choice([8.0, 64.0, 300.0])
            expected = _python.aabb_cross_pairs(a, b, cell, touching)
            assert native.aabb_cross_pairs(a, b, cell, touching) == expected


def test_native_handles_edges_touching_negative_cells_and_many_results():
    native = _native()
    a = ([0.0, -64.0], [0.0, -64.0], [10.0, -1.0], [10.0, -1.0])
    b = ([10.0, -1.0], [10.0, -1.0], [20.0, 0.0], [20.0, 0.0])
    assert native.aabb_cross_pairs(a, b, 64.0, False) == _python.aabb_cross_pairs(
        a, b, 64.0, False
    )
    assert native.aabb_cross_pairs(a, b, 64.0, True) == _python.aabb_cross_pairs(a, b, 64.0, True)
    n = 120  # every box overlaps every other: the result is larger than the first buffer guess
    pile = ([0.0] * n, [0.0] * n, [5.0] * n, [5.0] * n)
    assert len(native.aabb_cross_pairs(pile, pile, 64.0)) == n * n


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
