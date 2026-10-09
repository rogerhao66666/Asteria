"""CB1: authored event programs execute in the game session."""

from pathlib import Path

import pytest

from asteria.core import Entity, Scene, Transform
from asteria.editor import EditorDocument
from asteria.events import (
    EventBinding,
    EventCondition,
    EventInstruction,
    EventProgram,
    EventTriggerCondition,
    EventTriggerKind,
    SceneEventBindings,
    WorldCommand,
)
from asteria.project import Project
from asteria.runtime.game_save import GameRuntimeSave
from asteria.runtime.game_session import GameSessionRuntime
from asteria.runtime.world_command_handlers import STANDARD_WORLD_COMMANDS, WorldCommandError

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"
BOSS_PROGRAM = "boss_interaction_event"


def _project():
    return Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)


def _session(project=None):
    """Session from the reference save that stands in front of the boss."""
    project = project or _project()
    save = GameRuntimeSave.load_json(ROOT / "saves" / "boss_stress.asteria-save.json", project)
    return project, GameSessionRuntime(project, save)


def _replace_program(project, program_id, instructions):
    project.event_programs.unregister(program_id)
    project.event_programs.register(program_id, EventProgram(instructions, name=program_id))


def _interact(game):
    trigger = game.field_step({"interact": 1})
    if game.mode == "field":
        game.field_step({"interact": 0})
    return trigger


def _switch(name, value=True):
    return {"source": "switch", "name": name, "operator": "==", "value": value, "scope_id": None}


def test_every_standard_world_command_has_a_handler():
    _, game = _session()
    assert all(game.world_commands.can_handle(name) for name in STANDARD_WORLD_COMMANDS)


def test_authored_dialogue_choice_branch_and_encounter_run_in_order():
    project, game = _session()
    _replace_program(project, BOSS_PROGRAM, [
        EventInstruction("DIALOGUE", {"speaker": "Astral Tyrant", "text": "Fight?"}),
        EventInstruction("CHOICE", {"prompt": "Answer", "variable_name": "answer",
                                     "choices": [{"text": "Yes", "value": "yes"}, {"text": "No", "value": "no"}]}),
        EventInstruction("SET_SWITCH", {"name": "met_tyrant", "value": True}),
        EventInstruction("JUMP_IF", {"condition": {"source": "variable", "name": "answer", "operator": "==",
                                                   "value": "no", "scope_id": None}, "label": "refuse"}),
        EventInstruction("WORLD", {"command": "START_ENCOUNTER", "args": {"encounter_id": "boss_room"}}),
        EventInstruction("END"),
        EventInstruction("LABEL", {"name": "refuse"}),
        EventInstruction("DIALOGUE", {"text": "Coward."}),
        EventInstruction("END"),
    ])
    assert _interact(game) is not None
    assert game.pending_dialogue.line.text == "Fight?"
    assert game.event_busy and _interact(game) is None  # input blocked while the event waits
    game.acknowledge_dialogue()
    assert [c.text for c in game.pending_dialogue.choices] == ["Yes", "No"]
    assert game.mode == "field"
    game.choose(0)
    assert game.save.event_context.get_switch("met_tyrant") is True
    assert game.save.event_context.get_variable("answer") == "yes"
    assert game.mode == "battle" and game.encounter_id == "boss_room"
    assert game.event_errors == []


def test_refusing_takes_the_other_branch_and_starts_no_battle():
    project, game = _session()
    _replace_program(project, BOSS_PROGRAM, [
        EventInstruction("CHOICE", {"variable_name": "answer",
                                     "choices": [{"text": "Yes", "value": "yes"}, {"text": "No", "value": "no"}]}),
        EventInstruction("JUMP_IF", {"condition": {"source": "variable", "name": "answer", "operator": "==",
                                                   "value": "no", "scope_id": None}, "label": "refuse"}),
        EventInstruction("WORLD", {"command": "START_ENCOUNTER", "args": {"encounter_id": "boss_room"}}),
        EventInstruction("LABEL", {"name": "refuse"}),
        EventInstruction("END"),
    ])
    _interact(game)
    game.choose(1)
    assert game.mode == "field" and not game.event_busy


def test_item_currency_and_presentation_commands_change_session_state():
    project, game = _session()
    item_id = sorted(project.rpg_database.items)[0]
    before = game.save.rpg_state.inventory.count(item_id)
    gold = game.save.rpg_state.currencies.get("gold", 0.0)
    _replace_program(project, BOSS_PROGRAM, [
        EventInstruction("WORLD", {"command": "GIVE_ITEM", "args": {"item_id": item_id, "quantity": 2}}),
        EventInstruction("WORLD", {"command": "CHANGE_CURRENCY", "args": {"currency_id": "gold", "amount": 50}}),
        EventInstruction("WORLD", {"command": "PLAY_BGM", "args": {"asset_id": "music.boss"}}),
        EventInstruction("END"),
    ])
    _interact(game)
    assert game.save.rpg_state.inventory.count(item_id) == before + 2
    assert game.save.rpg_state.currencies["gold"] == pytest.approx(gold + 50)
    assert [c.name for c in game.presentation_requests] == ["PLAY_BGM"]
    with pytest.raises(WorldCommandError):
        game.world_commands.dispatch(WorldCommand("TAKE_ITEM", {"item_id": item_id, "quantity": 999}))


def test_failed_world_command_stops_the_event_and_is_reported():
    project, game = _session()
    _replace_program(project, BOSS_PROGRAM, [
        EventInstruction("WORLD", {"command": "GIVE_ITEM", "args": {"item_id": "no_such_item"}}),
        EventInstruction("SET_SWITCH", {"name": "after_failure"}),
    ])
    _interact(game)
    assert len(game.event_errors) == 1 and not game.event_busy
    assert not game.save.event_context.get_switch("after_failure")


def test_transfer_moves_the_player_to_another_scene_and_its_events():
    project = _project()
    town = project.add_scene(Scene("Town"))
    _replace_program(project, BOSS_PROGRAM, [
        EventInstruction("WORLD", {"command": "TRANSFER", "args": {"scene_id": town.id, "x": 5, "y": 7, "facing": "up"}}),
    ])
    project, game = _session(project)
    player = game.player
    _interact(game)
    assert game.scene is town and player.scene is town
    assert (player.get(Transform).x, player.get(Transform).y) == (5.0, 7.0)
    assert game.facing == "up" and game.save.scene_id == town.id


def test_event_waiting_on_dialogue_survives_save_and_reload(tmp_path):
    project, game = _session()
    _interact(game)
    assert game.pending_dialogue is not None
    path = tmp_path / "mid_event.asteria-save.json"
    game.sync_world_state().save_json(path)

    loaded = GameSessionRuntime(project, GameRuntimeSave.load_json(path, project))
    assert loaded.pending_dialogue.line.speaker == "Astral Tyrant"
    loaded.acknowledge_dialogue()
    assert loaded.mode == "battle"


def test_version_1_saves_without_active_event_still_load(tmp_path):
    project, game = _session()
    data = game.sync_world_state().to_data()
    data["version"] = 1
    data.pop("active_event")
    assert GameRuntimeSave.from_data(data, project).active_event is None


def test_autorun_binding_runs_once_until_its_condition_turns_off():
    project = _project()
    scene = project.scene(project.startup_scene_id)
    host = scene.add_entity(Entity("Intro Host"))
    project.event_programs.register("intro", EventProgram([
        EventInstruction("SET_VARIABLE", {"name": "intro_runs", "value": 1}),
        EventInstruction("SET_SWITCH", {"name": "intro_done", "value": True}),
    ], name="intro"))
    bindings = project.scene_event_bindings.setdefault(scene.id, SceneEventBindings())
    bindings.add(EventBinding(
        "intro_binding", host.id, "intro", trigger=EventTriggerKind.AUTORUN,
        conditions=(EventTriggerCondition(EventCondition("switch", "intro_done", "==", False)),),
    ))
    _, game = _session(project)
    for _ in range(3):
        game.update_events(0.1)
    assert game.save.event_context.get_switch("intro_done") is True
    assert game.save.event_context.get_variable("intro_runs") == 1


def test_legacy_flat_world_arguments_still_dispatch():
    project, game = _session()
    _replace_program(project, BOSS_PROGRAM, [
        EventInstruction("WORLD", {"command": "START_ENCOUNTER", "encounter_id": "boss_room"}),
    ])
    _interact(game)
    assert game.mode == "battle"


def test_editor_world_argument_text_parses_to_typed_args():
    from asteria.editor.event_editing import describe_instruction, parse_world_args

    assert parse_world_args("encounter_id=boss_room, quantity=2, amount=1.5, loop=true") == {
        "encounter_id": "boss_room", "quantity": 2, "amount": 1.5, "loop": True,
    }
    assert parse_world_args("  ") == {}
    with pytest.raises(ValueError):
        parse_world_args("no_equals_sign")
    instruction = EventInstruction("WORLD", {"command": "START_ENCOUNTER", "args": {"encounter_id": "boss_room"}})
    assert describe_instruction(instruction) == "World  START_ENCOUNTER  (encounter_id=boss_room)"
