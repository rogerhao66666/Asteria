"""Project input map editor (ENG-15): default bindings per action — keys and gamepad — with undo.

Players can rebind in the game (Settings → Controls); those overrides are
saved per player and laid over these project defaults.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
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

from .authoring_sidebar import authoring_sidebar
from .record_form import _help_tip
from .record_vocabulary import words as _words


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
            m.__init__(
                {a: [InputBinding.from_data(b) for b in bs] for a, bs in data["actions"].items()},
                mouse=m.mouse,
                click_move=m.click_move,
            )

        self._commit(change, f"Remove action {action_id}")

    def set_mouse(self, on):
        """Menus, dialogue and battles answer the mouse (on) or only keys and pads (off)."""

        def change(m):
            m.mouse = bool(on)

        self._commit(change, "Mouse control on" if on else "Mouse control off")

    def set_click_move(self, on):
        """A left click on the map walks the player there (on) or does nothing (off)."""

        def change(m):
            m.click_move = bool(on)

        self._commit(change, "Click to move on" if on else "Click to move off")

    def add_binding(self, action_id, binding, *, exclusive=False):
        self._commit(
            lambda m: m.rebind(action_id, None, binding, exclusive=exclusive), f"Bind {action_id}"
        )

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
        remove_action.clicked.connect(
            lambda: self._try(lambda: self.api.remove_action(self.action_id))
        )
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
            lambda: self._try(
                lambda: self.api.remove_binding(self.action_id, self.bindings.currentRow())
            )
        )
        self.status = QLabel(
            "Defaults for the project; players can rebind in the game (Settings → Controls)."
        )
        self.status.setWordWrap(True)
        self.mouse = QCheckBox("Mouse control")
        self.mouse.setObjectName("InputMapMouse")
        self.mouse.toggled.connect(self._mouse_toggled)
        mouse_help = QLabel("ⓘ")
        mouse_help.setObjectName("InputMapMouseHelp")
        mouse_help.setStyleSheet("color: #8b8e98;")
        mouse_help.setToolTip(
            "Menus, dialogue and battles answer the mouse: pointing at a row moves the cursor "
            "there, a left click chooses it, a right click goes back, the wheel moves up and "
            "down. Off: only keys and pads. Clicks on pictures and map figures with click "
            "events work either way."
        )
        self.click_move = QCheckBox("Click to move")
        self.click_move.setObjectName("InputMapClickMove")
        self.click_move.toggled.connect(self._click_move_toggled)
        move_help = QLabel("ⓘ")
        move_help.setObjectName("InputMapClickMoveHelp")
        move_help.setStyleSheet("color: #8b8e98;")
        move_help.setToolTip(
            "A left click on the map walks the player there around walls and figures. A key "
            "press stops the walk. Needs Mouse control."
        )
        mouse_row = QHBoxLayout()
        mouse_row.addWidget(self.mouse)
        mouse_row.addWidget(_help_tip(mouse_help))
        mouse_row.addSpacing(16)
        mouse_row.addWidget(self.click_move)
        mouse_row.addWidget(_help_tip(move_help))
        mouse_row.addStretch(1)
        form = QFormLayout()
        form.addRow("Device", self.device)
        form.addRow("Code", self.code)
        form.addRow("Direction (axes / hats)", self.direction)
        row = QHBoxLayout()
        row.addWidget(add_action)
        row.addWidget(remove_action)
        left_panel = authoring_sidebar("Actions", self.actions, footer=row)
        right = QVBoxLayout()
        right.setContentsMargins(12, 12, 12, 12)
        right.setSpacing(10)
        heading = QLabel("Bindings")
        heading.setObjectName("AuthoringSidebarTitle")
        right.addWidget(heading)
        right.addWidget(self.bindings, 1)
        right.addLayout(form)
        brow = QHBoxLayout()
        brow.addWidget(add_binding)
        brow.addWidget(remove_binding)
        right.addLayout(brow)
        right_panel = QFrame()
        right_panel.setObjectName("AuthoringPreviewCard")
        right_panel.setLayout(right)
        body = QHBoxLayout()
        body.addWidget(left_panel, 1)
        body.addWidget(right_panel, 2)
        layout = QVBoxLayout(self)
        layout.addLayout(mouse_row)
        layout.addLayout(body, 1)
        layout.addWidget(self.status)
        self.refresh()

    @property
    def action_id(self):
        from .ui_fit import named_id

        return named_id(self.actions.currentItem())

    def refresh(self, select=None):
        if self.api.document.project is None:
            return
        current = select or self.action_id
        self.mouse.blockSignals(True)
        self.mouse.setChecked(self.api.input_map.mouse)
        self.mouse.blockSignals(False)
        self.click_move.blockSignals(True)
        self.click_move.setChecked(self.api.input_map.click_move)
        self.click_move.setEnabled(self.api.input_map.mouse)
        self.click_move.blockSignals(False)
        ids = list(self.api.input_map.actions())
        self.actions.blockSignals(True)
        from .ui_fit import fill_named

        fill_named(self.actions, ids, _words)
        self.actions.blockSignals(False)
        if ids:
            self.actions.setCurrentRow(ids.index(current) if current in ids else 0)
        self._load_bindings()

    def _load_bindings(self):
        self.bindings.clear()
        if self.action_id is not None:
            self.bindings.addItems(
                [describe_binding(b) for b in self.api.input_map.bindings(self.action_id)]
            )

    def _try(self, action):
        try:
            action()
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            self.status.setText(str(exc))
            return False
        self.refresh()
        self.changed.emit()
        return True

    def _mouse_toggled(self, on):
        if on != self.api.input_map.mouse:
            self._try(lambda: self.api.set_mouse(on))

    def _click_move_toggled(self, on):
        if on != self.api.input_map.click_move:
            self._try(lambda: self.api.set_click_move(on))

    def remove_selected_binding(self):
        row = self.bindings.currentRow()
        return row >= 0 and self._try(lambda: self.api.remove_binding(self.action_id, row))

    def add_binding_from_form(self):
        try:
            binding = InputBinding(
                self.device.currentText(), self.code.text(), int(self.direction.value() or 1)
            )
        except ValueError as exc:
            self.status.setText(str(exc))
            return False
        return self._try(lambda: self.api.add_binding(self.action_id, binding))

    def _add_action_clicked(self):
        value, ok = QInputDialog.getText(self, "Add Action", "Action id:")
        if ok and value.strip():
            self._try(lambda: self.api.add_action(value.strip()))
            self.refresh(select=value.strip())
