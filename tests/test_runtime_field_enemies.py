"""D12 runtime integration: spawn zones and field enemy AI run inside the playable runtime.

Uses a minimal test fixture (one prefab, one spawn zone) added to the
reference project in memory; the reference project files are not changed.
"""

from math import hypot

import pytest

pygame = pytest.importorskip("pygame")


from asteria.core import Entity, Transform  # noqa: E402
from asteria.core.prefab import prefab_from_entity  # noqa: E402
from asteria.runtime import FieldAIComponent, SpawnZoneComponent, VisibleEncounterComponent  # noqa: E402


def _install_fixture(game, *, behaviour="chase", radius=0.0, offset=(70.0, 0.0)):
    template = Entity("Field Slime")
    template.add_component(Transform())
    ai = template.add_component(FieldAIComponent())
    ai.behaviour, ai.speed, ai.detect_radius, ai.lose_radius = behaviour, 60.0, 200.0, 400.0
    encounter = template.add_component(VisibleEncounterComponent())
    encounter.encounter_id = "boss_room"
    game.project.prefabs.add(prefab_from_entity(template, "field_slime"))
    zone = Entity("Slime Zone")
    p = game.player.get(Transform)
    zone_transform = zone.add_component(Transform())
    zone_transform.x, zone_transform.y = p.x + offset[0], p.y + offset[1]
    spec = zone.add_component(SpawnZoneComponent())
    spec.prefab_id, spec.max_alive, spec.radius, spec.respawn_seconds = "field_slime", 1, radius, 5.0
    game.scene.add_entity(zone)
    return zone


def _spawned(game):
    return [e for e in game.scene.entities() if e.has(FieldAIComponent)]


def test_spawned_enemy_chases_player_and_starts_battle_in_the_runtime(runtime):
    runtime._ui_mode = "field"
    game = runtime.game
    _install_fixture(game)
    runtime._frame([], 0.016)
    (slime,) = _spawned(game)
    start = hypot(
        slime.get(Transform).x - game.player.get(Transform).x, slime.get(Transform).y - game.player.get(Transform).y
    )
    pixel = runtime.screen.get_at(
        tuple(int(v) for v in runtime._field_screen_xy(slime.get(Transform).x, slime.get(Transform).y))
    )
    assert tuple(pixel)[:3] == (200, 70, 80)  # visible on the field
    frames = 0
    while game.mode == "field" and frames < 200:
        runtime._frame([], 0.05)
        frames += 1
    assert game.mode == "battle" and game.encounter_id == "boss_room"
    assert 0 < frames < 200 and start > 12
    assert not _spawned(game)  # touched enemy removed


def test_spawn_zone_respawns_and_field_ai_pauses_outside_the_field(runtime):
    runtime._ui_mode = "field"
    game = runtime.game
    _install_fixture(game, behaviour="wander", radius=10.0, offset=(100.0, 0.0))
    runtime._frame([], 0.016)
    (slime,) = _spawned(game)
    runtime._ui_mode = "pause"  # menus freeze the field
    before = (slime.get(Transform).x, slime.get(Transform).y)
    for _ in range(10):
        runtime._frame([], 0.05)
    assert (slime.get(Transform).x, slime.get(Transform).y) == before
    runtime._ui_mode = "field"
    game.scene.remove_entity(slime)
    runtime._frame([], 0.016)
    assert not _spawned(game)  # respawn waits
    for _ in range(110):
        runtime._frame([], 0.05)
    assert len(_spawned(game)) == 1


def _press(rt, key):
    rt._frame([pygame.event.Event(pygame.KEYDOWN, key=key)], 0.016)
    rt._frame([pygame.event.Event(pygame.KEYUP, key=key)], 0.016)


def test_battle_capture_menu_captures_a_weakened_enemy(runtime):
    from asteria.rpg import CaptureRule

    game = runtime.game
    db = game.project.rpg_database
    base = db.actors["hero_01"]
    db.add_actor(
        type(base)(
            "tyrant_ally",
            "Tyrant Ally",
            base_stats=base.base_stats,
            base_resources=base.base_resources,
            abilities=base.abilities,
        )
    )
    db.add_capture_rule(CaptureRule("astral_tyrant", "tyrant_ally", base_chance=0.0, low_health_bonus=1.0))
    runtime._ui_mode = "field"
    game.start_encounter("boss_room")
    runtime._frame([], 0.016)  # field branch starts the battle presentation
    runtime._advance_to_hero_turn()
    assert runtime._battle_actor() is not None
    targets = game.capture_targets()
    assert [t[0] for t in targets] == ["astral_tyrant:1"] and targets[0][1] == 0.0
    for _ in range(400):
        if not runtime._presentation_busy():
            break
        runtime._frame([], 0.05)
    _press(runtime, pygame.K_x)
    assert runtime._capture_menu
    _press(runtime, pygame.K_ESCAPE)
    assert not runtime._capture_menu and game.mode == "battle"
    tyrant = game.battle.member("astral_tyrant:1").subject.resources
    tyrant.set_current(game.rules.knockout_resource_id, 1)
    runtime._advance_to_hero_turn()
    for _ in range(400):  # commands are accepted once the choreography is idle
        if not runtime._presentation_busy():
            break
        runtime._frame([], 0.05)
    _press(runtime, pygame.K_x)
    _press(runtime, pygame.K_1)
    assert "astral_tyrant:1" not in game.active_enemy_ids()
    assert runtime._last_action_name.startswith("Captured") or runtime._victory
    assert "tyrant_ally" in game.save.rpg_state.party_actor_ids
    assert game.world.bestiary["astral_tyrant"]["captured"] == 1
