"""Enemy AI editor (EDT-07): decision rules, conditions, boss phases, enemy binding, live decision preview."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from asteria.rpg.enemy_ai import ACTION_KINDS, COMPARISONS, CONDITION_KINDS, CONDITION_PARAMS, TARGET_SELECTORS

from .enemy_ai_authoring import AIScenario, EnemyAIEditor, EnemyAIEditorError

SUBJECT_PARAM = {"resource": "resource_id", "resource_ratio": "resource_id", "stat": "stat_id", "memory": "key"}


def describe_condition(value):
    p = value.params
    subject = p.get("resource_id") or p.get("stat_id") or p.get("key") or ""
    if value.kind in ("always", "can_act"):
        text = value.kind.replace("_", " ")
    elif value.kind == "resource_ratio":
        text = f"{subject} {p.get('op', '<=')} {float(p.get('value', 0)) * 100:g}%"
    elif value.kind == "round_index":
        text = f"round {p.get('op', '>=')} {p.get('value')}"
    elif value.kind == "phase":
        text = f"phase {p.get('op', '==')} {p.get('value')}"
    else:
        text = f"{value.kind} {subject} {p.get('op', '')} {p.get('value', '')}".strip()
    return f"NOT ({text})" if value.negate else text


class ConditionList(QGroupBox):
    """Conditions of one rule or phase: list + a small form to add / replace / remove."""

    addRequested = Signal(str, bool, dict)
    replaceRequested = Signal(int, str, bool, dict)
    removeRequested = Signal(int)

    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.list = QListWidget()
        self.list.setMaximumHeight(90)
        self.list.currentRowChanged.connect(self._load)
        self.kind = QComboBox()
        self.kind.addItems(list(CONDITION_KINDS))
        self.kind.currentTextChanged.connect(self._kind_changed)
        self.subject = QLineEdit()
        self.op = QComboBox()
        self.op.addItems(list(COMPARISONS))
        self.value = QLineEdit()
        self.negate = QCheckBox("Not")
        row = QHBoxLayout()
        for w in (self.kind, self.subject, self.op, self.value, self.negate):
            row.addWidget(w)
        buttons = QHBoxLayout()
        for label, slot in (("Add", self._add), ("Replace", self._replace), ("Remove", self._remove)):
            b = QPushButton(label)
            b.clicked.connect(slot)
            buttons.addWidget(b)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list)
        layout.addLayout(row)
        layout.addLayout(buttons)
        self.conditions = ()
        self._kind_changed(self.kind.currentText())

    def set_conditions(self, conditions):
        self.conditions = tuple(conditions)
        self.list.clear()
        self.list.addItems([describe_condition(c) for c in self.conditions])

    def _kind_changed(self, kind):
        params = CONDITION_PARAMS.get(kind, ())
        self.subject.setVisible(kind in SUBJECT_PARAM)
        self.subject.setPlaceholderText(SUBJECT_PARAM.get(kind, ""))
        self.op.setVisible("op" in params)
        self.value.setVisible("value" in params)
        self.value.setPlaceholderText("0..1" if kind == "resource_ratio" else "value")

    def _load(self, row):
        if not 0 <= row < len(self.conditions):
            return
        c = self.conditions[row]
        self.kind.setCurrentText(c.kind)
        self.subject.setText(str(c.params.get(SUBJECT_PARAM.get(c.kind, ""), "")))
        self.op.setCurrentText(str(c.params.get("op", "==")))
        self.value.setText("" if c.params.get("value") is None else str(c.params.get("value")))
        self.negate.setChecked(c.negate)

    def form(self):
        kind = self.kind.currentText()
        params = {}
        if kind in SUBJECT_PARAM:
            params[SUBJECT_PARAM[kind]] = self.subject.text().strip()
        if "op" in CONDITION_PARAMS.get(kind, ()):
            params["op"] = self.op.currentText()
        if "value" in CONDITION_PARAMS.get(kind, ()):
            params["value"] = self.value.text().strip()
        return kind, self.negate.isChecked(), params

    def _add(self):
        self.addRequested.emit(*self.form())

    def _replace(self):
        if self.list.currentRow() >= 0:
            self.replaceRequested.emit(self.list.currentRow(), *self.form())

    def _remove(self):
        if self.list.currentRow() >= 0:
            self.removeRequested.emit(self.list.currentRow())


class EnemyAIEditorWidget(QWidget):
    changed = Signal()

    RULE_COLUMNS = ("Rule", "Action", "Ability / Hook", "Target", "Priority", "Weight", "When")
    PHASE_COLUMNS = ("Phase", "Priority", "Rules", "Actions / turn", "Enters when")

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.api = EnemyAIEditor(document)
        self.last_error = None

        # -- left: AI records --------------------------------------------------------
        self.ai_list = QListWidget()
        self.ai_list.currentTextChanged.connect(lambda _t: self._load())
        new_button, delete_button = QPushButton("New…"), QPushButton("Delete")
        new_button.clicked.connect(self._new_clicked)
        delete_button.clicked.connect(self.delete_ai)
        left = QVBoxLayout()
        left.addWidget(QLabel("Enemy AI"))
        left.addWidget(self.ai_list, 1)
        row = QHBoxLayout()
        row.addWidget(new_button)
        row.addWidget(delete_button)
        left.addLayout(row)
        left_box = QWidget()
        left_box.setLayout(left)

        # -- overview ------------------------------------------------------------------
        self.actions_per_ready = QSpinBox()
        self.actions_per_ready.setRange(1, 9)
        self.actions_per_ready.editingFinished.connect(self._apply_actions)
        self.initial_phase = QComboBox()
        self.initial_phase.activated.connect(lambda _i: self._apply_initial())
        self.used_by = QLabel("")
        self.used_by.setWordWrap(True)
        self.enemy = QComboBox()
        bind = QPushButton("Use for Enemy")
        bind.clicked.connect(lambda: self.bind_enemy(self.enemy.currentText()))
        bind_row = QHBoxLayout()
        bind_row.addWidget(self.enemy, 1)
        bind_row.addWidget(bind)
        overview = QGroupBox("Overview")
        form = QFormLayout(overview)
        form.addRow("Actions per turn", self.actions_per_ready)
        form.addRow("Starting phase", self.initial_phase)
        form.addRow("Used by", self.used_by)
        form.addRow("Bind", bind_row)

        # -- rules tab -------------------------------------------------------------------
        self.rules = QTableWidget(0, len(self.RULE_COLUMNS))
        self.rules.setHorizontalHeaderLabels(list(self.RULE_COLUMNS))
        self.rules.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.rules.setSelectionMode(QAbstractItemView.SingleSelection)
        self.rules.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.rules.verticalHeader().hide()
        self.rules.horizontalHeader().setStretchLastSection(True)
        self.rules.itemSelectionChanged.connect(self._rule_selected)
        self.action_kind = QComboBox()
        self.action_kind.addItems(list(ACTION_KINDS))
        self.action_kind.currentTextChanged.connect(self._action_changed)
        self.ability = QComboBox()
        self.ability.setEditable(True)
        self.hook = QLineEdit()
        self.hook.setPlaceholderText("hook name, e.g. rpg.boss.summon")
        self.target = QComboBox()
        self.target.setEditable(True)
        self.target.addItems([*TARGET_SELECTORS, "lowest_resource_ratio:vitality"])
        self.priority = QSpinBox()
        self.priority.setRange(-999, 999)
        self.weight = QDoubleSpinBox()
        self.weight.setRange(0.0, 999.0)
        self.weight.setDecimals(2)
        rule_box = QGroupBox("Selected rule")
        rule_form = QFormLayout(rule_box)
        rule_form.addRow("Action", self.action_kind)
        rule_form.addRow("Ability", self.ability)
        rule_form.addRow("Hook", self.hook)
        rule_form.addRow("Target", self.target)
        rule_form.addRow("Priority", self.priority)
        rule_form.addRow("Weight", self.weight)
        rule_buttons = QHBoxLayout()
        for label, slot in (
            ("Apply", self.apply_rule),
            ("Add Rule…", self._add_rule_clicked),
            ("Remove", self.remove_rule),
        ):
            b = QPushButton(label)
            b.clicked.connect(slot)
            rule_buttons.addWidget(b)
        rule_form.addRow(rule_buttons)
        self.rule_conditions = ConditionList("Rule applies when (all)")
        self._wire_conditions(self.rule_conditions, "rule")
        rules_tab = QWidget()
        rules_layout = QVBoxLayout(rules_tab)
        rules_layout.addWidget(self._table_over_detail(self.rules, rule_box, self.rule_conditions), 1)

        # -- phases tab ------------------------------------------------------------------
        self.phases = QTableWidget(0, len(self.PHASE_COLUMNS))
        self.phases.setHorizontalHeaderLabels(list(self.PHASE_COLUMNS))
        self.phases.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.phases.setSelectionMode(QAbstractItemView.SingleSelection)
        self.phases.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.phases.verticalHeader().hide()
        self.phases.horizontalHeader().setStretchLastSection(True)
        self.phases.itemSelectionChanged.connect(self._phase_selected)
        self.phase_priority = QSpinBox()
        self.phase_priority.setRange(-999, 999)
        self.phase_rules = QListWidget()
        self.phase_rules.setMaximumHeight(110)
        self.phase_actions = QSpinBox()
        self.phase_actions.setRange(0, 9)
        self.phase_actions.setSpecialValueText("AI default")
        self.enter_hook = QLineEdit()
        self.exit_hook = QLineEdit()
        phase_box = QGroupBox("Selected phase")
        phase_form = QFormLayout(phase_box)
        phase_form.addRow("Priority", self.phase_priority)
        phase_form.addRow("Rules (none = all)", self.phase_rules)
        phase_form.addRow("Actions per turn", self.phase_actions)
        phase_form.addRow("On enter hook", self.enter_hook)
        phase_form.addRow("On exit hook", self.exit_hook)
        phase_buttons = QHBoxLayout()
        for label, slot in (
            ("Apply", self.apply_phase),
            ("Add Phase…", self._add_phase_clicked),
            ("Remove", self.remove_phase),
        ):
            b = QPushButton(label)
            b.clicked.connect(slot)
            phase_buttons.addWidget(b)
        phase_form.addRow(phase_buttons)
        self.phase_conditions = ConditionList("Phase starts when (all)")
        self._wire_conditions(self.phase_conditions, "phase")
        phases_tab = QWidget()
        phases_layout = QVBoxLayout(phases_tab)
        phases_layout.addWidget(self._table_over_detail(self.phases, phase_box, self.phase_conditions), 1)

        self.tabs = QTabWidget()
        self.tabs.addTab(rules_tab, "Decision Rules")
        self.tabs.addTab(phases_tab, "Boss Phases")
        center = QVBoxLayout()
        center.addWidget(overview)
        center.addWidget(self.tabs, 1)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        center.addWidget(self.status)
        center_box = QWidget()
        center_box.setLayout(center)

        # -- right: preview & checks -----------------------------------------------------
        self.round_index = QSpinBox()
        self.round_index.setRange(1, 999)
        self.round_index.valueChanged.connect(lambda _v: self.run_preview())
        self.can_act = QCheckBox("Can act")
        self.can_act.setChecked(True)
        self.can_act.toggled.connect(lambda _v: self.run_preview())
        self.resource_form = QFormLayout()
        self.resource_inputs = {}
        self.decision = QListWidget()
        self.phase_label = QLabel("")
        self.curve = QLabel("")
        self.curve.setWordWrap(True)
        self.problem_list = QListWidget()
        preview = QGroupBox("Decision preview (battle rules)")
        pv = QVBoxLayout(preview)
        top = QFormLayout()
        top.addRow("Round", self.round_index)
        top.addRow(self.can_act)
        pv.addLayout(top)
        pv.addLayout(self.resource_form)
        pv.addWidget(self.phase_label)
        pv.addWidget(QLabel("Would pick"))
        pv.addWidget(self.decision)
        pv.addWidget(QLabel("Phase by vitality"))
        pv.addWidget(self.curve)
        checks = QGroupBox("Checks")
        cv = QVBoxLayout(checks)
        cv.addWidget(self.problem_list)
        right = QVBoxLayout()
        right.addWidget(preview, 2)
        right.addWidget(checks, 1)
        right_box = QWidget()
        right_box.setLayout(right)

        split = QSplitter()
        split.addWidget(left_box)
        split.addWidget(center_box)
        split.addWidget(right_box)
        split.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.addWidget(split)
        self.refresh()

    @staticmethod
    def _table_over_detail(table, box, conditions):
        """Table above its inspector in a splitter; the table always shows several rows."""
        table.setMinimumHeight(150)
        detail = QWidget()
        row = QHBoxLayout(detail)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(box, 1)
        row.addWidget(conditions, 1)
        split = QSplitter(Qt.Vertical)
        split.addWidget(table)
        split.addWidget(detail)
        split.setStretchFactor(0, 1)
        split.setChildrenCollapsible(False)
        return split

    # -- state --------------------------------------------------------------------------
    @property
    def ai_id(self):
        item = self.ai_list.currentItem()
        return None if item is None else item.text()

    @property
    def rule_id(self):
        row = self.rules.currentRow()
        item = self.rules.item(row, 0) if row >= 0 else None
        return None if item is None else item.text()

    @property
    def phase_id(self):
        row = self.phases.currentRow()
        item = self.phases.item(row, 0) if row >= 0 else None
        return None if item is None else item.text()

    def refresh(self, select=None):
        if self.api.document.project is None:
            self.ai_list.clear()
            return
        current = select or self.ai_id
        ids = self.api.ai_ids()
        self.ai_list.blockSignals(True)
        self.ai_list.clear()
        self.ai_list.addItems(list(ids))
        self.ai_list.blockSignals(False)
        self.ability.clear()
        self.ability.addItems(list(self.api.abilities()))
        self.enemy.clear()
        self.enemy.addItems(sorted(self.api.database.enemies))
        if ids:
            self.ai_list.setCurrentRow(ids.index(current) if current in ids else 0)
        self._load()

    def select_ai(self, ai_id):
        self.refresh(select=ai_id)
        return self.ai_id == ai_id

    def _select_row(self, table, key):
        for row in range(table.rowCount()):
            if table.item(row, 0).text() == key:
                table.selectRow(row)
                return True
        return False

    def select_rule(self, rule_id):
        self.tabs.setCurrentIndex(0)
        return self._select_row(self.rules, rule_id)

    def select_phase(self, phase_id):
        self.tabs.setCurrentIndex(1)
        return self._select_row(self.phases, phase_id)

    def _load(self, rule=None, phase=None):
        ai_id = self.ai_id
        if ai_id is None:
            return
        rule, phase = rule or self.rule_id, phase or self.phase_id
        ai = self.api.get(ai_id)
        self.actions_per_ready.blockSignals(True)
        self.actions_per_ready.setValue(ai.actions_per_ready)
        self.actions_per_ready.blockSignals(False)
        self.initial_phase.clear()
        self.initial_phase.addItem("(none)", None)
        for p in ai.phases:
            self.initial_phase.addItem(p.phase_id, p.phase_id)
        self.initial_phase.setCurrentIndex(max(0, self.initial_phase.findData(ai.initial_phase_id)))
        used = self.api.bound_enemies(ai_id)
        self.used_by.setText(", ".join(used) if used else "No enemy uses this AI yet")
        self.rules.blockSignals(True)
        self.rules.setRowCount(0)
        for r in ai.rules:
            row = self.rules.rowCount()
            self.rules.insertRow(row)
            what = r.payload.get("ability_id") or r.payload.get("hook") or ""
            when = " and ".join(describe_condition(c) for c in r.conditions) or "always"
            values = (r.rule_id, r.action_kind, what, r.target_selector, str(r.priority), f"{r.weight:g}", when)
            for col, text in enumerate(values):
                self.rules.setItem(row, col, QTableWidgetItem(text))
        self.rules.blockSignals(False)
        self.rules.resizeColumnsToContents()
        self.phases.blockSignals(True)
        self.phases.setRowCount(0)
        for p in ai.phases:
            row = self.phases.rowCount()
            self.phases.insertRow(row)
            when = " and ".join(describe_condition(c) for c in p.conditions) or "always"
            values = (
                p.phase_id,
                str(p.priority),
                ", ".join(p.decision_rule_ids) or "all",
                "default" if p.actions_per_ready is None else str(p.actions_per_ready),
                when,
            )
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col == 0 and p.phase_id == ai.initial_phase_id:
                    item.setToolTip("Starting phase")
                self.phases.setItem(row, col, item)
        self.phases.blockSignals(False)
        self.phases.resizeColumnsToContents()
        if not (rule and self._select_row(self.rules, rule)) and self.rules.rowCount():
            self.rules.selectRow(0)
        if not (phase and self._select_row(self.phases, phase)) and self.phases.rowCount():
            self.phases.selectRow(0)
        self._rule_selected()
        self._phase_selected()
        self._build_resource_inputs()
        self.problem_list.clear()
        problems = self.api.problems(ai_id)
        self.problem_list.addItems(problems or ["No problems"])
        self.run_preview()

    def _rule_selected(self):
        if self.ai_id is None or self.rule_id is None:
            self.rule_conditions.set_conditions(())
            return
        r = self.api.rule(self.ai_id, self.rule_id)
        self.action_kind.setCurrentText(r.action_kind)
        self.ability.setCurrentText(str(r.payload.get("ability_id", "")))
        self.hook.setText(str(r.payload.get("hook", "")))
        self.target.setCurrentText(r.target_selector)
        self.priority.setValue(r.priority)
        self.weight.setValue(r.weight)
        self.rule_conditions.set_conditions(r.conditions)
        self._action_changed(r.action_kind)

    def _phase_selected(self):
        ai_id, phase_id = self.ai_id, self.phase_id
        self.phase_rules.clear()
        if ai_id is None or phase_id is None:
            self.phase_conditions.set_conditions(())
            return
        p = self.api.phase(ai_id, phase_id)
        self.phase_priority.setValue(p.priority)
        for r in self.api.get(ai_id).rules:
            item = QListWidgetItem(r.rule_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if r.rule_id in p.decision_rule_ids else Qt.Unchecked)
            self.phase_rules.addItem(item)
        self.phase_actions.setValue(p.actions_per_ready or 0)
        self.enter_hook.setText(p.enter_hook or "")
        self.exit_hook.setText(p.exit_hook or "")
        self.phase_conditions.set_conditions(p.conditions)

    def _action_changed(self, kind):
        self.ability.setEnabled(kind == "ability")
        self.hook.setEnabled(kind == "hook")

    # -- edits --------------------------------------------------------------------------
    def _try(self, action, message, **select):
        try:
            result = action()
        except (EnemyAIEditorError, ValueError, KeyError, TypeError, RuntimeError) as exc:
            self.last_error = str(exc)
            self.status.setStyleSheet("color: #d9534f;")
            self.status.setText(str(exc))
            return None
        self.last_error = None
        self.status.setStyleSheet("")
        self.status.setText(message)
        self._load(**select)
        self.changed.emit()
        return result if result is not None else True

    def _apply_actions(self):
        if self.ai_id and self.actions_per_ready.value() != self.api.get(self.ai_id).actions_per_ready:
            self._try(lambda: self.api.set_actions_per_ready(self.ai_id, self.actions_per_ready.value()), "Saved")

    def _apply_initial(self):
        if self.ai_id:
            phase = self.initial_phase.currentData()
            self._try(lambda: self.api.set_initial_phase(self.ai_id, phase), "Starting phase set")

    def bind_enemy(self, enemy_id):
        ai_id = self.ai_id

        def bind():
            with self.api.document.group(f"Use {ai_id} for {enemy_id}"):  # one undo step, rolled back on failure
                if self.api.database.enemy_behavior_bindings.get(enemy_id) is not None:
                    self.api.unbind(enemy_id)
                return self.api.bind(enemy_id, ai_id)

        return self._try(bind, f"{enemy_id} now uses {ai_id}")

    def apply_rule(self):
        ai_id, rule_id = self.ai_id, self.rule_id
        if rule_id is None:
            return None
        kind = self.action_kind.currentText()
        changes = {
            "action_kind": kind,
            "target_selector": self.target.currentText().strip(),
            "priority": self.priority.value(),
            "weight": self.weight.value(),
        }
        if kind == "ability":
            changes["ability_id"] = self.ability.currentText().strip()
        elif kind == "hook":
            changes["hook"] = self.hook.text().strip()
        return self._try(lambda: self.api.edit_rule(ai_id, rule_id, **changes), f"Rule {rule_id} saved", rule=rule_id)

    def add_rule(self, rule_id):
        ability = self.ability.currentText().strip() or None
        return self._try(
            lambda: self.api.add_rule(self.ai_id, rule_id, ability_id=ability), f"Rule {rule_id} added", rule=rule_id
        )

    def remove_rule(self):
        rule_id = self.rule_id
        return rule_id and self._try(lambda: self.api.remove_rule(self.ai_id, rule_id), f"Rule {rule_id} removed")

    def apply_phase(self):
        ai_id, phase_id = self.ai_id, self.phase_id
        if phase_id is None:
            return None
        rules = [
            self.phase_rules.item(i).text()
            for i in range(self.phase_rules.count())
            if self.phase_rules.item(i).checkState() == Qt.Checked
        ]
        changes = {
            "priority": self.phase_priority.value(),
            "rule_ids": rules,
            "actions_per_ready": self.phase_actions.value() or None,
            "enter_hook": self.enter_hook.text().strip(),
            "exit_hook": self.exit_hook.text().strip(),
        }
        return self._try(
            lambda: self.api.edit_phase(ai_id, phase_id, **changes), f"Phase {phase_id} saved", phase=phase_id
        )

    def add_phase(self, phase_id):
        return self._try(lambda: self.api.add_phase(self.ai_id, phase_id), f"Phase {phase_id} added", phase=phase_id)

    def remove_phase(self):
        phase_id = self.phase_id
        return phase_id and self._try(lambda: self.api.remove_phase(self.ai_id, phase_id), f"Phase {phase_id} removed")

    def _wire_conditions(self, widget, kind):
        def owner():
            return (kind, self.rule_id if kind == "rule" else self.phase_id)

        def keep():
            return {"rule": self.rule_id} if kind == "rule" else {"phase": self.phase_id}

        widget.addRequested.connect(
            lambda k, neg, params: self._try(
                lambda: self.api.add_condition(self.ai_id, owner(), k, negate=neg, **params),
                "Condition added",
                **keep(),
            )
        )
        widget.replaceRequested.connect(
            lambda i, k, neg, params: self._try(
                lambda: self.api.replace_condition(self.ai_id, owner(), i, k, negate=neg, **params),
                "Condition replaced",
                **keep(),
            )
        )
        widget.removeRequested.connect(
            lambda i: self._try(
                lambda: self.api.remove_condition(self.ai_id, owner(), i), "Condition removed", **keep()
            )
        )

    def create_ai(self, ai_id):
        result = self._try(lambda: self.api.create(ai_id), f"Created {ai_id}")
        if result:
            self.refresh(select=ai_id)
        return result

    def delete_ai(self):
        ai_id = self.ai_id
        result = ai_id and self._try(lambda: self.api.delete(ai_id), f"Deleted {ai_id}")
        if result:
            self.refresh()
        return result

    def _new_clicked(self):
        value, ok = QInputDialog.getText(self, "New Enemy AI", "AI id:")
        if ok and value.strip():
            self.create_ai(value.strip())

    def _add_rule_clicked(self):
        value, ok = QInputDialog.getText(self, "Add Rule", "Rule id:")
        if ok and value.strip():
            self.add_rule(value.strip())

    def _add_phase_clicked(self):
        value, ok = QInputDialog.getText(self, "Add Boss Phase", "Phase id:")
        if ok and value.strip():
            self.add_phase(value.strip())

    # -- preview --------------------------------------------------------------------------
    def _build_resource_inputs(self):
        while self.resource_form.rowCount():
            self.resource_form.removeRow(0)
        self.resource_inputs = {}
        for rid in self.api.resources(self.ai_id):
            maximum = self.api.resource_maximum(self.ai_id, rid)
            spin = QDoubleSpinBox()
            spin.setRange(0.0, maximum)
            spin.setDecimals(0 if maximum >= 20 else 2)
            spin.setValue(maximum if rid == "vitality" else 0.0)
            spin.setSuffix(f" / {maximum:g}")
            spin.valueChanged.connect(lambda _v: self.run_preview())
            self.resource_inputs[rid] = (spin, maximum)
            self.resource_form.addRow(rid, spin)

    def set_preview_resource(self, resource_id, amount):
        self.resource_inputs[resource_id][0].setValue(float(amount))
        return self.run_preview()

    def scenario(self):
        values = {rid: spin.value() for rid, (spin, _) in self.resource_inputs.items()}
        maxima = {rid: maximum for rid, (_, maximum) in self.resource_inputs.items()}
        return AIScenario(
            round_index=self.round_index.value(),
            resource_values=values,
            resource_maxima=maxima,
            can_act=self.can_act.isChecked(),
        )

    def run_preview(self):
        self.decision.clear()
        if self.ai_id is None:
            return None
        scenario = self.scenario()
        try:
            result = self.api.preview(self.ai_id, scenario)
            vitality = (
                "vitality" if "vitality" in self.resource_inputs else next(iter(self.resource_inputs), "vitality")
            )
            curve = (
                self.api.phase_by_ratio(self.ai_id, vitality, steps=10, scenario=scenario)
                if self.api.get(self.ai_id).phases
                else []
            )
        except EnemyAIEditorError as exc:
            self.phase_label.setText(str(exc))
            self.curve.setText("")
            return None
        self.phase_label.setText(f"Phase: {result.phase_id or '—'}")
        for rule_id, chance in result.chances:
            self.decision.addItem(f"{rule_id}  {chance * 100:.0f}%")
        if not result.chances:
            self.decision.addItem("(no rule can be picked — the enemy skips its turn)")
        segments = []
        for ratio, phase in curve:
            if not segments or segments[-1][1] != phase:
                segments.append((ratio, phase))
        self.curve.setText("  →  ".join(f"{phase} ≤{ratio * 100:.0f}%" for ratio, phase in segments))
        return result
