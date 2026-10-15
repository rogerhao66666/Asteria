"""Event timers in a session: world commands start them, expiry queues the program."""

from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.events.world_commands import WorldCommand
from asteria.project import Project
from asteria.runtime.game_session import GameSessionRuntime
from asteria.runtime.world_command_handlers import WORLD_COMMAND_ARGUMENTS

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "octopath_demo"


@pytest.fixture
def game():
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    return GameSessionRuntime(project, project.game_start.instantiate(project))


def _run(game, name, **args):
    return game.world_commands.dispatch(WorldCommand(name, args))


def test_commands_start_pause_add_and_stop(game):
    _run(game, "TIMER_START", timer_id="t", seconds=20, on_expire="late")
    assert game.timers.remaining("t") == 20
    _run(game, "TIMER_PAUSE", timer_id="t")
    game.update_events(5)
    assert game.timers.remaining("t") == 20
    _run(game, "TIMER_RESUME", timer_id="t")
    _run(game, "TIMER_ADD", timer_id="t", seconds=10)
    game.update_events(5)
    assert game.timers.remaining("t") == 25
    _run(game, "TIMER_STOP", timer_id="t")
    assert game.timers.active() == ()


def test_expiry_queues_the_named_program_once(game):
    _run(game, "TIMER_START", timer_id="t", seconds=1, on_expire="late")
    game.update_events(0.4)
    assert game.pending_followups == []
    game.events.start = lambda program, **kw: setattr(game, "_started", program)
    game.update_events(0.7)
    assert getattr(game, "_started", None) == "late"
    game.update_events(1.0)
    assert game.pending_followups == []


def test_timers_do_not_run_during_battle(game):
    _run(game, "TIMER_START", timer_id="t", seconds=5)
    game.mode = "battle"
    game.update_events(3)
    assert game.timers.remaining("t") == 5


def test_bad_commands_raise_world_command_errors(game):
    from asteria.runtime.world_command_handlers import WorldCommandError

    with pytest.raises(WorldCommandError):
        _run(game, "TIMER_ADD", timer_id="ghost", seconds=1)
    with pytest.raises(WorldCommandError):
        _run(game, "TIMER_START", timer_id="a.b", seconds=1)
    with pytest.raises(WorldCommandError):
        _run(game, "TIMER_START", seconds=1)


def test_the_editor_knows_the_timer_commands():
    assert WORLD_COMMAND_ARGUMENTS["TIMER_START"][0] == "timer_id"
    assert set(WORLD_COMMAND_ARGUMENTS) >= {
        "TIMER_STOP",
        "TIMER_PAUSE",
        "TIMER_RESUME",
        "TIMER_ADD",
    }


def test_a_visible_timer_draws_on_the_field(monkeypatch):
    pygame = pytest.importorskip("pygame")
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), ROOT, width=960, height=540
    )
    runtime.open()
    try:
        runtime._ui_mode = "field"
        runtime.game.timers.start("t", 75)
        runtime.screen.fill((0, 0, 0))
        runtime._draw_event_timers()
        spot = runtime.screen.get_at((runtime.width - 66, 31))
        assert pygame.image.tobytes(runtime.screen, "RGB").count(b"\xf5\xf5\xfa") > 0
        assert spot[:3] != (0, 0, 0)
    finally:
        runtime.close()
