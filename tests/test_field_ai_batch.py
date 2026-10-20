"""Field AI without controllers in one batch: the same end state as the one-by-one update, with
every kernel set (``fieldai_free_step`` and ``points_blocked``)."""

import math
import random
from array import array

import pytest

from asteria import kernels
from asteria.core import Entity, Scene, Transform
from asteria.kernels import _python
from asteria.runtime import FieldAIComponent, FieldAISystem
from asteria.runtime.character_control import (
    CharacterController2DComponent,
    CharacterControllerSystem,
)
from asteria.runtime.collision import ALL_LAYERS, Collider2DComponent, CollisionWorld
from asteria.runtime.game_session import _EitherBlocks

DT = 1.0 / 60.0


def _set(component, **values):
    for key, value in values.items():
        setattr(component, key, value)
    return component


class _Tiles:
    """A tile-like query the kernels cannot see into: asked point by point."""

    def collides_world_point(self, x, y):
        return 70.0 <= x < 86.0 and -40.0 <= y < 40.0


def _wall(scene, name, x, y, **collider):
    wall = scene.add_entity(Entity(name))
    wall.add_component(Transform(x, y))
    wall.add_component(_set(Collider2DComponent(), **collider))
    return wall


def _scene():
    scene = Scene("S")
    player = scene.add_entity(Entity("P"))
    player.add_component(Transform(0.0, 0.0))
    player.add_component(_set(Collider2DComponent(), width=12.0, height=12.0))
    decoy = scene.add_entity(Entity("Decoy"))
    decoy.add_component(Transform(-120.0, 90.0))
    _wall(scene, "Box", 40.0, -30.0, width=30.0, height=50.0)
    _wall(scene, "Round", -50.0, 40.0, shape="circle", radius=18.0)
    _wall(scene, "Rise", 20.0, 70.0, shape="slope_right", width=60.0, height=30.0)
    _wall(scene, "Fall", -80.0, -60.0, shape="slope_left", width=50.0, height=40.0)
    _wall(scene, "Ledge", -10.0, -90.0, width=80.0, height=6.0, one_way=True)
    _wall(scene, "Trigger", 100.0, 100.0, width=60.0, height=60.0, is_trigger=True)
    _wall(scene, "Ladder", -100.0, 0.0, width=10.0, height=80.0, ladder=True)
    _wall(scene, "Glass", 0.0, 120.0, width=200.0, height=10.0, layer=3)  # skipped by mask 0b111
    _wall(scene, "Pole", 128.0, -64.0, shape="circle", radius=0.0)  # on a cell corner
    rng = random.Random(5)
    behaviours = ("chase", "flee", "wander", "patrol", "idle")
    masks = {}
    for k in range(90):
        enemy = scene.add_entity(Entity(f"E{k}"))
        enemy.add_component(Transform(rng.uniform(-150, 150), rng.uniform(-150, 150)))
        spec = _set(
            FieldAIComponent(),
            behaviour=behaviours[k % 5],
            speed=rng.choice((30.0, 55.0, 90.0, 0.0 if k == 7 else 40.0)),
            detect_radius=rng.uniform(40.0, 140.0),
            lose_radius=rng.uniform(140.0, 200.0),
            wander_radius=rng.uniform(5.0, 60.0),
            arrive_distance=rng.choice((0.0, 2.0, 5.0)),
            patrol_path=("0,0; 60,10; -30,40" if k % 3 else "" if k % 4 else "5,5"),
        )
        if k % 11 == 0:
            spec.target_entity_id = decoy.id
        elif k % 13 == 0:
            spec.target_entity_id = "nobody"  # a target that is not in the scene: go home
        enemy.add_component(spec)
        if k % 4 == 1:
            enemy.add_component(_set(Collider2DComponent(), width=10.0, height=10.0))
        elif k % 4 == 2:
            enemy.add_component(_set(Collider2DComponent(), shape="circle", radius=6.0))
        if k % 7 == 3:  # some steer through a controller: their rng draws interleave
            enemy.add_component(_set(CharacterController2DComponent(), speed=50.0))
        if k % 5 == 0:
            masks[enemy.id] = 0b111
    return scene, player, masks


def _run(batched, monkeypatch, frames=150):
    scene, player, masks = _scene()
    frame = {"world": None}

    def blocking(entity):
        if frame["world"] is None:
            frame["world"] = CollisionWorld.from_scene(scene)
        query = frame["world"].blocking_query(
            mask=masks.get(entity.id, ALL_LAYERS), exclude={entity.id, player.id}
        )
        index = int(entity.name[1:])
        if index % 3 == 0:
            return _EitherBlocks(query, _Tiles())
        return None if index % 17 == 5 else query

    system = FieldAISystem(blocking, rng=random.Random(9), default_target_id=player.id)
    walks = []
    walk = system._walk
    if batched:

        def spy(*args):
            walks.append(walk(*args))
            return walks[-1]

        monkeypatch.setattr(system, "_walk", spy)
    else:
        monkeypatch.setattr(system, "_walk", lambda *args: False)
    scene.scheduler.add(system)
    scene.scheduler.add(CharacterControllerSystem())
    for index in range(frames):
        frame["world"] = None
        transform = player.get(Transform)
        transform.x = 80.0 * math.sin(index / 25.0)
        transform.y = 60.0 * math.cos(index / 40.0)
        if index == 70:  # behaviour changed by a script while its mode lingers
            scene.get_entity(next(e.id for e in scene.entities() if e.name == "E3")).get(
                FieldAIComponent
            ).behaviour = "chase"
        scene.update(0.0 if index == 30 else DT)
    if batched:
        assert walks and all(walks)  # every update took the batch
    return [
        (e.name, t.x.hex(), t.y.hex(), system.state(e.id))
        for e, t in scene.query(Transform)
        if e.name.startswith("E")
    ] + [system.rng.random()]


def test_batched_field_ai_ends_exactly_like_the_one_by_one_update(monkeypatch):
    previous = kernels.use("python")
    try:
        before = _run(False, monkeypatch)
    finally:
        kernels.use(previous)
    modes = {state.mode for *_, state in before[:-1]}
    assert modes >= {"chase", "flee", "wander", "patrol", "idle", "return"}
    for name in kernels.available():
        previous = kernels.use(name)
        try:
            assert _run(True, monkeypatch) == before, name
        finally:
            kernels.use(previous)


def test_an_entity_chasing_a_batched_mover_keeps_the_one_by_one_order(monkeypatch):
    def run(batched):
        scene = Scene("S")
        leader = scene.add_entity(Entity("Leader"))
        leader.add_component(Transform(0.0, 0.0))
        leader.add_component(_set(FieldAIComponent(), behaviour="wander", wander_radius=80.0))
        follower = scene.add_entity(Entity("Follower"))
        follower.add_component(Transform(30.0, 0.0))
        follower.add_component(
            _set(FieldAIComponent(), behaviour="chase", target_entity_id=leader.id)
        )
        system = FieldAISystem(rng=random.Random(3))
        if not batched:
            monkeypatch.setattr(system, "_walk", lambda *args: False)
        scene.scheduler.add(system)
        for _ in range(90):
            scene.update(DT)
        return [(t.x.hex(), t.y.hex(), system.state(e.id)) for e, t in scene.query(Transform)]

    assert run(True) == run(False)


# -- the kernels themselves -------------------------------------------------------------------
def _free_inputs(rng, n=400):
    slots = rng.sample(range(n + 50), n)
    size = n + 50

    def doubles(low, high):
        return array("d", (rng.uniform(low, high) for _ in range(size)))

    f = {
        "mode_code": array("q", (rng.randrange(6) for _ in range(size))),
        "home_x": doubles(-100, 100),
        "home_y": doubles(-100, 100),
        "detect_radius": doubles(0, 150),
        "lose_radius": doubles(100, 250),
        "arrive_distance": array("d", (rng.choice((0.0, 2.0, 1e-9)) for _ in range(size))),
        "speed": array("d", (rng.choice((0.0, 30.0, 1e-3, 400.0)) for _ in range(size))),
    }
    t = {"x": doubles(-150, 150), "y": doubles(-150, 150)}
    for s in rng.sample(range(size), 30):  # standing on the target, home or goal
        t["x"][s], t["y"][s] = f["home_x"][s], f["home_y"][s]
    behaviour = [rng.randrange(5) for _ in slots]
    has = [rng.random() < 0.8 for _ in slots]
    tx = [rng.uniform(-150, 150) if h else float("nan") for h in has]
    ty = [rng.uniform(-150, 150) if h else float("nan") for h in has]
    goal = [rng.random() < 0.9 for _ in slots]
    gx = [rng.uniform(-150, 150) if g else float("nan") for g in goal]
    gy = [rng.uniform(-150, 150) if g else float("nan") for g in goal]
    return f, t, slots, behaviour, tx, ty, has, gx, gy, goal


def _copy(columns):
    return {name: array(column.typecode, column) for name, column in columns.items()}


def _kernel_sets():
    return [kernels._load(name) for name in kernels.available()]


@pytest.mark.parametrize("dt", [DT, 0.0, 0.5])
def test_free_step_kernels_match_the_reference(dt):
    rng = random.Random(11)
    for _ in range(5):
        f, *rest = _free_inputs(rng)
        start = _copy(f)
        reference = (*_python.fieldai_free_step(start, *rest, dt), start)
        for kernel in _kernel_sets():
            modes = _copy(f)
            status, mx, my = kernel.fieldai_free_step(modes, *rest, dt)
            assert status == reference[0], kernel.NAME
            assert [v.hex() for v in mx + my] == [v.hex() for v in reference[1] + reference[2]]
            assert modes == reference[3], kernel.NAME
        assert set(reference[0]) == {0, 1, 2} or dt <= 0


def test_points_blocked_kernels_match_the_reference():
    rng = random.Random(4)
    for _ in range(20):
        nw = rng.randrange(0, 60)
        cx = [rng.uniform(-200, 200) for _ in range(nw)]
        cy = [rng.uniform(-200, 200) for _ in range(nw)]
        shapes = [rng.randrange(4) for _ in range(nw)]
        radius = [rng.choice((0.0, rng.uniform(1, 40))) for _ in range(nw)]
        hw = [
            r if s == 1 else rng.choice((0.0, rng.uniform(1, 50))) for s, r in zip(shapes, radius)
        ]
        hh = [r if s == 1 else rng.uniform(0, 50) for s, r in zip(shapes, radius)]
        solids = (
            [c - h for c, h in zip(cx, hw)],
            [c - h for c, h in zip(cy, hh)],
            [c + h for c, h in zip(cx, hw)],
            [c + h for c, h in zip(cy, hh)],
        )
        bit = [1 << rng.randrange(4) for _ in range(nw)]
        n = 300
        px = [rng.uniform(-220, 220) for _ in range(n)]
        py = [rng.uniform(-220, 220) for _ in range(n)]
        for i in range(0, min(n, nw * 3), 3):  # on edges, corners and circle rims
            j = i // 3
            px[i] = rng.choice((solids[0][j], solids[2][j], cx[j] + radius[j]))
            py[i] = rng.choice((solids[1][j], solids[3][j], cy[j]))
        mask = [rng.choice((ALL_LAYERS, 0b101, 0)) for _ in range(n)]
        starts, skip = [0], []
        for _ in range(n):
            skip.extend(rng.sample(range(nw), min(nw, rng.randrange(3))))
            starts.append(len(skip))
        args = (px, py, solids, (cx, cy, radius), shapes, bit, 64.0, mask, starts, skip)
        reference = _python.points_blocked(*args)
        assert reference or nw < 10  # a few small walls may catch no point
        for kernel in _kernel_sets():
            assert kernel.points_blocked(*args) == reference, kernel.NAME


def test_points_blocked_agrees_with_query_point():
    scene, _, _ = _scene()
    world = CollisionWorld.from_scene(scene)
    shapes, solids = world.solid_columns()
    cx, cy, radius, bit, _, _, index_of = world.solid_extras()
    rng = random.Random(8)
    px = [rng.uniform(-160, 160) for _ in range(3000)]
    py = [rng.uniform(-160, 160) for _ in range(3000)]
    ids = list(index_of)
    excluded = [set(rng.sample(ids, 2)) for _ in px]
    starts, skip = [0], []
    for exclude in excluded:
        skip.extend(index_of[e] for e in exclude)
        starts.append(len(skip))
    expected = [
        i
        for i, (x, y) in enumerate(zip(px, py))
        if world.query_point(x, y, mask=0b111, exclude=excluded[i])
    ]
    assert expected
    codes = world.solid_shape_codes()
    for kernel in _kernel_sets():
        assert (
            kernel.points_blocked(
                px, py, solids, (cx, cy, radius), codes, bit, 64.0, [0b111] * 3000, starts, skip
            )
            == expected
        ), kernel.NAME
