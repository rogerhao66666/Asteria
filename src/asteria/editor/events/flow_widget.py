"""Common & battle events panel and the sequence track editor (EVT-03, EVT-04)."""

from __future__ import annotations

import json
import re

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
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

from asteria.editor.events.editing import describe_instruction
from asteria.editor.events.flow_authoring import BATTLE_HOOKS, EventFlowAuthoring, EventFlowError
from asteria.editor.events.world_command_form import record_names
from asteria.editor.records.hub import free_id
from asteria.editor.records.vocabulary import AI_COMPARISONS, trigger_label, vocabulary_for, words
from asteria.editor.ui.fit import ValueCombo, WordCombo
from asteria.editor.ui.i18n import translate
from asteria.editor.ui.responsive_form import ResponsiveColumns
from asteria.events import EventInstruction
from asteria.events.common import COMMON_TRIGGERS
from asteria.events.conditions import EventCondition

COMPARATORS = ("<=", "<", "==", "!=", ">", ">=")


def describe_condition(c, names=None):
    """A condition in one line: "Crimson Warlord HP % is at most 50 %", "Round is at least 3",
    "Throne · Hot is on"."""
    names = names or {}
    source = str(c.source).strip().lower()
    kind, _, key = str(c.name).partition(":")
    who = names.get(key) or words(key)
    comparison = AI_COMPARISONS.get(c.operator, c.operator)
    if source == "battle" and kind == "hp_ratio" and isinstance(c.value, (int, float)):
        return f"{who} HP % {comparison} {c.value * 100:g} %"
    holds = (c.operator == "!=") != bool(c.value)
    if source == "battle" and kind == "alive":
        return f"{who} {'is alive' if holds else 'is down'}"
    if source == "switch" and c.operator in ("==", "!="):
        return f"{words(c.name)} {'is on' if holds else 'is off'}"
    value = f"{c.value:g}" if isinstance(c.value, (int, float)) else c.value
    return f"{words(c.name)} {comparison} {value}"


def _heading(title, help_text):
    label = QLabel(f"{translate(title)}  ⓘ")
    label.setObjectName("CardTitle")
    label.setToolTip(help_text)
    return label


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
        self.common_program = WordCombo()
        self.common_trigger = WordCombo()
        self.common_trigger.addItems(list(COMMON_TRIGGERS))
        self.common_switch = ValueCombo()
        self.common_switch.setEditable(True)
        self.common_switch.setProperty("i18n_choices", True)
        self.common_switch.offer_new("New Switch", "new_switch")
        common_box = QGroupBox()
        common_box.setProperty("untitled", True)  # its heading is inside, not on the frame
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
        cv.addWidget(
            _heading(
                "Common Events",
                "Programs any event can call. Autorun and parallel ones run by themselves while "
                "their switch is on.",
            )
        )
        cv.addWidget(self.common, 1)
        cv.addLayout(form)
        cv.addLayout(buttons)

        # -- battle events --------------------------------------------------------------------
        self.battle = QTableWidget(0, 4)
        self.battle.setHorizontalHeaderLabels(["When", "Program", "Only if", "Once"])
        self._table(self.battle)
        self.battle.itemSelectionChanged.connect(self._battle_selected)
        self.battle_hook = QComboBox()

        for hook in BATTLE_HOOKS:  # the moment in words; the hook name is the data
            self.battle_hook.addItem(trigger_label(hook), hook)
        self.battle_program = WordCombo()
        self.battle_once = QCheckBox("Once per battle")
        self.conditions = QListWidget()
        self.conditions.setMaximumHeight(80)
        self.cond_source = WordCombo()
        self.cond_source.addItems(["battle", "switch", "variable"])
        self.cond_name = ValueCombo()
        self.cond_name.setProperty("i18n_choices", True)
        self.cond_op = ValueCombo()
        self.cond_op.set_choices(AI_COMPARISONS.items())
        self.cond_number = QDoubleSpinBox()
        self.cond_number.setRange(-1_000_000.0, 1_000_000.0)
        self.cond_flag = ValueCombo()
        self.cond_row = QFormLayout()
        for label, field in (
            ("Source", self.cond_source),
            ("Name", self.cond_name),
            ("Comparison", self.cond_op),
            ("Value", self.cond_number),
            ("State", self.cond_flag),
        ):
            self.cond_row.addRow(label, field)
        cond_row = self.cond_row
        self.cond_source.currentIndexChanged.connect(lambda _i: self._source_changed())
        self.cond_name.currentIndexChanged.connect(lambda _i: self._name_changed())
        add_cond, remove_cond = QPushButton("+ Condition"), QPushButton("− Condition")
        add_cond.clicked.connect(self.add_condition)
        remove_cond.clicked.connect(self.remove_condition)
        cond_buttons = QHBoxLayout()  # on their own line: the fields above keep their width
        for button in (add_cond, remove_cond):
            button.setMinimumWidth(button.fontMetrics().horizontalAdvance(button.text()) + 34)
            cond_buttons.addWidget(button)
        cond_buttons.addStretch(1)
        battle_box = QGroupBox()
        battle_box.setProperty("untitled", True)  # its heading is inside, not on the frame
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
        bv.addWidget(_heading("Battle Events", "Run a program when a battle reaches a moment."))
        bv.addWidget(self.battle, 1)
        bv.addLayout(bform)
        bv.addLayout(bbuttons)

        self.program_pick = WordCombo()  # the program New made, or any other to delete
        new_program = QPushButton("New Program")
        new_program.clicked.connect(self._new_program_clicked)
        self.delete_program_button = QPushButton("Delete Program")
        self.delete_program_button.clicked.connect(self.delete_program)
        top = QHBoxLayout()
        top.addWidget(_heading("Programs", "Their steps are edited in Entity Events or Code."))
        top.addStretch(1)
        top.addWidget(self.program_pick)
        top.addWidget(new_program)
        top.addWidget(self.delete_program_button)

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
        self.delete_program_button.setEnabled(bool(programs))
        for combo in (self.common_program, self.battle_program, self.program_pick):
            current = combo.currentText()
            combo.clear()
            combo.addItems(programs)
            if current in programs:
                combo.setCurrentText(current)
        self.common_switch.set_choices(
            [(name, words(name)) for name in self.api.names_used("switch")], none="Always"
        )
        self._fill_names()
        if not self.cond_flag.count() and not self._condition_values:
            self._name_changed()
        self.common.setRowCount(0)
        for c in self.api.common_events():
            row = self.common.rowCount()
            self.common.insertRow(row)
            cells = (
                words(c.program_id),
                words(c.trigger),
                words(c.switch) if c.switch else translate("Always"),
            )
            for col, text in enumerate(cells):
                self.common.setItem(row, col, QTableWidgetItem(text))
        self.battle.setRowCount(0)
        self._battle_index = []
        for index, b in self.api.battle_events():
            row = self.battle.rowCount()
            self.battle.insertRow(row)
            when = " and ".join(self._condition_words(c) for c in b.conditions)
            when = when or translate("always")
            values = (
                translate(trigger_label(b.hook_name)),
                words(b.event_program_id),
                when,
                translate("yes") if b.once else "",
            )
            for col, text in enumerate(values):
                self.battle.setItem(row, col, QTableWidgetItem(text))
            self._battle_index.append(index)
        for table in (self.common, self.battle):
            table.resizeColumnsToContents()
            header = table.horizontalHeader()  # sizing to contents undoes the stretch: again
            header.setStretchLastSection(False)
            header.setStretchLastSection(True)

    # -- common -----------------------------------------------------------------------------------
    def _common_selected(self):
        row = self.common.currentRow()
        if row < 0:
            return
        c = self.api.common_events()[row]
        self.common_program.setCurrentText(c.program_id)
        self.common_trigger.setCurrentText(c.trigger)
        self.common_switch.setCurrentText(c.switch)

    def add_common(self):
        pid, trigger, switch = (
            self.common_program.currentText(),
            self.common_trigger.currentText(),
            self.common_switch.currentText(),
        )
        return self._try(
            lambda: self.api.add_common_event(pid, trigger, switch.strip()),
            f"{pid} is a common event",
        )

    def apply_common(self):
        row = self.common.currentRow()
        trigger, switch = self.common_trigger.currentText(), self.common_switch.currentText()
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
        found = self.battle_hook.findData(binding.hook_name)
        if found < 0:
            self.battle_hook.addItem(binding.hook_name, binding.hook_name)
            found = self.battle_hook.count() - 1
        self.battle_hook.setCurrentIndex(found)
        self.battle_program.setCurrentText(binding.event_program_id)
        self.battle_once.setChecked(binding.once)
        self._condition_values = list(binding.conditions)
        self._show_conditions()

    def _condition_words(self, condition):
        return translate(describe_condition(condition, vocabulary_for(self.api.document).names()))

    def _show_conditions(self):
        self.conditions.clear()
        self.conditions.addItems([self._condition_words(c) for c in self._condition_values])

    def _battle_values(self):
        """What a battle condition can read, in words (session/battle_events.py)."""
        database = self.api.project.rpg_database
        pairs = [("round", "Round")]
        for records in (database.enemies, database.actors):
            for key, record in records.items():
                name = getattr(record, "display_name", "") or words(key)
                pairs.append((f"hp_ratio:{key}", f"{name} HP %"))
                pairs.append((f"alive:{key}", f"{name} {translate('alive')}"))
        return pairs

    def _source_changed(self):
        """Another source: its names, the first of them picked."""
        self.cond_name.blockSignals(True)
        self.cond_name.clear()
        self.cond_name.setEditable(self.cond_source.currentText() != "battle")
        self.cond_name.blockSignals(False)
        self._fill_names()
        self._name_changed()

    def _fill_names(self):
        """The names on offer come from the source: only a switch or a variable can be new."""
        if self.api.document.project is None:
            return
        source = self.cond_source.currentText()
        pairs = self._battle_values() if source == "battle" else ()
        if source != "battle":
            pairs = [(name, words(name)) for name in self.api.names_used(source)]
            self.cond_name.offer_new(f"New {source.title()}", f"new_{source}")
        else:
            self.cond_name._new = None
        self.cond_name.set_choices(pairs)

    def _name_changed(self):
        """The value in the kind that fits: a percent, a whole round, on or off, alive or down."""
        source = self.cond_source.currentText()
        name = self.cond_name.currentText()
        percent = name.startswith("hp_ratio:")
        alive = name.startswith("alive:")
        flag = alive or source == "switch"
        self.cond_row.setRowVisible(self.cond_op, not flag)
        self.cond_row.setRowVisible(self.cond_number, not flag)
        self.cond_row.setRowVisible(self.cond_flag, flag)
        if flag:
            pairs = (("true", "Alive"), ("false", "Down"))
            if not alive:
                pairs = (("true", "Turned on"), ("false", "Turned off"))
            self.cond_flag.clear()
            self.cond_flag.set_choices(pairs)
            return
        self.cond_number.setDecimals(0 if source == "battle" else 2)
        self.cond_number.setSuffix(" %" if percent else "")
        self.cond_number.setValue(50 if percent else 1)

    def add_condition(self):
        source = self.cond_source.currentText()
        name = self.cond_name.currentText().strip()
        if not name:
            self.status.setText("Choose what the condition reads first.")
            return False
        if name.startswith("alive:") or source == "switch":
            operator, value = "==", self.cond_flag.currentText() == "true"
        else:
            operator, value = self.cond_op.currentText(), self.cond_number.value()
            if name.startswith("hp_ratio:"):
                value = value / 100
            elif float(value).is_integer():
                value = int(value)
        self._condition_values.append(EventCondition(source, name, operator, value))
        self._show_conditions()
        return True

    def remove_condition(self):
        row = self.conditions.currentRow()
        if 0 <= row < len(self._condition_values):
            del self._condition_values[row]
            self._show_conditions()

    def _form_conditions(self):
        return tuple(self._condition_values)

    def add_battle(self):
        hook, pid, once = (
            self.battle_hook.currentData() or self.battle_hook.currentText(),
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
            self.battle_hook.currentData() or self.battle_hook.currentText(),
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
        value = free_id("", self.api.project.event_programs.ids(), "new_program")
        self._try(lambda: self.api.new_program(value), f"Created {words(value)}")
        self.program_pick.setCurrentText(value)  # ready to use, or to delete again

    def delete_program(self):
        """Delete the picked program (refused, with the reason, while something runs it)."""
        value = self.program_pick.currentText()
        return bool(value) and self._try(
            lambda: self.api.delete_program(value), f"Deleted {words(value)}"
        )


class _Number(QDoubleSpinBox):
    """A step's number; ``text`` / ``setText`` as every field of a step has them."""

    def __init__(self, value):
        super().__init__()
        self.setRange(-1_000_000.0, 1_000_000.0)
        self.setDecimals(2)
        self.setSingleStep(0.5)
        self.setValue(float(value or 0))

    def text(self):
        return f"{self.value():g}"

    def setText(self, value):  # noqa: N802 - Qt-style
        self.setValue(float(value or 0))


class _Tick(QCheckBox):
    """A step's yes or no."""

    def __init__(self, value):
        super().__init__()
        self.setText(value)

    def text(self):
        return "true" if self.isChecked() else "false"

    def setText(self, value):  # noqa: N802 - Qt-style
        self.setChecked(str(value).strip().lower() == "true")


class _Pick(ValueCombo):
    """A step's value picked from a list; ``new``: a name of the author's own is fine too."""

    def __init__(self, pairs, value, *, new=False, none=None):
        super().__init__()
        self.setEditable(new)
        self.setProperty("i18n_choices", True)
        self.set_choices(pairs, none=none)
        self.setCurrentText(value)

    def text(self):
        return self.currentText()

    def setText(self, value):  # noqa: N802 - Qt-style
        self.setCurrentText(value)


FACINGS = ("down", "up", "left", "right")


class SequenceEditorDialog(QDialog):
    """Edit a SEQUENCE: parallel tracks, each an ordered list of track instructions."""

    OPCODES = {
        "MOVE": "Move",
        "FACE": "Face a direction",
        "ANIMATE": "Play an animation",
        "DIALOGUE": "Dialogue",
        "WORLD": "World command",
        "WAIT": "Wait",
    }
    LABELS = {
        "x": "X",
        "y": "Y",
        "portrait_asset_id": "Portrait",
        "portrait_side": "Portrait side",
    }
    NUMBERS = ("x", "y", "duration", "wait", "seconds")

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
        "DIALOGUE": (
            ("speaker", ""),
            ("text", ""),
            ("portrait_asset_id", ""),
            ("portrait_side", "left"),
        ),
        "WORLD": (("wait", "0"),),
        "WAIT": (("seconds", "0.5"),),
    }

    def __init__(self, args=None, parent=None, *, document=None):
        super().__init__(parent)
        self.document = document
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
        self.steps.currentRowChanged.connect(self._step_selected)
        self.opcode = ValueCombo()
        self.opcode.set_choices(self.OPCODES.items())
        self.opcode.currentIndexChanged.connect(
            lambda _i: self._build_form(self.opcode.currentText())
        )
        self.form = QFormLayout()
        self.fields = {}
        add_step, remove_step, up, down = (
            QPushButton("Add Step"),
            QPushButton("Remove"),
            QPushButton("↑"),
            QPushButton("↓"),
        )
        add_step.clicked.connect(self._add_step_clicked)
        self.update_step_button = QPushButton("Update Step")
        self.update_step_button.setEnabled(False)
        self.update_step_button.clicked.connect(self._update_step_clicked)
        remove_step.clicked.connect(self.remove_step)
        up.clicked.connect(lambda: self.move_step(-1))
        down.clicked.connect(lambda: self.move_step(1))
        self.cutscene = QCheckBox("Cutscene (locks player control, letterbox)")
        self.cutscene.setChecked(bool(args.get("cutscene", True)))
        self.skippable = QCheckBox("Player can skip (Esc) — everything lands on its end state")
        self.skippable.setChecked(bool(args.get("skippable", True)))
        self.wait = ValueCombo()
        self.wait.set_choices((("all", "Every track"), ("none", "Nothing")))
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
        step_buttons = QHBoxLayout()
        step_buttons.addWidget(add_step)
        step_buttons.addWidget(self.update_step_button)
        right.addLayout(step_buttons)
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
        from asteria.editor.ui.page_layout import polish_presentation_page

        polish_presentation_page(self)
        self.resize(860, 700)

    def _show_tracks(self, select=0):
        self.track_list.blockSignals(True)
        self.track_list.clear()
        self.track_list.addItems(
            [re.sub(r"(\D)(\d+)$", r"\1 \2", words(t["name"])) for t in self.tracks]
        )
        self.track_list.blockSignals(False)
        self.track_list.setCurrentRow(min(select, len(self.tracks) - 1))
        self._show_track()

    def _show_track(self):
        self.steps.clear()
        track = self.current_track
        if track is None:
            return

        names = record_names(self.document) if self.document is not None else None
        self.steps.addItems(
            [
                describe_instruction(EventInstruction.from_data(x), names)
                for x in track["instructions"]
            ]
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
            edit = self._field(name, default)
            self.fields[name] = edit
            self.form.addRow(self.LABELS.get(name) or words(name), edit)
        self.world = None
        if opcode == "WORLD":
            from asteria.editor.events.world_command_form import WorldCommandForm

            self.world = WorldCommandForm(
                self.document, command="CAMERA_FOCUS", args={"entity": "player", "zoom": 1.5}
            )
            self.form.insertRow(0, self.world)

    def _field(self, name, default):
        """Picked by clicking; only what the author writes (a line) is typed."""
        if name in self.NUMBERS:
            return _Number(default)
        if name == "relative":
            return _Tick(default)
        if name == "facing":
            return _Pick([(f, words(f)) for f in FACINGS], default)
        if name == "portrait_side":
            return _Pick((("left", "Left"), ("right", "Right")), default)
        if name == "entity":
            return _Pick(self._entities(), default, new=True)
        if name == "clip":
            return _Pick(self._clips(), default, new=True)
        if name == "speaker":
            pairs = self._speakers()
            return _Pick(pairs, default, new=True, none="No speaker")
        if name == "portrait_asset_id" and self.document is not None:
            from asteria.editor.assets.image_tools import PortraitLibrary
            from asteria.editor.events.dialogue_dialog import _PortraitPicker

            return _PortraitPicker(PortraitLibrary(self.document))
        return QLineEdit(default)

    def _entities(self):
        """The player, then the entities of the project's scenes."""
        pairs, seen = [("player", "Player")], {"player"}
        project = getattr(self.document, "project", None)
        for scene in project.scenes() if project is not None else ():
            for entity in scene.entities():
                if entity.name and entity.name not in seen:
                    seen.add(entity.name)
                    pairs.append((entity.name, entity.name))
        return pairs

    def _speakers(self):
        """The actors by name; a line can be said by anyone, so another name can be typed."""
        if self.document is None:
            return []
        actors = vocabulary_for(self.document).choices("actors")
        return [(c.label, c.label) for c in actors]

    def _clips(self):
        if self.document is None:
            return [("idle", "Idle")]
        return [(c.value, c.label) for c in vocabulary_for(self.document).choices("clips")]

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
            args = {"command": self.world.command_name(), "args": self.world.result_args()}
            if float(values["wait"] or 0) > 0:
                args["wait"] = float(values["wait"])
            return {"opcode": "WORLD", "args": args}
        plain = ("entity", "text", "speaker", "clip", "facing", "portrait_asset_id")
        args = {k: (_coerce(v) if k not in plain else v) for k, v in values.items()}
        if opcode == "DIALOGUE":  # the portrait keys are kept only when set
            args["portrait_asset_id"] = str(args.get("portrait_asset_id", "")).strip()
            args["portrait_side"] = str(args.get("portrait_side", "")).strip().lower()
            if not args["portrait_asset_id"]:
                del args["portrait_asset_id"]
            if args["portrait_side"] in ("", "left"):
                del args["portrait_side"]
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

    def _step_selected(self, row):
        """A step clicked: the form shows it, to change and update (a step of a kind the form
        doesn't have stays as it is)."""
        items = self.current_track["instructions"] if self.current_track else []
        known = 0 <= row < len(items) and items[row].get("opcode") in self.FORMS
        self.update_step_button.setEnabled(known and self._load_step(items[row]))

    def _load_step(self, step):
        opcode, args = step["opcode"], step.get("args") or {}
        blocked = self.opcode.blockSignals(True)
        self.opcode.setCurrentText(opcode)
        self.opcode.blockSignals(blocked)
        self._build_form(opcode)
        try:
            if opcode == "WORLD":
                self.world.set_command(args.get("command", ""), args.get("args") or {})
                self.fields["wait"].setText(args.get("wait", 0))
                return True
            for name, default in self.FORMS[opcode]:
                self.fields[name].setText(args.get(name, default))
        except (TypeError, ValueError):  # a value the form can't hold: not changed from here
            return False
        return True

    def update_step(self, row):
        """The selected step becomes what the form says; what the form doesn't show stays."""
        items, new = self.current_track["instructions"], self.step_from_form()
        old = items[row]
        if old.get("opcode") == new["opcode"]:
            shown = {name for name, _default in self.FORMS[new["opcode"]]}
            shown |= {"command", "args"} if new["opcode"] == "WORLD" else set()
            kept = {k: v for k, v in (old.get("args") or {}).items() if k not in shown}
            new = dict(old, args={**kept, **new["args"]})
        items[row] = new
        self._show_track()
        self.steps.setCurrentRow(row)

    def _update_step_clicked(self):
        try:
            self.update_step(self.steps.currentRow())
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
