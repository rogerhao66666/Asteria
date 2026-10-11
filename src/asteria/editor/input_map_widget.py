"""Project input map editor (ENG-15): default bindings per action — keys and gamepad — with undo.

Players can rebind in the game (Settings → Controls); those overrides are
saved per player and laid over these project defaults.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from asteria.runtime.input_map import DEVICES, InputActionMap, InputBinding
from asteria.runtime.input_rebinding import describe_binding


@dataclass(slots=True)
class _SetInputMap:
    project: object
    new: dict
    old: dict
    description: str

    @property
    def label(self):
        return self.description

    def redo(self):
        self.project.input_map = InputActionMap.from_data(self.new)

    def undo(self):
        self.project.input_map = InputActionMap.from_data(self.old)


class InputMapAuthoring:
    """Undoable edits of ``project.input_map`` (shared by the widget and scripts)."""

    def __init__(self, document):
        self.document = document

    @property
    def input_map(self):
        return self.document.project.input_map

    def _commit(self, change, label):
        old = self.input_map.to_data()
        working = InputActionMap.from_data(old)
        change(working)
        self.document.execute(_SetInputMap(self.document.project, working.to_data(), old, label))

    def add_action(self, action_id):
        action_id = str(action_id).strip()
        if not action_id or action_id in self.input_map.actions():
            raise ValueError(f"action {action_id!r} is empty or exists")
        self._commit(lambda m: m.set_bindings(action_id, ()), f"Add action {action_id}")

    def remove_action(self, action_id):
        def change(m):
            data = m.to_data()
            data["actions"].pop(action_id)
            m.__init__({a: [InputBinding.from_data(b) for b in bs] for a, bs in data["actions"].items()})

        self._commit(change, f"Remove action {action_id}")

    def add_binding(self, action_id, binding, *, exclusive=False):
        self._commit(lambda m: m.rebind(action_id, None, binding, exclusive=exclusive), f"Bind {action_id}")

    def remove_binding(self, action_id, index):
        def change(m):
            bindings = list(m.bindings(action_id))
            bindings.pop(int(index))
            m.set_bindings(action_id, bindings)

        self._commit(change, f"Unbind {action_id}")


class InputMapWidget(QWidget):
    changed = Signal()

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.api = InputMapAuthoring(document)
        self.actions = QListWidget()
        self.actions.currentTextChanged.connect(lambda _t: self._load_bindings())
        self.bindings = QListWidget()
        add_action, remove_action = QPushButton("Add Action…"), QPushButton("Remove Action")
        add_action.clicked.connect(self._add_action_clicked)
        remove_action.clicked.connect(lambda: self._try(lambda: self.api.remove_action(self.action_id)))
        self.device = QComboBox()
        self.device.addItems(list(DEVICES))
        self.code = QLineEdit()
        self.code.setPlaceholderText("key name (a, left, space…) or pad button / axis number")
        self.direction = QSpinBox()
        self.direction.setRange(-1, 1)
        self.direction.setValue(1)
        add_binding, remove_binding = QPushButton("Add Binding"), QPushButton("Remove Binding")
        add_binding.clicked.connect(self.add_binding_from_form)
        remove_binding.clicked.connect(
            lambda: self._try(lambda: self.api.remove_binding(self.action_id, self.bindings.currentRow()))
        )
        self.status = QLabel("Defaults for the project; players can rebind in the game (Settings → Controls).")
        self.status.setWordWrap(True)
        form = QFormLayout()
        form.addRow("Device", self.device)
        form.addRow("Code", self.code)
        form.addRow("Direction (axes / hats)", self.direction)
        left = QVBoxLayout()
        left.addWidget(QLabel("Actions"))
        left.addWidget(self.actions, 1)
        row = QHBoxLayout()
        row.addWidget(add_action)
        row.addWidget(remove_action)
        left.addLayout(row)
        right = QVBoxLayout()
        right.addWidget(QLabel("Bindings"))
        right.addWidget(self.bindings, 1)
        right.addLayout(form)
        brow = QHBoxLayout()
        brow.addWidget(add_binding)
        brow.addWidget(remove_binding)
        right.addLayout(brow)
        body = QHBoxLayout()
        body.addLayout(left, 1)
        body.addLayout(right, 2)
        layout = QVBoxLayout(self)
        layout.addLayout(body, 1)
        layout.addWidget(self.status)
        self.refresh()

    @property
    def action_id(self):
        item = self.actions.currentItem()
        return None if item is None else item.text()

    def refresh(self, select=None):
        if self.api.document.project is None:
            return
        current = select or self.action_id
        ids = list(self.api.input_map.actions())
        self.actions.blockSignals(True)
        self.actions.clear()
        self.actions.addItems(ids)
        self.actions.blockSignals(False)
        if ids:
            self.actions.setCurrentRow(ids.index(current) if current in ids else 0)
        self._load_bindings()

    def _load_bindings(self):
        self.bindings.clear()
        if self.action_id is not None:
            self.bindings.addItems([describe_binding(b) for b in self.api.input_map.bindings(self.action_id)])

    def _try(self, action):
        try:
            action()
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            self.status.setText(str(exc))
            return False
        self.refresh()
        self.changed.emit()
        return True

    def remove_selected_binding(self):
        row = self.bindings.currentRow()
        return row >= 0 and self._try(lambda: self.api.remove_binding(self.action_id, row))

    def add_binding_from_form(self):
        try:
            binding = InputBinding(self.device.currentText(), self.code.text(), int(self.direction.value() or 1))
        except ValueError as exc:
            self.status.setText(str(exc))
            return False
        return self._try(lambda: self.api.add_binding(self.action_id, binding))

    def _add_action_clicked(self):
        value, ok = QInputDialog.getText(self, "Add Action", "Action id:")
        if ok and value.strip():
            self._try(lambda: self.api.add_action(value.strip()))
            self.refresh(select=value.strip())
