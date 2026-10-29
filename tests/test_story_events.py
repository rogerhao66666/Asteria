"""Story events: scripted grid routes and waiting for them, EXIT from a called program,
area autorun programs and entry programs queued while an event runs, people shown by a switch
or dressed by a variable, kept positions, giving a creature, and losing a battle back at the
last respawn point."""

from pathlib import Path

import pytest

from asteria.core import Entity, Transform
from asteria.events import EventProgram
from asteria.events.program import EventInstruction
from asteria.rpg.battle_session_rules import BattleSessionRules
from asteria.rpg.map_rules import AreaRule
from asteria.runtime.grid_actors import (
    GridMover2DComponent,
    LookByVariable2DComponent,
    RouteRunner,
    SwitchVisibility2DComponent,
    parse_looks,
    parse_step,
)

ROOT = Path(__file__).resolve().parents[1] / "reference_projects"


def _world(command, **args):
    return EventInstruction("WORLD", {"command": command, "args": args})


def _until(name):
    condition = {"source": "switch", "name": name, "operator": "==", "value": True}
    return EventInstruction("WAIT", {"until": {**condition, "scope_id": None}})


def _game(*programs):
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.game_session import GameSessionRuntime

    path = ROOT / "party_rpg_demo" / "project.asteria.json"
    project = Project.load_json(path, EditorDocument().component_registry)
    for program_id, instructions in programs:
        project.event_programs.register(
            program_id, EventProgram(tuple(instructions), name=program_id)
        )
    return GameSessionRuntime(project, project.game_start.instantiate(project))


def _run(game, seconds, dt=1 / 30):
    for _ in range(int(seconds / dt)):
        game.field_update(dt)
        game.update_events(dt)  # as the frame loop does


def test_route_steps_parse_and_walk_cell_by_cell():
    assert parse_step("walk_up") == ("move", "up", 60.0)
    assert parse_step("walk_fast_left") == ("move", "left", 120.0)
    assert parse_step("jump_2_down") == ("jump", "down", 2.0)
    assert parse_step("delay:0.5") == ("delay", "", 0.5)
    assert parse_step("emote:exclamation") == ("emote", "exclamation", 0.0)
    with pytest.raises(ValueError):
        parse_step("fly_up")
    transform, facings = Transform(8, 8), []

    class Host:
        transform = staticmethod(lambda _id: transform)
        set_facing = staticmethod(lambda _id, f: facings.append(f))
        set_lift = set_hidden = emote = staticmethod(lambda *_: None)

    runner = RouteRunner()
    runner.start("a", ["walk_right", "walk_right", "face_up"])
    for _ in range(20):
        runner.update(1 / 60, Host)
    assert not runner.done("a") and 8 < transform.x < 40
    for _ in range(60):
        runner.update(1 / 60, Host)
    assert runner.done() and (transform.x, transform.y) == (40.0, 8.0)
    assert facings == ["right", "right", "up"]


def test_an_event_waits_for_a_route_and_exit_stops_called_programs():
    game = _game(
        (
            "walk",
            [
                _world("GRID_ROUTE", entity="player", steps="walk_right, walk_right"),
                _until("route.all.done"),
                EventInstruction("SET_SWITCH", {"name": "walked", "value": True}),
                EventInstruction("CALL", {"program_id": "leave"}),
                EventInstruction("SET_SWITCH", {"name": "after_exit", "value": True}),
                EventInstruction("END"),
            ],
        ),
        ("leave", [EventInstruction("EXIT"), EventInstruction("END")]),
    )
    player = game.player.get(Transform)
    start = (player.x // 16) * 16 + 8
    game.events.start("walk")
    game.update_events(0.0)
    switches = game.save.event_context
    assert game.event_busy and not switches.get_switch("walked")
    _run(game, 1.0)
    assert not game.event_errors, game.event_errors
    assert player.x == start + 32 and switches.get_switch("walked")
    assert not switches.get_switch("after_exit") and not game.event_busy


def test_area_autorun_and_entry_programs_queued_while_busy():
    rule = AreaRule(
        "region:1",
        autorun=[
            {"variable": "story", "value": 1, "program": "one"},
            {"switch": "flag", "program": "flagged"},
        ],
    )
    assert AreaRule.from_data(rule.to_data()) == rule
    values = {"story": 0}
    assert rule.autorun_program(lambda n: n == "flag", values.get) == "flagged"
    values["story"] = 1
    assert rule.autorun_program(lambda n: False, values.get) == "one"
    assert rule.autorun_program(lambda n: False, {"story": 2}.get) == ""
    with pytest.raises(ValueError):
        AreaRule("region:1", autorun=[{"variable": "x"}])
    with pytest.raises(ValueError):
        AreaRule("region:1", autorun=[{"variable": "x", "switch": "y", "program": "p"}])

    from asteria.runtime.map_rules_field import FieldMapRules

    class Runtime:
        def advance(self, *_):
            return ()

        def rules_at(self, *_):
            return (rule,)

    game = _game(
        ("one", [EventInstruction("SET_VARIABLE", {"name": "story", "value": 2})]),
        ("queued", [EventInstruction("SET_SWITCH", {"name": "queued_ran", "value": True})]),
    )
    context = game.save.event_context
    context.set_variable("story", 1)
    rules = FieldMapRules(game, Runtime())
    rules._scale_enemy_sight = lambda *_: None
    game.pending_area_programs.append("queued")
    rules.update(0.0)  # the queued entry program first
    game.update_events(0.0)
    assert context.get_switch("queued_ran") and context.get_variable("story") == 1
    rules.update(0.0)
    game.update_events(0.0)
    assert context.get_variable("story") == 2  # the autorun ran once and moved the story on
    rules.update(0.0)
    assert not game.event_busy


def test_switch_visibility_looks_and_kept_positions():
    game = _game()
    person = game.scene.add_entity(Entity("Rival"))
    person.add_component(Transform(40, 40))
    person.add_component(GridMover2DComponent())
    shown = person.add_component(SwitchVisibility2DComponent())
    shown.hidden_switch = "rival_gone"
    look = person.add_component(LookByVariable2DComponent())
    look.variable, look.looks = "rival", "0=may_sheet|may_walk; 1=brendan_sheet|brendan_walk"
    from asteria.runtime.components2d import Animator2DComponent, SpriteRenderer2D

    sprite = person.add_component(SpriteRenderer2D())
    animator = person.add_component(Animator2DComponent())
    assert parse_looks(look.looks)["1"] == ("brendan_sheet", "brendan_walk")
    context = game.save.event_context
    context.set_variable("rival", 1)
    game._story_frame(0.0)
    assert person.enabled and sprite.sprite_sheet_asset_id == "brendan_sheet"
    assert animator.clip_set_id == "brendan_walk"
    context.set_switch("rival_gone", True)
    game._story_frame(0.0)
    assert not person.enabled
    game.set_entity_position(person.id, 72, 24, facing="left", permanent=True)
    assert context.get_variable(f"pos.{person.id}") == "72.0|24.0|left"
    person.get(Transform).x = 0.0
    game._story_scene = None  # the scene loads again
    game._story_frame(0.0)
    assert person.get(Transform).x == 72.0
    assert person.get(GridMover2DComponent).facing == "left"


def test_defeat_rules_round_trip_and_validate():
    rules = BattleSessionRules(
        "r", defeat="respawn", defeat_currency="gold", defeat_currency_loss=0.5,
        defeat_event="after_loss",
    )  # fmt: skip
    assert BattleSessionRules.from_data(rules.to_data()) == rules
    assert "defeat" not in BattleSessionRules("r").to_data()
    with pytest.raises(ValueError):
        BattleSessionRules("r", defeat="explode")
    with pytest.raises(ValueError):
        BattleSessionRules("r", defeat_currency_loss=2)


def test_losing_heals_the_party_back_at_the_respawn_point(monkeypatch):
    import sys

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    sys.path.insert(0, str(ROOT / "full_verification_demo"))
    import run_trial_smoke as smoke
    import trial_creatures

    project, game = smoke.load()
    trial_creatures.install(project, max_moves=4)
    db = project.rpg_database
    old = db.battle_session_rules[sorted(db.battle_session_rules)[0]].to_data()
    db.battle_session_rules.clear()
    db.add_battle_session_rules(
        BattleSessionRules.from_data({
            **old, "defeat": "respawn", "defeat_currency": "gold",
            "defeat_currency_loss": 0.5, "defeat_event": "after_loss",
        })
    )  # fmt: skip
    project.event_programs.register(
        "after_loss",
        EventProgram(
            (EventInstruction("SET_SWITCH", {"name": "mum_spoke", "value": True}),),
            name="after_loss",
        ),
    )
    project.event_programs.register(
        "gift",
        EventProgram(
            (
                _world("GIVE_PET", species_id="cub", level=5, moves=["pet_shot"]),
                _world("SET_RESPAWN", scene_id=game.scene.id, x=40, y=56, facing="up"),
            ),
            name="gift",
        ),
    )
    game.events.start("gift")
    game.update_events(0.0)
    gifted = [p for p in game.party_pets() if p.species_id == "cub" and p.level == 5]
    assert gifted and gifted[-1].moves == ["pet_shot"]
    game.save.rpg_state.currencies["gold"] = 301.0
    game.start_encounter("wild_cubs")
    game.respawn_after_defeat()
    assert game.mode == "field" and game.battle is None
    assert game.save.rpg_state.currencies["gold"] == 151.0
    player = game.player.get(Transform)
    assert (player.x, player.y) == (40.0, 56.0) and game.facing == "up"
    assert game.save.event_context.get_switch("mum_spoke")


def test_story_commands_show_move_and_copy():
    game = _game(
        (
            "story",
            [
                EventInstruction("SET_VARIABLE", {"name": "who", "value": "Guard"}),
                _world("SHOW_ENTITY", entity="var:who", shown=False),
                _world("SET_MOVEMENT", entity="Guard", behaviour="still", facing="left"),
                EventInstruction("SET_VARIABLE", {"name": "copy", "from_variable": "who"}),
                _world("RESTORE_BGM"),
            ],
        ),
    )
    guard = game.scene.add_entity(Entity("Guard"))
    guard.add_component(Transform(40, 40))
    mover = guard.add_component(GridMover2DComponent())
    mover.behaviour = "wander"
    shown = guard.add_component(SwitchVisibility2DComponent())
    shown.hidden_switch = "guard_gone"
    game.events.start("story")
    game.update_events(0.0)
    assert not game.event_errors, game.event_errors
    context = game.save.event_context
    assert context.get_switch("guard_gone") and context.get_variable("copy") == "Guard"
    assert (mover.behaviour, mover.facing) == ("still", "left")
    assert game.presentation_requests[-1].name == "RESTORE_BGM"
    game._story_frame(0.0)
    assert not guard.enabled


def test_a_route_turns_to_the_player_and_self_names_the_events_entity():
    game = _game(
        ("look", [_world("GRID_ROUTE", entity="self", steps=["face_player"])]),
    )
    person = game.scene.add_entity(Entity("Clerk"))
    person.add_component(Transform(200, 40))
    mover = person.add_component(GridMover2DComponent())
    game.player.get(Transform).x, game.player.get(Transform).y = 40, 40
    game.events.start("look", source_entity_id=person.id)
    game.update_events(0.0)
    game._story_frame(0.1)
    assert mover.facing == "left"
    assert game.save.event_context.get_switch("route.Clerk.done")


def test_the_facing_an_event_starts_with_and_the_battle_running_switch():
    game = _game(("wait", [EventInstruction("WAIT", {"seconds": 5})]))
    game.set_player_facing("left")
    game._story_frame(0.0)
    context = game.save.event_context
    assert context.get_variable("player.facing") == "left"
    game.events.start("wait")
    game.update_events(0.0)
    game.set_player_facing("up")  # the event turned the player: the start facing stays
    game._story_frame(0.0)
    assert context.get_variable("player.facing") == "left"
    context.set_switch("battle.running", True)
    game._story_frame(0.0)  # back in the field: the battle is over
    assert not context.get_switch("battle.running")


def test_an_area_runs_an_arrival_program_once_on_entering():
    rule = AreaRule(
        "region:1", autorun=[{"variable": "door", "value": 1, "program": "p", "when": "enter"}]
    )
    assert rule.autorun_program(lambda n: False, {"door": 1}.get) == ""  # not an always one
    assert rule.autorun_program(lambda n: False, {"door": 1}.get, "enter") == "p"
    assert rule.autorun_program(lambda n: False, {"door": "1"}.get, "enter") == "p"
    with pytest.raises(ValueError):
        AreaRule("region:1", autorun=[{"switch": "s", "program": "p", "when": "later"}])


def test_a_hidden_person_comes_back_when_the_switch_turns_off():
    game = _game()
    mum = game.scene.add_entity(Entity("Mum"))
    mum.add_component(Transform(40, 40))
    spec = mum.add_component(SwitchVisibility2DComponent())
    spec.hidden_switch = "mum_inside"
    plain = game.scene.add_entity(Entity("Box"))
    plain.add_component(Transform(56, 40))
    context = game.save.event_context
    game._story_frame(0.0)  # the scene has loaded
    context.set_switch("mum_inside", True)
    game.show_entity("Box", False)
    game._story_frame(0.0)
    assert not mum.enabled and not plain.enabled
    context.set_switch("mum_inside", False)
    game.show_entity("Box", True)
    game._story_frame(0.0)
    assert mum.enabled and plain.enabled
