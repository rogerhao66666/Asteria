"""Map area rules in a game session: damage, footsteps, event programs, stealth, enemy blocks."""

from pathlib import Path

import pytest

from asteria.core import Entity, Transform
from asteria.editor import EditorDocument
from asteria.project import Project
from asteria.rpg.map_rules import AreaRule, MapRuleSet
from asteria.runtime.field_ai import FieldAIComponent
from asteria.runtime.game_session import GameSessionRuntime

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "octopath_demo"


def _session(rules, **options):
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    project.rpg_database.add_map_rule_set(MapRuleSet("m", rules, **options))
    game = GameSessionRuntime(project, project.game_start.instantiate(project))
    return game


def _everywhere(*keys):
    return lambda x, y: tuple(keys)


def test_without_a_rule_set_nothing_binds():
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    game = GameSessionRuntime(project, project.game_start.instantiate(project))
    assert game.bind_map_rules(_everywhere("region:1")) is None and game.map_rules is None
    game.field_update(0.1)  # runs fine without rules


def test_floor_damage_hurts_the_party_but_leaves_the_last_point():
    game = _session((AreaRule("region:1", damage_resource="vitality", damage_per_second=10),))
    hero = game.save.rpg_state.party_active_actor_ids[0]
    from asteria.gameplay import ResourcePool

    start = game.resolve_actor_build(hero).resources.current("vitality")
    game.bind_map_rules(_everywhere("region:1"))
    game.map_rules.update(0.0)
    game.map_rules.update(1.0)
    now = ResourcePool.from_data(game.save.rpg_state.actor_snapshots[hero].resources)
    assert now.current("vitality") == pytest.approx(start - 10)
    game.damage_party("vitality", 10**9)  # more than they have
    last = ResourcePool.from_data(game.save.rpg_state.actor_snapshots[hero].resources)
    assert last.current("vitality") == last.get("vitality").minimum + 1.0
    game.damage_party("vitality", 10, can_kill=True)
    dead = ResourcePool.from_data(game.save.rpg_state.actor_snapshots[hero].resources)
    assert dead.current("vitality") == dead.get("vitality").minimum


def test_footsteps_queue_sound_requests_while_walking():
    rule = AreaRule("region:1", footstep_cue="step_grass", step_distance=8)
    game = _session((rule,))
    game.bind_map_rules(_everywhere("region:1"))
    game.presentation_requests.clear()
    game.map_rules.update(0.1)
    transform = game.player.get(Transform)
    for _ in range(3):
        transform.x += 5
        game.map_rules.update(0.1)
    cues = [r for r in game.presentation_requests if r.name == "PLAY_SE"]
    assert len(cues) == 1 and cues[0].args["asset_id"] == "step_grass"


def test_enter_and_leave_start_event_programs_when_idle():
    rule = AreaRule("region:7", on_enter="welcome", on_leave="goodbye")
    game = _session((rule,))
    started = []
    game.events.start = lambda program, **kw: started.append(program)
    here = {"on": True}
    game.bind_map_rules(lambda x, y: ("region:7",) if here["on"] else ())
    game.map_rules.update(0.1)
    here["on"] = False
    game.map_rules.update(0.1)
    assert started == ["welcome", "goodbye"]


def test_stealth_scales_enemy_sight_and_restores_it():
    game = _session(
        (AreaRule("region:2", visibility=0.5),), crouch_visibility=0.5, still_visibility=0.5
    )
    enemy = Entity("wolf")
    enemy.add_component(Transform())
    spec = enemy.add_component(FieldAIComponent())
    spec.detect_radius, spec.lose_radius = 100.0, 200.0
    game.scene.add_entity(enemy)
    here = {"keys": ("region:2",)}
    game.bind_map_rules(lambda x, y: here["keys"])
    game.map_rules.update(0.1)  # first frame: no earlier position, so not "still" yet
    assert (spec.detect_radius, spec.lose_radius) == (50.0, 100.0)  # the dark area alone
    game.save.event_context.set_switch("stealth.crouch", True)
    game.map_rules.update(0.1)
    assert spec.detect_radius == pytest.approx(100.0 * 0.5 * 0.5 * 0.5)  # area x crouch x still
    here["keys"] = ()
    game.save.event_context.set_switch("stealth.crouch", False)
    game.player.get(Transform).x += 20
    game.map_rules.update(0.1)
    assert (spec.detect_radius, spec.lose_radius) == (100.0, 200.0)


def test_enemy_blocking_query_includes_restricted_areas():
    game = _session((AreaRule("region:3", blocks=("enemy",)),))
    game.bind_map_rules(lambda x, y: ("region:3",))
    query = game.map_rules.block_query("enemy")
    assert query.collides_world_point(0, 0)
    assert not game.map_rules.block_query("player").collides_world_point(0, 0)
