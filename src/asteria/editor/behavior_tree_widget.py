"""Behavior tree editor (RPG-09): tree list, node hierarchy, node kind and parameters, add / remove
/ move."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSplitter,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from asteria.rpg.behavior_tree import COMPOSITES, DECORATORS

from .authoring_sidebar import authoring_sidebar
from .behavior_tree_authoring import (
    ABSENT_AT_ZERO,
    KIND_GROUPS,
    PARAMS,
    REFERENCE_SOURCES,
    BehaviorTreeAuthoring,
    BehaviorTreeAuthoringError,
    parse_points,
)
from .behavior_tree_words import (
    AT_LEAST_ONE,
    FOREVER_AT_ZERO,
    KIND_HELP,
    KIND_NAMES,
    MAY_BE_NEGATIVE,
    PARAM_HELP,
    PIXELS,
    SECONDS,
    SETTING_CHOICES,
    SHARES,
    WHOLE_NUMBERS,
    ZERO_WORDS,
    describe,
    kind_name,
    param_label,
    setting_value,
)
from .event_name_dialog import name_picker
from .i18n import CURRENT, translate
from .record_form import NumberBox, Picker, _help_tip, _wheel_guard
from .record_vocabulary import vocabulary_for
from .record_vocabulary import words as _words
from .ui_fit import ValueCombo

_GROUP_LINE = "#46b896"  # a group's line in the kind lists: not one of the choices
_NODES_LEAST_WIDTH = 240  # the rows are sentences: the list never folds away
_NODES_HELP = (
    "A character runs this list from the top, over and over. Each node succeeds, fails or keeps "
    "going, and the group it is in decides what comes next."
)


def _fill_kinds(combo):
    """Every kind of node by its name, under a line for each group (a line can't be picked)."""
    for label, kinds in KIND_GROUPS:
        combo.addItem(label, "")
        line = combo.model().item(combo.count() - 1)
        line.setEnabled(False)
        font = line.font()
        font.setBold(True)
        line.setFont(font)
        line.setForeground(QColor(_GROUP_LINE))
        for kind in kinds:
            combo.addItem(KIND_NAMES[kind], kind)
    combo.setCurrentIndex(1)


class PatrolPlaces(QWidget):
    """A patrol's places, a row each: the data's ``"x,y; x,y"`` is never shown."""

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.rows = []
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(4)
        self.add_button = QPushButton("Add Place")
        self.add_button.clicked.connect(lambda _checked=False: self.add_place())
        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        buttons.addWidget(self.add_button)
        self.layout_.addLayout(buttons)
        try:
            points = parse_points(text)
        except ValueError:  # hand-written data the game itself cannot read either
            points = []
        for x, y in points or [(0.0, 0.0)]:
            self.add_place(x, y)

    def add_place(self, x=None, y=None):
        """A new place stands one step past the last one, so it's a place of its own."""
        if x is None:
            x, y = self.places()[-1] if self.rows else (0.0, 0.0)
            x += 32.0
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(4)
        boxes = (NumberBox(x), NumberBox(y))
        for caption, box in zip("XY", boxes, strict=True):
            line.addWidget(QLabel(caption))
            line.addWidget(box)
        remove = QToolButton()
        remove.setText("✕")
        remove.clicked.connect(lambda _checked=False: self._remove(row))
        line.addWidget(remove)
        self.rows.append((row, boxes, remove))
        self.layout_.insertWidget(self.layout_.count() - 1, row)
        self._one_stays()

    def _remove(self, row):
        self.rows = [entry for entry in self.rows if entry[0] is not row]
        self.layout_.removeWidget(row)
        row.hide()
        row.deleteLater()
        self._one_stays()

    def _one_stays(self):
        """A patrol without a place does nothing: the last one has no ✕."""
        for _row, _boxes, remove in self.rows:
            remove.setEnabled(len(self.rows) > 1)

    def places(self):
        return [(boxes[0].number(), boxes[1].number()) for _row, boxes, _remove in self.rows]

    def text(self):
        return "; ".join(f"{x:g},{y:g}" for x, y in self.places())


class BehaviorTreeEditorWidget(QWidget):
    changed = Signal()

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.api = BehaviorTreeAuthoring(document)
        self.last_error = None
        self.tree_list = QListWidget()
        self.tree_list.currentTextChanged.connect(lambda _t: self._load())
        new_button, delete_button = QPushButton("New"), QPushButton("Delete")
        new_button.clicked.connect(self._new_clicked)
        delete_button.clicked.connect(self.delete_tree)
        self.record_buttons = (new_button, delete_button)
        left_box = authoring_sidebar("Behavior Trees", self.tree_list)
        left_box.setMinimumWidth(170)  # a tree's name is short, the rows beside it are sentences

        self.nodes = QTreeWidget()
        self.nodes.setObjectName("BehaviorTreeNodes")
        self.nodes.setHeaderLabels(["Node"])
        self.nodes.setHeaderHidden(True)
        self.nodes.setFrameShape(QFrame.NoFrame)
        self.nodes.itemSelectionChanged.connect(self._node_selected)
        center_box = QGroupBox()
        center_box.setObjectName("EnemyAISectionCard")
        center_box.setContentsMargins(0, 0, 0, 0)
        center = QVBoxLayout(center_box)
        center.setContentsMargins(10, 10, 10, 10)
        center.setSpacing(10)
        nodes_heading = QLabel("Node")
        nodes_heading.setObjectName("EnemyAISectionTitle")
        nodes_help = QLabel("ⓘ")
        nodes_help.setObjectName("FormSectionHelp")
        nodes_help.setToolTip(_NODES_HELP)
        nodes_head = QHBoxLayout()
        nodes_head.addWidget(nodes_heading)
        nodes_head.addWidget(_help_tip(nodes_help))
        nodes_head.addStretch(1)
        center.addLayout(nodes_head)
        center.addWidget(self.nodes, 1)

        self.kind = QComboBox()
        self.add_kind = QComboBox()
        for combo in (self.kind, self.add_kind):
            _wheel_guard(combo)
            _fill_kinds(combo)
            # the longest kind's name must not push the buttons beside it off the page
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(6)
        self.kind_help = QLabel("ⓘ")
        self.kind_help.setObjectName("FormSectionHelp")
        _help_tip(self.kind_help)
        self.form = QFormLayout()
        self.form.setRowWrapPolicy(QFormLayout.WrapLongRows)  # a patrol's places take the width
        self.fields = {}
        apply_kind, apply_params = QPushButton("Change Kind"), QPushButton("Apply Parameters")
        apply_kind.clicked.connect(self.apply_kind)
        apply_params.clicked.connect(self.apply_params)
        self.apply_params_button = apply_params
        add_child, remove, up, down = (
            QPushButton("Add Child"),
            QPushButton("Remove"),
            QPushButton("↑"),
            QPushButton("↓"),
        )
        self.add_child_button = add_child
        add_child.clicked.connect(lambda: self.add_child(self.add_kind.currentData()))
        remove.clicked.connect(self.remove_node)
        up.clicked.connect(lambda: self.move_node(-1))
        down.clicked.connect(lambda: self.move_node(1))
        node_box = QGroupBox()
        node_box.setObjectName("EnemyAISectionCard")
        node_box.setMinimumHeight(320)
        card_layout = QVBoxLayout(node_box)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(10)
        heading = QLabel("Selected Node")
        heading.setObjectName("EnemyAISectionTitle")
        card_layout.addWidget(heading)
        node_content = QWidget()
        nv = QVBoxLayout(node_content)
        nv.setContentsMargins(8, 8, 8, 8)
        nv.setSpacing(12)
        kind_row = QHBoxLayout()
        kind_row.addWidget(self.kind, 1)
        kind_row.addWidget(self.kind_help)
        kind_row.addWidget(apply_kind)
        nv.addLayout(kind_row)
        nv.addLayout(self.form)
        nv.addWidget(apply_params)
        order = QHBoxLayout()
        for b in (up, down, remove):
            order.addWidget(b)
        nv.addLayout(order)
        add_row = QHBoxLayout()
        add_row.addWidget(self.add_kind, 1)
        add_row.addWidget(add_child)
        nv.addLayout(add_row)
        nv.addStretch(1)
        node_scroll = QScrollArea()
        node_scroll.setWidgetResizable(True)
        node_scroll.setFrameShape(QFrame.NoFrame)
        node_scroll.setViewportMargins(0, 0, 8, 0)
        node_scroll.setWidget(node_content)
        card_layout.addWidget(node_scroll, 1)
        self.status = QLabel("")
        self._said_in = CURRENT["language"]
        self.status.setWordWrap(True)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.addWidget(node_box, 1)
        right.addWidget(self.status)
        right_box = QWidget()
        right_box.setProperty("sidePanel", True)  # Focus Mode folds it away
        right_box.setLayout(right)
        center_box.setMinimumWidth(_NODES_LEAST_WIDTH)
        split = QSplitter()
        for w in (left_box, center_box, right_box):
            split.addWidget(w)
        split.setStretchFactor(1, 1)
        split.setChildrenCollapsible(False)
        split.setSizes([170, 320, 310])  # any room beyond these goes to the rows
        from .record_actions import record_action_bar

        layout = QVBoxLayout(self)
        layout.addWidget(split, 1)
        layout.addLayout(record_action_bar(*self.record_buttons)[0])
        self.refresh()

    # -- state -----------------------------------------------------------------------------------
    @property
    def tree_id(self):
        from .ui_fit import named_id

        return named_id(self.tree_list.currentItem())

    @property
    def path(self):
        item = self.nodes.currentItem()
        return None if item is None else tuple(item.data(0, Qt.UserRole))

    def refresh(self, select=None):
        if self.api.document.project is None:
            return
        if self._said_in != CURRENT["language"]:  # the status line's words were another language's
            self.status.clear()
            self._said_in = CURRENT["language"]
        current = select or self.tree_id
        node_path = self.path if current == self.tree_id else None  # an edit keeps its node
        ids = self.api.ids()
        self.tree_list.blockSignals(True)
        from .ui_fit import fill_named

        fill_named(self.tree_list, ids, _words)
        self.tree_list.blockSignals(False)
        if ids:
            self.tree_list.setCurrentRow(ids.index(current) if current in ids else 0)
        self._load(node_path)

    def _names(self):
        """``names(setting, value)``: what a setting refers to by its name in the project; one
        that isn't there any more is marked."""
        vocabulary = vocabulary_for(self.api.document)
        found = {}

        def names(setting, value):
            source = REFERENCE_SOURCES.get(setting)
            if source is None:
                return _words(value)
            if source not in found:
                found[source] = {c.value: c.label for c in vocabulary.choices(source)}
            label = found[source].get(str(value))
            return label if label is not None else f"⚠ {_words(value)}"

        return names

    def _load(self, path=None):
        blocked = self.nodes.blockSignals(True)  # the old rows may name nodes no longer there
        self.nodes.clear()
        self.nodes.blockSignals(blocked)
        if self.tree_id is None or self.tree_id not in self.api.ids():
            self._node_selected()  # nothing is selected: the form empties
            return  # none picked, or the one picked was just deleted (the list refreshes next)
        tree = self.api.get(self.tree_id)
        items = {}
        names = self._names()
        for node_path, node in tree.root.walk():
            item = QTreeWidgetItem([describe(node, names)])  # drawn as given
            item.setData(0, Qt.UserRole, list(node_path))
            if node_path:
                items[node_path[:-1]].addChild(item)
            else:
                self.nodes.addTopLevelItem(item)
            items[node_path] = item
        self.nodes.expandAll()
        self._keep_rows_whole()
        target = items.get(tuple(path) if path is not None else ()) or items[()]
        self.nodes.setCurrentItem(target)
        self._node_selected()

    def _keep_rows_whole(self):
        """A row wider than the list scrolls sideways: its sentence is never cut off."""
        self.nodes.header().setMinimumSectionSize(self.nodes.sizeHintForColumn(0))

    def select_node(self, path):
        self._load(path)
        return self.path == tuple(path)

    def _node_selected(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        self.fields = {}
        if self.tree_id is None or self.path is None:
            return
        node = self.api.get(self.tree_id).node(self.path)
        self.kind.setCurrentIndex(self.kind.findData(node.kind))
        about = KIND_HELP.get(node.kind, "")
        self.kind_help.setToolTip(about)
        self.kind_help.setVisible(bool(about))
        self.add_child_button.setEnabled(node.kind in COMPOSITES + DECORATORS)
        for name, default in PARAMS.get(node.kind, ()):
            unset = 0 if (node.kind, name) in ABSENT_AT_ZERO else default
            field = self._field(node.kind, name, node.params.get(name, unset))
            self.fields[name] = field
            self.form.addRow(self._field_label(node.kind, name), field)
        self.apply_params_button.setVisible(bool(self.fields))

    def _field_label(self, kind, name):
        about = PARAM_HELP.get(name, "")
        label = QLabel()
        words = param_label(kind, name)
        label.setText(f"{translate(words)}  ⓘ" if about else words)
        if about:
            label.setToolTip(about)
            _help_tip(label)
        return label

    def _field(self, kind, name, value):
        """The setting's own kind of field, in words: a number, or a list to pick from."""
        if name == "points":
            return PatrolPlaces(value)
        if name == "name":
            return name_picker(self.api.document, "switch", str(value or ""))
        if name in REFERENCE_SOURCES:
            return Picker(self._choices(REFERENCE_SOURCES[name]), value, allow_other=False)
        if name in SETTING_CHOICES:
            combo = QComboBox()
            _wheel_guard(combo)
            for choice, words in SETTING_CHOICES[name]:
                combo.addItem(words, choice)
            combo.setCurrentIndex(combo.findData(setting_value(name, value)))
            return combo
        return self._number_field(kind, name, value)

    def _choices(self, source):
        """What ``source`` lists, by name; two with one name say their ids too, in words."""
        choices = vocabulary_for(self.api.document).choices(source)
        times = Counter(choice.label for choice in choices)
        return tuple(
            replace(c, label=f"{translate(c.label)} ({translate(_words(c.value))})")
            if times[c.label] > 1
            else c
            for c in choices
        )

    @staticmethod
    def _number_field(kind, name, value):
        box = NumberBox(value, integer=name in WHOLE_NUMBERS, percent=name in SHARES)
        if name not in MAY_BE_NEGATIVE:
            box.setMinimum(1.0 if (kind, name) in AT_LEAST_ONE else 0.0)
        if name in SHARES:
            box.setMaximum(100.0)
        if name in PIXELS:
            box.setSuffix(f" {translate('px')}")
        elif name in SECONDS:
            box.setSuffix(f" {translate('sec')}")
        if (kind, name) in FOREVER_AT_ZERO:
            box.setSpecialValueText("Forever")
        if (kind, name) in ZERO_WORDS:
            box.setSpecialValueText(ZERO_WORDS[kind, name])
        box.set_value(value)
        return box

    @staticmethod
    def _field_value(field):
        if isinstance(field, NumberBox):
            return field.number()
        if isinstance(field, Picker):
            return field.value()
        if isinstance(field, PatrolPlaces):
            return field.text()
        if isinstance(field, ValueCombo):
            return field.currentText()
        return field.currentData()

    def _say(self, template, **values):
        """A sentence for the status line, in the editor's language now."""
        return translate(template).format(**values)

    # -- edits -----------------------------------------------------------------------------------
    def _try(self, action, message, path=None):
        try:
            result = action()
        except (BehaviorTreeAuthoringError, ValueError, TypeError, KeyError) as exc:
            self.last_error = str(exc)
            self.status.setStyleSheet("color: #d9534f;")
            self.status.setText(str(exc))
            return None
        self.last_error = None
        self.status.setStyleSheet("")
        self.status.setText(message)
        self._load(path if path is not None else self.path)
        self.changed.emit()
        return result if result is not None else True

    def apply_params(self):
        values = {name: self._field_value(field) for name, field in self.fields.items()}
        path = self.path
        return self._try(
            lambda: self.api.set_params(self.tree_id, path, **values), "Parameters saved", path
        )

    def apply_kind(self):
        path, kind = self.path, self.kind.currentData()
        said = self._say("Changed to {name}", name=kind_name(kind))
        return self._try(lambda: self.api.set_kind(self.tree_id, path, kind), said, path)

    def add_child(self, kind):
        path = self.path
        said = self._say("Added {name}", name=kind_name(kind))
        return self._try(lambda: self.api.add_child(self.tree_id, path, kind), said, path)

    def remove_node(self):
        path = self.path
        if not path:
            self.status.setText("The root node cannot be removed")
            return None
        if len(self.api.get(self.tree_id).node(path[:-1]).children) == 1:
            self.status.setText("The node around it needs one inside: add another one first")
            return None
        return self._try(lambda: self.api.remove(self.tree_id, path), "Removed", path[:-1])

    def move_node(self, delta):
        path = self.path
        if not path:
            return None
        target = (*path[:-1], path[-1] + delta)
        return self._try(lambda: self.api.move(self.tree_id, path, delta), "Moved", target)

    def create_tree(self, tree_id, root_kind="selector"):
        said = self._say("Created {name}", name=translate(_words(tree_id)))
        result = self._try(lambda: self.api.create(tree_id, root_kind), said)
        if result:
            self.refresh(select=tree_id)
        return result

    def delete_tree(self):
        tree_id = self.tree_id
        said = tree_id and self._say("Deleted {name}", name=translate(_words(tree_id)))
        result = tree_id and self._try(lambda: self.api.delete(tree_id), said)
        if result:
            self.refresh()
        return result

    def _new_clicked(self):
        from .authoring_hub_widget import _free_id

        self.create_tree(_free_id("", self.api.ids(), "new_tree"))  # its id made for it
