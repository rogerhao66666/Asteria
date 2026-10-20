"""CB5: colliders, layers/masks, broad phase, triggers, character blocking (ASTERIA_SPEC §8)."""

import random
import time

from asteria.core import Entity, Scene, Transform
from asteria.runtime import (
    CharacterController2D,
    Collider2DComponent,
    CollisionSystem,
    CollisionWorld,
    CombinedQuery,
)
from asteria.runtime.collision import SpatialHash, overlap, shape_of


def _body(scene, name, x, y, *, shape="box", size=16.0, layer=0, mask=0xFFFFFFFF, trigger=False):
    entity = scene.add_entity(Entity(name))
    entity.add_component(Transform(x, y))
    collider = entity.add_component(Collider2DComponent())
    collider.shape, collider.width, collider.height, collider.radius = shape, size, size, size / 2
    collider.layer, collider.mask, collider.is_trigger = layer, mask, trigger
    return entity


def test_narrow_phase_box_circle_and_mixed_shapes():
    scene = Scene("S")
    a = shape_of(
        _body(scene, "A", 0, 0), scene.get_entity(scene.entities()[0].id).get(Collider2DComponent)
    )
    b_entity = _body(scene, "B", 12, 0)
    b = shape_of(b_entity, b_entity.get(Collider2DComponent))
    contact = overlap(a, b)
    assert contact.normal == (1.0, 0.0) and contact.depth == 4.0
    c_entity = _body(scene, "C", 0, 11, shape="circle", size=8)
    c = shape_of(c_entity, c_entity.get(Collider2DComponent))
    assert overlap(a, c) is not None and overlap(c, a).normal[1] < 0
    far = _body(scene, "Far", 100, 100)
    assert overlap(a, shape_of(far, far.get(Collider2DComponent))) is None


def test_layers_and_masks_filter_pairs_both_ways():
    scene = Scene("S")
    _body(scene, "Player", 0, 0, layer=1, mask=0b100)  # collides with layer 2 only
    _body(scene, "Wall", 5, 0, layer=2, mask=0b010)  # collides with layer 1 only
    _body(scene, "Ghost", 5, 0, layer=3, mask=0xFFFFFFFF)  # player ignores layer 3
    names = {e.id: e.name for e in scene.entities()}
    pairs = {
        tuple(sorted((names[c.a], names[c.b])))
        for c in CollisionWorld.from_scene(scene).contacts()
    }
    assert ("Player", "Wall") in pairs and ("Ghost", "Player") not in pairs


def test_trigger_reports_enter_stay_exit():
    scene = Scene("S")
    zone = _body(scene, "Zone", 0, 0, size=32, trigger=True)
    hero = _body(scene, "Hero", 100, 0)
    system = CollisionSystem()
    scene.scheduler.add(system)
    seen = []
    system.listeners.append(lambda kind, trigger, other: seen.append(kind))
    scene.update(0.1)
    hero.get(Transform).x = 0
    scene.update(0.1)
    scene.update(0.1)
    hero.get(Transform).x = 100
    scene.update(0.1)
    assert seen == ["enter", "stay", "exit"]
    assert system.trigger_events == [("exit", zone.id, hero.id)]


def test_colliders_follow_the_transform_hierarchy():
    scene = Scene("S")
    cart = scene.add_entity(Entity("Cart"))
    cart.add_component(Transform(200, 0))
    wheel = _body(scene, "Wheel", 10, 0)
    wheel.get(Transform).parent_id = cart.id
    world = CollisionWorld.from_scene(scene)
    assert world.query_point(210, 0) == (wheel.id,)
    assert world.query_point(10, 0) == ()


def test_character_controller_is_blocked_by_solid_colliders_but_not_triggers():
    scene = Scene("S")
    hero = _body(scene, "Hero", 0, 0, size=12)
    _body(scene, "Rock", 30, 0, size=16)
    _body(scene, "Mist", 0, 30, size=16, trigger=True)
    world = CollisionWorld.from_scene(scene)
    query = CombinedQuery(world.blocking_query(exclude={hero.id}))
    controller = CharacterController2D(0.0, 0.0, speed=100.0, half_width=6.0, half_height=6.0)
    for _ in range(30):
        controller.move(1.0, 0.0, 0.05, query)
    assert controller.x < 30 - 8 - 6 + 1e-6  # stopped at the rock's left face
    for _ in range(10):
        controller.move(0.0, 1.0, 0.05, query)
    assert controller.y > 30  # walked through the trigger


def test_broad_phase_scales_to_a_thousand_colliders():
    rng = random.Random(7)
    scene = Scene("Stress")
    for i in range(1000):
        _body(scene, f"E{i}", rng.uniform(0, 2000), rng.uniform(0, 2000), size=12)
    started = time.perf_counter()
    world = CollisionWorld.from_scene(scene, cell_size=64)
    contacts = world.contacts()
    elapsed = time.perf_counter() - started
    candidates = len(world.grid.candidate_pairs())
    assert candidates < 1000 * 999 // 2 // 50  # far fewer than all n^2 pairs
    assert all(isinstance(c.depth, float) for c in contacts)
    assert elapsed < 1.0, f"collision build+contacts took {elapsed:.3f}s"
    print(
        f"\n1000 colliders: {candidates} candidate pairs, {len(contacts)} contacts, "
        f"{elapsed * 1000:.1f} ms"
    )


def test_spatial_hash_rejects_bad_cell_size():
    import pytest

    with pytest.raises(ValueError):
        SpatialHash(0)


def test_playable_field_movement_stops_at_a_solid_collider(monkeypatch, tmp_path):
    import shutil
    from pathlib import Path

    import pytest

    pytest.importorskip("pygame")
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.input_map import RawInputState
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    root = Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"
    shutil.copy(root / "playable_test_manifest.json", tmp_path / "playable_test_manifest.json")
    shutil.copytree(root / "playable_assets", tmp_path / "playable_assets")
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(project, project.game_start.instantiate(project), tmp_path)
    runtime.open()
    try:
        runtime._ui_mode = "field"
        player = runtime.game.player.get(Transform)
        start = player.x
        _body(runtime.game.scene, "Fence", start + 20, player.y, size=8)  # left face at start + 16
        monkeypatch.setattr(
            runtime.input_source, "raw_state", lambda: RawInputState(keys={"right"})
        )
        for _ in range(40):
            runtime._frame([], 0.05)
        assert start < player.x < start + 16
    finally:
        runtime.close()


def test_a_followed_world_answers_like_a_rebuilt_one():
    """``follow`` updates the snapshot in place (moved and resized colliders, each in its own
    grid cells) and gives up - so the caller rebuilds - on any change it cannot follow exactly;
    every query then answers as a world built from scratch."""
    from asteria.runtime.collision import CollisionWorld

    rng = random.Random(7)
    scene = Scene("S")
    bodies = [
        _body(scene, f"b{i}", rng.uniform(0, 400), rng.uniform(0, 400),
              shape=rng.choice(("box", "circle")), size=rng.uniform(4, 90))
        for i in range(40)
    ]  # fmt: skip
    world = CollisionWorld.from_scene(scene)

    def same(world):
        fresh = CollisionWorld.from_scene(scene)
        for _ in range(300):
            x, y = rng.uniform(-20, 420), rng.uniform(-20, 420)
            assert world.query_point(x, y) == fresh.query_point(x, y)
            box = (x, y, x + rng.uniform(0, 80), y + rng.uniform(0, 80))
            assert [s.entity_id for s in world.query_box(box)] == [
                s.entity_id for s in fresh.query_box(box)
            ]
        assert world.shapes == fresh.shapes

    for _step in range(25):  # foes wander, some grow or shrink
        for entity in rng.sample(bodies, 12):
            t = entity.get(Transform)
            t.x, t.y = t.x + rng.uniform(-70, 70), t.y + rng.uniform(-70, 70)
        entity = rng.choice(bodies)
        entity.get(Collider2DComponent).width = rng.uniform(4, 90)
        assert world.follow(scene)
        same(world)
    victim = bodies[3]
    victim.enabled = False
    assert not world.follow(scene)  # a disabled collider: rebuild
    world = CollisionWorld.from_scene(scene)
    victim.enabled = True
    assert not world.follow(scene)  # enabled again: rebuild
    world = CollisionWorld.from_scene(scene)
    bodies[5].get(Collider2DComponent).layer = 3
    assert not world.follow(scene)  # another layer: rebuild
    world = CollisionWorld.from_scene(scene)
    _body(scene, "new", 10, 10)
    assert not world.follow(scene)  # a new collider: rebuild
    assert not CollisionWorld.from_scene(scene).follow(Scene("other"))  # another scene
