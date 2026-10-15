"""Shared empty state for authoring pages that require an open project."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from .icons import icon


class ProjectEmptyState(QWidget):
    def __init__(self, description, parent=None):
        super().__init__(parent)
        self.setObjectName("ProjectEmptyState")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addStretch(1)
        content = QWidget()
        content.setMaximumWidth(420)
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)
        illustration = QLabel()
        illustration.setPixmap(icon("assets", "#8b8f99").pixmap(48, 48))
        illustration.setAlignment(Qt.AlignCenter)
        body.addWidget(illustration)
        heading = QLabel("No project open")
        heading.setObjectName("EmptyStateTitle")
        heading.setAlignment(Qt.AlignCenter)
        body.addWidget(heading)
        hint = QLabel(description)
        hint.setObjectName("EmptyStateHint")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignCenter)
        body.addWidget(hint)
        button = QPushButton("Open Project…")
        button.setProperty("role", "primary")
        button.setMinimumWidth(160)
        button.clicked.connect(self._open_project)
        body.addWidget(button, 0, Qt.AlignHCenter)
        layout.addWidget(content, 0, Qt.AlignHCenter)
        layout.addStretch(1)

    def _open_project(self):
        action = getattr(self.window(), "open_project", None)
        if callable(action):
            action()
