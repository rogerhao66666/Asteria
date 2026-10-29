"""Dialogue portraits (D41): the line's portrait and side, the project's portrait style, the game's
message window drawing them, and the editor's Dialogue window that picks them."""

import json
from pathlib import Path

import pytest

from asteria.events import EventInstruction, EventProgram
from asteria.events.dialogue import DialogueLine, DialogueRequest
from asteria.rpg.localization import MessageSettings

REPO = Path(__file__).resolve().parents[1]
MAGENTA = (255, 0, 255)


# --- data ------------------------------------------------------------------------------------


def test_a_line_writes_its_portrait_side_only_when_it_is_right():
    left = DialogueLine("Hi", "Hana", "portraits/hana.png")
    assert "portrait_side" not in left.to_data() and left.portrait_side == "left"
    right = DialogueLine("Hi", "Hana", "portraits/hana.png", "right")
    assert right.to_data()["portrait_side"] == "right"
    assert DialogueLine.from_data(right.to_data()) == right
    old = {"text": "Hi", "speaker": "", "portrait_asset_id": ""}  # data from before D41
    assert DialogueLine.from_data(old) == DialogueLine("Hi")
    with pytest.raises(ValueError):
        DialogueLine("Hi", portrait_side="middle")
    with pytest.raises(ValueError):
        DialogueLine.from_data({**old, "extra": 1})


def test_the_runner_passes_the_side_and_reads_an_unknown_one_as_left():
    from asteria.events import EventContext, EventProgramRegistry, EventRunner

    def line_of(args):
        registry = EventProgramRegistry()
        registry.register("e", EventProgram([EventInstruction("DIALOGUE", args)]))
        runner = EventRunner(registry, context=EventContext())
        runner.start("e", source_entity_id="npc", local_scope_id="npc")
        runner.update()
        return runner.dialogue.dialogue.line

    line = line_of({"text": "Hi", "portrait_asset_id": "p.png", "portrait_side": "Right"})
    assert (line.portrait_asset_id, line.portrait_side) == ("p.png", "right")
    assert line_of({"text": "Hi", "portrait_side": "up"}).portrait_side == "left"


def test_message_settings_write_the_portrait_options_only_when_set():
    plain = MessageSettings("default")
    assert (plain.portrait_style, plain.portrait_size) == ("face", 0)
    assert "portrait_style" not in plain.to_data() and "portrait_size" not in plain.to_data()
    bust = MessageSettings("default", portrait_style="bust", portrait_size=320)
    assert MessageSettings.from_data(bust.to_data()) == bust
    with pytest.raises(ValueError):
        MessageSettings("default", portrait_style="huge")
    with pytest.raises(ValueError):
        MessageSettings("default", portrait_size=-1)


def test_the_script_api_writes_portrait_keys_only_when_set():
    from asteria.authoring.api import say

    assert say("Hana", "Hi") == ("DIALOGUE", {"speaker": "Hana", "text": "Hi"})
    assert say("Hana", "Hi", portrait="portraits/hana.png", side="right")[1] == {
        "speaker": "Hana",
        "text": "Hi",
        "portrait_asset_id": "portraits/hana.png",
        "portrait_side": "right",
    }
    with pytest.raises(ValueError):
        say("Hana", "Hi", side="up")


# --- the game's message window ------------------------------------------------------------------


def _picture(path, size, color=MAGENTA):
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (*color, 255)).save(path)


def _show(runtime, monkeypatch, line):
    request = DialogueRequest(line)
    monkeypatch.setattr(type(runtime.game), "pending_dialogue", property(lambda self: request))
    calls = []
    original = runtime.text

    def text(value, x, y, **kw):
        calls.append((str(value), int(x), int(y), kw.get("anchor")))
        return original(value, x, y, **kw)

    monkeypatch.setattr(runtime, "text", text)
    runtime.screen.fill((0, 0, 0))
    runtime._draw_dialogue()
    return calls


def test_a_face_sits_in_the_window_and_the_text_makes_room(runtime, monkeypatch):
    _picture(runtime.resource_root / "portraits" / "face.png", (32, 32))
    calls = _show(runtime, monkeypatch, DialogueLine("Hello", "Hana", "portraits/face.png"))
    # 960 x 540: the window is (60, 310, 840, 130); the face's square is (72, 322, 106, 106)
    assert runtime.screen.get_at((125, 375))[:3] == MAGENTA
    assert ("Hana", 196, 322, None) in calls  # the speaker starts after the face
    assert ("Hello", 196, 356, None) in calls
    assert runtime.dialogue_portrait("portraits/face.png", 106, 106).get_size() == (106, 106)
    assert ("portraits/face.png", 106, 106) in runtime._portrait_cache
    runtime.release_resource_scope("field")
    assert runtime._portrait_cache == {}

    calls = _show(
        runtime, monkeypatch, DialogueLine("Hello", "Hana", "portraits/face.png", "right")
    )
    assert runtime.screen.get_at((835, 375))[:3] == MAGENTA
    assert runtime.screen.get_at((125, 375))[:3] != MAGENTA
    assert ("Hana", 84, 322, None) in calls
    hint = next(c for c in calls if c[0] == "Enter / E: continue")
    assert hint[1] == 782 - 14 and hint[3] == "topright"  # ends before the face


def test_a_big_face_grows_the_window_and_a_bust_stands_on_it(runtime, monkeypatch):
    _picture(runtime.resource_root / "portraits" / "tall.png", (100, 300))
    assert runtime.dialogue_portrait("portraits/tall.png", 106, 106).get_size() == (35, 106)
    _picture(runtime.resource_root / "portraits" / "face.png", (32, 32))
    db = runtime.project.rpg_database
    db.add_message_settings(MessageSettings("default", portrait_size=160))
    calls = _show(runtime, monkeypatch, DialogueLine("Hello", "Hana", "portraits/face.png"))
    # the window grows to 184 high: (60, 256, 840, 184); the square is (72, 268, 160, 160)
    assert runtime.screen.get_at((152, 348))[:3] == MAGENTA
    assert ("Hana", 72 + 160 + 18, 268, None) in calls

    db.message_settings.clear()
    db.add_message_settings(MessageSettings("default", portrait_style="bust", portrait_size=200))
    calls = _show(runtime, monkeypatch, DialogueLine("Hello", "Hana", "portraits/face.png"))
    # 200 x 200 standing on the window's bottom edge (y 440), its top above the window
    assert runtime.screen.get_at((184, 260))[:3] == MAGENTA
    assert ("Hana", 84, 322, None) in calls  # a bust leaves the text where it was


def test_a_missing_portrait_shows_the_line_without_one(runtime, monkeypatch):
    calls = _show(runtime, monkeypatch, DialogueLine("Hello", "Hana", "portraits/none.png"))
    assert ("Hana", 84, 322, None) in calls
    assert runtime.dialogue_portrait("portraits/none.png", 50, 50) is None


# --- the editor ---------------------------------------------------------------------------------


@pytest.fixture
def document(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.project import Project

    QApplication.instance() or QApplication([])
    ref = REPO / "reference_projects" / "party_rpg_demo" / "project.asteria.json"
    doc = EditorDocument()
    doc.project = Project.load_json(ref, doc.component_registry)
    doc.file_path = tmp_path / "project.asteria.json"  # pictures are looked for in tmp_path
    _picture(tmp_path / "portraits" / "hana.png", (48, 48))
    _picture(tmp_path / "art" / "faces" / "kai.png", (48, 48))
    _picture(tmp_path / "icons" / "gem.png", (16, 16))
    return doc


def test_the_portrait_list_has_portrait_folders_only_and_browse_copies_in(document, tmp_path):
    from asteria.editor.image_tools import PortraitLibrary

    library = PortraitLibrary(document)
    ids = [i for i, _ in library.choices()]
    assert "portraits/hana.png" in ids and "art/faces/kai.png" in ids
    assert "icons/gem.png" not in ids and not any(i.startswith("forged:") for i in ids)
    outside = tmp_path.parent / f"{tmp_path.name}_outside" / "mira.png"
    _picture(outside, (40, 40))
    assert library.import_file(outside) == "portraits/mira.png"
    assert "portraits/mira.png" in [i for i, _ in library.choices()]


def test_the_dialogue_window_edits_speaker_text_portrait_and_side(document):
    from PySide6.QtWidgets import QDialogButtonBox

    from asteria.editor.dialogue_command_dialog import DialogueCommandDialog

    dialog = DialogueCommandDialog({"speaker": "Hana", "text": "Hi", "note": 1}, document=document)
    assert dialog.result_args() == {"note": 1, "speaker": "Hana", "text": "Hi"}
    dialog.portrait.setText("portraits/hana.png")
    dialog.side.setCurrentIndex(dialog.side.findData("right"))
    assert dialog.result_args() == {
        "note": 1,
        "speaker": "Hana",
        "text": "Hi",
        "portrait_asset_id": "portraits/hana.png",
        "portrait_side": "right",
    }
    assert not dialog.portrait.preview.pixmap().isNull()  # the picker shows the picture
    assert not dialog.preview.grab().isNull()  # the message-window preview paints (face)
    document.project.rpg_database.add_message_settings(
        MessageSettings("default", portrait_style="bust")
    )
    assert not dialog.preview.grab().isNull()  # and a bust
    save = dialog.buttons.button(QDialogButtonBox.Save)
    assert save.isEnabled()
    dialog.text.setPlainText("   ")
    assert not save.isEnabled()  # a line needs words
    dialog.close()


def test_the_event_editor_adds_and_edits_a_dialogue_with_a_portrait(monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.workspace import WorkspaceMode
    from asteria.project import Project

    ref = REPO / "reference_projects/complex_reference_rpg/project.asteria.json"
    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow(None)
    try:
        window.document.set_project(
            Project.load_json(ref, window.document.component_registry), file_path=ref
        )
        window.workspace.set_mode(WorkspaceMode.EVENT)
        boss = next(
            e for e in window.document.project.scenes()[0].entities() if e.name == "Astral Tyrant"
        )
        window.document.selection.set_single("entity", boss)
        window.refresh_all()
        added = {"speaker": "Hana", "text": "Hi", "portrait_asset_id": "portraits/hana.png"}
        monkeypatch.setattr(window, "_dialogue_dialog", lambda current=None: dict(added))
        programs = window.document.project.event_programs
        before = programs.require("boss_interaction_event")
        window._event_add_command("dialogue")
        program = programs.require("boss_interaction_event")
        index = next(i for i, x in enumerate(program.instructions) if x.args == added)
        assert "[portrait: hana.png]" in window.event_editor.commands.item(index).text()
        monkeypatch.setattr(
            window, "_dialogue_dialog", lambda current=None: dict(current, portrait_side="right")
        )
        assert window._event_edit_command(index)
        edited = programs.require("boss_interaction_event").instructions[index]
        assert edited.args == {**added, "portrait_side": "right"}
        assert "[portrait: hana.png, right]" in window.event_editor.commands.item(index).text()
        window.document.undo()
        assert programs.require("boss_interaction_event") == program
        window.document.undo()
        assert programs.require("boss_interaction_event") == before
    finally:
        window.document.mark_saved()
        window.close()
        app.processEvents()


def test_sequence_dialogue_steps_keep_portrait_keys_only_when_set():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.event_flow_widget import SequenceEditorDialog

    QApplication.instance() or QApplication([])
    dialog = SequenceEditorDialog()
    dialog.opcode.setCurrentText("DIALOGUE")
    dialog.fields["text"].setText("Hi")
    assert dialog.step_from_form()["args"] == {"speaker": "", "text": "Hi"}
    dialog.fields["portrait_asset_id"].setText("portraits/hana.png")
    dialog.fields["portrait_side"].setText("right")
    assert dialog.step_from_form()["args"] == {
        "speaker": "",
        "text": "Hi",
        "portrait_asset_id": "portraits/hana.png",
        "portrait_side": "right",
    }
    dialog.close()


def test_the_message_settings_form_offers_the_portrait_options_in_both_languages():
    from asteria.editor.game_systems_authoring import FORMS

    fields = {f.key: f for f in FORMS["message_settings"]}
    assert fields["portrait_style"].choices == ("face", "bust")
    assert fields["portrait_size"].kind == "int"
    table = json.loads(
        (REPO / "src/asteria/editor/translations/zh_TW.json").read_text(encoding="utf-8")
    )["exact"]
    for text in (
        "Portrait Style",
        "Portrait Size (px, 0 = automatic)",
        "Face",
        "Bust",
        "Portrait side",
        "Choose a portrait",
        "Nobody (narration)",
        "Write the line's text first",
        "Use a picture file of your own as the portrait",
    ):
        assert table.get(text), text


def test_the_preview_holds_its_dialog_weakly(document):
    """The preview kept its dialog in an attribute while the dialog held the preview; PySide6
    6.12 crashed collecting that cycle (CI segfaulted in this file)."""
    import gc
    import weakref

    from asteria.editor.dialogue_command_dialog import DialogueCommandDialog

    dialog = DialogueCommandDialog({"speaker": "Hana", "text": "Hi"}, document=document)
    assert dialog.preview.owner is dialog
    assert dialog not in gc.get_referents(dialog.preview.__dict__)
    gone = weakref.ref(dialog)
    dialog.close()
    del dialog
    assert gone() is None  # freed by reference counting, without the cycle collector
