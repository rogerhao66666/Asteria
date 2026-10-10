"""CB11: field AI (RPG-09), spawn zones / waves / respawn and visible encounters (RPG-10)."""

from math import hypot

from asteria.core import Entity, Scene, Transform
from asteria.core.prefab import PrefabDefinition, PrefabLibrary
from asteria.editor import EditorDocument
from asteria.runtime import (
    FieldAIComponent,
    FieldAISystem,
    SpawnSystem,
    SpawnZoneComponent,
    VisibleEncounterComponent,
)


def _entity(scene, name, x=0.0, y=0.0):
    entity = scene.add_entity(Entity(name))
    transform = entity.add_component(Transform())
    transform.x, transform.y = x, y
    return entity


def _ai(entity, behaviour, **values):
    spec = entity.add_component(FieldAIComponent())
    spec.behaviour = behaviour
    for key, value in values.items():
        setattr(spec, key, value)
    return spec


def _distance(a, b):
    ta, tb = a.get(Transform), b.get(Transform)
    return hypot(ta.x - tb.x, ta.y - tb.y)


def test_chase_gives_up_and_returns_home():
    scene = Scene("S")
    system = FieldAISystem()
    scene.scheduler.add(system)
    player = _entity(scene, "Player", 60, 0)
    wolf = _entity(scene, "Wolf")
    _ai(wolf, "chase", speed=40.0, detect_radius=80.0, lose_radius=120.0, target_entity_id=player.id)
    scene.update(0.5)
    assert system.state(wolf.id).mode == "chase" and _distance(wolf, player) < 60
    player.get(Transform).x = 400                       # out of lose radius
    scene.update(0.1)
    assert system.state(wolf.id).mode == "return"
    for _ in range(40):
        scene.update(0.1)
    assert system.state(wolf.id).mode == "idle" and abs(wolf.get(Transform).x) < 1e-6


def test_flee_patrol_wander_and_blocking():
    scene = Scene("S")

    class Wall:
        def collides_world_point(self, x, y):
            return x > 30

    system = FieldAISystem(blocking=Wall())
    scene.scheduler.add(system)
    player = _entity(scene, "Player", 10, 0)
    rabbit = _entity(scene, "Rabbit")
    _ai(rabbit, "flee", speed=50.0, target_entity_id=player.id)
    guard = _entity(scene, "Guard", 0, 100)
    _ai(guard, "patrol", speed=100.0, patrol_path="0,100; 20,100; 100,100")
    slime = _entity(scene, "Slime", 0, -200)
    _ai(slime, "wander", wander_radius=10.0)
    for _ in range(10):
        scene.update(0.1)
    assert rabbit.get(Transform).x < -40                # ran away from the player
    assert guard.get(Transform).x <= 30                 # wall blocks the third patrol point
    assert system.state(guard.id).patrol_index == 2
    assert hypot(slime.get(Transform).x, slime.get(Transform).y + 200) <= 10.0 + 1e-6


def _spawning(waves="", **values):
    registry = EditorDocument().component_registry
    prefabs = PrefabLibrary()
    prefabs.add(PrefabDefinition("slime", "Slime", ({"type": "asteria.Transform", "version": 1, "fields": {}},)))
    prefabs.add(PrefabDefinition("gold_slime", "Gold Slime", (), base_prefab_id="slime"))
    scene = Scene("S")
    switches = set()
    system = SpawnSystem(prefabs, registry, switches=switches.__contains__)
    scene.scheduler.add(system)
    zone_entity = _entity(scene, "Zone", 100, 100)
    zone = zone_entity.add_component(SpawnZoneComponent())
    zone.prefab_id, zone.waves, zone.radius = "slime", waves, 20.0
    for key, value in values.items():
        setattr(zone, key, value)
    system.zone_id = zone_entity.id
    return scene, system, switches


def _kill_all(scene, system):
    for entity_id in system.state(system.zone_id).alive:
        scene.remove_entity(scene.get_entity(entity_id))


def test_spawn_zone_respawns_after_cooldown_inside_radius():
    scene, system, _ = _spawning(max_alive=2, respawn_seconds=1.0, rare_prefab_id="gold_slime", rare_chance=1.0)
    scene.update(0.1)
    alive = system.state(system.zone_id).alive
    assert len(alive) == 2 and {x[2] for x in system.spawned} == {"gold_slime"}
    for entity_id in alive:
        t = scene.get_entity(entity_id).get(Transform)
        assert hypot(t.x - 100, t.y - 100) <= 20.0 + 1e-6
    _kill_all(scene, system)
    scene.update(0.5)
    assert system.state(system.zone_id).alive == []
    scene.update(0.6)                                     # cooldown elapsed
    assert len(system.state(system.zone_id).alive) == 2


def test_waves_spawn_after_clear_and_condition_switch_gates_the_zone():
    scene, system, switches = _spawning("2, 3", respawn_seconds=0.0, condition_switch="night")
    scene.update(0.1)
    assert system.state(system.zone_id).alive == []               # switch off
    switches.add("night")
    scene.update(0.1)
    assert len(system.state(system.zone_id).alive) == 2
    scene.update(0.1)
    assert len(system.state(system.zone_id).alive) == 2           # next wave waits for a clear
    _kill_all(scene, system)
    scene.update(0.1)
    assert len(system.state(system.zone_id).alive) == 3
    _kill_all(scene, system)
    scene.update(0.1)
    scene.update(0.1)
    assert system.state(system.zone_id).finished and system.state(system.zone_id).alive == []


def test_touching_a_visible_encounter_starts_the_battle():
    from test_session_events import _session

    _, game = _session()
    p = game.player.get(Transform)
    enemy = Entity("Field Tyrant")
    t = enemy.add_component(Transform())
    t.x, t.y = p.x + 5, p.y
    marker = enemy.add_component(VisibleEncounterComponent())
    marker.encounter_id = "boss_room"
    game.scene.add_entity(enemy)
    assert game.check_visible_encounter() == "boss_room"
    assert game.mode == "battle" and game.scene.get_entity(enemy.id) is None
