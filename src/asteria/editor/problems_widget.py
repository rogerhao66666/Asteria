"""Problems dock (EDT-15): the project's validation issues in one list; double-click jumps to the
place."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .problems import collect_problems

ALL_AREAS = "All areas"


class ProblemsWidget(QWidget):
    navigate = Signal(object)  # Problem
    counted = Signal(int)

    def __init__(self, document, parent=None, *, resource_root=None):
        super().__init__(parent)
        self.document = document
        self.resource_root = resource_root
        self.problems = []
        self.summary = QLabel("No problems")
        self.area = QComboBox()
        self.area.addItem(ALL_AREAS)
        self.area.currentTextChanged.connect(lambda _text: self._fill())
        refresh = QPushButton("Re-check")
        refresh.clicked.connect(self.refresh)
        top = QHBoxLayout()
        top.addWidget(self.summary, 1)
        top.addWidget(self.area)
        top.addWidget(refresh)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["", "Area", "Problem", "Location"])
        self.tree.setRootIsDecorated(False)
        self.tree.setColumnWidth(0, 28)
        self.tree.setColumnWidth(1, 130)
        self.tree.setColumnWidth(2, 460)
        self.tree.itemActivated.connect(self._activated)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(top)
        layout.addWidget(self.tree, 1)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(400)
        self._debounce.timeout.connect(self.refresh)

    def schedule_refresh(self):
        """Re-check shortly after edits settle (edits come in bursts)."""
        self._debounce.start()

    def refresh(self):
        self._debounce.stop()
        self.problems = collect_problems(self.document, resource_root=self.resource_root)
        current = self.area.currentText()
        areas = sorted({p.area for p in self.problems})
        self.area.blockSignals(True)
        self.area.clear()
        self.area.addItems([ALL_AREAS, *areas])
        self.area.setCurrentText(current if current in areas else ALL_AREAS)
        self.area.blockSignals(False)
        self._fill()
        self.counted.emit(len(self.problems))
        return self.problems

    def visible_problems(self):
        area = self.area.currentText()
        return [p for p in self.problems if area == ALL_AREAS or p.area == area]

    def _fill(self):
        self.tree.clear()
        shown = self.visible_problems()
        for problem in shown:
            item = QTreeWidgetItem(
                ["✗" if problem.severity == "error" else "!", problem.area, problem.message]
            )
            item.setText(3, problem.location)
            item.setToolTip(2, problem.message)
            item.setData(0, Qt.UserRole, problem)
            if not problem.target:
                item.setToolTip(3, "No single location — fix in the area named on the left")
            self.tree.addTopLevelItem(item)
        errors = sum(p.severity == "error" for p in self.problems)
        warnings = len(self.problems) - errors
        if not self.problems:
            self.summary.setText("No problems — the project validates")
        else:
            self.summary.setText(
                f"{errors} error(s), {warnings} warning(s)"
                + ("" if len(shown) == len(self.problems) else f" — showing {len(shown)}")
            )

    def _activated(self, item, _column=0):
        problem = item.data(0, Qt.UserRole)
        if problem is not None:
            self.navigate.emit(problem)
