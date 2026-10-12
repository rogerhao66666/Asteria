"""D21: compute kernels - the numpy set must give the reference (python) results exactly."""

import random

import pytest

from asteria import kernels
from asteria.kernels import _python
from asteria.presentation.particles import PRESETS, ParticleSystem, preset

np_kernels = pytest.importorskip("asteria.kernels._numpy")


@pytest.fixture
def restore_kernels():
    previous = kernels.active().NAME
    yield
    kernels.use(previous)


def _system(kernel, definition, **kwargs):
    kernels.use(kernel)
    return ParticleSystem(definition, **kwargs)


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_numpy_particles_match_the_reference_frame_by_frame(name, restore_kernels):
    definition = preset(name, f"fx.{name}").replace(local=True)
    ref = _system("python", definition, seed=4, emit_for=1.0)
    fast = _system("numpy", definition, seed=4, emit_for=1.0)
    for frame in range(150):
        dt = 1 / 60 if frame % 7 else 1 / 30
        for system in (ref, fast):
            system.update(dt)
            system.move_to(frame * 0.5, -frame * 0.25)
        assert fast.views() == ref.views(), f"{name} differs at frame {frame}"
        assert fast.count == ref.count and fast.finished == ref.finished
    assert ref.spawned > 0


def test_an_empty_store_is_fine_in_both_sets():
    for kernel in (_python, np_kernels):
        store = kernel.ParticleStore()
        store.step(0.1, 0.0, 10.0, 1.0)
        store.shift(1.0, 1.0)
        assert len(store) == 0 and store.views(1.0, 2.0, (0, 0, 0, 0), (9, 9, 9, 9), 1.0) == []


def _boxes(rng, n, width, height, size):
    x0 = [rng.uniform(0, width) for _ in range(n)]
    y0 = [rng.uniform(0, height) for _ in range(n)]
    sizes = [rng.choice((0.0, size, size * 3)) for _ in range(n)]
    return x0, y0, [x + s for x, s in zip(x0, sizes)], [y + s for y, s in zip(y0, sizes)]


@pytest.mark.parametrize(("n", "width", "height"), [(0, 10, 10), (1, 10, 10), (300, 800, 800), (400, 60, 3000)])
def test_numpy_broad_phase_finds_exactly_the_reference_pairs(n, width, height):
    x0, y0, x1, y1 = _boxes(random.Random(n), n, width, height, 12.0)
    expected = _python.aabb_pairs(x0, y0, x1, y1, 64.0)
    assert np_kernels.aabb_pairs(x0, y0, x1, y1, 64.0) == expected
    brute = sorted(
        (i, j)
        for i in range(n)
        for j in range(i + 1, n)
        if x0[i] <= x1[j] and x0[j] <= x1[i] and y0[i] <= y1[j] and y0[j] <= y1[i]
    )
    assert expected == brute


def test_touching_and_identical_boxes_count_as_pairs():
    # A touches B on a cell border (x = 64); C sits exactly on A; D is apart
    x0, y0, x1, y1 = [48, 64, 48, 200], [0, 0, 0, 0], [64, 80, 64, 210], [10, 10, 10, 10]
    for kernel in (_python, np_kernels):
        assert kernel.aabb_pairs(x0, y0, x1, y1, 64.0) == [(0, 1), (0, 2), (1, 2)]
        with pytest.raises(ValueError):
            kernel.aabb_pairs(x0, y0, x1, y1, 0)


def test_kernel_selection(monkeypatch, restore_kernels):
    assert kernels.available()[0] == "numpy" and "python" in kernels.available()
    assert kernels.use("python") is not None and kernels.active().NAME == "python"
    kernels.use("auto")
    assert kernels.active().NAME == "numpy"
    with pytest.raises(ValueError):
        kernels.use("cobol")
    monkeypatch.setattr(kernels, "_active", None)
    monkeypatch.setenv("ASTERIA_KERNELS", "python")
    assert kernels.active().NAME == "python"


def test_collision_contacts_are_the_same_with_either_kernel(restore_kernels):
    from asteria.core import Entity, Scene, Transform
    from asteria.runtime import Collider2DComponent, CollisionWorld

    rng = random.Random(11)
    scene = Scene("S")
    for i in range(400):
        entity = scene.add_entity(Entity(f"E{i}"))
        entity.add_component(Transform(rng.uniform(0, 600), rng.uniform(0, 600)))
        collider = entity.add_component(Collider2DComponent())
        collider.shape = rng.choice(("box", "circle"))
        collider.width = collider.height = rng.uniform(4, 30)
        collider.radius = rng.uniform(2, 15)
    results = {}
    for kernel in ("python", "numpy"):
        kernels.use(kernel)
        results[kernel] = CollisionWorld.from_scene(scene).contacts()
    assert results["numpy"] == results["python"] and len(results["python"]) > 20
