"""Fanfares (PLAY_ME) that pause the music and give it back, event programs waiting for a
fanfare or a sound (the ``audio`` condition source), tiles changed while playing (SET_TILE: for
the visit or for good), and choices that start on an option and answer the cancel key."""

import time
import wave
from pathlib import Path

import pytest

from asteria.events import EventProgram
from asteria.events.program import EventInstruction

ROOT = Path(__file__).resolve().parents[1] / "reference_projects"


def _world(command, **args):
    return EventInstruction("WORLD", {"command": command, "args": args})


def _wav(path, seconds):
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(1)
        out.setframerate(8000)
        out.writeframes(bytes([128]) * int(8000 * seconds))
    return path


def _game(project_folder, *programs):
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.game_session import GameSessionRuntime

    path = ROOT / project_folder / "project.asteria.json"
    project = Project.load_json(path, EditorDocument().component_registry)
    for program_id, instructions in programs:
        project.event_programs.register(
            program_id, EventProgram(tuple(instructions), name=program_id)
        )
    return GameSessionRuntime(project, project.game_start.instantiate(project))


def test_a_fanfare_pauses_the_music_and_gives_it_back(tmp_path):
    from asteria.events.world_commands import WorldCommand
    from asteria.runtime.audio_mixer import AudioMixer, RecordingAudioDevice

    files = {"town": _wav(tmp_path / "town.wav", 1.0), "jingle": _wav(tmp_path / "j.wav", 0.1)}
    device = RecordingAudioDevice()
    mixer = AudioMixer(device, files.get)
    mixer.play_music("town")
    mixer.handle_world_request(WorldCommand("PLAY_ME", {"asset_id": "jingle"}))
    assert ("pause_music",) in device.calls and mixer.me_playing()
    mixer.update()
    assert ("resume_music",) not in device.calls  # still playing: the music waits
    time.sleep(0.15)
    mixer.update()
    assert device.calls[-1] == ("resume_music",) and not mixer.me_playing()
    assert mixer.music_asset_id == "town"
    mixer.handle_world_request(WorldCommand("PLAY_SE", {"asset_id": "jingle"}))
    assert mixer.se_playing()


def test_an_event_waits_for_the_fanfare_only_where_sound_plays():
    wait = {"source": "audio", "name": "me", "operator": "==", "value": False}
    program = [
        _world("PLAY_ME", asset_id="jingle"),
        EventInstruction("WAIT", {"until": {**wait, "scope_id": None}}),
        EventInstruction("SET_SWITCH", {"name": "after", "value": True}),
    ]
    game = _game("party_rpg_demo", ("fanfare", program))
    context = game.save.event_context
    game.plays_audio = True  # a host that plays sound (the playtest window)
    game.events.start("fanfare")
    game.update_events(0.0)
    assert game.audio_status["me"] and not context.get_switch("after")
    game.audio_status["me"] = False  # the host: the jingle ended
    game.update_events(0.0)
    assert context.get_switch("after")
    headless = _game("party_rpg_demo", ("fanfare", program))
    headless.events.start("fanfare")
    headless.update_events(0.0)  # no sound here: nothing to wait for
    assert headless.save.event_context.get_switch("after")
    with pytest.raises(ValueError):
        headless._audio_value("bgm")


def _set_tile_game():
    return _game("party_rpg_demo")


def test_set_tile_lasts_for_the_visit_or_for_good():
    from asteria.rpg.world_record import WorldRecord

    game = _set_tile_game()
    here = game.scene.id
    program = [
        _world("SET_TILE", layer="Below", x=3, y=4, tile=7),
        _world("SET_TILE", layer="Collision", x=3, y=4, tile=-1, permanent=True),
    ]
    game.project.event_programs.register("tiles", EventProgram(tuple(program), name="tiles"))
    version = game.tile_changes_version
    game.events.start("tiles")
    game.update_events(0.0)
    assert game.tile_changes() == {("Below", 3, 4): 7, ("Collision", 3, 4): -1}
    assert game.tile_changes_version > version
    from asteria.core import Scene

    game.scene = Scene("Elsewhere")  # the player left: this visit's change is gone, the kept
    game._forget_tile_changes()  # one stays
    assert game.tile_changes(here) == {("Collision", 3, 4): -1}
    saved = WorldRecord.from_data(game.world.to_data())
    assert saved.systems[f"tiles.{here}"] == {"Collision|3|4": -1}


def test_the_field_view_draws_and_walks_by_changed_tiles(monkeypatch):
    pytest.importorskip("pygame")
    import real_window

    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    if not real_window.enabled():
        monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
        monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from asteria.editor import EditorDocument
    from asteria.project import Project

    root = ROOT / "arpg_demo"
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    rt = PlayableTestRuntime(
        project, project.game_start.instantiate(project), root, width=960, height=540
    )
    rt.open()
    rt._ui_mode = "field"
    try:
        rt._frame([], 1 / 60)
        view = rt.tile_view
        walls = next(layer for layer in view.tilemap.layers if layer.collision_enabled)
        source = next(layer for layer in view._source_tilemap.layers if layer.name == walls.name)
        tw = view.tilemap.tile_width
        x, y = 2, 2
        before = view.blocking.collides_world_point((x + 0.5) * tw, (y + 0.5) * tw)
        rt.game.set_tile(walls.name, x, y, -1 if before else 0)
        rt._frame([], 1 / 60)
        after = view.blocking.collides_world_point((x + 0.5) * tw, (y + 0.5) * tw)
        assert after is not before  # the wall opened (or closed)
        cw = view.tilemap.chunk_width
        key = (x // cw, y // cw)
        if key in source.chunks:  # the loaded map itself is not changed
            assert walls.chunks[key] is not source.chunks[key]
        rt.game._tile_changes.clear()
        rt.game.tile_changes_version += 1
        rt._frame([], 1 / 60)
        assert view.blocking.collides_world_point((x + 0.5) * tw, (y + 0.5) * tw) is before
    finally:
        rt.close()


def test_a_choice_starts_on_its_option_and_answers_the_cancel_key():
    from asteria.events.dialogue import ChoiceRequest, DialogueChoice

    choice = {
        "prompt": "Which?",
        "choices": [{"text": "A", "value": 0}, {"text": "B", "value": 1}],
        "variable_name": "answer",
        "cursor": 1,
        "cancel": 127,
    }
    game = _game(
        "party_rpg_demo",
        ("ask", [EventInstruction("CHOICE", choice)]),
    )
    game.events.start("ask")
    game.update_events(0.0)
    request = game.pending_dialogue
    assert request.cursor == 1 and request.cancel == (127,)
    assert ChoiceRequest.from_data(request.to_data()) == request
    assert game.cancel_choice()
    assert game.save.event_context.get_variable("answer") == 127
    plain = ChoiceRequest("Go?", [DialogueChoice("Yes", 1)], cursor=5)
    assert plain.cursor == 0 and plain.cancel == () and "cancel" not in plain.to_data()
    assert plain.columns == 1 and "columns" not in plain.to_data()
    grid = ChoiceRequest("Topic?", [DialogueChoice(str(n), n) for n in range(6)], columns=3)
    assert ChoiceRequest.from_data(grid.to_data()).columns == 3
    without = dict(choice)
    del without["cancel"]
    game.project.event_programs.register(
        "free", EventProgram((EventInstruction("CHOICE", without),), name="free")
    )
    game.events.start("free")
    game.update_events(0.0)
    assert not game.cancel_choice() and game.pending_dialogue is not None  # still waiting


def test_the_choice_editor_writes_options_start_cancel_and_place():
    widgets = pytest.importorskip("PySide6.QtWidgets")
    _app = widgets.QApplication.instance() or widgets.QApplication([])
    from asteria.editor.choice_command_dialog import ChoiceCommandDialog, parse_options

    assert parse_options("YES = 1\nNO = 0\nMAYBE") == [
        {"text": "YES", "value": 1},
        {"text": "NO", "value": 0},
        {"text": "MAYBE", "value": 3},
    ]
    dialog = ChoiceCommandDialog({"prompt": "Go?", "choices": [{"text": "Y", "value": 1}],
                                  "variable_name": "v", "prompt_key": "k"})  # fmt: skip
    try:
        dialog.options.setPlainText("FOSSIL = 0\nEXIT = 1")
        dialog.cursor.setValue(2)
        dialog.cancel.setText("127")
        dialog.box_at.setText("144, 56")
        dialog.columns.setValue(3)
        args = dialog.result_args()
    finally:
        dialog.deleteLater()
    assert args["choices"] == [{"text": "FOSSIL", "value": 0}, {"text": "EXIT", "value": 1}]
    assert args["cursor"] == 1 and args["cancel"] == 127 and args["box_at"] == [144, 56]
    assert args["prompt_key"] == "k" and args["variable_name"] == "v" and args["columns"] == 3


def test_the_wait_editor_writes_seconds_or_a_condition_of_any_source():
    widgets = pytest.importorskip("PySide6.QtWidgets")
    _app = widgets.QApplication.instance() or widgets.QApplication([])
    from asteria.editor.wait_command_dialog import SOURCES, WaitCommandDialog

    assert "audio" in SOURCES and "rpg" in SOURCES
    until = {"source": "audio", "name": "me", "operator": "==", "value": False, "scope_id": None}
    dialog = WaitCommandDialog({"until": until})
    try:
        assert dialog.result_args() == {"until": until}  # opened as written, written back
        dialog.mode.setCurrentIndex(0)
        dialog.seconds.setValue(0.25)
        assert dialog.result_args() == {"seconds": 0.25}
    finally:
        dialog.deleteLater()
