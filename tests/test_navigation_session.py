"""Pathfinding and WALK_TO in a game session: colliders block, the walker does not block itself."""

from pathlib import Path

import pytest

from asteria.core import Entity, Transform
from asteria.editor import EditorDocument
from asteria.events.world_commands import WorldCommand
from asteria.project import Project
from asteria.runtime.collision import Collider2DComponent
from asteria.runtime.game_session import GameSessionRuntime

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "party_rpg_demo"


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


def test_move_route_walks_relative_steps_and_flags_arrival(game):
    npc = _add(game, "patrol", 100.0, 100.0)
    game.world_commands.dispatch(
        WorldCommand(
            "MOVE_ROUTE",
            {"entity": "patrol", "route": "right 2, down 1", "step": 10, "speed": 100},
        )
    )
    assert npc.id in game.walkers
    for _ in range(40):
        game._advance_walkers(0.05)
    transform = npc.get(Transform)
    assert (transform.x, transform.y) == (120.0, 110.0)
    assert game.save.event_context.get_switch(f"walk.{npc.id}.done")


def test_move_route_rejects_an_unknown_direction(game):
    from asteria.runtime.world_command_handlers import WorldCommandError

    _add(game, "sailor", 10.0, 10.0)
    with pytest.raises(WorldCommandError):
        game.world_commands.dispatch(
            WorldCommand("MOVE_ROUTE", {"entity": "sailor", "route": "north 2"})
        )


def test_show_balloon_posts_a_short_popup_over_the_entity(game):
    _add(game, "talker", 10.0, 10.0)
    game.world_commands.dispatch(
        WorldCommand("SHOW_BALLOON", {"entity": "talker", "balloon": "question"})
    )
    assert any(p["text"] == "?" and p["kind"] == "balloon" for p in game.notices)


def test_events_can_spawn_copy_and_morph_entities(game):
    from asteria.core.prefab import PrefabDefinition

    transform = {"type": "asteria.Transform", "version": 1, "fields": {}}
    game.project.prefabs.add(PrefabDefinition("slime", "Slime", (transform,)))
    game.project.prefabs.add(
        PrefabDefinition("gold_slime", "Gold Slime", (), base_prefab_id="slime")
    )
    prefab_ids = ("slime", "gold_slime")
    spawned = game.world_commands.dispatch(
        WorldCommand("SPAWN_ENTITY", {"prefab_id": prefab_ids[0], "x": 50, "y": 60})
    )
    entity = game.scene.get_entity(spawned)
    assert entity is not None and (entity.get(Transform).x, entity.get(Transform).y) == (50, 60)
    copy_id = game.world_commands.dispatch(
        WorldCommand("COPY_ENTITY", {"entity": spawned, "x": 70, "y": 80})
    )
    copy = game.scene.get_entity(copy_id)
    assert copy is not None and copy.id != spawned and copy.get(Transform).x == 70
    other = prefab_ids[1] if len(prefab_ids) > 1 else prefab_ids[0]
    morphed = game.world_commands.dispatch(
        WorldCommand("MORPH_ENTITY", {"entity": copy_id, "prefab_id": other})
    )
    game.scene.update(0)
    assert game.scene.get_entity(morphed).get(Transform).x == 70
    from asteria.runtime.world_command_handlers import WorldCommandError

    with pytest.raises(WorldCommandError):
        game.world_commands.dispatch(
            WorldCommand("SPAWN_ENTITY", {"prefab_id": "nope", "x": 0, "y": 0})
        )
    with pytest.raises(WorldCommandError):
        game.world_commands.dispatch(
            WorldCommand("MORPH_ENTITY", {"entity": "player", "prefab_id": other})
        )


def test_a_click_triggered_interaction_starts_its_program_on_click(game):
    from asteria.runtime.components2d import Interaction2DComponent

    npc = _add(game, "signpost", 100.0, 100.0)
    interaction = npc.add_component(Interaction2DComponent())
    interaction.event_program_id = "greet"
    interaction.trigger = "click"
    interaction.range = 12.0
    started = []
    game.events.start_trigger = lambda trigger, replace=False: started.append(trigger)
    game.update_events = lambda dt=0.0: None
    assert game.click_entity(300.0, 300.0) is None  # nothing near
    trigger = game.click_entity(104.0, 100.0)
    assert trigger is not None and trigger.event_program_id == "greet"
    assert started and started[0].source_entity_id == npc.id
    interaction.trigger = "action"  # only click-triggered interactions answer clicks
    assert game.click_entity(104.0, 100.0) is None


def test_an_event_can_keep_an_icon_over_an_entity(game):
    npc = _add(game, "quest_giver", 40.0, 40.0)
    assert game.entity_icons() == {}
    game.world_commands.dispatch(
        WorldCommand("SET_ENTITY_ICON", {"entity": "quest_giver", "icon_id": "icon.quest"})
    )
    assert game.entity_icons() == {npc.id: "icon.quest"}
    assert game.save.event_context.get_variable(f"icon.{npc.id}") == "icon.quest"
    game.world_commands.dispatch(WorldCommand("SET_ENTITY_ICON", {"entity": npc.id}))
    assert game.entity_icons() == {}
    from asteria.runtime.world_command_handlers import WorldCommandError

    with pytest.raises(WorldCommandError):
        game.world_commands.dispatch(
            WorldCommand("SET_ENTITY_ICON", {"entity": "nobody", "icon_id": "x"})
        )
