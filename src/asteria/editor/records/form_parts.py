"""The parts of a record page: foldable sections whose cells flow to the width they get, nested
parts laid out like a section, and lists of entries (cards, or a table when each entry is a
few plain values)."""

from __future__ import annotations

import re
import weakref
from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from asteria.editor.records.form_chips import ChipList
from asteria.editor.records.form_controls import (
    LABEL_GAP,
    ColorButton,
    NumberBox,
    Picker,
    WrappedWords,
    help_tip,
    hint_label,
)
from asteria.editor.records.form_shapes import (
    FORMAT_KEYS,
    LIST_TEMPLATES,
    ai_condition_defaults,
    ai_condition_words,
    ai_context,
    engine_template,
    entry_name,
    entry_noun,
    entry_title,
    field_help,
    fresh_ids,
    is_ai_condition,
    is_ai_rule,
    is_boss_phase,
    is_empty_optional,
    is_scalar_list,
    node_pair,
    own_id,
    table_columns,
    title_names,
)
from asteria.editor.records.form_tables import AmountTable, NumberMatrix, TextTable
from asteria.editor.records.vocabulary import (
    AI_ACTION_HELP,
    AI_ACTIONS,
    AI_COMPARISONS,
    AI_CONDITIONS,
    PHASE_PRIORITY_HELP,
    PHASE_RULES_HELP,
    PHASE_START_HELP,
    TECHNICAL,
    Choice,
    label_for,
    resource_order,
    words,
)
from asteria.editor.ui.fit import layout_widgets
from asteria.editor.ui.i18n import translate
from asteria.editor.ui.icons import icon
from asteria.editor.ui.responsive_form import columns_that_fit
from asteria.rpg.enemies.ai import CONDITION_PARAMS


class _SectionBody(QWidget):
    """A section's fields. Fields in columns re-flow to fewer columns when the width runs out,
    so the narrowest the section needs is one column, not all of them side by side."""

    def __init__(self, section):
        super().__init__()
        # a weak reference: the section holds this body, and a cycle between a widget and the
        # widget it sits in can crash the cycle collector (tests/test_widget_cycles.py)
        self._section = weakref.ref(section)

    def minimumSizeHint(self):  # noqa: N802 - Qt API
        size = super().minimumSizeHint()
        section = self._section()
        if section is not None and section.flow_cells:
            margins = section.form.contentsMargins()
            needed = max(_flow_cell_width(cell) for cell in section.flow_cells)
            size.setWidth(needed + margins.left() + margins.right())
        return size

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        section = self._section()
        if section is not None and event.size().width() != event.oldSize().width():
            section.reflow()


def _flow_cell_width(cell):
    """How wide one field of a section's columns must be: its own minimum, and its label's."""
    title, field, _wide = cell
    width = field.minimumSizeHint().width()
    return width if title is None else max(width, title.minimumSizeHint().width())


class Section(QFrame):
    """A titled card holding fields; ``collapsed`` starts it folded (Advanced)."""

    def __init__(self, title, *, icon=None, collapsed=False, hint="", compact=False, columns=0):
        super().__init__()
        self.setObjectName("FormSection")
        self.compact = compact  # labels above their fields (nested parts: narrow)
        self._pair_row = None  # a row holding one number, waiting for a second
        # ``columns``: small fields (pickers, numbers, switches) sit side by side, this many to
        # a row; lists and long text take a whole row (cards of a list)
        self.columns = columns
        self.shown_columns = columns  # fewer when the width runs out (see reflow)
        # (label or None, field, "" | "field" whole row under a label | "whole" row), in order
        self.flow_cells = []
        self._cell = (0, 0)
        self.keeps_empty = False  # empty optional fields show here (no "show more" link)
        self.toggle = QToolButton()
        self.toggle.setObjectName("FormSectionTitle")
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(not collapsed)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.DownArrow if not collapsed else Qt.RightArrow)
        self.body = _SectionBody(self)
        self.form = QGridLayout(self.body)
        self.form.setContentsMargins(4, 2, 4, 4)
        self.form.setHorizontalSpacing(12)
        self.form.setVerticalSpacing(6)
        self.form.setColumnStretch(1, 1)
        if compact:
            self.form.setColumnStretch(0, 1)  # paired numbers get half each
        for column in range(columns):
            self.form.setColumnStretch(column, 1)
        if columns:
            self.form.setHorizontalSpacing(16)
            self.form.setVerticalSpacing(LABEL_GAP)  # a label to its field; rows: see below
        self.body.setVisible(not collapsed)
        self.toggle.toggled.connect(self._toggled)
        self.labels = []  # every field's name, shown or waiting
        self._more = []  # (label, widget, help) of empty fields, shown on request
        self.more_button = QToolButton()
        self.more_button.setObjectName("FormMoreButton")
        self.more_button.hide()
        self.more_button.clicked.connect(self.show_more)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(4)
        head = QHBoxLayout()
        head.addWidget(self.toggle)
        if hint:  # the section's help on hover, like a field's
            mark = QLabel("ⓘ")
            mark.setObjectName("FormSectionHelp")
            mark.setToolTip(hint)
            mark.setStyleSheet("color: #8b8e98;")
            head.addWidget(help_tip(mark))
        head.addStretch(1)
        layout.addLayout(head)
        layout.addWidget(self.body)
        layout.addWidget(self.more_button, 0, Qt.AlignLeft)

    def add_empty(self, label, widget, *, help_text=""):
        """An empty optional field: listed under "Show N more fields" until asked for."""
        self.labels.append(label)
        self._more.append((label, widget, help_text))
        widget.hide()
        widget.setParent(self)
        self.more_button.setText("＋ Empty fields")
        self.more_button.show()

    def show_more(self):
        for label, widget, help_text in self._more:
            widget.show()
            self.add_row(label, widget, help_text=help_text)
        self._more = []
        self.more_button.hide()

    def has_rows(self):
        return self.form.count() > 0 or bool(self._more)

    def _toggled(self, open_):
        self.body.setVisible(open_)
        self.toggle.setArrowType(Qt.DownArrow if open_ else Qt.RightArrow)

    def add_row(self, label, widget, *, help_text=""):
        self.labels.append(label)
        row = self.form.rowCount()
        title = QLabel(label + ("  ⓘ" if help_text else ""))
        title.setObjectName("FormFieldLabel")
        title.setToolTip(help_text)  # on the label's left: not over the field
        help_tip(title)
        holder = QVBoxLayout()
        if self.columns:
            self._grid_place(title, label, widget, holder)
        elif self.compact:
            holder.addWidget(title)
            small = isinstance(widget, NumberBox) and not help_text
            if small and self._pair_row is not None:  # two numbers share a row (X  Y)
                self.form.addLayout(holder, self._pair_row, 1)
                self._pair_row = None
            elif small:
                self.form.addLayout(holder, row, 0)
                self._pair_row = row
            else:
                self.form.addLayout(holder, row, 0, 1, 2)
                self._pair_row = None
        else:
            # the label stands level with the field's first line (a box, a row of chips)
            title.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            title.setFixedHeight(first_line_height(widget))
            title.setMinimumWidth(140)
            if isinstance(widget, QCheckBox):  # a switch reads as one line: "[x] Shown in HUD"
                widget.setText(label)
                title.setText("")
            self.form.addWidget(title, row, 0, Qt.AlignTop)
            self.form.addLayout(holder, row, 1)
        holder.setSpacing(LABEL_GAP)
        if isinstance(widget, (NumberBox, QCheckBox, ColorButton)):
            line = QHBoxLayout()  # a small control stays small
            line.addWidget(widget)
            line.addStretch(1)
            holder.addLayout(line)
        else:
            holder.addWidget(widget)

    def _grid_place(self, title, label, widget, holder):
        """Label above the field; a small field takes the next free column, a wide one (a list,
        long text) a row of its own. A switch carries its label beside its box.

        Each row of fields is two grid rows (D91): the labels', each label standing on the
        bottom of its cell, then the fields', each at the top of its own. A label that wraps to
        two lines or a tall field beside it no longer pushes its neighbours' boxes down."""
        wide = "field" if _is_wide(widget) else ""
        if not wide and isinstance(widget, Picker):  # its column still shows its longest choice
            widget.setMinimumWidth(max(widget.minimumWidth(), widget.choice_width(220)))
        holder.setContentsMargins(0, 0, 0, 8)  # room below a row of fields, before the next
        field = QWidget()  # a widget, not a layout: a re-flow can place it again
        field.setLayout(holder)
        if isinstance(widget, QCheckBox) and label:
            widget.setText(label)
            title = None
            # the unused label has no parent: Python frees it (a deleteLater as well would
            # free it twice and crash later)
        self._add_flow_cell((title, field, wide))

    def _add_flow_cell(self, cell):
        self.flow_cells.append(cell)
        self._place_flow_cell(cell)
        if self.body.width() > 0 and self.body.testAttribute(Qt.WA_Resized):
            self.reflow()  # added after the section got its width (＋ Empty fields)

    def _place_flow_cell(self, cell):
        title, field, wide = cell
        row, column = self._cell
        if wide:
            if column:
                row, column = row + 1, 0
            self._cell = (row + 1, 0)
            if wide == "whole":  # add_wide: no label line above it
                self.form.addWidget(field, 2 * row, 0, 2, self.shown_columns)
                return
            span = self.shown_columns
        else:
            span = 1
            last = column + 1 >= self.shown_columns
            self._cell = (row + 1, 0) if last else (row, column + 1)
        self.form.addWidget(field, 2 * row + 1, column, 1, span, Qt.AlignTop)
        if title is not None:
            self.form.addWidget(title, 2 * row, column, 1, span, Qt.AlignBottom | Qt.AlignLeft)

    def reflow(self):
        """As many of the section's columns as this width holds: fields wrap to the next line
        when side by side they would stick out of the window."""
        if not self.flow_cells:
            return
        margins = self.form.contentsMargins()
        room = self.body.width() - margins.left() - margins.right()
        widths = [None if c[2] else _flow_cell_width(c) for c in self.flow_cells]
        columns = columns_that_fit(
            widths, room, spacing=self.form.horizontalSpacing(), most=self.columns
        )
        if columns == self.shown_columns:
            return
        self.shown_columns = columns
        while self.form.count():
            self.form.takeAt(0)
        for column in range(self.columns):
            self.form.setColumnStretch(column, 1 if column < columns else 0)
        self._cell = (0, 0)
        for cell in self.flow_cells:
            self._place_flow_cell(cell)

    def add_wide(self, widget):
        if self.columns:
            self._add_flow_cell((None, widget, "whole"))
            return
        self.form.addWidget(widget, self.form.rowCount(), 0, 1, 2)


class SubForm(QWidget):
    """The fields of a nested part, laid out like a section's body."""

    def __init__(self, form, data, key):
        super().__init__()
        self.section = Section(label_for(key), compact=True, columns=3)
        self.section.toggle.hide()
        self.section.setObjectName("FormSubSection")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.section)

        # HP above MP (the saved order is alphabetical: technique before vitality)
        for k, v in sorted(data.items(), key=lambda kv: resource_order(kv[0])):
            if k in FORMAT_KEYS or k in TECHNICAL:  # an effect's effect_id: made, not shown
                continue
            if isinstance(v, list) and not is_scalar_list(k, v):
                self.section.add_row(label_for(k), entry_list(form, data, k, v))
            else:
                form._field(self.section, data, k, v)


QWIDGETSIZE_MAX = 16777215  # Qt's "no maximum width"


FOLD_AFTER = 8  # a list with more entries than this opens one entry at a time


class CardList(QWidget):
    """A list of entries as cards; each card holds the entry's fields."""

    def __init__(self, form, parent, key, entries):
        super().__init__()
        self.form, self.parent_data, self.key = form, parent, key
        self.entries = entries
        self.names = title_names(form.vocabulary)  # card titles show names, not ids
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        noun = entry_noun(key)
        # a long list (a skill tree's nodes) shows each entry as its title line; its fields
        # are built when it is opened - building every card at once took many seconds
        self.folded = len(entries) > FOLD_AFTER
        if not entries:
            layout.addWidget(hint_label(f"No {label_for(key).lower()} yet."))
        elif self.folded:
            layout.addWidget(hint_label("Click ▸ to open one."))
        for index, entry in enumerate(entries):
            layout.addWidget(self._card(index, entry, noun))
        add = QPushButton(f"+ Add {noun}")
        add.setObjectName("FormAddButton")
        add.clicked.connect(self.add)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addStretch(1)
        layout.addLayout(row)

    def _card(self, index, entry, noun):
        card = QFrame()
        card.setObjectName("FormCard")
        body = QVBoxLayout(card)
        body.setContentsMargins(8, 6, 8, 6)
        head = QHBoxLayout()
        foldable = self.folded and isinstance(entry, dict)
        opened = self._opened()
        is_open = not foldable or (id(self.entries), index) in opened
        if foldable:
            arrow = QToolButton()
            arrow.setText("▾" if is_open else "▸")
            arrow.setToolTip("Show or hide this entry's fields")
            arrow.setObjectName("FormCardMore")
            head.addWidget(arrow)
        title = WrappedWords(f"<b>{index + 1}.</b>  {entry_title(entry, noun, self.names)}")
        context = ai_context(self.form._data, entry, self.names)
        if context:  # which phases use the rule / when the phase starts, quieter
            title.setText(f"{title.text()}  <span style='color:#8b8e98'>{context}</span>")
        head.addWidget(title, 1)
        for text, tip, handler in (
            ("↑", "Move up", lambda: self.move(index, -1)),
            ("↓", "Move down", lambda: self.move(index, 1)),
            ("⧉", "Duplicate", lambda: self.duplicate(index)),
            ("✕", "Remove", lambda: self.remove(index)),
        ):
            button = QToolButton()
            button.setText(text)
            button.setToolTip(tip)
            button.clicked.connect(handler)
            head.addWidget(button)
        body.addLayout(head)
        if foldable:
            holder = QWidget()
            holder_layout = QVBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            body.addWidget(holder)

            def toggle(_checked=False, holder=holder, arrow=arrow):
                key = (id(self.entries), index)
                if key in opened:
                    opened.discard(key)
                    holder.hide()
                    arrow.setText("▸")
                    return
                opened.add(key)
                if not holder_layout.count():
                    self._fill_card(holder_layout, index, entry)
                holder.show()
                arrow.setText("▾")

            arrow.clicked.connect(toggle)
            if is_open:
                self._fill_card(holder_layout, index, entry)
            else:
                holder.hide()
            return card
        self._fill_card(body, index, entry)
        return card

    def _opened(self):
        """Which folded entries are open, kept by the form across its rebuilds."""
        return self.form.__dict__.setdefault("_open_cards", set())

    def _fill_card(self, body, index, entry):
        if isinstance(entry, dict):
            plain = "QFrame#FormSection { border: none; background: transparent; }"
            section = Section("", compact=True, columns=3)
            section.toggle.hide()
            section.setStyleSheet(plain)
            section.layout().setContentsMargins(0, 0, 0, 0)
            # empty and technical fields wait behind one small "More" fold
            extra = Section("More", collapsed=True, compact=True, columns=3)
            extra.keeps_empty = True
            extra.setStyleSheet(plain)
            extra.toggle.setObjectName("FormCardMore")
            extra.layout().setContentsMargins(0, 0, 0, 0)
            if is_ai_condition(entry):  # when an AI rule applies: one line of picks
                self._ai_condition(section, index, entry)
                body.addWidget(section)
                return
            if is_boss_phase(entry):  # a boss phase: its name, when it starts, its rules
                self._boss_phase(section, extra, index, entry)
                body.addWidget(section)
                if extra.form.count():
                    body.addWidget(extra)
                return
            rule = is_ai_rule(entry)
            if rule:  # an enemy AI rule: its action picked, its id made from it (folded)
                self._ai_action(section, extra, index, entry)
            for key, value in entry.items():
                if key in FORMAT_KEYS or (rule and key in ("action_kind", "payload")):
                    continue
                folded = (
                    key in TECHNICAL
                    or is_empty_optional(value)
                    or (rule and key == "rule_id")
                    or own_id(self.key, key)  # a node's node_id: made for it, folded
                )
                target = extra if folded else section
                if isinstance(value, list) and not is_scalar_list(key, value):
                    target.add_row(label_for(key), entry_list(self.form, entry, key, value))
                else:
                    self.form._field(target, entry, key, value)
            body.addWidget(section)
            if extra.form.count():
                body.addWidget(extra)
        elif node_pair(self.key, entry):  # [node, rank]: the node by name, then the rank
            body.addWidget(self._node_needed(index, entry))
        else:
            body.addWidget(self.form.widget_for(self.entries, index, entry))

    def _node_needed(self, index, entry):
        """A node another needs, picked by name from the record's nodes, and its rank."""

        nodes = [n for n in (self.form._data or {}).get("nodes") or () if isinstance(n, dict)]
        choices = [
            Choice(str(n["node_id"]), str(n.get("display_name") or words(str(n["node_id"]))))
            for n in nodes
            if n.get("node_id")
        ]
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        node = Picker(choices, str(entry[0]), allow_none=False)
        node.setEditable(False)
        rank = NumberBox(entry[1], integer=True)
        rank.setPrefix(translate("Rank") + " ")

        def changed():
            self.entries[index] = [node.value() or str(entry[0]), int(rank.number())]
            self.form.changed.emit()

        node.picked.connect(changed)
        rank.valueChanged.connect(lambda _v: changed())
        line.addWidget(node, 1)
        line.addWidget(rank)
        return row

    def _ai_action(self, section, extra, index, entry):
        """What an AI rule does, picked: Skill or Custom Code, then which skill (or hook)."""

        payload = entry["payload"]
        kinds = dict(AI_ACTIONS)
        kinds.setdefault(entry["action_kind"], label_for(entry["action_kind"]))
        kind = Picker([Choice(k, w) for k, w in kinds.items()], entry["action_kind"])
        kind.setEditable(False)
        kind.picked.connect(lambda: self._ai_kind(index, kind.value()))
        section.add_row(translate("Action"), kind, help_text=translate(AI_ACTION_HELP))
        if entry["action_kind"] == "ability":
            skills = self.form.vocabulary.choices("abilities")
            pick = Picker(skills, payload.get("ability_id", ""), icons=self.form.icon)
            pick.picked.connect(lambda: self._ai_target(index, "ability_id", pick.value()))
            section.add_row(translate("Skill"), pick)
        elif entry["action_kind"] == "hook":
            hook = QLineEdit(str(payload.get("hook", "")))
            hook.editingFinished.connect(lambda: self._ai_target(index, "hook", hook.text()))
            section.add_row(translate("Hook"), hook)
        for key, value in payload.items():  # anything else the rule passes on
            if key not in ("ability_id", "hook"):
                self.form._field(extra, payload, key, value)

    def _ai_condition(self, section, index, entry):
        """A condition as picks: what is checked (in words), which resource / stat / phase,
        how it compares, the amount, and Not."""

        params = entry["params"]
        kinds = dict(AI_CONDITIONS)
        kinds.setdefault(entry["kind"], label_for(entry["kind"]))
        kind = Picker([Choice(k, w) for k, w in kinds.items()], entry["kind"], allow_none=False)
        kind.setEditable(False)
        kind.picked.connect(lambda: self._ai_condition_kind(index, kind.value()))
        section.add_row(translate("Check"), kind)
        sources = {"resource_id": "resources", "stat_id": "stats"}
        for key in CONDITION_PARAMS.get(entry["kind"], ()):
            value = params.get(key)
            if key in sources:
                choices = self.form.vocabulary.choices(sources[key])
                pick = Picker(choices, str(value or ""), icons=self.form.icon)
                pick.picked.connect(lambda p=pick, k=key: self._ai_param(index, k, p.value()))
                section.add_row(translate(label_for(sources[key][:-1])), pick)
            elif key == "op":
                ops = [Choice(o, w) for o, w in AI_COMPARISONS.items()]
                pick = Picker(ops, str(value or "=="), allow_none=False)
                pick.setEditable(False)
                pick.picked.connect(lambda p=pick: self._ai_param(index, "op", p.value()))
                section.add_row(translate("Compare"), pick)
            elif key == "value" and entry["kind"] == "phase":
                phases = [
                    Choice(str(ph.get("phase_id")), words(str(ph.get("phase_id"))))
                    for ph in self.form._data.get("phases") or ()
                    if isinstance(ph, dict) and ph.get("phase_id")
                ]
                pick = Picker(phases, str(value or ""), allow_none=False)
                pick.picked.connect(lambda p=pick: self._ai_param(index, "value", p.value()))
                section.add_row(translate("Phase"), pick)
            elif key == "value":
                share = entry["kind"] == "resource_ratio"
                box = NumberBox(value, integer=entry["kind"] == "round_index", percent=share)
                box.valueChanged.connect(
                    lambda _v, b=box: self._ai_param(index, "value", b.number(), rebuild=False)
                )
                section.add_row(translate("Round" if entry["kind"] == "round_index" else
                                          "Amount"), box)  # fmt: skip
            else:  # a memory key: the project's own word
                text = QLineEdit(str(value or ""))
                text.editingFinished.connect(
                    lambda t=text, k=key: self._ai_param(index, k, t.text().strip())
                )
                section.add_row(translate(label_for(key)), text)
        negate = QCheckBox("Not")
        negate.setChecked(bool(entry.get("negate")))
        negate.setToolTip("Ticked: the rule applies when this is not so.")
        negate.toggled.connect(lambda on: self._ai_param(index, None, bool(on)))
        section.add_row("", negate)

    def _boss_phase(self, section, extra, index, entry):
        """A phase as plain choices: its name, Starts When (conditions), Priority, the
        rules it uses (picked by name), and the rest folded."""

        name = QLineEdit(words(str(entry["phase_id"])))
        name.setToolTip("Its name; rules and conditions follow a rename.")
        name.editingFinished.connect(lambda: self._phase_rename(index, name.text()))
        section.add_row(translate("Phase"), name)
        priority = NumberBox(entry.get("priority", 0), integer=True)
        priority.valueChanged.connect(
            lambda _v: (entry.__setitem__("priority", priority.number()), self.form.changed.emit())
        )
        section.add_row(translate("Priority"), priority, help_text=translate(PHASE_PRIORITY_HELP))
        conditions = entry.setdefault("conditions", [])
        section.add_row(
            translate("Starts When"),
            entry_list(self.form, entry, "conditions", conditions),
            help_text=translate(PHASE_START_HELP),
        )
        rules = [r for r in self.form._data.get("rules") or () if is_ai_rule(r)]
        names = self.names or {}
        choices = [
            Choice(r["rule_id"], f"{i}. {entry_name(r, 'rule', names)}")
            for i, r in enumerate(rules, 1)
        ]
        detail = {
            r["rule_id"]: "  ·  ".join(ai_condition_words(c, names) for c in r["conditions"])
            for r in rules
            if r.get("conditions")
        }
        used = ChipList(
            entry.get("decision_rule_ids") or [],
            choices,
            icons=self.form.icon,
            allow_new=False,
            noun="rule",
            detail=lambda v, d=detail: d.get(v, ""),
        )
        used.edited.connect(
            lambda: (entry.__setitem__("decision_rule_ids", list(used.values)),
                     self.form.changed.emit())
        )  # fmt: skip
        section.add_row(translate("Rules Used"), used, help_text=translate(PHASE_RULES_HELP))
        for key in ("actions_per_ready", "enter_hook", "exit_hook"):
            if key in entry:
                self.form._field(extra, entry, key, entry[key])

    def _phase_rename(self, index, text):
        """A phase's new name becomes its id everywhere it is named: the starting phase and
        every Phase condition of the record."""
        entry = self.entries[index]
        new = re.sub(r"\W+", "_", text.strip().lower()).strip("_")
        old = entry["phase_id"]
        taken = {p.get("phase_id") for i, p in enumerate(self.entries) if i != index}
        if not new or new == old or new in taken:
            self.form.restructure()  # the name shown again as it was
            return
        entry["phase_id"] = new
        data = self.form._data
        if data.get("initial_phase_id") == old:
            data["initial_phase_id"] = new
        for owner in [*(data.get("rules") or ()), *(data.get("phases") or ())]:
            for condition in owner.get("conditions") or () if isinstance(owner, dict) else ():
                if condition.get("kind") == "phase" and condition["params"].get("value") == old:
                    condition["params"]["value"] = new
        self.form.restructure()

    def _ai_condition_kind(self, index, kind):
        entry = self.entries[index]
        if not kind or kind == entry["kind"]:
            return
        entry["kind"] = kind
        entry["params"] = ai_condition_defaults(kind, self.form)
        self.form.restructure()

    def _ai_param(self, index, key, value, *, rebuild=True):
        entry = self.entries[index]
        if key is None:
            entry["negate"] = value
        else:
            entry["params"][key] = value
        if rebuild:
            self.form.restructure()  # the card's title says the condition in words
        else:
            self.form.changed.emit()

    def _ai_kind(self, index, kind):
        entry = self.entries[index]
        if not kind or kind == entry["action_kind"]:
            return
        entry["action_kind"] = kind
        payload = {k: v for k, v in entry["payload"].items() if k not in ("ability_id", "hook")}
        if kind == "ability":
            skills = self.form.vocabulary.choices("abilities")
            payload["ability_id"] = skills[0].value if skills else ""
        elif kind == "hook":
            payload["hook"] = ""
        entry["payload"] = payload
        self._ai_rename(index)
        self.form.restructure()

    def _ai_target(self, index, key, value):
        entry = self.entries[index]
        value = str(value or "").strip()
        if not value or entry["payload"].get(key) == value:
            return
        entry["payload"][key] = value
        self._ai_rename(index)
        self.form.restructure()

    def _ai_rename(self, index):
        """The rule's id follows what it does (``beast_maul``, ``beast_maul_2``); the record's
        phases that list the old id list the new one."""
        entry = self.entries[index]
        payload = entry["payload"]
        base = re.sub(r"\W+", "_", str(payload.get("ability_id") or payload.get("hook") or "rule"))
        used = {e.get("rule_id") for i, e in enumerate(self.entries) if i != index}
        new, n = base, 2
        while new in used:
            new, n = f"{base}_{n}", n + 1
        old = entry.get("rule_id")
        if new == old:
            return
        entry["rule_id"] = new
        for phase in self.form._data.get("phases") or ():
            ids = phase.get("decision_rule_ids") if isinstance(phase, dict) else None
            if isinstance(ids, list) and old in ids:
                phase["decision_rule_ids"] = [new if x == old else x for x in ids]

    def add(self):
        if self.entries:
            entry = deepcopy(self.entries[-1])
        else:
            entry = engine_template(self.key) or deepcopy(LIST_TEMPLATES.get(str(self.key)))
            if entry is None:
                return  # nothing known to start from (copy an entry from another record)
        self.entries.append(fresh_ids(entry, self.entries, self.form))
        self._opened().add((id(self.entries), len(self.entries) - 1))  # a new one opens
        self.form.restructure()

    def duplicate(self, index):
        entry = fresh_ids(deepcopy(self.entries[index]), self.entries, self.form)
        self.entries.insert(index + 1, entry)
        self._opened().add((id(self.entries), index + 1))
        self.form.restructure()

    def remove(self, index):
        del self.entries[index]
        self.form.restructure()

    def move(self, index, step):
        other = index + step
        if 0 <= other < len(self.entries):
            self.entries[index], self.entries[other] = self.entries[other], self.entries[index]
            self.form.restructure()


class ListCell(QToolButton):
    """A few tags in a table cell, in words; a click opens them to edit."""

    def __init__(self, form, entry, key):
        super().__init__()
        self.form, self.entry, self.key = form, entry, key
        self.setObjectName("FormListCell")
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setIcon(icon("tag"))  # a button to pick, not words in the row
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"Click to pick: {label_for(key)}")
        self.clicked.connect(self.edit)
        self._show()

    def _show(self):
        values = self.entry.get(self.key) or []
        labels = {**self.form.vocabulary.names()}
        labels.update({c.value: c.label for c in self.form.vocabulary_tags()})
        words = [translate(str(labels.get(str(v), v))) for v in values]
        self.setProperty("empty", not words)
        self.setText(", ".join(words) if words else translate("(none)"))

    def edit(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(label_for(self.key))
        column = QVBoxLayout(dialog)
        widget = self.form.widget_for(self.entry, self.key, self.entry.get(self.key) or [])
        column.addWidget(widget)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.accept)
        column.addWidget(buttons)
        dialog.resize(520, 300)
        dialog.exec()
        self._show()


def entry_list(form, parent, key, entries):
    """A list of entries: a table when each is a few plain values, else cards."""
    columns = table_columns(entries, key)
    if columns is not None:
        return EntryTable(form, parent, key, entries, columns)
    return CardList(form, parent, key, entries)


def _table_part_width(widget):
    """How wide a part of an entry table must be to show whole: a width it was given, else its
    own minimum (as a layout reads it)."""
    return widget.minimumWidth() or widget.minimumSizeHint().width()


class EntryTable(CardList):
    """Entries as the rows of a table (as RPG Maker's Traits and drops): a column per field,
    the edit buttons at the row's end; the fields an entry leaves empty open under its row
    (⋯). Too narrow for its columns, each entry stacks its fields instead (``reflow``)."""

    def __init__(self, form, parent, key, entries, columns):
        QWidget.__init__(self)
        self.form, self.parent_data, self.key = form, parent, key
        self.entries, self.columns = entries, columns
        self.names = title_names(form.vocabulary)
        self.setObjectName("FormEntryTable")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        frame = QFrame()
        frame.setObjectName("FormCard")
        self.grid = QGridLayout(frame)
        self.grid.setContentsMargins(8, 6, 8, 6)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(4)
        self.stacked = 0  # how many fields a line when too narrow for a table (0: a table)
        self._wants = {}  # each drop-down's width that shows its longest choice whole
        self._rows = []  # each entry's (number, cells, buttons, what opens under it)
        self._captions = None  # each entry's own field names, made the first time it stacks
        head = QLabel("#")
        head.setObjectName("FormTableHead")
        self._heads = [head]
        self._stretches = {len(columns) + 1: 1}  # the buttons keep to the right
        for column, field in enumerate(columns, start=1):
            self._heads.append(self._field_title(field))
            sample = next((e[field] for e in entries if field in e), "")
            small = isinstance(sample, (bool, int, float))
            self._stretches[column] = 0 if small else 2
        for index, entry in enumerate(entries):
            self._row(index, entry)
        self._place_table()
        layout.addWidget(frame)
        add = self._add = QPushButton(f"+ Add {entry_noun(key)}")
        add.setObjectName("FormAddButton")
        add.clicked.connect(self.add)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addStretch(1)
        layout.addLayout(row)

    def _field_title(self, field):
        about = field_help(self.entries[0], field)
        title = QLabel(label_for(field) + ("  ⓘ" if about else ""))
        title.setObjectName("FormTableHead")
        if about:
            title.setToolTip(about)
            help_tip(title)
        return title

    PICKER_LEAST = 140  # one field a line, a drop-down may show only how its words begin

    def minimumSizeHint(self):  # noqa: N802 - Qt API
        """One field a line is the narrowest this table goes (see reflow)."""
        size = super().minimumSizeHint()
        margins = self.grid.contentsMargins()
        frame = self.grid.parentWidget()  # its border is room too
        border = frame.width() - frame.contentsRect().width()
        parts = [*self._heads]
        for _number, cells, buttons, opens in self._rows:
            parts.extend((*cells, buttons))
            if opens is not None and not opens.isHidden():
                parts.append(opens)
        widest = max(self._least(part) for part in parts)
        needed = widest + margins.left() + margins.right() + border
        size.setWidth(max(needed, _table_part_width(self._add)))
        return size

    def _least(self, part):
        want = self._wants.get(part)
        return _table_part_width(part) if want is None else min(want, self.PICKER_LEAST)

    def _want(self, part):
        want = self._wants.get(part)
        return _table_part_width(part) if want is None else want

    def _fit_pickers(self, room):
        """Each drop-down shows its longest choice, unless one field a line is still too
        narrow for it: then it takes the room there is (``PICKER_LEAST`` at the least)."""
        for picker, want in self._wants.items():
            least = want if self.stacked != 1 else max(self.PICKER_LEAST, min(want, room))
            if picker.minimumWidth() != least:
                picker.setMinimumWidth(least)

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self.reflow()

    def reflow(self):
        """A table while its columns fit; narrower, each entry lays its fields out below its
        number, as many a line as fit, each under its own name."""
        margins = self.grid.contentsMargins()
        frame = self.grid.parentWidget()
        border = frame.width() - frame.contentsRect().width()
        room = self.width() - margins.left() - margins.right() - border
        spacing = self.grid.horizontalSpacing()
        count = len(self.columns)
        wanted = [_table_part_width(head) for head in self._heads]
        wanted.append(0)  # the buttons
        for number, cells, buttons, _opens in self._rows:
            wanted[0] = max(wanted[0], _table_part_width(number))
            for column, cell in enumerate(cells, start=1):
                wanted[column] = max(wanted[column], self._want(cell))
            wanted[-1] = max(wanted[-1], _table_part_width(buttons))
        if sum(wanted) + spacing * (count + 1) <= room:
            stacked = 0
        else:
            titles = self._heads[1:]
            widths = []
            for _number, cells, _buttons, _opens in self._rows:
                widths.extend(
                    max(self._want(c), _table_part_width(t))
                    for c, t in zip(cells, titles, strict=True)
                )
                widths.append(None)
            stacked = columns_that_fit(widths, room, spacing=spacing, most=count)
        changed = stacked != self.stacked
        self.stacked = stacked
        self._fit_pickers(room)
        if changed:
            if stacked:
                self._place_stacked()
            else:
                self._place_table()

    def _clear_grid(self):
        while self.grid.count():
            self.grid.takeAt(0)
        for column in range(len(self.columns) + 2):
            self.grid.setColumnStretch(column, 0)

    def _place_table(self):
        self._clear_grid()
        for column, stretch in self._stretches.items():
            self.grid.setColumnStretch(column, stretch)
        for column, head in enumerate(self._heads):
            head.show()
            self.grid.addWidget(head, 0, column)
        for captions in self._captions or ():
            for caption in captions:
                caption.hide()
        for index, (number, cells, buttons, opens) in enumerate(self._rows):
            line = 1 + 2 * index
            self.grid.addWidget(number, line, 0)
            for column, cell in enumerate(cells, start=1):
                self.grid.addWidget(cell, line, column, Qt.AlignVCenter)
            self.grid.addWidget(buttons, line, len(self.columns) + 1)
            if opens is not None:
                self.grid.addWidget(opens, line + 1, 0, 1, len(self.columns) + 2)

    def _place_stacked(self):
        self._clear_grid()
        for head in self._heads:
            head.hide()
        if self._captions is None:
            self._captions = [[self._field_title(f) for f in self.columns] for _r in self._rows]
        fields = self.stacked
        for column in range(fields):
            self.grid.setColumnStretch(column, 1)
        line = 0
        for index, (number, cells, buttons, opens) in enumerate(self._rows):
            self.grid.addWidget(number, line, 0, Qt.AlignLeft | Qt.AlignVCenter)
            self.grid.addWidget(buttons, line, 0, 1, fields, Qt.AlignRight)
            line += 1
            for at, (cell, caption) in enumerate(zip(cells, self._captions[index], strict=True)):
                row = line + 2 * (at // fields)
                caption.show()
                self.grid.addWidget(caption, row, at % fields, Qt.AlignBottom)
                # a field that stays small (a number) keeps left: in a grid it would cap the
                # width of its whole column, and every column would float apart
                grows = cell.sizePolicy().horizontalPolicy().value & QSizePolicy.GrowFlag.value
                small = cell.maximumWidth() < QWIDGETSIZE_MAX or not grows
                align = Qt.AlignTop | Qt.AlignLeft if small else Qt.AlignTop
                self.grid.addWidget(cell, row + 1, at % fields, align)
            line += 2 * -(-len(cells) // fields)
            if opens is not None:
                self.grid.addWidget(opens, line, 0, 1, fields)
                line += 1

    def _row(self, index, entry):
        number = QLabel(f"<b>{index + 1}</b>")
        number.setToolTip(entry_title(entry, entry_noun(self.key), self.names))
        cells = []
        for field in self.columns:
            if isinstance(entry.get(field), list):
                widget = ListCell(self.form, entry, field)
            elif field in entry:
                widget = self.form.widget_for(entry, field, entry[field])
            else:
                widget = None
            if widget is None:
                widget = hint_label("—")
            elif isinstance(widget, QCheckBox):
                widget.setText("")
            elif isinstance(widget, Picker):  # its column still shows its longest choice
                want = max(widget.minimumWidth(), widget.choice_width(220))
                widget.setMinimumWidth(want)
                self._wants[widget] = want
            cells.append(widget)
        hidden = [k for k in entry if k not in FORMAT_KEYS and k not in self.columns]
        actions = QWidget()  # a widget, not a layout: a re-flow can place it again
        buttons = QHBoxLayout(actions)
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(2)
        buttons.addStretch(1)
        more = None
        if hidden:
            more = QToolButton()
            more.setText("⋯")
            more.setToolTip(
                translate("More settings: ") + ", ".join(translate(label_for(k)) for k in hidden)
            )
            buttons.addWidget(more)
        for text, tip, handler in (
            ("↑", "Move up", lambda: self.move(index, -1)),
            ("↓", "Move down", lambda: self.move(index, 1)),
            ("⧉", "Duplicate", lambda: self.duplicate(index)),
            ("✕", "Remove", lambda: self.remove(index)),
        ):
            button = QToolButton()
            button.setText(text)
            button.setToolTip(tip)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        if more is None:
            self._rows.append((number, cells, actions, None))
            return
        holder = QFrame()
        holder.setObjectName("FormRowMore")  # framed: it belongs to the row above
        holder_layout = QVBoxLayout(holder)
        holder_layout.setContentsMargins(12, 4, 0, 6)
        self._rows.append((number, cells, actions, holder))
        opened = self._opened()
        mark = ("row", id(self.entries), index)

        def toggle(_checked=False):
            if mark in opened:
                opened.discard(mark)
                holder.hide()
                return
            opened.add(mark)
            if not holder_layout.count():
                self._fill_extra(holder_layout, entry, hidden)
            holder.show()

        more.clicked.connect(toggle)
        if mark in opened:
            self._fill_extra(holder_layout, entry, hidden)
        else:
            holder.hide()

    def _fill_extra(self, body, entry, keys):
        section = Section("", compact=True, columns=3)
        section.toggle.hide()
        section.keeps_empty = True
        section.setStyleSheet("QFrame#FormSection { border: none; background: transparent; }")
        section.layout().setContentsMargins(0, 0, 0, 0)
        for key in keys:
            value = entry[key]
            if isinstance(value, list) and not is_scalar_list(key, value):
                section.add_row(label_for(key), entry_list(self.form, entry, key, value))
            else:
                self.form._field(section, entry, key, value)
        body.addWidget(section)


def first_line_height(widget):
    """The height of a field's first line: a box's own height, a chip row's, a hint's first
    line, else a box's."""
    if isinstance(widget, QLabel):
        widget.ensurePolished()  # its own small font, not the default one
        return widget.fontMetrics().height()
    if isinstance(widget, CardList) and widget.layout() is not None:
        layout = widget.layout()
        first = next((w for w in layout_widgets(layout) if layout.indexOf(w) == 0), None)
        if isinstance(first, QLabel):
            return first_line_height(first)  # "No entries yet." / "12 entries..."
    if isinstance(widget, ChipList):
        chip = widget.findChild(QToolButton)
        return max(22, chip.sizeHint().height() if chip is not None else 24)
    if isinstance(widget, (QLineEdit, QComboBox, QDoubleSpinBox, QCheckBox, QPushButton)):
        return max(22, widget.sizeHint().height())
    return QLineEdit().sizeHint().height()


def _is_wide(widget):
    """A field that needs a whole row: a list, a table, long text."""
    wide = (
        ChipList,
        AmountTable,
        NumberMatrix,
        TextTable,
        CardList,
        SubForm,
        QPlainTextEdit,
        Section,
    )
    return isinstance(widget, wide) or bool(widget.property("wide"))
