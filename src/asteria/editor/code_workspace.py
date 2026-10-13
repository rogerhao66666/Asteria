from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from PySide6.QtCore import QStringListModel, Qt, Signal
    from PySide6.QtGui import QFontDatabase, QKeySequence, QShortcut, QTextCursor
    from PySide6.QtWidgets import (
        QComboBox,
        QCompleter,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QListWidget,
        QPlainTextEdit,
        QPushButton,
        QSplitter,
        QVBoxLayout,
        QWidget,
    )

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

    class QWidget:
        pass


DEFAULT_AUTHORING_SCRIPT = (
    "# Asteria project script\n"
    "# Asteria Python Authoring API v1\n"
    "\n"
    "# Example:\n"
    '# scene = project.scene_named("Town")\n'
    '# npc = scene.entity_named("Village Girl")\n'
    "# npc.transform.position = (120, 88)\n"
)


@dataclass(slots=True)
class CodeBuffer:
    path: Path | None = None
    text: str = DEFAULT_AUTHORING_SCRIPT
    saved_text: str = DEFAULT_AUTHORING_SCRIPT

    @property
    def dirty(self):
        return self.text != self.saved_text

    def load(self, path):
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        self.path = path
        self.text = text
        self.saved_text = text

    def save(self, path=None):
        target = Path(path) if path is not None else self.path
        if target is None:
            raise ValueError("code buffer has no path")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.text, encoding="utf-8")
        self.path = target
        self.saved_text = self.text
        return target


class CodeWorkspaceWidget(QWidget):
    """First-class Python authoring workspace shell.

    Provides a first-class Python workspace backed by the canonical Authoring
    API, including project/selection context and structured diagnostics.
    """

    if QT_AVAILABLE:
        saved = Signal(str)
        runRequested = Signal(str, str)

    def __init__(self, document, parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required for CodeWorkspaceWidget")
        super().__init__(parent)
        self.document = document
        self.buffer = CodeBuffer()
        self._refreshing = False

        self.context_label = QLabel("No project loaded")
        self.context_label.setObjectName("MutedLabel")
        self.selection_label = QLabel("Selection: none")
        self.selection_label.setObjectName("MutedLabel")
        self.path_label = QLabel("scripts/main.py")
        for label in (self.context_label, self.selection_label, self.path_label):
            label.setWordWrap(
                True
            )  # long paths and contexts wrap instead of widening the editor window

        self.editor = QPlainTextEdit()
        self.editor.setPlainText(self.buffer.text)
        fixed = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        self.editor.setFont(fixed)
        self.editor.textChanged.connect(self._text_changed)
        from .script_tools import PythonHighlighter

        self.highlighter = PythonHighlighter(self.editor.document())
        self.completer = QCompleter(self)
        self.completer.setModel(QStringListModel(self))
        self.completer.setWidget(self.editor)
        self.completer.setCaseSensitivity(Qt.CaseSensitive)
        self.completer.activated.connect(self.insert_completion)
        self._completion_prefix = ""
        self.complete_shortcut = QShortcut(QKeySequence("Ctrl+Space"), self.editor)
        self.complete_shortcut.activated.connect(self.show_completions)

        self.quick_reference = QPlainTextEdit()
        self.quick_reference.setReadOnly(True)
        self.quick_reference.setMaximumWidth(330)
        self.quick_reference.setFont(fixed)
        self.quick_reference.setPlainText(
            "ASTERIA AUTHORING API\n\n"
            "Globals\n"
            "  project   current project\n"
            "  selected  current selection\n"
            "  scene     selected/owning scene\n"
            "  entity    selected entity\n\n"
            "Examples\n"
            '  scene = project.scene("Town")\n'
            '  hero = scene.entity("Hero")\n'
            "  hero.transform.position = (120, 88)\n\n"
            '  npc = scene.create_entity("Lina", x=160, y=96)\n'
            '  npc.event("Greeting")\\\n'
            '     .dialogue("Lina", "Hello")\\\n'
            "     .end()\n\n"
            "Run: Ctrl+Enter"
        )

        self.script_list = QComboBox()
        self.script_list.currentTextChanged.connect(self._script_selected)
        self.new_button = QPushButton("New Script…")
        self.new_button.clicked.connect(self._new_script_clicked)
        self.reload_button = QPushButton("Reload")
        self.reload_button.setToolTip(
            "Reload the script from disk (picks up edits made outside the editor)"
        )
        self.reload_button.clicked.connect(self.reload_script)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(fixed)
        self.output.setPlaceholderText("Script output and errors appear here after Run.")
        self.frames = QListWidget()
        self.frames.setToolTip("Traceback frames in this script — click to jump to the line")
        self.frames.itemClicked.connect(self._frame_clicked)
        self.save_button = QPushButton("Save Script")
        self.save_button.clicked.connect(self.save_default_script)
        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self._request_run)
        self.run_button.setToolTip(
            "Run this trusted local script through the canonical Asteria Authoring API. Ctrl+Enter"
        )
        self.run_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.run_shortcut.activated.connect(self._request_run)

        top = QHBoxLayout()
        top.addWidget(self.path_label)
        top.addWidget(self.script_list)
        top.addStretch(1)
        top.addWidget(self.new_button)
        top.addWidget(self.reload_button)
        top.addWidget(self.save_button)
        top.addWidget(self.run_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.addWidget(self.context_label)
        layout.addWidget(self.selection_label)
        layout.addLayout(top)
        body = QHBoxLayout()
        body.addWidget(self.editor, 1)
        body.addWidget(self.quick_reference)
        body_box = QWidget()
        body_box.setLayout(body)
        results = QSplitter()
        results.addWidget(self.output)
        results.addWidget(self.frames)
        results.setStretchFactor(0, 3)
        split = QSplitter(Qt.Vertical)
        split.addWidget(body_box)
        split.addWidget(results)
        split.setStretchFactor(0, 4)
        layout.addWidget(split, 1)
        self.refresh_project_context()

    def scripts_dir(self):
        if self.document.file_path is None:
            return None
        return self.document.file_path.parent / "scripts"

    def script_names(self):
        folder = self.scripts_dir()
        names = (
            sorted(p.name for p in folder.glob("*.py"))
            if folder is not None and folder.is_dir()
            else []
        )
        return names or ["main.py"]

    def default_script_path(self):
        folder = self.scripts_dir()
        if folder is None:
            return None
        name = getattr(self, "_current_script", "main.py") or "main.py"
        return folder / name

    def refresh_project_context(self):
        project = self.document.project
        if project is None:
            self.context_label.setText("No project loaded")
            self.selection_label.setText("Selection: none")
            self.save_button.setEnabled(False)
            self.run_button.setEnabled(False)
            return
        self.context_label.setText(f"Project: {project.name}")
        sel = self.document.selection
        if sel.value is None or sel.multiple:
            text = "none" if sel.value is None else f"{len(sel.values)} selected"
        else:
            name = getattr(sel.value, "name", type(sel.value).__name__)
            text = f"{sel.kind}: {name}"
        self.selection_label.setText(
            f"Selection: {text}  ·  scripts can use project, selected, scene, entity"
        )
        self.save_button.setEnabled(self.document.file_path is not None)
        self.run_button.setEnabled(project is not None)
        target = self.default_script_path()
        self.path_label.setText(
            str(target.relative_to(self.document.file_path.parent))
            if target is not None
            else "Save project first to create scripts/main.py"
        )

    def load_default_script(self):
        target = self.default_script_path()
        self._refreshing = True
        try:
            if target is not None and target.exists():
                self.buffer.load(target)
            else:
                self.buffer = CodeBuffer(path=target)
            self.editor.setPlainText(self.buffer.text)
        finally:
            self._refreshing = False
        self.refresh_project_context()
        self._refresh_script_list()

    def save_default_script(self):
        target = self.default_script_path()
        if target is None:
            return False
        self.buffer.text = self.editor.toPlainText()
        saved = self.buffer.save(target)
        self.saved.emit(str(saved))
        self._refresh_title_state()
        return True

    def _request_run(self):
        if self.document.project is None:
            return
        self.buffer.text = self.editor.toPlainText()
        target = self.default_script_path()
        filename = str(target) if target is not None else "<asteria-script>"
        self.runRequested.emit(self.buffer.text, filename)

    def jump_to_diagnostic(self, line=None, column=None):
        if line is None:
            return False
        block = self.editor.document().findBlockByLineNumber(max(0, int(line) - 1))
        if not block.isValid():
            return False
        cursor = QTextCursor(block)
        if column is not None:
            cursor.movePosition(
                QTextCursor.Right,
                QTextCursor.MoveAnchor,
                max(0, int(column) - 1),
            )
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self.editor.setFocus()
        return True

    # -- script files (EDT-09) --------------------------------------------------------
    def _refresh_script_list(self):
        current = getattr(self, "_current_script", "main.py")
        self.script_list.blockSignals(True)
        self.script_list.clear()
        names = self.script_names()
        if current not in names:
            names.append(current)
        self.script_list.addItems(sorted(names))
        self.script_list.setCurrentText(current)
        self.script_list.blockSignals(False)

    def open_script(self, name):
        self._current_script = name
        self.load_default_script()
        self._refresh_script_list()

    def _script_selected(self, name):
        if name and name != getattr(self, "_current_script", "main.py"):
            self.open_script(name)

    def new_script(self, name):
        name = name if name.endswith(".py") else f"{name}.py"
        self._current_script = name
        self.buffer = CodeBuffer(path=self.default_script_path())
        self._refreshing = True
        self.editor.setPlainText(self.buffer.text)
        self._refreshing = False
        self.save_default_script()
        self._refresh_script_list()

    def _new_script_clicked(self):
        name, ok = QInputDialog.getText(self, "New Script", "File name (scripts/…):")
        if ok and name.strip():
            self.new_script(name.strip())

    def reload_script(self):
        """Re-read the current script from disk."""
        self.load_default_script()
        path = self.default_script_path()
        self.output.setPlainText(f"Reloaded {path.name if path else 'script'}")

    # -- completion ---------------------------------------------------------------
    def completion_namespace(self):
        from asteria.authoring.runner import script_namespace

        if self.document.project is None:
            return {}
        sel = self.document.selection
        return script_namespace(
            self.document.project,
            selection_kind=sel.kind if not sel.multiple else "none",
            selection_value=sel.value if not sel.multiple else None,
        )

    def completions(self):
        from .script_tools import complete

        source = self.editor.toPlainText()
        return complete(source, self.editor.textCursor().position(), self.completion_namespace())

    def show_completions(self):
        prefix, names = self.completions()
        self._completion_prefix = prefix
        self.completer.model().setStringList(names)
        if not names:
            return names
        self.completer.setCompletionPrefix(prefix)
        rect = self.editor.cursorRect()
        rect.setWidth(240)
        self.completer.complete(rect)
        return names

    def insert_completion(self, name):
        cursor = self.editor.textCursor()
        cursor.insertText(
            name[len(self._completion_prefix) :]
            if name.startswith(self._completion_prefix)
            else name
        )
        self.editor.setTextCursor(cursor)

    # -- results ------------------------------------------------------------------
    def show_result(self, result):
        """Show a ScriptRunResult: output, full traceback, clickable script frames."""
        from .script_tools import script_frames

        self.frames.clear()
        text = result.stdout
        if not result.success:
            text += result.error
            for line, function, code in script_frames(result.error, result.filename):
                self.frames.addItem(f"line {line} in {function}: {code}")
                self.frames.item(self.frames.count() - 1).setData(Qt.UserRole, line)
        self.output.setPlainText(text.rstrip() or "Script completed successfully")
        return self.frames.count()

    def _frame_clicked(self, item):
        self.jump_to_diagnostic(item.data(Qt.UserRole))

    def _text_changed(self):
        if self._refreshing:
            return
        self.buffer.text = self.editor.toPlainText()
        self._refresh_title_state()
        position = self.editor.textCursor().position()
        if position and self.buffer.text[position - 1 : position] == ".":
            self.show_completions()  # member completion right after typing "."

    def _refresh_title_state(self):
        suffix = " *" if self.buffer.dirty else ""
        target = self.default_script_path()
        name = target.name if target is not None else "main.py"
        self.path_label.setText(f"scripts/{name}{suffix}")
