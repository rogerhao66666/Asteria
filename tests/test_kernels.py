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


@pytest.mark.parametrize("kind", ["rain", "snow", "leaves", "dust"])
@pytest.mark.parametrize("wind", [0.0, 60.0, -900.0])
def test_numpy_weather_moves_and_draws_exactly_like_the_reference(kind, wind, restore_kernels):
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import numpy as np
    import pygame

    from asteria.runtime.weather import WeatherSystem

    pygame.init()
    systems = {}
    for kernel in ("python", "numpy"):
        kernels.use(kernel)
        systems[kernel] = WeatherSystem(320, 180, seed="w")
    for frame in range(90):
        camera = (frame * 0.7, -frame * 0.3)
        for system in systems.values():
            system.update(1 / 60 if frame % 5 else 1 / 20, kind, 0.9, 400, wind, camera=camera, scale=2.0)
        ref, fast = systems["python"], systems["numpy"]
        assert (fast.x, fast.y, fast.size, fast.phase) == (ref.x, ref.y, ref.size, ref.phase), frame
        if frame % 15 == 0:
            frames = []
            for system in (ref, fast):
                screen = pygame.Surface((320, 180))
                screen.fill((20, 40, 60))
                assert system.draw(pygame, screen, wind) == system.count
                frames.append(pygame.surfarray.array3d(screen))
            assert np.array_equal(*frames), f"{kind} pixels differ at frame {frame}"
            assert (frames[0] != (20, 40, 60)).any()


# -- D22 A2: cross pairs and projectiles ------------------------------------------------------------------------
def _cross_boxes(rng, n, spread, size):
    x0 = [rng.uniform(-spread, spread) for _ in range(n)]
    y0 = [rng.uniform(-spread, spread) for _ in range(n)]
    w = [rng.uniform(0.5, size) for _ in range(n)]
    h = [rng.uniform(0.5, size) for _ in range(n)]
    return (x0, y0, [x + d for x, d in zip(x0, w, strict=True)], [y + d for y, d in zip(y0, h, strict=True)])


@pytest.mark.parametrize("seed", range(6))
def test_cross_pairs_match_brute_force_in_both_sets(seed):
    rng = random.Random(seed)
    a = _cross_boxes(rng, 150, 300, 40 if seed % 2 else 150)  # large boxes span many cells
    b = _cross_boxes(rng, 220, 300, 20)
    b[0][5], b[2][5] = a[2][3], a[2][3] + 4  # an edge that only touches: not a hit
    b[1][5], b[3][5] = a[1][3], a[3][3]
    brute = sorted(
        (i, j)
        for i in range(150)
        for j in range(220)
        if a[0][i] < b[2][j] and b[0][j] < a[2][i] and a[1][i] < b[3][j] and b[1][j] < a[3][i]
    )
    assert brute and (3, 5) not in brute
    for cell in (16.0, 64.0, 500.0):
        assert _python.aabb_cross_pairs(a, b, cell) == brute
        assert np_kernels.aabb_cross_pairs(a, b, cell) == brute
    touching = sorted(
        (i, j)
        for i in range(150)
        for j in range(220)
        if a[0][i] <= b[2][j] and b[0][j] <= a[2][i] and a[1][i] <= b[3][j] and b[1][j] <= a[3][i]
    )
    assert (3, 5) in touching
    assert _python.aabb_cross_pairs(a, b, 64.0, touching=True) == touching
    assert np_kernels.aabb_cross_pairs(a, b, 64.0, touching=True) == touching
    assert np_kernels.aabb_cross_pairs(([], [], [], []), b) == _python.aabb_cross_pairs(([], [], [], []), b) == []


def test_numpy_projectiles_match_the_reference_step_by_step():
    rng = random.Random(7)
    rows = []
    for uid in range(400):
        turn = rng.choice((0.0, 0.0, 3.0, 8.0))
        rows.append(
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
                turn,
                uid,
            )
        )
    ref, fast = _python.ProjectileStore(), np_kernels.ProjectileStore()
    ref.add(rows)
    fast.add(rows)
    for frame in range(150):
        dt = 1 / 60 if frame % 5 else 1 / 30
        n = len(ref)
        tx = [float("nan") if k % 3 == 0 else 50.0 * (k % 7) - 150.0 for k in range(n)]
        ty = [float("nan") if k % 3 == 0 else -20.0 * (k % 5) for k in range(n)]
        if frame % 11 == 0 and n:
            tx[0], ty[0] = ref.x[0], ref.y[0]  # target exactly on the projectile
        ref.step(dt, tx, ty)
        fast.step(dt, tx, ty)
        for name in _python.PROJECTILE_FIELDS:
            assert fast.column(name) == ref.column(name), f"{name} differs at frame {frame}"
        assert [list(map(float, c)) for c in fast.boxes()] == [list(c) for c in ref.boxes()]
        assert fast.expired() == ref.expired()
        if frame % 4 == 0 and n:
            ref.set_velocity(0, -10, 5)
            fast.set_velocity(0, -10, 5)
        alive = [i for i in range(len(ref)) if i not in set(ref.expired())]
        ref.keep(alive)
        fast.keep(alive)
    assert 0 < len(ref) < 400


def test_homing_turns_at_most_its_rate_then_aims_straight():
    store = _python.ProjectileStore()
    store.add([(0, 0, 100, 0, 0, 0, 10, 1, 1, 3.0, 1)])
    store.step(0.1, [0.0], [100.0])  # target straight below: turn 0.3 rad toward it
    import math

    assert math.atan2(store.vy[0], store.vx[0]) == pytest.approx(0.3)
    assert math.hypot(store.vx[0], store.vy[0]) == pytest.approx(100)
    store.step(1.0, [store.x[0] + 10.0], [store.y[0] + 10.0])  # within 3 rad: straight at it
    assert math.atan2(store.vy[0], store.vx[0]) == pytest.approx(math.pi / 4)
