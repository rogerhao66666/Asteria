"""Presentation page for editing skeletons, with an optional separate preview window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget

from .dock_title import DockTitleBar
from .icons import icon
from .skeleton_widget import SkeletonViewerWidget


class SkeletonWorkspacePage(QWidget):
    """Keep the skeleton editor in Presentation and let users detach it temporarily."""

    def __init__(self, viewer: SkeletonViewerWidget, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self._dialog = None
        self.setObjectName("SkeletonWorkspacePage")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.title_bar = DockTitleBar(
            None,
            "animation",
            "layers",
            title="Skeleton",
            float_action=self.toggle_floating,
            close_action=self.return_to_page,
            show_close_button=False,
            parent=self,
        )
        self._layout.addWidget(self.title_bar)
        self._layout.addWidget(self.viewer, 1)

    @property
    def is_floating(self):
        return self._dialog is not None

    def toggle_floating(self):
        if self._dialog is None:
            self._open_dialog()
        else:
            self.return_to_page()

    def _open_dialog(self):
        dialog = QDialog(self.window(), Qt.Window)
        dialog.setObjectName("SkeletonFloatingWindow")
        dialog.setWindowTitle("Skeleton")
        dialog.setWindowIcon(icon("animation", self.title_bar.accent.name()))
        dialog.resize(1100, 820)
        dialog.setMinimumSize(640, 480)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._layout.removeWidget(self.title_bar)
        self._layout.removeWidget(self.viewer)
        self.title_bar.setParent(dialog)
        self.title_bar.close_button.show()
        self.viewer.setParent(dialog)
        layout.addWidget(self.title_bar)
        layout.addWidget(self.viewer, 1)
        self._dialog = dialog
        dialog.finished.connect(lambda _result: self._restore_page(dialog))
        dialog.show()

    def return_to_page(self):
        dialog = self._dialog
        if dialog is not None:
            dialog.close()
            if self._dialog is dialog:
                self._restore_page(dialog)

    def _restore_page(self, dialog):
        if self._dialog is not dialog:
            return
        self._dialog = None
        dialog.layout().removeWidget(self.title_bar)
        dialog.layout().removeWidget(self.viewer)
        self.title_bar.setParent(self)
        self.title_bar.close_button.hide()
        self.viewer.setParent(self)
        self._layout.addWidget(self.title_bar)
        self._layout.addWidget(self.viewer, 1)
        dialog.deleteLater()
