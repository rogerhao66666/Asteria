"""Graphical animation state machine editor (ANI-02): states as draggable nodes, transitions as
arrows."""

from __future__ import annotations

from math import atan2, cos, sin

from PySide6.QtCore import QPointF, QRectF, Signal
from PySide6.QtGui import QBrush, QColor, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .animation_state_machine_authoring import (
    AnimationStateMachineAuthoring,
    StateMachineAuthoringError,
)
from .flow_layout import FlowLayout
from .ui_fit import fit_list_to_width

NODE_W, NODE_H = 120, 44
ANY = "*"


class _StateNode(QGraphicsRectItem):
    def __init__(self, view, state, clip, initial, current):
        super().__init__(0, 0, NODE_W, NODE_H)
        self.view, self.state = view, state
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
        fill = "#35603f" if current else ("#3a4a6e" if initial else "#2a3142")
        self.setBrush(QBrush(QColor(fill)))
        self.setPen(QPen(QColor("#f0c674" if initial else "#8fa3bf"), 2 if initial else 1))
        label = QGraphicsSimpleTextItem(
            f"{state}\n▶ {clip}" if state != ANY else "Any State", self
        )
        label.setBrush(QBrush(QColor("#e8ecf2")))
        label.setPos(8, 5)

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt API
        super().mouseReleaseEvent(event)
        self.view.nodeMoved.emit(self.state, self.pos().x(), self.pos().y())


class StateMachineGraphView(QGraphicsView):
    nodeMoved = Signal(str, float, float)
    stateSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setMinimumSize(260, 220)
        self.nodes = {}
        self.scene().selectionChanged.connect(self._selection)

    def _selection(self):
        items = [i for i in self.scene().selectedItems() if isinstance(i, _StateNode)]
        if items:
            self.stateSelected.emit(items[0].state)

    def show_machine(self, definition, layout, current=None):
        scene = self.scene()
        scene.blockSignals(True)
        scene.clear()
        self.nodes = {}
        if definition is None:
            scene.addSimpleText("No state machine yet — Create one for this sheet.")
            scene.blockSignals(False)
            return
        states = list(definition.states)
        if any(t.source == ANY for t in definition.transitions):
            states.append(ANY)
        for i, state in enumerate(states):
            node = _StateNode(
                self,
                state,
                definition.states.get(state, ""),
                state == definition.initial,
                state == current,
            )
            x, y = layout.get(state, (40 + (i % 3) * 170, 40 + (i // 3) * 110))
            node.setPos(float(x), float(y))
            scene.addItem(node)
            self.nodes[state] = node
        for transition in definition.transitions:
            self._arrow(transition)
        scene.blockSignals(False)

    def _arrow(self, transition):
        a, b = self.nodes.get(transition.source), self.nodes.get(transition.target)
        if a is None or b is None:
            return
        start = a.pos() + QPointF(NODE_W / 2, NODE_H / 2)
        end = b.pos() + QPointF(NODE_W / 2, NODE_H / 2)
        angle = atan2(end.y() - start.y(), end.x() - start.x())
        end = end - QPointF(cos(angle) * NODE_W / 2.2, sin(angle) * NODE_H / 1.6)
        pen = QPen(QColor("#9fb4d1"), 1.6)
        self.scene().addLine(start.x(), start.y(), end.x(), end.y(), pen)
        head = QPolygonF(
            [
                end,
                end - QPointF(cos(angle - 0.4) * 10, sin(angle - 0.4) * 10),
                end - QPointF(cos(angle + 0.4) * 10, sin(angle + 0.4) * 10),
            ]
        )
        self.scene().addPolygon(head, pen, QBrush(QColor("#9fb4d1")))
        label = " & ".join(f"{c.parameter}{c.operator}{c.value}" for c in transition.conditions)
        if transition.when_finished:
            label = (label + " · " if label else "") + "when finished"
        if label:
            text = self.scene().addSimpleText(label)
            text.setBrush(QBrush(QColor("#c8d3e2")))
            mid = (start + end) / 2
            text.setPos(mid.x() + 4, mid.y() - 16)

    def node_rect(self, state):
        node = self.nodes[state]
        return QRectF(node.pos(), node.rect().size())


class AnimationStateMachineWidget(QWidget):
    changed = Signal()

    def __init__(self, document, parent=None, *, resource_root=None):
        super().__init__(parent)
        self.api = AnimationStateMachineAuthoring(document, resource_root=resource_root)
        self.last_error = None
        self.preview_state = None
        self.sheet_list = QListWidget()
        fit_list_to_width(self.sheet_list)
        self.sheet_list.currentTextChanged.connect(lambda _t: self._load())
        create, remove = QPushButton("Create Machine"), QPushButton("Remove Machine")
        create.clicked.connect(lambda: self._try(lambda: self.api.create(self.sheet), "Created"))
        remove.clicked.connect(
            lambda: self._try(lambda: self.api.remove_machine(self.sheet), "Removed")
        )
        left = QVBoxLayout()
        left.addWidget(QLabel("Sprite Sheets"))
        left.addWidget(self.sheet_list, 1)
        left.addWidget(create)
        left.addWidget(remove)
        left_box = QWidget()
        left_box.setLayout(left)

        self.graph = StateMachineGraphView()
        self.graph.nodeMoved.connect(self._moved)
        self.graph.stateSelected.connect(self._state_selected)

        # state inspector
        self.state_label = QLabel("—")
        self.state_clip = QComboBox()
        set_clip, set_initial, remove_state = (
            QPushButton("Set Clip"),
            QPushButton("Make Initial"),
            QPushButton("Remove"),
        )
        set_clip.clicked.connect(
            lambda: self._try(
                lambda: self.api.set_state_clip(
                    self.sheet, self.selected_state, self.state_clip.currentText()
                ),
                "Clip set",
            )
        )
        set_initial.clicked.connect(
            lambda: self._try(
                lambda: self.api.set_initial(self.sheet, self.selected_state), "Initial state set"
            )
        )
        remove_state.clicked.connect(
            lambda: self._try(
                lambda: self.api.remove_state(self.sheet, self.selected_state), "State removed"
            )
        )
        self.new_state = QLineEdit()
        self.new_state.setPlaceholderText("new state name")
        add_state = QPushButton("Add State")
        add_state.clicked.connect(
            lambda: self.add_state(self.new_state.text().strip(), self.state_clip.currentText())
        )
        state_box = QGroupBox("State")
        sf = QFormLayout(state_box)
        sf.addRow("Selected", self.state_label)
        sf.addRow("Clip", self.state_clip)
        # button and field rows wrap in a narrow window instead of widening the page
        row_box = QWidget()
        row = FlowLayout(row_box)
        for b in (set_clip, set_initial, remove_state):
            row.addWidget(b)
        sf.addRow(row_box)
        sf.addRow(self.new_state, add_state)

        # transitions
        self.transitions = QListWidget()
        self.transitions.currentRowChanged.connect(self._transition_selected)
        self.source, self.target = QComboBox(), QComboBox()
        self.conditions = QLineEdit()
        self.conditions.setPlaceholderText("speed > 0.1; grounded == true")
        self.when_finished = QCheckBox("When the clip finished")
        self.priority = QSpinBox()
        self.priority.setRange(-99, 99)
        add_t, apply_t, remove_t = QPushButton("Add"), QPushButton("Apply"), QPushButton("Remove")
        add_t.clicked.connect(self.add_transition)
        apply_t.clicked.connect(self.apply_transition)
        remove_t.clicked.connect(
            lambda: self._try(
                lambda: self.api.remove_transition(self.sheet, self.transitions.currentRow()),
                "Removed",
            )
        )
        t_box = QGroupBox("Transitions")
        tf = QFormLayout(t_box)
        tf.addRow(self.transitions)
        pair = QHBoxLayout()
        pair.addWidget(self.source)
        pair.addWidget(QLabel("→"))
        pair.addWidget(self.target)
        tf.addRow("From / To", pair)
        tf.addRow("Conditions", self.conditions)
        tf.addRow(self.when_finished)
        tf.addRow("Priority", self.priority)
        trow_box = QWidget()
        trow = FlowLayout(trow_box)
        for b in (add_t, apply_t, remove_t):
            trow.addWidget(b)
        tf.addRow(trow_box)

        # parameters + preview
        self.parameters = QListWidget()
        self.param_name = QLineEdit()
        self.param_name.setPlaceholderText("parameter name")
        self.param_default = QLineEdit("0")
        self.param_trigger = QCheckBox("Trigger")
        add_p = QPushButton("Add Parameter")
        add_p.clicked.connect(self.add_parameter)
        self.preview_values = QLineEdit()
        self.preview_values.setPlaceholderText("preview: speed=1, grounded=true, !jump (trigger)")
        step = QPushButton("Step 0.1 s")
        step.clicked.connect(lambda: self.preview_step(0.1))
        self.preview_label = QLabel("")
        p_box = QGroupBox("Parameters & Preview")
        pf = QFormLayout(p_box)
        pf.addRow(self.parameters)
        prow_box = QWidget()
        prow = FlowLayout(prow_box)
        for w in (self.param_name, self.param_default, self.param_trigger, add_p):
            prow.addWidget(w)
        pf.addRow(prow_box)
        pf.addRow(self.preview_values, step)
        pf.addRow(self.preview_label)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        right = QVBoxLayout()
        for w in (state_box, t_box, p_box, self.status):
            right.addWidget(w)
        right_box = QWidget()
        right_box.setLayout(right)

        split = QSplitter()
        for w in (left_box, self.graph, right_box):
            split.addWidget(w)
        split.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.addWidget(split)
        self.selected_state = None
        self._preview_steps = []
        self.refresh()

    @property
    def sheet(self):
        item = self.sheet_list.currentItem()
        return None if item is None else item.text()

    def refresh(self, select=None):
        if self.api.document.project is None:
            return
        current = select or self.sheet
        ids = self.api.sheets()
        self.sheet_list.blockSignals(True)
        self.sheet_list.clear()
        self.sheet_list.addItems(list(ids))
        self.sheet_list.blockSignals(False)
        if ids:
            self.sheet_list.setCurrentRow(ids.index(current) if current in ids else 0)
        self._load()

    def _load(self):
        if self.sheet is None:
            return
        definition = self.api.definition(self.sheet)
        self.graph.show_machine(definition, self.api.layout(self.sheet), self.preview_state)
        self.state_clip.clear()
        self.state_clip.addItems(list(self.api.clips(self.sheet)))
        self.transitions.clear()
        self.parameters.clear()
        for combo in (self.source, self.target):
            combo.clear()
        if definition is None:
            return
        self.source.addItems([*definition.states, "*"])
        self.target.addItems(list(definition.states))
        for t in definition.transitions:
            cond = ", ".join(f"{c.parameter} {c.operator} {c.value}" for c in t.conditions)
            self.transitions.addItem(
                f"{t.source} → {t.target}"
                + (f"  [{cond}]" if cond else "")
                + ("  (finished)" if t.when_finished else "")
            )
        self.parameters.addItems(
            [f"{k} = {v}" for k, v in definition.parameters.items()]
            + [f"{t} (trigger)" for t in definition.triggers]
        )
        if self.selected_state not in definition.states:
            self.selected_state = definition.initial
        self._state_selected(self.selected_state)

    def _state_selected(self, state):
        definition = self.api.definition(self.sheet) if self.sheet else None
        if definition is None or state not in definition.states:
            return
        self.selected_state = state
        self.state_label.setText(state + ("  (initial)" if state == definition.initial else ""))
        self.state_clip.setCurrentText(definition.states[state])

    def _transition_selected(self, row):
        definition = self.api.definition(self.sheet) if self.sheet else None
        if definition is None or not 0 <= row < len(definition.transitions):
            return
        t = definition.transitions[row]
        self.source.setCurrentText(t.source)
        self.target.setCurrentText(t.target)
        self.conditions.setText(
            "; ".join(f"{c.parameter} {c.operator} {c.value}" for c in t.conditions)
        )
        self.when_finished.setChecked(t.when_finished)
        self.priority.setValue(t.priority)

    def _try(self, action, message):
        try:
            result = action()
        except (StateMachineAuthoringError, ValueError, KeyError, TypeError, IndexError) as exc:
            self.last_error = str(exc)
            self.status.setStyleSheet("color: #d9534f;")
            self.status.setText(str(exc))
            return None
        self.last_error = None
        self.status.setStyleSheet("")
        self.status.setText(message)
        self._load()
        self.changed.emit()
        return result if result is not None else True

    @staticmethod
    def parse_conditions(text):
        result = []
        for chunk in str(text).split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            for op in (">=", "<=", "==", "!=", ">", "<"):
                if op in chunk:
                    name, value = (x.strip() for x in chunk.split(op, 1))
                    break
            else:
                name, op, value = chunk, "==", "true"
            lowered = value.lower()
            value = True if lowered == "true" else False if lowered == "false" else float(value)
            result.append((name, op, value))
        return result

    def set_clip(self):
        clip = self.state_clip.currentText()
        return self._try(
            lambda: self.api.set_state_clip(self.sheet, self.selected_state, clip), "Clip set"
        )

    def make_initial(self):
        return self._try(
            lambda: self.api.set_initial(self.sheet, self.selected_state), "Initial state set"
        )

    def remove_state(self):
        return self._try(
            lambda: self.api.remove_state(self.sheet, self.selected_state), "State removed"
        )

    def remove_transition(self):
        row = self.transitions.currentRow()
        return row >= 0 and self._try(
            lambda: self.api.remove_transition(self.sheet, row), "Removed"
        )

    def add_state(self, name, clip):
        if not name:
            self.status.setText("Name the new state")
            return None
        rect = self.graph.scene().itemsBoundingRect()
        return self._try(
            lambda: self.api.add_state(self.sheet, name, clip, (rect.right() + 30, rect.top())),
            f"Added {name}",
        )

    def add_transition(self):
        conditions = self.parse_conditions(self.conditions.text())
        return self._try(
            lambda: self.api.add_transition(
                self.sheet,
                self.source.currentText(),
                self.target.currentText(),
                conditions=conditions,
                when_finished=self.when_finished.isChecked(),
                priority=self.priority.value(),
            ),
            "Transition added",
        )

    def apply_transition(self):
        row = self.transitions.currentRow()
        conditions = self.parse_conditions(self.conditions.text())
        return row >= 0 and self._try(
            lambda: self.api.edit_transition(
                self.sheet,
                row,
                source=self.source.currentText(),
                target=self.target.currentText(),
                conditions=conditions,
                when_finished=self.when_finished.isChecked(),
                priority=self.priority.value(),
            ),
            "Transition saved",
        )

    def add_parameter(self):
        name = self.param_name.text().strip()
        default = self.param_default.text().strip()
        value = (
            True
            if default.lower() == "true"
            else False
            if default.lower() == "false"
            else float(default or 0)
        )
        return self._try(
            lambda: self.api.add_parameter(
                self.sheet, name, value, trigger=self.param_trigger.isChecked()
            ),
            f"Added {name}",
        )

    def _moved(self, state, x, y):
        if state != "*":
            self._try(lambda: self.api.move_state(self.sheet, state, x, y), f"Moved {state}")

    def preview_step(self, dt):
        values, triggers = {}, []
        for chunk in self.preview_values.text().split(","):
            chunk = chunk.strip()
            if chunk.startswith("!"):
                triggers.append(chunk[1:])
            elif "=" in chunk:
                name, value = (x.strip() for x in chunk.split("=", 1))
                lowered = value.lower()
                values[name] = (
                    True if lowered == "true" else False if lowered == "false" else float(value)
                )
        self._preview_steps.append((dt, values, triggers))
        try:
            states = self.api.simulate(self.sheet, self._preview_steps)
        except (StateMachineAuthoringError, KeyError, ValueError) as exc:
            self.preview_label.setText(str(exc))
            self._preview_steps.pop()
            return None
        self.preview_state = states[-1]
        self.preview_label.setText(
            f"State now: {self.preview_state}  (after {len(self._preview_steps)} steps)"
        )
        self.graph.show_machine(
            self.api.definition(self.sheet), self.api.layout(self.sheet), self.preview_state
        )
        return self.preview_state
