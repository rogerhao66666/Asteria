"""Debugger dock (EDT-10): inspect a running play-test and run debug actions over the debug channel."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from asteria.runtime.debug_server import DebugClient, DebugClientError

# command -> (label, [(arg, kind)]) ; kinds: text, number, bool, json
ACTIONS = {
    "give_item": ("Give item", [("item_id", "text"), ("quantity", "number")]),
    "remove_item": ("Remove item", [("item_id", "text"), ("quantity", "number")]),
    "set_currency": ("Set currency", [("currency_id", "text"), ("amount", "number")]),
    "set_resource": (
        "Set resource (HP, SP, ...)",
        [("member_id", "text"), ("resource_id", "text"), ("value", "number")],
    ),
    "set_stat": ("Set stat", [("member_id", "text"), ("stat", "text"), ("value", "number")]),
    "add_state": ("Add state (battle)", [("member_id", "text"), ("state_id", "text")]),
    "remove_state": ("Remove state (battle)", [("member_id", "text"), ("state_id", "text")]),
    "teleport": ("Teleport player", [("x", "number"), ("y", "number")]),
    "trigger_event": ("Trigger event", [("program_id", "text")]),
    "spawn_enemy": ("Spawn enemy", [("enemy_id", "text"), ("prefab_id", "text"), ("x", "number"), ("y", "number")]),
    "kill_enemy": ("Kill enemy", [("target_id", "text")]),
    "set_switch": ("Set switch", [("name", "text"), ("value", "bool")]),
    "set_variable": ("Set variable", [("name", "text"), ("value", "text")]),
    "quest": (
        "Quest (start/advance/complete/fail)",
        [("action", "text"), ("quest_id", "text"), ("objective_id", "text"), ("amount", "number")],
    ),
    "reputation": ("Change reputation", [("faction_id", "text"), ("amount", "number")]),
}


def _fill(parent, key, value):
    item = QTreeWidgetItem([str(key), ""])
    parent.addChild(item) if isinstance(parent, QTreeWidgetItem) else parent.addTopLevelItem(item)
    if isinstance(value, dict):
        for k, v in value.items():
            _fill(item, k, v)
    elif isinstance(value, list) and value and isinstance(value[0], (dict, list)):
        for i, v in enumerate(value):
            _fill(item, f"[{i}]", v)
    else:
        item.setText(1, str(value))
    return item


class DebuggerWidget(QWidget):
    actionExecuted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.client = None
        self.pump = None
        self.status = QLabel("Not attached — start Run Project to debug the game.")
        self.status.setWordWrap(True)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        self.auto = QCheckBox("Auto refresh")
        self.auto.toggled.connect(lambda on: self.timer.start() if on else self.timer.stop())
        top = QHBoxLayout()
        top.addWidget(self.status, 1)
        top.addWidget(self.auto)
        top.addWidget(self.refresh_button)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Game State", "Value"])
        self.tree.setColumnWidth(0, 220)

        self.command = QComboBox()
        for name, (label, _) in ACTIONS.items():
            self.command.addItem(label, name)
        self.command.currentIndexChanged.connect(self._build_args)
        self.args_form = QFormLayout()
        self.arg_widgets = {}
        run = QPushButton("Execute")
        run.clicked.connect(self.execute_current)
        self.result = QLabel("")
        self.result.setWordWrap(True)
        self.history = QListWidget()
        actions = QGroupBox("Debug Actions")
        box = QVBoxLayout(actions)
        box.addWidget(self.command)
        box.addLayout(self.args_form)
        box.addWidget(run)
        box.addWidget(self.result)
        box.addWidget(QLabel("History"))
        box.addWidget(self.history, 1)

        split = QSplitter()
        split.addWidget(self.tree)
        split.addWidget(actions)
        split.setStretchFactor(0, 2)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(split, 1)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh)
        self._build_args()

    # -- connection -----------------------------------------------------------------
    def attach(self, port, token, *, pump=None):
        self.detach()
        self.client = DebugClient(port, token, pump=pump)
        self.status.setText(f"Attaching to the game on port {port}…")
        return self.client

    def detach(self):
        if self.client is not None:
            self.client.close()
        self.client = None
        self.timer.stop()
        self.auto.setChecked(False)
        self.status.setText("Not attached — start Run Project to debug the game.")

    def _ensure(self):
        if self.client is None:
            raise DebugClientError("not attached to a running game")
        if not self.client.connected:
            self.client.connect()
            self.status.setText(f"Attached to the game on port {self.client.port}")
        return self.client

    # -- inspection -----------------------------------------------------------------
    def refresh(self):
        try:
            snapshot = self._ensure().request("snapshot")
        except DebugClientError as exc:
            self.status.setText(str(exc))
            return None
        expanded = {
            self.tree.topLevelItem(i).text(0)
            for i in range(self.tree.topLevelItemCount())
            if self.tree.topLevelItem(i).isExpanded()
        }
        self.tree.clear()
        for key, value in snapshot.items():
            item = _fill(self.tree, key, value)
            item.setExpanded(key in expanded or key in {"player", "party", "battle"})
        self.status.setText(f"Attached — mode {snapshot.get('mode')}, scene {snapshot.get('scene', {}).get('name')}")
        return snapshot

    # -- actions --------------------------------------------------------------------
    def _build_args(self):
        while self.args_form.rowCount():
            self.args_form.removeRow(0)
        self.arg_widgets = {}
        for name, kind in ACTIONS[self.command.currentData()][1]:
            widget = QCheckBox() if kind == "bool" else QLineEdit()
            if kind == "bool":
                widget.setChecked(True)
            self.arg_widgets[name] = (widget, kind)
            self.args_form.addRow(name, widget)

    def set_args(self, command, **values):
        self.command.setCurrentIndex(self.command.findData(command))
        for name, value in values.items():
            widget, kind = self.arg_widgets[name]
            widget.setChecked(bool(value)) if kind == "bool" else widget.setText(str(value))

    def execute_current(self):
        command = self.command.currentData()
        args = {}
        for name, (widget, kind) in self.arg_widgets.items():
            if kind == "bool":
                args[name] = widget.isChecked()
                continue
            text = widget.text().strip()
            if not text:
                continue
            if kind == "number":
                try:
                    args[name] = float(text) if "." in text else int(text)
                except ValueError:
                    self.result.setText(f"{name} must be a number")
                    return None
            else:
                args[name] = text
        try:
            result = self._ensure().request(command, **args)
        except DebugClientError as exc:
            self.result.setStyleSheet("color: #d9534f;")
            self.result.setText(str(exc))
            self.history.addItem(f"✗ {command} {args}")
            return None
        self.result.setStyleSheet("")
        self.result.setText(f"{command}: {result}")
        self.history.addItem(f"✓ {command} {args} → {result}")
        self.actionExecuted.emit(command)
        self.refresh()
        return result
