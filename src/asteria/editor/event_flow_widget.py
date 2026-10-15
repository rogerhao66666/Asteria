"""Common & battle events panel and the sequence track editor (EVT-03, EVT-04)."""

from __future__ import annotations

import json

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from asteria.events.common import COMMON_TRIGGERS
from asteria.events.conditions import EventCondition

from .event_editing import describe_instruction, parse_world_args
from .event_flow_authoring import BATTLE_HOOKS, EventFlowAuthoring, EventFlowError

COMPARATORS = ("<=", "<", "==", "!=", ">", ">=")


def describe_condition(c):
    return f"{c.source} {c.name} {c.operator} {c.value}"


def _coerce(text):
    text = str(text).strip()
    for kind in (int, float):
        try:
            return kind(text)
        except ValueError:
            pass
    return {"true": True, "false": False}.get(text.lower(), text)


class EventFlowWidget(QWidget):
    changed = Signal()

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.api = EventFlowAuthoring(document)
        self.last_error = None
        self.status = QLabel("")
        self.status.setWordWrap(True)

        # -- common events ------------------------------------------------------------------
        self.common = QTableWidget(0, 3)
        self.common.setHorizontalHeaderLabels(["Program", "Trigger", "Runs while switch"])
        self._table(self.common)
        self.common.itemSelectionChanged.connect(self._common_selected)
        self.common_program = QComboBox()
        self.common_trigger = QComboBox()
        self.common_trigger.addItems(list(COMMON_TRIGGERS))
        self.common_switch = QLineEdit()
        self.common_switch.setPlaceholderText("switch name (empty = always)")
        common_box = QGroupBox(
            "Common events — reusable programs; autorun / parallel ones run while the switch is on"
        )
        form = QFormLayout()
        form.addRow("Program", self.common_program)
        form.addRow("Trigger", self.common_trigger)
        form.addRow("Switch", self.common_switch)
        buttons = QHBoxLayout()
        for label, slot in (
            ("Add", self.add_common),
            ("Apply", self.apply_common),
            ("Remove", self.remove_common),
        ):
            b = QPushButton(label)
            b.clicked.connect(slot)
            buttons.addWidget(b)
        cv = QVBoxLayout(common_box)
        cv.addWidget(self.common, 1)
        cv.addLayout(form)
        cv.addLayout(buttons)

        # -- battle events --------------------------------------------------------------------
        self.battle = QTableWidget(0, 4)
        self.battle.setHorizontalHeaderLabels(["When", "Program", "Only if", "Once"])
        self._table(self.battle)
        self.battle.itemSelectionChanged.connect(self._battle_selected)
        self.battle_hook = QComboBox()
        self.battle_hook.addItems(list(BATTLE_HOOKS))
        self.battle_program = QComboBox()
        self.battle_once = QCheckBox("Once per battle")
        self.conditions = QListWidget()
        self.conditions.setMaximumHeight(80)
        self.cond_source = QComboBox()
        self.cond_source.addItems(["battle", "switch", "variable"])
        self.cond_name = QLineEdit()
        self.cond_name.setPlaceholderText(
            "round · hp_ratio:astral_tyrant · alive:mender_wisp · switch name"
        )
        self.cond_op = QComboBox()
        self.cond_op.addItems(list(COMPARATORS))
        self.cond_value = QLineEdit("0.5")
        cond_row = QFormLayout()
        for label, field in (
            ("Source", self.cond_source),
            ("Name", self.cond_name),
            ("Comparison", self.cond_op),
            ("Value", self.cond_value),
        ):
            cond_row.addRow(label, field)
        add_cond, remove_cond = QPushButton("+ Condition"), QPushButton("− Condition")
        add_cond.clicked.connect(self.add_condition)
        remove_cond.clicked.connect(lambda: self.conditions.takeItem(self.conditions.currentRow()))
        cond_buttons = QHBoxLayout()  # on their own line: the fields above keep their width
        for button in (add_cond, remove_cond):
            button.setMinimumWidth(button.fontMetrics().horizontalAdvance(button.text()) + 34)
            cond_buttons.addWidget(button)
        cond_buttons.addStretch(1)
        battle_box = QGroupBox("Battle events — run a program when the battle reaches a moment")
        bform = QFormLayout()
        bform.addRow("When", self.battle_hook)
        bform.addRow("Program", self.battle_program)
        bform.addRow("Only if (all)", self.conditions)
        bform.addRow("", cond_row)
        bform.addRow("", cond_buttons)
        bform.addRow("", self.battle_once)
        bbuttons = QHBoxLayout()
        for label, slot in (
            ("Add", self.add_battle),
            ("Apply", self.apply_battle),
            ("Remove", self.remove_battle),
        ):
            b = QPushButton(label)
            b.clicked.connect(slot)
            bbuttons.addWidget(b)
        bv = QVBoxLayout(battle_box)
        bv.addWidget(self.battle, 1)
        bv.addLayout(bform)
        bv.addLayout(bbuttons)

        new_program = QPushButton("New Program…")
        new_program.clicked.connect(self._new_program_clicked)
        top = QHBoxLayout()
        hint = QLabel("Edit programs in Entity Events or Code.")
        hint.setObjectName("MutedLabel")
        hint.setWordWrap(True)
        top.addWidget(hint, 1)
        top.addStretch(1)
        top.addWidget(new_program)
        from .responsive_form import ResponsiveColumns

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addLayout(top)
        panels = ResponsiveColumns((common_box, battle_box), column_width=420)
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setWidget(panels)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.status)
        self._condition_values = []
        self.refresh()

    @staticmethod
    def _table(table):
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().hide()
        table.horizontalHeader().setStretchLastSection(True)

    def _try(self, action, message):
        try:
            result = action()
        except (EventFlowError, ValueError, KeyError, TypeError, IndexError) as exc:
            self.last_error = str(exc)
            self.status.setStyleSheet("color: #d9534f;")
            self.status.setText(str(exc))
            return None
        self.last_error = None
        self.status.setStyleSheet("")
        self.status.setText(message)
        self.refresh()
        self.changed.emit()
        return result if result is not None else True

    def refresh(self):
        if self.api.document.project is None:
            return
        programs = list(self.api.project.event_programs.ids())
        for combo in (self.common_program, self.battle_program):
            current = combo.currentText()
            combo.clear()
            combo.addItems(programs)
            if current in programs:
                combo.setCurrentText(current)
        self.common.setRowCount(0)
        for c in self.api.common_events():
            row = self.common.rowCount()
            self.common.insertRow(row)
            for col, text in enumerate((c.program_id, c.trigger, c.switch or "—")):
                self.common.setItem(row, col, QTableWidgetItem(text))
        self.battle.setRowCount(0)
        self._battle_index = []
        for index, b in self.api.battle_events():
            row = self.battle.rowCount()
            self.battle.insertRow(row)
            when = " and ".join(describe_condition(c) for c in b.conditions) or "always"
            values = (
                b.hook_name.removeprefix("rpg.battle."),
                b.event_program_id,
                when,
                "yes" if b.once else "",
            )
            for col, text in enumerate(values):
                self.battle.setItem(row, col, QTableWidgetItem(text))
            self._battle_index.append(index)
        self.common.resizeColumnsToContents()
        self.battle.resizeColumnsToContents()

    # -- common -----------------------------------------------------------------------------------
    def _common_selected(self):
        row = self.common.currentRow()
        if row < 0:
            return
        c = self.api.common_events()[row]
        self.common_program.setCurrentText(c.program_id)
        self.common_trigger.setCurrentText(c.trigger)
        self.common_switch.setText(c.switch)

    def add_common(self):
        pid, trigger, switch = (
            self.common_program.currentText(),
            self.common_trigger.currentText(),
            self.common_switch.text(),
        )
        return self._try(
            lambda: self.api.add_common_event(pid, trigger, switch.strip()),
            f"{pid} is a common event",
        )

    def apply_common(self):
        row = self.common.currentRow()
        trigger, switch = self.common_trigger.currentText(), self.common_switch.text().strip()
        return row >= 0 and self._try(
            lambda: self.api.set_common_event(row, trigger=trigger, switch=switch), "Saved"
        )

    def remove_common(self):
        row = self.common.currentRow()
        return row >= 0 and self._try(lambda: self.api.remove_common_event(row), "Removed")

    # -- battle -----------------------------------------------------------------------------------
    def _battle_selected(self):
        row = self.battle.currentRow()
        if row < 0:
            return
        binding = self.api.project.lifecycle_event_bindings[self._battle_index[row]]
        self.battle_hook.setCurrentText(binding.hook_name)
        self.battle_program.setCurrentText(binding.event_program_id)
        self.battle_once.setChecked(binding.once)
        self._condition_values = list(binding.conditions)
        self._show_conditions()

    def _show_conditions(self):
        self.conditions.clear()
        self.conditions.addItems([describe_condition(c) for c in self._condition_values])

    def add_condition(self):
        name = self.cond_name.text().strip()
        if not name:
            self.status.setText("Condition needs a name")
            return False
        self._condition_values.append(
            EventCondition(
                self.cond_source.currentText(),
                name,
                self.cond_op.currentText(),
                _coerce(self.cond_value.text()),
            )
        )
        self._show_conditions()
        return True

    def _form_conditions(self):
        kept = {self.conditions.item(i).text() for i in range(self.conditions.count())}
        self._condition_values = [
            c for c in self._condition_values if describe_condition(c) in kept
        ]
        return tuple(self._condition_values)

    def add_battle(self):
        hook, pid, once = (
            self.battle_hook.currentText(),
            self.battle_program.currentText(),
            self.battle_once.isChecked(),
        )
        conditions = self._form_conditions()
        return self._try(
            lambda: self.api.add_battle_event(hook, pid, conditions=conditions, once=once), "Added"
        )

    def apply_battle(self):
        row = self.battle.currentRow()
        if row < 0:
            return False
        index = self._battle_index[row]
        hook, pid, once = (
            self.battle_hook.currentText(),
            self.battle_program.currentText(),
            self.battle_once.isChecked(),
        )
        conditions = self._form_conditions()
        return self._try(
            lambda: self.api.set_battle_event(
                index, hook=hook, program_id=pid, conditions=conditions, once=once
            ),
            "Saved",
        )

    def remove_battle(self):
        row = self.battle.currentRow()
        return row >= 0 and self._try(
            lambda: self.api.remove_battle_event(self._battle_index[row]), "Removed"
        )

    def _new_program_clicked(self):
        value, ok = QInputDialog.getText(self, "New Event Program", "Program id:")
        if ok and value.strip():
            self._try(lambda: self.api.new_program(value.strip()), f"Created {value.strip()}")


class SequenceEditorDialog(QDialog):
    """Edit a SEQUENCE: parallel tracks, each an ordered list of track instructions."""

    FORMS = {
        "MOVE": (
            ("entity", "player"),
            ("x", "0"),
            ("y", "0"),
            ("duration", "1.0"),
            ("relative", "false"),
        ),
        "FACE": (("entity", "player"), ("facing", "down")),
        "ANIMATE": (("entity", "player"), ("clip", "idle")),
        "DIALOGUE": (("speaker", ""), ("text", "")),
        "WORLD": (("command", "CAMERA_FOCUS"), ("args", "entity=player, zoom=1.5"), ("wait", "0")),
        "WAIT": (("seconds", "0.5"),),
    }

    def __init__(self, args=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sequence — parallel tracks")
        args = dict(args or {})
        self.tracks = [
            dict(name=t.get("name", f"track{i + 1}"), instructions=list(t["instructions"]))
            for i, t in enumerate(args.get("tracks", []))
        ] or [{"name": "track1", "instructions": []}]
        self.track_list = QListWidget()
        self.track_list.currentRowChanged.connect(lambda _r: self._show_track())
        add_track, remove_track = QPushButton("+ Track"), QPushButton("− Track")
        add_track.clicked.connect(lambda: self.add_track(f"track{len(self.tracks) + 1}"))
        remove_track.clicked.connect(self.remove_track)
        self.steps = QListWidget()
        self.opcode = QComboBox()
        self.opcode.addItems(list(self.FORMS))
        self.opcode.currentTextChanged.connect(self._build_form)
        self.form = QFormLayout()
        self.fields = {}
        add_step, remove_step, up, down = (
            QPushButton("Add Step"),
            QPushButton("Remove"),
            QPushButton("↑"),
            QPushButton("↓"),
        )
        add_step.clicked.connect(self._add_step_clicked)
        remove_step.clicked.connect(self.remove_step)
        up.clicked.connect(lambda: self.move_step(-1))
        down.clicked.connect(lambda: self.move_step(1))
        self.cutscene = QCheckBox("Cutscene (locks player control, letterbox)")
        self.cutscene.setChecked(bool(args.get("cutscene", True)))
        self.skippable = QCheckBox("Player can skip (Esc) — everything lands on its end state")
        self.skippable.setChecked(bool(args.get("skippable", True)))
        self.wait = QComboBox()
        self.wait.addItems(["all", "none"])
        self.wait.setCurrentText(args.get("wait", "all"))
        self.error = QLabel("")
        self.error.setStyleSheet("color: #d9534f;")
        left = QVBoxLayout()
        tracks_heading = QLabel("Tracks (run in parallel)")
        tracks_heading.setProperty("presentationHeading", True)
        tracks_heading.setWordWrap(True)
        left.addWidget(tracks_heading)
        left.addWidget(self.track_list, 1)
        row = QHBoxLayout()
        row.addWidget(add_track)
        row.addWidget(remove_track)
        left.addLayout(row)
        right = QVBoxLayout()
        steps_heading = QLabel("Steps of the selected track (in order)")
        steps_heading.setProperty("presentationHeading", True)
        steps_heading.setWordWrap(True)
        right.addWidget(steps_heading)
        right.addWidget(self.steps, 1)
        order = QHBoxLayout()
        for b in (up, down, remove_step):
            order.addWidget(b)
        right.addLayout(order)
        right.addWidget(self.opcode)
        right.addLayout(self.form)
        right.addWidget(add_step)
        body = QHBoxLayout()
        body.addLayout(left, 1)
        body.addLayout(right, 2)
        options = QFormLayout()
        options.addRow(self.cutscene)
        options.addRow(self.skippable)
        options.addRow("Event waits for", self.wait)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(body, 1)
        layout.addLayout(options)
        layout.addWidget(self.error)
        layout.addWidget(buttons)
        self._build_form(self.opcode.currentText())
        self._show_tracks()
        from .presentation_layout import polish_presentation_page

        polish_presentation_page(self)
        self.resize(860, 700)

    def _show_tracks(self, select=0):
        self.track_list.blockSignals(True)
        self.track_list.clear()
        self.track_list.addItems([t["name"] for t in self.tracks])
        self.track_list.blockSignals(False)
        self.track_list.setCurrentRow(min(select, len(self.tracks) - 1))
        self._show_track()

    def _show_track(self):
        self.steps.clear()
        track = self.current_track
        if track is None:
            return
        from asteria.events import EventInstruction

        self.steps.addItems(
            [describe_instruction(EventInstruction.from_data(x)) for x in track["instructions"]]
        )

    @property
    def current_track(self):
        row = self.track_list.currentRow()
        return self.tracks[row] if 0 <= row < len(self.tracks) else None

    def _build_form(self, opcode):
        while self.form.rowCount():
            self.form.removeRow(0)
        self.fields = {}
        for name, default in self.FORMS[opcode]:
            edit = QLineEdit(default)
            self.fields[name] = edit
            self.form.addRow(name, edit)

    def add_track(self, name):
        self.tracks.append({"name": str(name), "instructions": []})
        self._show_tracks(len(self.tracks) - 1)

    def remove_track(self):
        row = self.track_list.currentRow()
        if row >= 0 and len(self.tracks) > 1:
            self.tracks.pop(row)
            self._show_tracks(max(0, row - 1))

    def step_from_form(self):
        opcode = self.opcode.currentText()
        values = {k: w.text() for k, w in self.fields.items()}
        if opcode == "WORLD":
            args = {
                "command": values["command"].strip().upper(),
                "args": parse_world_args(values["args"]),
            }
            if float(values["wait"] or 0) > 0:
                args["wait"] = float(values["wait"])
            return {"opcode": "WORLD", "args": args}
        args = {
            k: (_coerce(v) if k not in ("entity", "text", "speaker", "clip", "facing") else v)
            for k, v in values.items()
        }
        return {"opcode": opcode, "args": args}

    def add_step(self, step):
        track = self.current_track
        track["instructions"].append(step)
        self._show_track()
        self.steps.setCurrentRow(len(track["instructions"]) - 1)

    def _add_step_clicked(self):
        try:
            self.add_step(self.step_from_form())
        except ValueError as exc:
            self.error.setText(str(exc))

    def remove_step(self):
        row = self.steps.currentRow()
        if row >= 0:
            self.current_track["instructions"].pop(row)
            self._show_track()

    def move_step(self, delta):
        row = self.steps.currentRow()
        items = self.current_track["instructions"] if self.current_track else []
        target = row + delta
        if 0 <= row < len(items) and 0 <= target < len(items):
            items[row], items[target] = items[target], items[row]
            self._show_track()
            self.steps.setCurrentRow(target)

    def result_args(self):
        return EventFlowAuthoring.sequence_args(
            json.loads(json.dumps(self.tracks)),
            cutscene=self.cutscene.isChecked(),
            skippable=self.skippable.isChecked(),
            wait=self.wait.currentText(),
        )

    def _accept(self):
        try:
            self.result_args()
        except EventFlowError as exc:
            self.error.setText(str(exc))
            return
        self.accept()
