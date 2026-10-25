"""The game folder's own settings file (``playable_test_manifest.json``) edited in a settings
tree instead of by hand: every section shown, the file written back only when changed (and
byte for byte as before when nothing changed), never created."""

import json
from pathlib import Path

import pytest

from asteria.editor.game_folder_settings_dialog import sections, with_section

DEMOS = Path(__file__).resolve().parents[1] / "reference_projects"
MANIFEST = {
    "schema": "asteria.playable_test_content",
    "version": 1,
    "field": {"background": "maps/town.png", "player_start": [40, 60]},
    "title": "Trial",
    "battle": {"bgm": "audio/fight.ogg"},
}


def test_sections_and_the_plain_values_keep_their_order():
    assert sections(MANIFEST) == [("", "General"), ("field", "field"), ("battle", "battle")]
    plain = {"schema": MANIFEST["schema"], "version": 1, "title": "Other", "new": True}
    changed = with_section(MANIFEST, "", plain)
    assert list(changed) == ["schema", "version", "field", "title", "battle", "new"]
    assert changed["title"] == "Other" and changed["field"] == MANIFEST["field"]
    battle = with_section(MANIFEST, "battle", {"bgm": "audio/boss.ogg"})
    assert list(battle) == list(MANIFEST) and battle["battle"] == {"bgm": "audio/boss.ogg"}


@pytest.fixture
def dialog_for(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor.game_folder_settings_dialog import GameFolderSettingsDialog

    QApplication.instance() or QApplication([])

    def make(text):
        (tmp_path / "playable_test_manifest.json").write_text(text, encoding="utf-8")
        return GameFolderSettingsDialog(EditorDocument(), tmp_path)

    return make


def test_an_edit_is_written_back_and_nothing_else_moves(dialog_for, tmp_path):
    path = tmp_path / "playable_test_manifest.json"
    dialog = dialog_for(json.dumps(MANIFEST, indent=2) + "\n")
    assert [dialog.list.item(r).text() for r in range(dialog.list.count())] == [
        "General", "field", "battle"]  # fmt: skip
    dialog.list.setCurrentRow(1)
    dialog.tree.set_point(("player_start",), [10, 20])
    dialog.tree._set(("background",), "maps/cave.png")
    dialog._accept()
    assert dialog.changed
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["field"] == {"background": "maps/cave.png", "player_start": [10, 20]}
    assert written["battle"] == MANIFEST["battle"] and list(written) == list(MANIFEST)


@pytest.mark.parametrize("demo", ["full_verification_demo", "diablo_demo", "octopath_demo"])
def test_ok_without_changes_leaves_the_file_byte_for_byte(dialog_for, tmp_path, demo):
    text = (DEMOS / demo / "playable_test_manifest.json").read_text(encoding="utf-8")
    dialog = dialog_for(text)
    for row in range(dialog.list.count()):  # every section opened, none changed
        dialog.list.setCurrentRow(row)
    dialog._accept()
    assert not dialog.changed
    assert (tmp_path / "playable_test_manifest.json").read_text(encoding="utf-8") == text


def test_a_folder_without_the_file_is_left_without_it(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    from asteria.editor import EditorDocument
    from asteria.editor.menu_layout_widget import MenuLayoutWorkspace

    QApplication.instance() or QApplication([])
    document = EditorDocument()
    document.file_path = tmp_path / "project.asteria.json"
    shown = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: shown.append(a[2]))
    page = MenuLayoutWorkspace(document)
    assert page.edit_game_folder_settings() is False
    assert shown and not (tmp_path / "playable_test_manifest.json").exists()
