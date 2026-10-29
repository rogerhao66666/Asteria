"""A title screen made as an event program (``title_screen.program``): it runs before any game
with its pictures and choices, waits for a control (``rpg`` ``pressed:<action>``) and
TITLE_COMMAND starts a new game, continues the latest save, opens the load slots or a menu
screen, or quits."""

from pathlib import Path

import pytest

from asteria.events import EventProgram
from asteria.events.program import EventInstruction

ROOT = Path(__file__).resolve().parents[1] / "reference_projects"


def _world(command, **args):
    return EventInstruction("WORLD", {"command": command, "args": args})


def _project():
    from asteria.editor import EditorDocument
    from asteria.project import Project

    path = ROOT / "arpg_demo" / "project.asteria.json"
    return Project.load_json(path, EditorDocument().component_registry)


def test_title_requests_and_the_control_conditions():
    from asteria.runtime.game_session import GameSessionError, GameSessionRuntime

    project = _project()
    game = GameSessionRuntime(project, project.game_start.instantiate(project))
    assert game.request_title("new_game") == {"action": "new_game", "screen": ""}
    for wrong in (("dance",), ("screen",)):
        with pytest.raises(GameSessionError):
            game.request_title(*wrong)
    assert game._rpg_value("pressed:confirm") is False and game._rpg_value("saves") == 0
    game.input_actions = {"held": {"confirm"}, "pressed": {"confirm"}}
    game.saves_used = 2
    assert game._rpg_value("pressed:confirm") and game._rpg_value("held:confirm")
    assert not game._rpg_value("pressed:cancel") and game._rpg_value("saves") == 2
    assert game._rpg_value("pressed:cancel|confirm") and not game._rpg_value("held:menu|cancel")


def test_the_title_program_runs_then_starts_a_new_game(monkeypatch, tmp_path):
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = _project()
    pressed = {"source": "rpg", "name": "pressed:confirm", "operator": "==", "value": True,
               "scope_id": None}  # fmt: skip
    asset = "logo_image"  # (not drawn: the picture is there all the same)
    project.event_programs.register(
        "title",
        EventProgram(
            (
                _world("SHOW_PICTURE", picture_id="logo", asset_id=asset),
                EventInstruction("WAIT", {"until": pressed}),
                _world("TITLE_COMMAND", action="new_game"),
            ),
            name="title",
        ),
    )
    rt = PlayableTestRuntime(
        project, project.game_start.instantiate(project), ROOT / "arpg_demo", width=960,
        height=540,
    )  # fmt: skip
    rt.open()
    rt.resource_root = tmp_path  # no saves: the title runs in a new game
    rt.manifest["title_screen"] = {"program": "title"}
    try:
        import pygame

        rt._frame([], 1 / 60)
        assert rt._ui_mode == "title" and rt.game.pictures.exists("logo")
        assert rt.game.saves_used == 0
        escape = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        rt._frame([escape], 1 / 60)
        assert rt.running  # the title's own program has the keys
        title_game = rt.game
        rt.game.input_actions = {"held": {"confirm"}, "pressed": {"confirm"}}
        rt._title_program_frame([], 1 / 60, "title")
        assert rt._ui_mode == "field"
        assert rt.game is not title_game and not rt.game.pictures.exists("logo")
    finally:
        rt.close()


def test_a_title_menu_screen_comes_back_to_the_title(monkeypatch):
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = _project()
    rt = PlayableTestRuntime(
        project, project.game_start.instantiate(project), ROOT / "arpg_demo", width=960,
        height=540,
    )  # fmt: skip
    rt.open()
    try:
        rt._title_action({"action": "quit", "screen": ""})
        assert not rt.running
        rt.running = True
        rt._title_action({"action": "load", "screen": ""})
        assert rt._ui_mode == "slots" and rt._slots_back == "title"
        rt._ui_mode = "title"
        rt._title_action({"action": "screen", "screen": "options"})
        menu = rt._creature_menu
        assert rt._ui_mode == "creature_menu" and menu.phase == "options" and menu.alone
        menu._back()  # leaving the screen opened by itself closes the menu: the title again
        assert menu.done
    finally:
        rt.close()


def test_a_picture_of_words_fills_in_its_variables(monkeypatch):
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = _project()
    rt = PlayableTestRuntime(
        project, project.game_start.instantiate(project), ROOT / "arpg_demo", width=960,
        height=540,
    )  # fmt: skip
    rt.open()
    try:
        game = rt.game
        game.save.event_context.set_variable("badges", "1")
        game.pictures.show("info", "", 8, 8, text="BADGES \\V[badges]", text_color=[0, 0, 0],
                           shadow_color=[200, 200, 200])  # fmt: skip
        one = rt._picture_image(game.pictures.get("info"))
        game.save.event_context.set_variable("badges", "12")
        two = rt._picture_image(game.pictures.get("info"))
        assert two.get_width() > one.get_width() > 0  # the words were drawn again
        with pytest.raises(ValueError):
            game.pictures.show("nothing", "", 0, 0)
        rt._frame([], 1 / 60)  # drawn among the pictures
    finally:
        rt.close()


def test_the_message_words_for_time_played_and_creatures_owned():
    from asteria.runtime.game_session import GameSessionRuntime

    project = _project()
    game = GameSessionRuntime(project, project.game_start.instantiate(project))
    game.world.add_counter("play.seconds", 3 * 3600 + 7 * 60 + 59)
    game.world.bestiary["lotad"] = {"seen": 1, "captured": 1}
    game.world.bestiary["wurmple"] = {"seen": 2}
    assert game.expand_message("\\V[play.time]", plain=True) == "3:07"
    assert game.expand_message("\\V[creatures.owned]", plain=True) == str(
        1 + len({p.species_id for p in game.pets()} - {"lotad"})
    )
    game.save.event_context.set_variable("play.time", "kept")  # a variable comes first
    assert game.expand_message("\\V[play.time]", plain=True) == "kept"
    with pytest.raises(ValueError):
        game.pictures.show("p", "", 0, 0, text="X", text_align="up")


def test_a_wait_ends_on_its_condition_or_its_time_limit():
    from asteria.events import EventContext, EventVM

    lit = {"source": "switch", "name": "key", "operator": "==", "value": True,
           "scope_id": None}  # fmt: skip
    program = EventProgram(
        (EventInstruction("WAIT", {"until": lit, "seconds": 1.0}),
         EventInstruction("SET_SWITCH", {"name": "after", "value": True})),
        name="w",
    )  # fmt: skip
    for pressed_at, ended_at in ((None, 1.0), (0.25, 0.25)):
        context = EventContext()
        vm = EventVM(program, context=context)
        vm.step()
        clock = 0.0
        while vm.waiting:
            clock += 0.125
            if pressed_at is not None and clock >= pressed_at:
                context.set_switch("key", True)
            vm.update_wait(0.125)
        assert clock == ended_at
