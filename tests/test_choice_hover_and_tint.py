"""A choice's hover commands (run when the pointer comes to an option: the picture changing
with it) and a picture mixed with a colour (``tint`` and ``tint_color``, tweened by
MOVE_PICTURE)."""

from pathlib import Path

import pytest

from asteria.events import EventProgram
from asteria.events.program import EventInstruction

ROOT = Path(__file__).resolve().parents[1] / "reference_projects"


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


def _show(picture_id, **args):
    return EventInstruction("WORLD", {"command": "SHOW_PICTURE",
                                      "args": {"picture_id": picture_id, **args}})  # fmt: skip


def test_hover_commands_run_when_the_pointer_comes_to_an_option():
    from asteria.events.dialogue import DialogueChoice

    move = {"command": "MOVE_PICTURE", "args": {"picture_id": "who", "x": 99}}
    choice = {
        "prompt": "Boy or girl?",
        "choices": [{"text": "BOY", "value": 0}, {"text": "GIRL", "value": 1, "hover": [move]}],
        "variable_name": "gender",
    }
    game = _game(("ask", [_show("who", asset_id="x", x=10), EventInstruction("CHOICE", choice)]))
    game.events.start("ask")
    game.update_events(0.0)
    assert game.pictures.get("who").x == 10
    assert game.hover_choice(1)
    assert game.pictures.get("who").x == 99
    assert game.hover_choice(0) and game.pictures.get("who").x == 99  # BOY has none
    data = game.pending_dialogue.choices[1].to_data()
    assert DialogueChoice.from_data(data).hover == (move,)
    with pytest.raises(ValueError):
        DialogueChoice("X", 1, hover=({"args": {}},))


def test_a_picture_is_tinted_and_tweened_back():
    game = _game()
    game.pictures.show("lotad", "x", 0, 0, tint=1.0, tint_color=[248, 176, 240])
    shown = game.pictures.get("lotad")
    assert (shown.tint, shown.tint_color) == (1.0, (248, 176, 240))
    game.pictures.move("lotad", tint=0.0, duration=1.0)
    game.pictures.update(0.5)
    assert game.pictures.get("lotad").tint == pytest.approx(0.5)
    game.pictures.update(0.5)
    assert game.pictures.get("lotad").tint == 0.0
    game.pictures.move("lotad", tint_color="0, 0, 0")
    assert game.pictures.get("lotad").tint_color == (0, 0, 0)
    game.pictures.show("plain", "x", 0, 0)
    plain = game.pictures.get("plain")
    assert (plain.tint, plain.tint_color) == (0.0, (255, 255, 255))  # white unless given
    with pytest.raises(ValueError):
        game.pictures.show("bad", "x", 0, 0, tint_color=[1, 2])


def test_a_delayed_move_plays_after_an_instant_one():
    game = _game()
    game.pictures.show("may", "x", 0, 0, opacity=1.0)
    game.pictures.move("may", x=240.0, opacity=0.0)  # at once: off to the right, unseen
    game.pictures.move("may", x=180.0, opacity=1.0, duration=0.25, delay=0.25)
    game.pictures.update(0.2)
    assert (game.pictures.get("may").x, game.pictures.get("may").opacity) == (240.0, 0.0)
    game.pictures.update(0.175)  # half way through the slide
    assert game.pictures.get("may").x == pytest.approx(210.0)
    game.pictures.update(0.2)
    assert (game.pictures.get("may").x, game.pictures.get("may").opacity) == (180.0, 1.0)


def test_a_sheet_cycles_its_cells_from_its_showing():
    game = _game()
    game.pictures.update(5.0)  # time before the showing does not count
    game.pictures.show("star", "x", 0, 0, columns=6, frame=1, frame_rate=60.0)
    assert game.pictures.get("star").frame == 1
    game.pictures.update(2 / 60)
    assert game.pictures.get("star").frame == 3
    game.pictures.update(3 / 60)
    assert game.pictures.get("star").frame == 0  # round again
    game.pictures.show("still", "x", 0, 0, columns=6, frame=2)
    game.pictures.update(1.0)
    assert game.pictures.get("still").frame == 2


def test_a_sheet_can_play_once_and_keep_its_last_cell():
    game = _game()
    game.pictures.show("shine", "x", 0, 0, columns=4, frame_rate=60.0, frame_loop=False)
    game.pictures.update(10 / 60)
    assert game.pictures.get("shine").frame == 3


def test_scroll_and_wave_follow_the_pictures_age():
    game = _game()
    game.pictures.show("clouds", "x", 0, 0, scroll_y=-15.0, wave_amplitude=4.0,
                       wave_length=64.0, wave_speed=64.0)  # fmt: skip
    game.pictures.update(2.0)
    clouds = game.pictures.get("clouds")
    assert clouds.age == pytest.approx(2.0)
    assert clouds.scroll_offset() == pytest.approx((0.0, -30.0))
    assert clouds.wave_offset(16) == pytest.approx(4.0)  # (16 + 128) / 64: a quarter on
    with pytest.raises(ValueError):
        game.pictures.show("bad", "x", 0, 0, wave_length=0.0)
    with pytest.raises(ValueError):
        game.pictures.show("bad", "x", 0, 0, sway=1.0)
    with pytest.raises(ValueError):
        game.pictures.show("bad", "x", 0, 0, blend="multiply")
    game.pictures.show("glow", "x", 0, 0, blend="add", opacity=0.375)
    assert game.pictures.get("glow").blend == "add"


def test_the_field_draws_a_picture_scrolled_round(monkeypatch):
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    import pygame

    from asteria.runtime.pictures import Picture
    from asteria.runtime.playtest.field_ui import FieldUiMixin

    class Host(FieldUiMixin):
        pg = pygame

    image = pygame.Surface((4, 4), pygame.SRCALPHA)
    image.fill((0, 0, 0, 255))
    image.set_at((0, 0), (255, 0, 0, 255))
    moved = Picture("p", "x", 0, 0, scroll_x=1.0, scroll_y=2.0, age=1.0)
    out = Host()._picture_motion(image, moved)
    assert tuple(out.get_at((1, 2)))[:3] == (255, 0, 0)  # one right, two down
    still = Picture("p", "x", 0, 0)
    assert Host()._picture_motion(image, still) is image


def test_the_choice_editor_writes_hover_lines():
    widgets = pytest.importorskip("PySide6.QtWidgets")
    _app = widgets.QApplication.instance() or widgets.QApplication([])
    from asteria.editor.choice_command_dialog import ChoiceCommandDialog, hover_text, parse_hover

    lines = "2: MOVE_PICTURE picture_id=girl, x=148, duration=0.25"
    hover = parse_hover(lines, 2)
    girl = {"picture_id": "girl", "x": 148, "duration": 0.25}
    assert hover == {1: [{"command": "MOVE_PICTURE", "args": girl}]}
    two = [{"text": "A", "value": 0}, {"text": "B", "value": 1}]
    dialog = ChoiceCommandDialog({"prompt": "?", "choices": two})
    try:
        dialog.hover.setPlainText(lines)
        args = dialog.result_args()
    finally:
        dialog.deleteLater()
    assert args["choices"][1]["hover"] == hover[1] and "hover" not in args["choices"][0]
    assert hover_text(args["choices"]) == lines
