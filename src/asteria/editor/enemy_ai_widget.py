"""Enemy AI editor (EDT-07): the AI records edited with the same plain form as Game Data ▸ Enemy
AI (rules picked by name, conditions in words, boss phases with Starts When), beside the enemy
binding, a live decision preview and the record's checks."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .enemy_ai_authoring import AIScenario, EnemyAIEditor, EnemyAIEditorError
from .i18n import translate
from .responsive_form import FlowForm


class EnemyAIEditorWidget(QWidget):
    changed = Signal()

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.api = EnemyAIEditor(document)
        self.last_error = None
        from .authoring_hub_widget import FamilyHostWidget

        # -- left and centre: the AI records, the same form as Game Data's -----------------
        self.host = FamilyHostWidget("Enemy AI", _AIRecords(document).categories)
        self.host.changed.connect(self._edited)
        self._wired = None

        # -- right: who uses it, what it would do now, its checks -------------------------
        self.used_by = QLabel("")
        self.used_by.setWordWrap(True)
        self.enemy = QComboBox()  # enemies by name
        bind = QPushButton(translate("Use for Enemy"))
        bind.setToolTip(translate("The picked enemy fights with this AI."))
        bind.clicked.connect(lambda: self.bind_enemy(self.enemy.currentData()))
        bind_row = QHBoxLayout()
        bind_row.addWidget(self.enemy, 1)
        bind_row.addWidget(bind)
        users = QGroupBox(translate("Used By"))
        uv = QVBoxLayout(users)
        uv.addWidget(self.used_by)
        uv.addLayout(bind_row)

        self.round_index = QSpinBox()
        self.round_index.setRange(1, 999)
        self.round_index.valueChanged.connect(lambda _v: self.run_preview())
        self.can_act = QCheckBox(translate("Can act"))
        self.can_act.setChecked(True)
        self.can_act.toggled.connect(lambda _v: self.run_preview())
        self.resource_form = FlowForm(column_width=130)  # HP, MP, Shield side by side
        self.resource_form.setVerticalSpacing(10)
        self.resource_form.setHorizontalSpacing(12)
        self.resource_inputs = {}
        self.decision = QListWidget()
        self.phase_label = QLabel("")
        self.curve = QLabel("")
        self.curve.setWordWrap(True)
        self.problem_list = QListWidget()
        self.status = QLabel("")
        self.status.setWordWrap(True)
        preview = QGroupBox(translate("Decision Preview"))
        preview.setToolTip(
            translate("Set a moment of the battle: the boss's phase and pick follow.")
        )
        pv = QVBoxLayout(preview)
        top = FlowForm(column_width=110)  # the round and "can act" on one line
        top.addRow(translate("Round"), self.round_index)
        top.addRow("", self.can_act)
        pv.addWidget(top)
        pv.addWidget(self.resource_form)
        pv.addWidget(self.phase_label)
        pv.addWidget(QLabel(translate("Would pick")))
        pv.addWidget(self.decision)
        pv.addWidget(QLabel(translate("Phase by HP")))
        pv.addWidget(self.curve)
        checks = QGroupBox(translate("Checks"))
        cv = QVBoxLayout(checks)
        cv.addWidget(self.problem_list)
        cv.addWidget(self.status)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.addWidget(users)
        right.addWidget(preview, 2)
        right.addWidget(checks, 1)
        right_box = QWidget()
        right_box.setProperty("sidePanel", True)  # Focus Mode folds it away
        right_box.setLayout(right)
        right_box.setMaximumWidth(420)

        split = QSplitter()
        split.addWidget(self.host)
        split.addWidget(right_box)
        split.setStretchFactor(0, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(split, 1)
        self._preview_timer = QTimer(self)  # an edit's preview once the form has applied it
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(50)
        self._preview_timer.timeout.connect(self._load)
        self.refresh()

    # -- state --------------------------------------------------------------------------
    @property
    def family(self):
        """The AI records' list and form (Game Data's own), or None with no project open."""
        from .authoring_hub_widget import AdapterFamilyWidget

        child = self.host.child
        return child if isinstance(child, AdapterFamilyWidget) else None

    @property
    def ai_id(self):
        return self.family.selected_id if self.family is not None else None

    def _names(self):
        from .record_form import _title_names
        from .record_vocabulary import vocabulary_for

        return _title_names(vocabulary_for(self.api.document))

    def _rule_words(self, ai, rule_id):
        """A rule as its card shows it: "1. Iron Stance"."""
        from .record_form import _entry_name

        names = self._names()
        for number, rule in enumerate(ai.rules, 1):
            if rule.rule_id == rule_id:
                return f"{number}. {_entry_name(rule.to_data(), 'rule', names)}"
        return rule_id

    def refresh(self, select=None):
        select = select or self.ai_id  # the rebuilt list keeps the record being edited
        self.host.rebuild()  # a project opened (or another one): its records
        family = self.family
        if family is None:
            return
        if self._wired is not family:  # a new list and form: heard from once
            self._wired = family
            family.category.hide()  # one kind of record here
            family.browser.currentRowChanged.connect(lambda _row: self._load())
        if select:
            family.refresh(keep=[select])
            family.select_ids([select])
        names = self._names()
        self.enemy.clear()
        for enemy_id in sorted(self.api.database.enemies):
            self.enemy.addItem(names.get(enemy_id, enemy_id), enemy_id)
        self._load()

    def select_ai(self, ai_id):
        self.refresh(select=ai_id)
        return self.ai_id == ai_id

    def _edited(self):
        self._preview_timer.start()
        self.changed.emit()

    def _load(self):
        ai_id = self.ai_id
        if ai_id is None or ai_id not in self.api.ai_ids():
            self.used_by.setText("")
            self.decision.clear()
            return
        names = self._names()
        used = [names.get(e, e) for e in self.api.bound_enemies(ai_id)]
        self.used_by.setText(", ".join(used) if used else translate("No enemy uses this AI yet"))
        self._build_resource_inputs()
        self.problem_list.clear()
        problems = self.api.problems(ai_id)
        self.problem_list.addItems(problems or [translate("No problems")])
        self.run_preview()

    def _try(self, action, message):
        try:
            result = action()
        except (EnemyAIEditorError, KeyError, TypeError, ValueError) as exc:
            self.last_error = str(exc)
            self.status.setStyleSheet("color: #d66;")
            self.status.setText(str(exc))
            return False
        self.last_error = None
        self.status.setStyleSheet("")
        self.status.setText(message)
        self.refresh()
        self.changed.emit()
        return result if result is not None else True

    def bind_enemy(self, enemy_id):
        ai_id = self.ai_id
        names = self._names()

        def bind():
            with self.api.document.group(f"Use {ai_id} for {enemy_id}"):  # one undo step
                if self.api.database.enemy_behavior_bindings.get(enemy_id) is not None:
                    self.api.unbind(enemy_id)
                return self.api.bind(enemy_id, ai_id)

        return self._try(bind, f"{names.get(enemy_id, enemy_id)} now uses this AI")

    def create_ai(self, ai_id):
        result = self._try(lambda: self.api.create(ai_id), f"Created {ai_id}")
        if result:
            self.refresh(select=ai_id)
        return result

    def delete_ai(self):
        ai_id = self.ai_id
        return bool(ai_id) and self._try(lambda: self.api.delete(ai_id), f"Deleted {ai_id}")

    # -- preview --------------------------------------------------------------------------
    def _build_resource_inputs(self):
        while self.resource_form.rowCount():
            self.resource_form.removeRow(0)
        self.resource_inputs = {}
        names = self._names()
        for rid in self.api.resources(self.ai_id):
            maximum = self.api.resource_maximum(self.ai_id, rid)
            spin = QDoubleSpinBox()
            spin.setRange(0.0, maximum)
            spin.setDecimals(0 if maximum >= 20 else 2)
            spin.setValue(maximum if rid == "vitality" else 0.0)
            spin.setSuffix(f" / {maximum:g}")
            spin.valueChanged.connect(lambda _v: self.run_preview())
            self.resource_inputs[rid] = (spin, maximum)
            self.resource_form.addRow(names.get(rid, rid), spin)
            spin.ensurePolished()  # measured once parented: the inherited font included
            spin.setMinimumHeight(spin.sizeHint().height())

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
        """What the AI would do at the moment set above: its phase, then each rule it could
        pick with its chance, all in words; and where its phases start as HP falls."""
        from .record_vocabulary import words

        self.decision.clear()
        if self.ai_id is None:
            return None
        scenario = self.scenario()
        try:
            ai = self.api.get(self.ai_id)
            result = self.api.preview(self.ai_id, scenario)
            vitality = (
                "vitality"
                if "vitality" in self.resource_inputs
                else next(iter(self.resource_inputs), "vitality")
            )
            curve = (
                self.api.phase_by_ratio(self.ai_id, vitality, steps=100, scenario=scenario)
                if ai.phases
                else []
            )
        except EnemyAIEditorError as exc:
            self.phase_label.setText(str(exc))
            self.curve.setText("")
            return None
        phase = words(result.phase_id) if result.phase_id else "—"
        self.phase_label.setText(f"{translate('Phase')}: {phase}")
        for rule_id, chance in result.chances:
            self.decision.addItem(f"{self._rule_words(ai, rule_id)}  {chance * 100:.0f}%")
        if not result.chances:
            self.decision.addItem(translate("No rule can be picked: the enemy skips its turn"))
        segments = []
        for ratio, phase_id in curve:
            if not segments or segments[-1][1] != phase_id:
                segments.append((ratio, phase_id))
        self.curve.setText(
            "  →  ".join(f"{words(p)} ≤{ratio * 100:.0f}%" for ratio, p in segments)
        )
        self.curve.setAlignment(Qt.AlignLeft)
        return result


class _AIRecords:
    """Game Data's adapters, only the Enemy AI one (a FamilyHostWidget builder)."""

    def __init__(self, document):
        self.document = document

    @property
    def project(self):
        return self.document.project

    def categories(self):
        from .integrated_authoring import IntegratedAuthoringControllers

        adapters = IntegratedAuthoringControllers(self.document).rpg_categories()
        return [a for a in adapters if a.category_id == "ai"]
