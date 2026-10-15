"""Pathfinding and WALK_TO in a game session: colliders block, the walker does not block itself."""

from pathlib import Path

import pytest

from asteria.core import Entity, Transform
from asteria.editor import EditorDocument
from asteria.events.world_commands import WorldCommand
from asteria.project import Project
from asteria.runtime.collision import Collider2DComponent
from asteria.runtime.game_session import GameSessionRuntime

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "octopath_demo"


@pytest.fixture
def game():
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    game = GameSessionRuntime(project, project.game_start.instantiate(project))
    game.field_bounds = (0.0, 0.0, 320.0, 320.0)
    game.player.get(Transform).x = 8.0
    game.player.get(Transform).y = 8.0
    return game


def _add(game, name, x, y, *, solid=False, width=16.0, height=16.0):
    entity = Entity(name)
    transform = entity.add_component(Transform())
    transform.x, transform.y = x, y
    if solid:
        collider = entity.add_component(Collider2DComponent())
        collider.width, collider.height = width, height
    game.scene.add_entity(entity)
    game.scene.update(0)  # flush the pending add
    return entity


def test_a_free_path_is_direct_and_ends_on_the_goal(game):
    path = game.find_path((40.0, 40.0), (200.0, 40.0))
    assert path == [(200.0, 40.0)]


def test_a_solid_collider_makes_the_path_go_around(game):
    _add(game, "wall", 120.0, 40.0, solid=True, width=16.0, height=160.0)
    path = game.find_path((40.0, 40.0), (200.0, 40.0))
    assert path is not None and len(path) >= 2
    assert max(py for _, py in path) > 110  # it clears the bottom of the wall


def test_walk_to_moves_an_entity_along_the_path_and_flags_arrival(game):
    npc = _add(game, "guide", 40.0, 40.0)
    _add(game, "wall", 120.0, 40.0, solid=True, width=16.0, height=160.0)
    waypoints = game.walk_to("guide", 200.0, 40.0, speed=100.0)
    done = f"walk.{npc.id}.done"
    assert waypoints and not game.save.event_context.get_switch(done)
    for _ in range(400):
        game._advance_walkers(0.05)
        if game.save.event_context.get_switch(done):
            break
    transform = npc.get(Transform)
    assert game.save.event_context.get_switch(done) and npc.id not in game.walkers
    assert (transform.x, transform.y) == (200.0, 40.0)


def test_the_walker_is_not_blocked_by_its_own_collider(game):
    npc = _add(game, "guard", 40.0, 40.0, solid=True)
    assert game.walk_to("guard", 100.0, 40.0)
    assert npc.id in game.walkers


def test_an_unreachable_goal_leaves_the_entity_where_it_is(game):
    npc = _add(game, "lost", 40.0, 40.0)
    for x in range(0, 320, 16):  # a solid ring around the goal
        _add(game, f"w{x}", float(x), 100.0, solid=True, width=16.0, height=16.0)
    assert game.walk_to("lost", 100.0, 250.0) is None
    assert npc.id not in game.walkers
    assert game.save.event_context.get_switch(f"walk.{npc.id}.done")


def test_the_walk_to_command_starts_a_walk(game):
    npc = _add(game, "pilgrim", 40.0, 40.0)
    game.world_commands.dispatch(
        WorldCommand("WALK_TO", {"entity": "pilgrim", "x": 120, "y": 40, "speed": 50})
    )
    assert npc.id in game.walkers
    from asteria.runtime.world_command_handlers import WorldCommandError

    with pytest.raises(WorldCommandError):
        game.world_commands.dispatch(WorldCommand("WALK_TO", {"entity": "nobody", "x": 1, "y": 1}))


def test_field_update_advances_walkers(game):
    npc = _add(game, "runner", 40.0, 40.0)
    game.walk_to("runner", 140.0, 40.0, speed=50.0)
    game.field_update(1.0)
    assert npc.get(Transform).x == pytest.approx(90.0)
