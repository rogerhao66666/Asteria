from asteria.editor.code_workspace import DEFAULT_AUTHORING_SCRIPT, CodeBuffer
from asteria.editor.workspace import EditorWorkspace, WorkspaceMode


def _qapp():
    import pytest

    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


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


def test_script_editor_gutter_widens_as_lines_are_added():
    _qapp()
    from asteria.editor.code_workspace import ScriptEditor

    editor = ScriptEditor()
    editor.setPlainText("one line")
    narrow = editor.gutter_width()
    editor.setPlainText("\n".join(str(i) for i in range(200)))
    assert editor.gutter_width() > narrow


def test_script_editor_marks_and_clears_error_line():
    _qapp()
    from asteria.editor.code_workspace import ScriptEditor

    editor = ScriptEditor()
    editor.setPlainText("a = 1\nb = 2\nc = 3\n")

    editor.set_error_line(2)
    assert len(editor.extraSelections()) == 1

    editor.setPlainText(editor.toPlainText() + "d = 4\n")
    assert editor.extraSelections() == []


def test_python_highlighter_colors_keyword_string_and_comment():
    _qapp()
    from PySide6.QtGui import QTextDocument

    from asteria.editor.code_workspace import PythonHighlighter

    document = QTextDocument()
    document.setPlainText('def hi():\n    return "x"  # comment\n')
    highlighter = PythonHighlighter(document)
    highlighter.rehighlight()
    block = document.findBlockByLineNumber(1)
    formats = {
        f.format.foreground().color().name()
        for f in block.layout().formats()
    }
    # keyword (return), string ("x"), and comment (# comment) each got a
    # distinct foreground color from PythonHighlighter's format table.
    assert len(formats) == 3
