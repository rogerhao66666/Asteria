"""CB10: Animation Editor and Action Timeline tabs, driven inside the real editor window."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from asteria.editor import EditorDocument  # noqa: E402
from asteria.project import Project  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    value = AsteriaEditorWindow(project)
    value.document.file_path = ROOT / "project.asteria.json"
    value.animation_editor.api._resource_root = ROOT
    value.animation_editor.refresh()
    value.action_timeline_editor.refresh()
    yield value
    value.document.mark_saved()
    value.close()
    app.processEvents()


def test_animation_editor_builds_a_clip_by_clicking_frames_and_previews_it(window):
    editor = window.animation_editor
    sheet = "battle.combatant.hero_01"
    editor.sheet_list.setCurrentRow(editor.api.sheets().index(sheet))
    assert editor.new_clip("victory")
    editor.frames.setText("")
    for cell in (0, 2, 0, 2):
        editor.grid.frameClicked.emit(cell)  # clicking grid cells appends frames
    assert editor.frames.text() == "0, 2, 0, 2"
    editor.duration.setValue(0.25)
    editor.events.setText("1:cheer")
    assert editor.apply_clip(), editor.status.text()
    clip = editor.api.data(sheet)["clips"]["victory"]
    assert clip == {
        "frames": [0, 2, 0, 2],
        "frame_duration": 0.25,
        "loop": True,
        "events": {"1": ["cheer"]},
    }
    editor.clip_list.setCurrentRow(sorted(editor.api.data(sheet)["clips"]).index("victory"))
    shown = set()
    for _ in range(40):
        editor.tick(0.05)
        shown.add(editor.current_frame())
    assert shown == {0, 2} and not editor.preview.pixmap().isNull()
    pivot_y = editor.api.data(sheet)["pivot"][1]  # where the sheet puts its feet
    editor.pivot_x.setValue(0.4)
    assert editor.apply_sheet()
    assert editor.api.data(sheet)["pivot"] == pytest.approx([0.4, pivot_y], abs=1e-3)
    editor.frames.setText("0, 99")
    assert (
        not editor.apply_clip() and "outside" in editor.status.text()
    )  # validation surfaces in the UI
    window.document.undo()  # pivot
    window.document.undo()  # events
    window.document.undo()  # clip edit
    assert editor.api.data(sheet)["clips"]["victory"]["frames"] == [0]


def test_action_timeline_moves_beats_by_drag_and_previews(window):
    editor = window.action_timeline_editor
    editor.sequence_list.setCurrentRow(editor.api.sequences().index("fire_arc"))
    editor.view.beatSelected.emit("impact")
    assert editor.beat_id.text() == "impact" and editor.channel.currentText() == "animation"
    editor.view.beatMoved.emit("impact", 0.45)  # what a drag-and-drop emits
    assert next(b.at for b in editor.api.beats("fire_arc") if b.beat_id == "impact") == 0.45
    assert editor.add_beat("extra", 0.5, "vfx", "battle.fx.slash")
    editor.at.setValue(0.55)
    assert editor.apply_beat()
    editor.set_playhead(0.5)
    assert (
        "animation:hit@0.45" in editor.released.text()
        and "vfx:battle.fx.slash" not in editor.released.text()
    )
    editor.cue.setCurrentText("battle.fx.unknown")
    assert not editor.apply_beat() and "unknown VFX" in editor.status.text()
    window.document.undo()
    window.document.undo()
    window.document.undo()
    assert next(b.at for b in editor.api.beats("fire_arc") if b.beat_id == "impact") == 0.32
