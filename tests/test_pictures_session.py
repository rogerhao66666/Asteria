"""Pictures in a session and in the playable runtime: commands, clicks, drawing, saving."""

from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.events.world_commands import WorldCommand
from asteria.project import Project
from asteria.runtime.game_session import GameSessionRuntime
from asteria.runtime.world_command_handlers import WORLD_COMMAND_ARGUMENTS, WorldCommandError

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "octopath_demo"
IMAGE = "playable_assets/item_icons.png"


def _project():
    return Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)


def _session():
    project = _project()
    return GameSessionRuntime(project, project.game_start.instantiate(project))


def _run(game, name, **args):
    return game.world_commands.dispatch(WorldCommand(name, args))


def test_commands_show_move_frame_and_erase():
    game = _session()
    _run(game, "SHOW_PICTURE", picture_id="p", asset_id=IMAGE, x=10, y=20, columns=2, rows=2)
    assert game.pictures.get("p").x == 10 and game.pictures.get("p").columns == 2
    _run(game, "MOVE_PICTURE", picture_id="p", x=50, duration=1.0)
    game.update_events(0.5)
    assert game.pictures.get("p").x == pytest.approx(30)  # the tween runs with the session
    _run(game, "SET_PICTURE_FRAME", picture_id="p", frame=3)
    assert game.pictures.get("p").frame == 3 and game.pictures.get("p").y == 20  # y untouched
    _run(game, "ERASE_PICTURE", picture_id="p")
    assert game.pictures.get("p") is None


def test_bad_picture_commands_are_world_command_errors():
    game = _session()
    for name, args in (
        ("SHOW_PICTURE", {"picture_id": "p"}),
        ("SHOW_PICTURE", {"picture_id": "a.b", "asset_id": IMAGE}),
        ("MOVE_PICTURE", {"picture_id": "ghost", "x": 1}),
    ):
        with pytest.raises(WorldCommandError):
            _run(game, name, **args)
    assert {"SHOW_PICTURE", "MOVE_PICTURE", "SET_PICTURE_FRAME", "ERASE_PICTURE"} <= set(
        WORLD_COMMAND_ARGUMENTS
    )


def test_clicking_a_picture_queues_its_event_program_once():
    game = _session()
    _run(game, "SHOW_PICTURE", picture_id="door", asset_id=IMAGE, x=100, y=100, click_event="open")
    size = lambda picture: (64, 64)  # noqa: E731
    assert game.click_picture(10, 10, size) is None and game.pending_followups == []
    assert game.click_picture(120, 120, size).picture_id == "door"
    assert game.pending_followups == ["open"]
    game.mode = "battle"
    assert game.click_picture(120, 120, size) is None  # clicks only count in the field


def test_pictures_are_saved_with_the_game():
    game = _session()
    _run(game, "SHOW_PICTURE", picture_id="p", asset_id=IMAGE, x=7, y=8, opacity=0.5)
    other = GameSessionRuntime(game.project, game.save)
    assert other.pictures.get("p").x == 7 and other.pictures.get("p").opacity == 0.5


def _runtime(monkeypatch):
    pytest.importorskip("pygame")
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = _project()
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), ROOT, width=960, height=540
    )
    runtime.open()
    return runtime


def test_pictures_are_drawn_scaled_and_faded(monkeypatch):
    runtime = _runtime(monkeypatch)
    try:
        runtime.screen.fill((0, 0, 0))
        _run(runtime.game, "SHOW_PICTURE", picture_id="p", asset_id=IMAGE, x=20, y=20, scale=2.0)
        runtime._draw_pictures()
        assert runtime.pg.image.tobytes(runtime.screen, "RGB") != bytes(960 * 540 * 3)
        size = runtime._picture_size(runtime.game.pictures.get("p"))
        assert size and size[0] > 0
        runtime.screen.fill((0, 0, 0))
        _run(runtime.game, "MOVE_PICTURE", picture_id="p", opacity=0.0)
        runtime._draw_pictures()
        assert runtime.pg.image.tobytes(runtime.screen, "RGB") == bytes(960 * 540 * 3)
    finally:
        runtime.close()


def test_a_mouse_click_on_a_picture_starts_its_event(monkeypatch):
    runtime = _runtime(monkeypatch)
    try:
        _run(
            runtime.game,
            "SHOW_PICTURE",
            picture_id="b",
            asset_id=IMAGE,
            x=50,
            y=50,
            click_event="go",
        )
        click = runtime.pg.event.Event(runtime.pg.MOUSEBUTTONDOWN, pos=(60, 60), button=1)
        runtime._ui_mode = "field"
        runtime._field_input([click], 0.016)
        assert runtime.game.pending_followups == ["go"]
        miss = runtime.pg.event.Event(runtime.pg.MOUSEBUTTONDOWN, pos=(900, 500), button=1)
        runtime.game.pending_followups.clear()
        runtime._field_input([miss], 0.016)
        assert runtime.game.pending_followups == []
    finally:
        runtime.close()
