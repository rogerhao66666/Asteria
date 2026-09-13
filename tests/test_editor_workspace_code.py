from asteria.editor.code_workspace import DEFAULT_AUTHORING_SCRIPT, CodeBuffer
from asteria.editor.workspace import EditorWorkspace, WorkspaceMode


def test_workspace_modes_are_stable_authoring_surfaces():
    assert [m.value for m in WorkspaceMode] == [
        "scene",
        "rpg",
        "battle",
        "ui",
        "event",
        "code",
    ]


def test_workspace_hides_redundant_native_tab_base():
    import pytest

    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QWidget

    app = QApplication.instance() or QApplication([])
    pages = {mode: QWidget() for mode in WorkspaceMode}
    workspace = EditorWorkspace(pages)

    assert not workspace.tabs.drawBase()

    workspace.close()
    app.processEvents()


def test_code_buffer_tracks_dirty_and_saves(tmp_path):
    path = tmp_path / "scripts" / "main.py"
    buffer = CodeBuffer(path=path)
    assert buffer.text == DEFAULT_AUTHORING_SCRIPT
    assert buffer.dirty is False

    buffer.text += "\nvalue = 1\n"
    assert buffer.dirty is True
    saved = buffer.save()

    assert saved == path
    assert path.read_text(encoding="utf-8") == buffer.text
    assert buffer.dirty is False


def test_code_buffer_load_roundtrip(tmp_path):
    path = tmp_path / "scripts" / "main.py"
    path.parent.mkdir(parents=True)
    path.write_text("print('asteria')\n", encoding="utf-8")

    buffer = CodeBuffer()
    buffer.load(path)

    assert buffer.path == path
    assert buffer.text == "print('asteria')\n"
    assert buffer.dirty is False
