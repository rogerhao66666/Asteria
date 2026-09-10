from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from PySide6.QtCore import Signal
    from PySide6.QtGui import QFontDatabase, QKeySequence, QShortcut, QTextCursor
    from PySide6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QPlainTextEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

    class QWidget:
        pass


DEFAULT_AUTHORING_SCRIPT = """# Asteria project script\n# Asteria Python Authoring API v1\n\n# Example:\n# scene = project.scene_named("Town")\n# npc = scene.entity_named("Village Girl")\n# npc.transform.position = (120, 88)\n"""


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
        self.selection_label = QLabel("Selection context: none")
        self.selection_label.setObjectName("MutedLabel")
        self.path_label = QLabel("scripts/main.py")

        self.editor = QPlainTextEdit()
        self.editor.setPlainText(self.buffer.text)
        fixed = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        self.editor.setFont(fixed)
        self.editor.textChanged.connect(self._text_changed)

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
        top.addStretch(1)
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
        layout.addLayout(body, 1)
        self.refresh_project_context()

    def default_script_path(self):
        if self.document.file_path is None:
            return None
        return self.document.file_path.parent / "scripts" / "main.py"

    def refresh_project_context(self):
        project = self.document.project
        if project is None:
            self.context_label.setText("No project loaded")
            self.selection_label.setText("Selection context: none")
            self.save_button.setEnabled(False)
            self.run_button.setEnabled(False)
            return
        self.context_label.setText(
            f"Project context: {project.name}  ·  canonical Project/Scene/Entity data"
        )
        sel = self.document.selection
        if sel.value is None or sel.multiple:
            text = "none" if sel.value is None else f"{len(sel.values)} selected"
        else:
            name = getattr(sel.value, "name", type(sel.value).__name__)
            text = f"{sel.kind}: {name}"
        self.selection_label.setText(
            f"Selection context: {text}  ·  globals: selected / scene / entity"
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

    def _text_changed(self):
        if self._refreshing:
            return
        self.buffer.text = self.editor.toPlainText()
        self._refresh_title_state()

    def _refresh_title_state(self):
        suffix = " *" if self.buffer.dirty else ""
        target = self.default_script_path()
        name = target.name if target is not None else "main.py"
        self.path_label.setText(f"scripts/{name}{suffix}")
