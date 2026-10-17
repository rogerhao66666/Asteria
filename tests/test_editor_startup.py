"""The editor starts on a current starter project and on the left tab it was left on."""

import json

import pytest

pytest.importorskip("PySide6")


def test_the_starter_project_is_made_once_and_kept(tmp_path):
    from asteria.editor.shell import ensure_starter_project

    folder = tmp_path / "Basic RPG"
    path = ensure_starter_project(folder)
    assert path.is_file() and (folder / ".starter.json").is_file()
    marker = path.read_bytes()
    assert ensure_starter_project(folder) == path and path.read_bytes() == marker
    assert not (tmp_path / "Basic RPG (previous)").exists()


def test_an_old_untouched_starter_is_rebuilt_in_place(tmp_path):
    from asteria.editor.shell import ensure_starter_project

    folder = tmp_path / "Basic RPG"
    path = ensure_starter_project(folder)
    stamp = json.loads((folder / ".starter.json").read_text())
    stamp["fingerprint"] = "an-older-template"  # the template has changed since
    (folder / ".starter.json").write_text(json.dumps(stamp))
    (folder / "stray.txt").write_text("from the old copy")
    ensure_starter_project(folder)
    assert path.is_file() and not (folder / "stray.txt").exists()
    assert not (tmp_path / "Basic RPG (previous)").exists()  # nothing of the user's to keep


def test_an_edited_or_unknown_starter_is_moved_aside_not_lost(tmp_path):
    from asteria.editor.shell import ensure_starter_project

    folder = tmp_path / "Basic RPG"
    path = ensure_starter_project(folder)
    data = json.loads(path.read_text())
    data["name"] = "My game"  # the user edited it
    path.write_text(json.dumps(data))
    stamp = json.loads((folder / ".starter.json").read_text())
    stamp["fingerprint"] = "an-older-template"
    (folder / ".starter.json").write_text(json.dumps(stamp))
    ensure_starter_project(folder)
    kept = tmp_path / "Basic RPG (previous)" / "project.asteria.json"
    assert json.loads(kept.read_text())["name"] == "My game"
    assert json.loads(path.read_text())["name"] == "Basic RPG"
    # a starter made before the stamp existed is treated the same way
    (folder / ".starter.json").unlink()
    ensure_starter_project(folder)
    assert (tmp_path / "Basic RPG (previous 2)" / "project.asteria.json").is_file()


def test_the_left_panel_always_opens_on_project(tmp_path):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "layout.ini"), QSettings.IniFormat)
    first = AsteriaEditorWindow()
    try:
        first.resize(1280, 800)
        first.show()
        for _ in range(10):
            app.processEvents()
        assert first.current_left_tab() == "ProjectSceneDock"  # the default
        first.show_left_tab("LayersDock")
        for _ in range(5):
            app.processEvents()
        assert first.current_left_tab() == "LayersDock"
        first.layout_settings = settings
        first.save_layout()
    finally:
        first.close()
    second = AsteriaEditorWindow()
    try:
        second.restore_layout(settings)
        second.show()
        for _ in range(10):
            app.processEvents()
        assert second.current_left_tab() == "ProjectSceneDock"  # not remembered
    finally:
        second.close()
