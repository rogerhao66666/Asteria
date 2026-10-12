"""D22-C1 / C2: column storage for hot components, the per-type scene index, and the column kernels."""

import random
from array import array

import pytest

from asteria import kernels
from asteria.core import Entity, Scene, Transform, deserialize_component, serialize_component
from asteria.core.columns import column_spec
from asteria.core.scene_transition import carry_persistent_entities
from asteria.kernels import _python
from asteria.runtime.character_control import CharacterController2DComponent, Hitbox2DComponent
from asteria.runtime.collision import Collider2DComponent, CollisionWorld
from asteria.runtime.component_registry import default_component_registry

np_kernels = pytest.importorskip("asteria.kernels._numpy")


def _entity(scene, name, x=0.0, y=0.0, *components):
    entity = Entity(name)
    entity.add_component(Transform(x, y))
    for component in components:
        entity.add_component(component)
    return scene.add_entity(entity) if scene is not None else entity


def test_hot_components_keep_numbers_in_scene_columns_and_plain_attributes_still_work():
    assert {"x", "y", "rotation", "scale_x", "scale_y"} <= set(column_spec(Transform))
    assert "parent_id" not in column_spec(Transform) and "enabled" not in column_spec(Collider2DComponent)
    assert {"intent_x", "push_x", "control_lock", "facing_code"} <= set(column_spec(CharacterController2DComponent))
    scene = Scene("S")
    hero = _entity(scene, "Hero", 3.0, 4.0, CharacterController2DComponent())
    table = scene.columns(Transform)
    slot = scene.slot_of(hero)
    assert table.data["x"][slot] == 3.0 and hero.get(Transform)._ctable is table
    hero.get(Transform).x = 9.5
    assert table.data["x"][slot] == 9.5
    table.data["y"][slot] = -2.0  # a system writing the column is what game code sees
    assert hero.get(Transform).y == -2.0
    controller = hero.get(CharacterController2DComponent)
    controller.facing = "left"
    assert scene.columns(CharacterController2DComponent).data["facing_code"][slot] == 2
    controller.jump = True
    assert controller.jump is True
    with pytest.raises(ValueError):
        controller.facing = "north"
    with pytest.raises(TypeError):
        hero.get(Transform).x = "far"


def test_values_survive_detach_reattach_scene_moves_and_serialization():
    registry = default_component_registry()
    first, second = Scene("A"), Scene("B")
    hero = _entity(first, "Hero", 1.0, 2.0, Collider2DComponent())
    hero.get(Collider2DComponent).width = 33.0
    first.detach_entity(hero)  # undo-style detach: values come back onto the components
    t = hero.get(Transform)
    assert t._ctable is None and (t.x, t.y) == (1.0, 2.0) and hero.get(Collider2DComponent).width == 33.0
    t.x = 5.0
    second.add_entity(hero)
    assert second.columns(Transform).data["x"][second.slot_of(hero)] == 5.0
    data = serialize_component(hero.get(Collider2DComponent))
    assert data["fields"]["width"] == 33.0 and isinstance(data["fields"]["one_way"], bool)
    assert deserialize_component(data, registry).width == 33.0
    hero.remove_component(Collider2DComponent)
    assert second.columns(Collider2DComponent).slots() == []
    hero.add_component(Hitbox2DComponent()).width = 7.0
    assert second.columns(Hitbox2DComponent).data["width"][second.slot_of(hero)] == 7.0


def test_slots_are_reused_and_queries_follow_scene_order():
    scene = Scene("S")
    a, b, c = (_entity(scene, n) for n in "abc")
    slot_b = scene.slot_of(b)
    scene.remove_entity(b)
    d = _entity(scene, "d")
    assert scene.slot_of(d) == slot_b and scene.get_entity(b.id) is None
    assert [e.name for e, _ in scene.query(Transform)] == ["a", "c", "d"]
    scene.move_entity(d, 0)
    assert [e.name for e, _ in scene.query(Transform)] == ["d", "a", "c"]
    c.add_component(Collider2DComponent())
    a.add_component(Collider2DComponent())
    assert [e.name for e, *_ in scene.query(Transform, Collider2DComponent)] == ["a", "c"]
    a.enabled = False
    assert [e.name for e, *_ in scene.query(Collider2DComponent)] == ["c"]


def test_adding_and_removing_during_an_update_waits_for_the_flush():
    from asteria.core.system import System

    scene = Scene("S")
    keep = _entity(scene, "keep", 1.0)
    late = _entity(None, "late", 2.0)

    class Spawner(System):
        def update(self, scene, dt):
            scene.add_entity(late)
            scene.remove_entity(keep)
            assert late.get(Transform)._ctable is None  # not attached until the update ends

    scene.scheduler.add(Spawner())
    scene.update(0.016)
    assert scene.get_entity(keep.id) is None and late.get(Transform)._ctable is scene.columns(Transform)
    assert [e.name for e, _ in scene.query(Transform)] == ["late"]


def test_persistent_entities_carry_their_values_to_the_next_scene():
    from asteria.core import PersistentComponent

    old, new = Scene("Old"), Scene("New")
    hero = _entity(old, "Hero", 12.0, -3.0, PersistentComponent())
    carry_persistent_entities(old, new)
    assert new.columns(Transform).data["x"][new.slot_of(hero)] == 12.0 and hero.get(Transform).y == -3.0


def test_collision_world_from_columns_matches_the_shapes_built_one_by_one():
    from asteria.runtime.collision import shape_of

    rng = random.Random(5)
    scene = Scene("S")
    parent = _entity(scene, "Parent", 50.0, 0.0)
    for k in range(40):
        collider = Collider2DComponent()
        collider.shape = "circle" if k % 3 == 0 else "box"
        collider.width, collider.height, collider.radius = rng.uniform(2, 30), rng.uniform(2, 30), rng.uniform(1, 9)
        collider.offset_x, collider.layer, collider.one_way = rng.uniform(-5, 5), k % 4, k % 5 == 0
        child = _entity(scene, f"C{k}", rng.uniform(-100, 100), rng.uniform(-100, 100), collider)
        if k % 7 == 0:
            child.get(Transform).parent_id = parent.id
    world = CollisionWorld.from_scene(scene)
    expected = {e.id: shape_of(e, c) for e, c in scene.query(Collider2DComponent)}
    assert world.shapes == expected and list(world.shapes) == list(expected) and world.parented


# -- column kernels: numpy == python -------------------------------------------------------------------------------
def _columns(rng, spec, n):
    data = {}
    for name, typecode in spec.items():
        if typecode == "d":
            data[name] = array("d", (rng.uniform(-50, 50) for _ in range(n)))
        elif typecode == "b":
            data[name] = array("b", (rng.random() < 0.5 for _ in range(n)))
        else:
            data[name] = array("q", (rng.randrange(0, 4) for _ in range(n)))
    return data


def _copy(data):
    return {k: array(v.typecode, v) for k, v in data.items()}


@pytest.mark.parametrize("seed", range(4))
def test_column_kernels_match_the_reference(seed):
    rng = random.Random(seed)
    n = 120
    controller = _columns(rng, column_spec(CharacterController2DComponent), n)
    for s in range(n):
        controller["control_lock"][s] = rng.choice((0.0, 0.0, 0.01, 0.3))
        controller["half_width"][s] = controller["half_height"][s] = rng.uniform(2, 8)
        controller["knockback_decay"][s] = rng.choice((0.0, 8.0, 10.0))
        controller["push_x"][s] = rng.choice((0.0, 0.3, 120.0))
    transform = _columns(rng, column_spec(Transform), n)
    boxes = _columns(rng, column_spec(Hitbox2DComponent), n)
    collider = _columns(rng, column_spec(Collider2DComponent), n)
    slots = sorted(rng.sample(range(n), 80))
    a, b = _copy(controller), _copy(controller)
    ref = _python.topdown_prepare(a, slots, 1 / 60)
    fast = np_kernels.topdown_prepare(b, slots, 1 / 60)
    assert list(fast) == list(ref) and a == b
    dx, dy, mx, my, locked = ref
    assert np_kernels.facing_codes(dx, dy, [a["facing_code"][s] for s in slots], locked) == _python.facing_codes(
        dx, dy, [a["facing_code"][s] for s in slots], locked
    )
    assert [list(map(float, c)) for c in np_kernels.moved_boxes(a, transform, slots, mx, my)] == list(
        map(list, _python.moved_boxes(a, transform, slots, mx, my))
    )
    pa, pb = _copy(a), _copy(a)
    _python.decay_push(pa, slots, 1 / 60, 0.5)
    np_kernels.decay_push(pb, slots, 1 / 60, 0.5)
    assert pa == pb
    ta, tb = _copy(transform), _copy(transform)
    _python.add_to_column(ta["x"], slots, mx)
    np_kernels.add_to_column(tb["x"], slots, mx)
    assert ta == tb
    codes = [rng.randrange(4) for _ in slots]
    assert list(np_kernels.box_columns(transform, boxes, slots, codes)) == list(
        _python.box_columns(transform, boxes, slots, codes)
    )
    circle = [rng.random() < 0.3 for _ in slots]
    assert list(np_kernels.collider_columns(transform, collider, slots, circle)) == list(
        _python.collider_columns(transform, collider, slots, circle)
    )
    walls = ([rng.uniform(-60, 60) for _ in range(30)] for _ in range(3))
    cx, cy, radius = (list(w) for w in walls)
    radius = [abs(r) / 4 for r in radius]
    movers = _python.moved_boxes(a, transform, slots, mx, my)
    wall_boxes = (
        [x - r - 5 for x, r in zip(cx, radius)],
        [y - r - 5 for y, r in zip(cy, radius)],
        [x + r + 5 for x, r in zip(cx, radius)],
        [y + r + 5 for y, r in zip(cy, radius)],
    )
    pairs = _python.aabb_cross_pairs(movers, wall_boxes, 32.0, touching=True)
    args = (
        movers,
        (cx, cy, radius),
        pairs,
        [rng.choice((1, 2, 0xFFFFFFFF)) for _ in slots],
        [rng.choice((-1, 0, 3)) for _ in slots],
        [1 << rng.randrange(3) for _ in range(30)],
        [rng.random() < 0.2 for _ in range(30)],
        [rng.random() < 0.4 for _ in range(30)],
    )
    assert pairs and np_kernels.blocked_rows(*args) == _python.blocked_rows(*args)


def test_the_arpg_stress_scene_ends_identically_with_both_kernel_sets(resource_root):
    from pathlib import Path

    from asteria.validation.arpg_stress import run_arpg_stress

    repo = Path(__file__).resolve().parents[1]
    reports = [
        run_arpg_stress(repo, enemies=40, projectiles=60, frames=45, kernel=name) for name in kernels.available()
    ]
    assert len({(r["arpg"]["hits"], r["arpg"]["damage_events"], r["arpg"]["state_digest"]) for r in reports}) == 1
    assert reports[0]["arpg"]["hits"] > 0
