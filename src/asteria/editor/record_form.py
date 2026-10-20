"""The record form: one friendly editor for every database, battle and presentation record.

It replaces the field / value tree. Each field gets the widget its data asks for - a check box,
a number box (chances as percentages), a drop-down of the records it refers to (with icons, so
nothing is typed by hand), tag chips with suggestions, a stat table whose stats come from a
list, cards for lists of entries (add, duplicate, move, remove) and sections for nested parts.
The name and icon head the form; internal ids and rarely used fields wait under *Advanced*.
Every field has its help on hover (and a short hint under it). Edits are reported through
``changed``; the host applies them (and shows a problem with ``set_error``).

The form only edits plain record data; each record type's own decoder still validates it.
"""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .record_vocabulary import (
    CATEGORY_HELP,
    HELP,
    NOT_REFERENCES,
    REFERENCES,
    TECHNICAL,
    TERM_KEY_SOURCES,
    is_chance_field,
    is_tag_field,
    is_trigger_field,
    label_for,
    map_source,
    tag_label,
    trigger_label,
    vocabulary_for,
    words,
)

FORMAT_KEYS = ("schema", "version")
NAME_KEYS = ("display_name", "name", "label", "title")
_SCALARS = (str, int, float, bool, type(None))
_LIST_TEMPLATES = {  # what a new entry of an empty list starts as
    "hits": {"tags": [], "power": 1.0, "checks": []},
    "apply_states": {"state": "", "to": "targets", "remove": False},
    "battle_resource_gains": {"to": "targets", "resource": "", "amount": 1.0},
    "commands": {"command": "", "args": {}},
    "modifiers": {
        "modifier_id": "",
        "stat": "",
        "operation": "add",
        "value": 0.0,
        "priority": 0,
        "required_tags": [],
        "blocked_tags": [],
    },
    "sockets": {"socket_id": "", "accepted_tags": ["gem"], "locked": False},
}
_ENUMS = {}  # hand-kept fixed sets; the engine's own checks are read (engine_enums)


def _engine_template(key):
    """A new entry for a list the engine defines (built by its own type, so it decodes)."""
    from asteria.gameplay import Effect, EffectOperation, PeriodicEffect, StatModifier

    def effect(name):
        operation = EffectOperation("resource_delta", "vitality", 0.0)
        return Effect(name, (operation,))

    builders = {
        "modifiers": lambda: StatModifier("modifier1", "power", "add", 0.0).to_data(),
        "on_apply": lambda: effect("on_apply1").to_data(),
        "on_remove": lambda: effect("on_remove1").to_data(),
        "on_expire": lambda: effect("on_expire1").to_data(),
        "periodic": lambda: PeriodicEffect(1, effect("tick1")).to_data(),
        "operations": lambda: EffectOperation("resource_delta", "vitality", 0.0).to_data(),
    }
    build = builders.get(str(key))
    return build() if build else None


RECORD_LISTS = set(_LIST_TEMPLATES) | {
    "modifiers", "on_apply", "on_remove", "on_expire", "periodic", "operations", "effects",
    "triggers", "forms", "nodes", "entries", "impacts", "thresholds", "steps", "rules",
}  # fmt: skip


def _choice_text(choice, repeated=()):
    """A choice as players read it: its name only (the id is in the tooltip); a name two
    choices share carries the id too, so they can be told apart."""
    if choice.label in repeated and choice.label != choice.value:
        return f"{choice.label}  ({choice.value})"
    return choice.label


def _repeated(choices):
    seen, twice = set(), set()
    for choice in choices:
        (twice if choice.label in seen else seen).add(choice.label)
    return twice


def _wheel_guard(widget):
    """Scrolling the form must not change a number or a choice it passes over."""
    widget.setFocusPolicy(Qt.StrongFocus)
    original = widget.wheelEvent

    def wheel(event):
        if widget.hasFocus():
            original(event)
        else:
            event.ignore()

    widget.wheelEvent = wheel
    return widget


def _small(text, color="#8b8e98"):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {color}; font-size: 11px;")
    return label


# -- layouts and small widgets ----------------------------------------------------------------
class FlowLayout(QLayout):
    """Children left to right, wrapping (tag chips)."""

    def __init__(self, parent=None, spacing=4):
        super().__init__(parent)
        self._items = []
        self.setSpacing(spacing)
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):  # noqa: N802 - Qt API
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self):  # noqa: N802
        return True

    def heightForWidth(self, width):  # noqa: N802
        return self._place(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect):  # noqa: N802
        super().setGeometry(rect)
        self._place(rect, apply=True)

    def sizeHint(self):  # noqa: N802
        return self.minimumSize()

    def minimumSize(self):  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _place(self, rect, apply):
        x, y, line = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > rect.right() and line > 0:
                x, y, line = rect.x(), y + line + self.spacing(), 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self.spacing()
            line = max(line, hint.height())
        return y + line - rect.y()


class NumberBox(QDoubleSpinBox):
    """A number; ``percent`` shows a 0..1 share as 0..100 %."""

    def __init__(self, value, *, integer=False, percent=False):
        super().__init__()
        _wheel_guard(self)
        self.percent = percent
        self.integer = integer
        if percent:
            self.setRange(0.0, 1000.0)
            self.setDecimals(1)
            self.setSuffix(" %")
            self.setSingleStep(5.0)
        else:
            self.setRange(-1e9, 1e9)
            self.setDecimals(0 if integer else 3)
            self.setSingleStep(1.0)
        self.setButtonSymbols(QDoubleSpinBox.NoButtons)  # every number looks alike
        self.setMinimumWidth(90)
        self.setMaximumWidth(140)
        self.set_value(value)

    def set_value(self, value):
        value = float(value or 0)
        self.setValue(value * 100.0 if self.percent else value)

    def number(self):
        value = self.value() / 100.0 if self.percent else self.value()
        return int(round(value)) if self.integer else round(value, 6)

    def textFromValue(self, value):  # noqa: N802 - trailing zeros hidden: 2, 0.5, 12.25
        if self.decimals() == 0:
            return str(int(round(value)))
        return f"{value:.{self.decimals()}f}".rstrip("0").rstrip(".")


class Picker(QComboBox):
    """A drop-down of choices (with icons), searchable by typing; ``allow_other`` keeps a
    typed value that is not in the list."""

    picked = Signal()

    def __init__(self, choices, value, *, icons=None, allow_none=True, allow_other=True):
        super().__init__()
        _wheel_guard(self)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setMaxVisibleItems(16)
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(16)
        self.allow_other = allow_other
        self._values = []
        if allow_none:
            self.addItem("(none)", "")
            self._values.append("")
        choices = tuple(choices)
        repeated = _repeated(choices)
        for choice in choices:
            text = _choice_text(choice, repeated)
            icon = icons(choice.icon) if icons and choice.icon else None
            if icon is not None:
                self.addItem(icon, text, choice.value)
            else:
                self.addItem(text, choice.value)
            if text != choice.value:
                self.setItemData(self.count() - 1, f"ID: {choice.value}", Qt.ToolTipRole)
            self._values.append(choice.value)
        completer = QCompleter([self.itemText(i) for i in range(self.count())], self)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.setCompleter(completer)
        self.set_value(value)
        self.activated.connect(lambda _i: self.picked.emit())
        self.lineEdit().editingFinished.connect(self._typed)

    def set_value(self, value):
        value = "" if value is None else str(value)
        if value not in self._values:  # a reference to something that is not there
            self.addItem(f"⚠ {value}  (missing - pick one from the list)", value)
            self._values.append(value)
        self.setCurrentIndex(self._values.index(value))

    def _typed(self):
        text = self.currentText().strip()
        for i in range(self.count()):
            if self.itemText(i) == text:
                self.setCurrentIndex(i)
                self.picked.emit()
                return
        lowered = text.lower()
        for i in range(self.count()):  # an id or a name typed on its own
            if str(self.itemData(i)).lower() == lowered or self.itemText(i).lower() == lowered:
                self.setCurrentIndex(i)
                self.picked.emit()
                return
        if self.allow_other and text:
            self.set_value(text)
            self.picked.emit()

    def value(self):
        data = self.currentData()
        return "" if data is None else str(data)


class PickDialog(QDialog):
    """Choose one or more entries from a long list (with a filter); ``allow_new`` lets a typed
    value that is not listed be added."""

    def __init__(self, title, choices, *, icons=None, allow_new=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(420, 520)
        self.filter = QLineEdit()
        hint = "Type to filter…" + ("  (or a new one)" if allow_new else "")
        self.filter.setPlaceholderText(hint)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setIconSize(QSize(24, 24))
        for choice in choices:
            item = QListWidgetItem(_choice_text(choice))
            item.setData(Qt.UserRole, choice.value)
            if icons and choice.icon:
                icon = icons(choice.icon)
                if icon is not None:
                    item.setIcon(icon)
            self.list.addItem(item)
        self.allow_new = allow_new
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.list.itemDoubleClicked.connect(lambda _i: self.accept())
        self.filter.textChanged.connect(self._filter)
        layout = QVBoxLayout(self)
        layout.addWidget(self.filter)
        layout.addWidget(self.list, 1)
        layout.addWidget(buttons)

    def _filter(self, text):
        text = text.lower().strip()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(bool(text) and text not in item.text().lower())

    def values(self):
        chosen = [i.data(Qt.UserRole) for i in self.list.selectedItems()]
        typed = self.filter.text().strip()
        if not chosen and self.allow_new and typed:
            chosen = [typed]
        return chosen


class ChipList(QWidget):
    """A list of values as chips (click one to remove it) and an Add button with a picker."""

    edited = Signal()

    def __init__(self, values, choices, *, icons=None, allow_new=True, noun="entry", namer=None):
        super().__init__()
        self.namer = namer  # words for a value that is not a listed choice (a new tag)
        self.values = [str(v) for v in values]
        self.choices = tuple(choices)
        self.icons = icons
        self.allow_new = allow_new
        self.noun = noun
        self.flow = FlowLayout(self)
        self._labels = {c.value: c for c in self.choices}
        self._build()

    def hasHeightForWidth(self):  # noqa: N802 - Qt API: the chips wrap
        return True

    def heightForWidth(self, width):  # noqa: N802
        return max(26, self.flow.heightForWidth(width))

    def minimumSizeHint(self):  # noqa: N802 - a layout that ignores height-for-width still
        width = self.width() if self.width() > 50 else 360  # gives the chips their rows
        return QSize(120, self.heightForWidth(width))

    def sizeHint(self):  # noqa: N802
        return self.minimumSizeHint()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._fit()

    def _fit(self):
        """Ask for the height the chips need at this width (any parent layout honours it)."""
        width = self.width() if self.width() > 50 else 360
        needed = self.heightForWidth(width)
        if self.minimumHeight() != needed:
            self.setMinimumHeight(needed)
            self.updateGeometry()

    def _build(self):
        while self.flow.count():
            item = self.flow.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()  # gone now, not only once the event loop runs
                item.widget().deleteLater()
        for value in self.values:
            choice = self._labels.get(value)
            chip = QToolButton()
            chip.setObjectName("FormChip")
            shown = choice.label if choice else (self.namer(value) if self.namer else value)
            chip.setText(shown + "  ✕")
            chip.setToolTip(f"{self.noun.title()}: {value}\nClick to remove")
            if choice is not None and choice.icon and self.icons:
                icon = self.icons(choice.icon)
                if icon is not None:
                    chip.setIcon(icon)
                    chip.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            chip.clicked.connect(lambda _c=False, v=value: self._remove(v))
            self.flow.addWidget(chip)
        add = QToolButton()
        add.setObjectName("FormAddChip")
        add.setText(f"+ Add {self.noun}")
        add.clicked.connect(self._add)
        self.flow.addWidget(add)
        self._fit()

    def _remove(self, value):
        self.values = [v for v in self.values if v != value]
        self._build()
        self.edited.emit()

    def _add(self):
        free = [c for c in self.choices if c.value not in self.values]
        dialog = PickDialog(
            f"Add {self.noun}", free, icons=self.icons, allow_new=self.allow_new, parent=self
        )
        if dialog.exec():
            self.add_values(dialog.values())

    def setText(self, text):  # noqa: N802 - the former comma-separated text field's API
        self.values = [v.strip() for v in str(text).split(",") if v.strip()]
        self._build()
        self.edited.emit()

    def text(self):
        return ", ".join(self.values)

    def set_checked(self, value, checked=True):
        """Add (or drop) one value, as the former checkable list did; False if it is not a
        choice and new values are not allowed."""
        value = str(value)
        if checked and value not in self.values:
            if not self.allow_new and value not in self._labels:
                return False
            self.add_values([value])
        elif not checked and value in self.values:
            self._remove(value)
        return True

    def add_values(self, values):
        for value in values:
            if value and value not in self.values:
                self.values.append(str(value))
        self._build()
        self.edited.emit()


class AmountTable(QWidget):
    """``{name: number}``: one row per name (picked from a list) with its number."""

    edited = Signal()

    def __init__(self, values, choices, *, percent=False, noun="stat"):
        super().__init__()
        self.values = dict(values)
        self.choices = tuple(choices)
        self.percent = percent
        self.noun = noun
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(4)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.grid)
        add = QPushButton(f"+ Add {noun}")
        add.setObjectName("FormAddButton")
        add.clicked.connect(self._add)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addStretch(1)
        layout.addLayout(row)
        self._labels = {c.value: c.label for c in self.choices}
        self._build()

    def _build(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()  # gone now, not only once the event loop runs
                item.widget().deleteLater()
        if not self.values:
            self.grid.addWidget(_small(f"No {_plural(self.noun)} yet."), 0, 0)
        order = {c.value: i for i, c in enumerate(self.choices)}
        ordered = sorted(self.values.items(), key=lambda kv: (order.get(kv[0], 1e9), kv[0]))
        for index, (key, value) in enumerate(ordered):
            row, column = divmod(index, 2)
            column *= 4
            name = QLabel(self._labels.get(key) or label_for(key))
            name.setToolTip(key)
            text_width = name.fontMetrics().horizontalAdvance(name.text()) + 10
            name.setMinimumWidth(min(260, max(120, text_width)))  # long names are not cut
            box = NumberBox(value, integer=isinstance(value, int), percent=self.percent)
            box.setMaximumWidth(120)
            box.valueChanged.connect(lambda _v, k=key, b=box: self._set(k, b.number()))
            remove = QToolButton()
            remove.setText("✕")
            remove.setToolTip(f"Remove {self._labels.get(key, key)}")
            remove.clicked.connect(lambda _c=False, k=key: self._remove(k))
            self.grid.addWidget(name, row, column)
            self.grid.addWidget(box, row, column + 1)
            self.grid.addWidget(remove, row, column + 2)
        self.grid.setColumnMinimumWidth(3, 32)
        self.grid.setColumnStretch(7, 1)
        for index in range(self.grid.count()):  # new rows count at once, not once shown
            widget = self.grid.itemAt(index).widget()
            if widget is not None:
                widget.show()
        # any parent layout gives the table (and its Add button) the height it needs
        self.grid.invalidate()
        self.layout().invalidate()
        self.setMinimumHeight(self.layout().sizeHint().height())

    def _set(self, key, value):
        self.values[key] = value
        self.edited.emit()

    def add_row(self, key, value):
        """Add or set one row (the former key / amount table's API)."""
        self.values[str(key)] = float(value)
        self._build()
        self.edited.emit()

    def rows(self):
        return [(k, f"{v:g}") for k, v in self.values.items()]

    def _remove(self, key):
        self.values.pop(key, None)
        self._build()
        self.edited.emit()

    def _add(self):
        free = [c for c in self.choices if c.value not in self.values]
        dialog = PickDialog(f"Add {self.noun}", free, allow_new=True, parent=self)
        if dialog.exec():
            for value in dialog.values():
                self.values.setdefault(str(value), 0.0)
            self._build()
            self.edited.emit()


class TextTable(QWidget):
    """``{name: text}``: rows of two text boxes."""

    edited = Signal()

    def __init__(self, values, noun="entry"):
        super().__init__()
        self.rows = [[str(k), str(v)] for k, v in dict(values).items()]
        self.noun = noun
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.grid)
        add = QPushButton(f"+ Add {noun}")
        add.setObjectName("FormAddButton")
        add.clicked.connect(lambda: self._add())
        row = QHBoxLayout()
        row.addWidget(add)
        row.addStretch(1)
        layout.addLayout(row)
        self._build()

    def _build(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()  # gone now, not only once the event loop runs
                item.widget().deleteLater()
        for index, (key, value) in enumerate(self.rows):
            k, v = QLineEdit(key), QLineEdit(value)
            k.setPlaceholderText("name")
            v.setPlaceholderText("text")
            k.textEdited.connect(lambda t, i=index: self._set(i, 0, t))
            v.textEdited.connect(lambda t, i=index: self._set(i, 1, t))
            remove = QToolButton()
            remove.setText("✕")
            remove.clicked.connect(lambda _c=False, i=index: self._remove(i))
            self.grid.addWidget(k, index, 0)
            self.grid.addWidget(v, index, 1)
            self.grid.addWidget(remove, index, 2)

    def _set(self, index, column, text):
        self.rows[index][column] = text
        self.edited.emit()

    def _remove(self, index):
        del self.rows[index]
        self._build()
        self.edited.emit()

    def _add(self):
        self.rows.append(["", ""])
        self._build()

    def value(self):
        return {k.strip(): v for k, v in self.rows if k.strip()}


class ColorButton(QPushButton):
    edited = Signal()

    def __init__(self, value):
        super().__init__()
        self.color = str(value or "#ffffff")
        self.clicked.connect(self._pick)
        self._show()

    def _show(self):
        self.setText(self.color)
        self.setStyleSheet(
            f"QPushButton {{ background: {self.color}; color: "
            f"{'#000' if QColor(self.color).lightness() > 140 else '#fff'}; }}"
        )

    def _pick(self):
        chosen = QColorDialog.getColor(QColor(self.color), self, "Colour")
        if chosen.isValid():
            self.color = chosen.name()
            self._show()
            self.edited.emit()


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
        self._cell = (0, 0)
        self.keeps_empty = False  # empty optional fields show here (no "show more" link)
        self.toggle = QToolButton()
        self.toggle.setObjectName("FormSectionTitle")
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(not collapsed)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.DownArrow if not collapsed else Qt.RightArrow)
        self.body = QWidget()
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
        self.body.setVisible(not collapsed)
        self.toggle.toggled.connect(self._toggled)
        self._more = []  # (label, widget, help, key) of empty fields, shown on request
        self.more_button = QToolButton()
        self.more_button.setObjectName("FormMoreButton")
        self.more_button.hide()
        self.more_button.clicked.connect(self.show_more)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(4)
        head = QHBoxLayout()
        head.addWidget(self.toggle)
        if hint:
            head.addWidget(_small(hint), 1)
        else:
            head.addStretch(1)
        layout.addLayout(head)
        layout.addWidget(self.body)
        layout.addWidget(self.more_button, 0, Qt.AlignLeft)

    def add_empty(self, label, widget, *, help_text="", key=""):
        """An empty optional field: listed under "Show N more fields" until asked for."""
        self._more.append((label, widget, help_text, key))
        widget.hide()
        widget.setParent(self)
        self.more_button.setText(f"＋ Show {len(self._more)} more field(s)  (empty)")
        self.more_button.show()

    def show_more(self):
        for label, widget, help_text, key in self._more:
            widget.show()
            self.add_row(label, widget, help_text=help_text, key=key)
        self._more = []
        self.more_button.hide()

    def has_rows(self):
        return self.form.count() > 0 or bool(self._more)

    def _toggled(self, open_):
        self.body.setVisible(open_)
        self.toggle.setArrowType(Qt.DownArrow if open_ else Qt.RightArrow)

    def add_row(self, label, widget, *, help_text="", key=""):
        row = self.form.rowCount()
        title = QLabel(label + ("  ⓘ" if help_text else ""))
        title.setObjectName("FormFieldLabel")
        tip = (help_text + "\n\n" if help_text else "") + (f"data: {key}" if key else "")
        title.setToolTip(tip.strip())
        widget.setToolTip(widget.toolTip() or tip.strip())
        holder = QVBoxLayout()
        if self.columns:
            help_text = ""  # a card stays compact: its help is the field's tooltip
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
            title.setFixedHeight(_first_line_height(widget))
            title.setMinimumWidth(140)
            if isinstance(widget, QCheckBox):  # a switch reads as one line: "[x] Shown in HUD"
                widget.setText(label)
                title.setText("")
            self.form.addWidget(title, row, 0, Qt.AlignTop)
            self.form.addLayout(holder, row, 1)
        holder.setSpacing(1)
        if help_text and _is_wide(widget) and not isinstance(widget, ChipList):
            # a table's hint above it, not under its Add button
            holder.addWidget(_small(help_text))
            help_text = ""
        if isinstance(widget, (NumberBox, QCheckBox, ColorButton)):
            line = QHBoxLayout()  # a small control stays small
            line.addWidget(widget)
            line.addStretch(1)
            holder.addLayout(line)
        else:
            holder.addWidget(widget)
        if help_text:
            holder.addWidget(_small(help_text))

    def _grid_place(self, title, label, widget, holder):
        """Label above the field; a small field takes the next free column, a wide one (a list,
        long text) a row of its own. A switch carries its label beside its box."""
        row, column = self._cell
        if _is_wide(widget):
            if column:
                row, column = row + 1, 0
            self.form.addLayout(holder, row, 0, 1, self.columns)
            self._cell = (row + 1, 0)
        else:
            self.form.addLayout(holder, row, column, Qt.AlignTop)
            column += 1
            self._cell = (row + 1, 0) if column >= self.columns else (row, column)
        if isinstance(widget, QCheckBox) and label:
            widget.setText(label)
            holder.addSpacing(title.sizeHint().height() + 1)  # in line with labelled fields
            # the unused label has no parent: Python frees it (a deleteLater as well would
            # free it twice and crash later)
        else:
            holder.addWidget(title)

    def add_wide(self, widget):
        if self.columns:
            row, column = self._cell
            row += 1 if column else 0
            self.form.addWidget(widget, row, 0, 1, self.columns)
            self._cell = (row + 1, 0)
            return
        self.form.addWidget(widget, self.form.rowCount(), 0, 1, 2)


# -- the form ---------------------------------------------------------------------------------
class RecordForm(QScrollArea):
    """Edits one record's data with a form; ``record()`` gives the edited data back."""

    changed = Signal()

    def __init__(self, parent=None, *, document=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.document = document
        self.field_choices = {}  # field -> callable ((value, QIcon or None), ...) (extra lists)
        self.icon_library = None
        self.category = ""
        self.optional = set()
        self._data = None
        self._title = None
        self._icons = {}
        self.vocabulary = vocabulary_for(document)
        self._page = QWidget()
        self._page.setObjectName("RecordFormPage")
        self.setWidget(self._page)
        self._layout = QVBoxLayout(self._page)
        self._layout.setContentsMargins(4, 4, 4, 12)
        self._layout.setSpacing(10)
        self.error = QLabel()
        self.error.setObjectName("FormError")
        self.error.setWordWrap(True)
        self.error.hide()
        self._apply_style()

    # -- public API ---------------------------------------------------------------------------
    def clear(self):
        self._data = None
        self._rebuild()

    def set_record(self, data, title=None, *, optional=(), category="", defer=False):
        """Show ``data``; ``defer`` keeps it (``record()`` has it) but builds the fields only
        when the form is first shown - a skill tree's form has thousands of fields, and it
        sits behind the graph until asked for."""
        same = (
            self._data is not None
            and data == self._data
            and title == self._title
            and set(optional) == self.optional
            and (category or self.category) == self.category
        )
        if same:  # already showing exactly this (a refresh after an edit elsewhere): keep it
            return
        self._data = deepcopy(data)
        self._title = title
        self.optional = set(optional)
        self.category = category or self.category
        self.vocabulary = vocabulary_for(self.document)
        self._unbuilt = bool(defer) and not self.isVisible()
        if not self._unbuilt:
            self._rebuild()

    def showEvent(self, event):  # noqa: N802 - Qt API
        super().showEvent(event)
        if getattr(self, "_unbuilt", False):
            self._unbuilt = False
            self._rebuild()

    def record(self):
        return None if self._data is None else deepcopy(self._data)

    # -- the structure API of the former tree editor (scripts and tests use it) --------------
    def _at(self, path):
        value = self._data
        for part in path:
            value = value[part]
        return value

    def add_entry(self, path):
        """Append an entry to the list at ``path`` (a copy of the last, else a template)."""
        entries = self._at(path)
        key = next((p for p in reversed(path) if isinstance(p, str)), "")
        if entries:
            entry = deepcopy(entries[-1])
        else:
            entry = _engine_template(key) or deepcopy(_LIST_TEMPLATES.get(key, {}))
        entries.append(_fresh_ids(entry, entries, self))
        self.restructure()
        return entry

    def remove_entry(self, path):
        del self._at(path[:-1])[path[-1]]
        self.restructure()

    def add_field(self, path, name, value=0.0):
        self._at(path)[str(name).strip()] = value
        self.restructure()
        return name

    def set_error(self, text):
        self.error.setText("⚠  Not applied: " + text if text else "")
        self.error.setVisible(bool(text))

    # -- building -----------------------------------------------------------------------------
    def _rebuild(self):
        self._unbuilt = False
        scroll = self.verticalScrollBar().value()
        old = self.takeWidget()  # kept alive until the new page is in (the banner moves over)
        self.error.setParent(None)
        self._page = QWidget()
        self._page.setObjectName("RecordFormPage")
        self._layout = QVBoxLayout(self._page)
        self._layout.setContentsMargins(4, 4, 4, 12)
        self._layout.setSpacing(10)
        self._layout.addWidget(self.error)
        if self._data is not None:
            self._build(self._data)
        self._layout.addStretch(1)
        self.setWidget(self._page)
        if old is not None:
            # takeWidget hands the old page to Python, which would free it at once - while a
            # click on one of its buttons (an "+ Add" that rebuilt the form) is still being
            # handled: a use-after-free that crashes later. It is held until deleteLater runs.
            old.hide()
            self._retired = old  # held (not a child, so it is never found among them)
            old.deleteLater()
        QTimer.singleShot(0, self._page, lambda: self.verticalScrollBar().setValue(scroll))

    def _build(self, data):
        if not isinstance(data, dict):
            section = Section("Value")
            section.add_wide(QLabel(str(data)))
            self._layout.addWidget(section)
            return
        self._header(data)
        record_id_key = self._id_key(data)
        name_key = next((k for k in NAME_KEYS if isinstance(data.get(k), str)), None)
        basics = Section("Basics", hint=CATEGORY_HELP.get(self.category, ""))
        tags = Section("Tags and lists")
        numbers = Section("Numbers")
        advanced = Section("Advanced", collapsed=True, hint="Filled in for you; rarely changed.")
        nested = []
        for key, value in data.items():
            if key in FORMAT_KEYS or key in (record_id_key, name_key):
                continue
            if key == "icon_id":
                continue
            target = basics
            if key in TECHNICAL or (key in self.optional and _empty(value)):
                target = advanced
            if isinstance(value, dict) and _number_map(value) and not _nested_record(value):
                section = target if target is advanced else numbers
                self._field(section, data, key, value)
            elif isinstance(value, list) and _scalar_list(key, value):
                self._field(advanced if target is advanced else tags, data, key, value)
            elif isinstance(value, (dict, list)):
                nested.append((key, value, target is advanced))
            else:
                self._field(target, data, key, value)
        more = Section("More fields", collapsed=True, hint="Optional, nothing written yet.")
        for section in (basics, numbers, tags):
            if section.form.count():
                self._layout.addWidget(section)
            else:  # only empty optional fields: they wait together at the end
                for label, widget, help_text, key in section._more:
                    widget.show()
                    more.add_row(label, widget, help_text=help_text, key=key)
                section._more = []
        for key, value, is_advanced in nested:
            box = Section(label_for(key), collapsed=is_advanced, hint=HELP.get(key, ""))
            self._nested(box, data, key, value)
            self._layout.addWidget(box)
        if more.form.count():
            self._layout.addWidget(more)
        if advanced.has_rows():
            self._layout.addWidget(advanced)

    def _header(self, data):
        card = QFrame()
        card.setObjectName("FormHeader")
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(12)
        if "icon_id" in data and self.icon_library is not None:
            from .game_systems_widget import _IconPicker

            picker = _IconPicker(self.icon_library)
            picker.preview.setFixedSize(48, 48)
            picker.setText(str(data.get("icon_id") or ""))
            picker.changed.connect(lambda p=picker: self._set(data, "icon_id", p.text()))
            picker.setToolTip(HELP["icon_id"])
            icon_box = QHBoxLayout()
            label = _small("Icon")
            label.setFixedHeight(48)  # level with the picture
            icon_box.addWidget(label, 0, Qt.AlignTop)
            icon_box.addWidget(picker, 1)
        else:
            icon_box = None
        names = QVBoxLayout()
        name_key = next((k for k in NAME_KEYS if isinstance(data.get(k), str)), None)
        if name_key is not None:
            edit = QLineEdit(data[name_key])
            edit.setObjectName("FormName")
            edit.setPlaceholderText("Name players see")
            edit.textEdited.connect(lambda text, k=name_key: self._set(data, k, text))
            names.addWidget(_small(label_for(name_key)))
            names.addWidget(edit)
        id_key = self._id_key(data)
        if id_key is not None and name_key is None:  # no name: a title from its parts
            from .record_vocabulary import record_title

            title = record_title(self.category, data, self.vocabulary, data.get(id_key))
            if title:
                heading = QLabel(title)
                heading.setObjectName("FormTitle")
                names.addWidget(heading)
        if id_key is not None:
            names.addWidget(
                _small(
                    f"Internal ID: {data[id_key]}   ·   other records refer to it by this, "
                    "so it stays fixed (use Duplicate to make a copy with a new one)"
                )
            )
        elif self._title:
            names.addWidget(_small(str(self._title)))
        if icon_box is not None:
            names.addSpacing(4)
            names.addLayout(icon_box)
        row.addLayout(names, 1)
        self._layout.addWidget(card)

    def _id_key(self, data):
        """The key holding the record's own id: the one whose value is the record id the host
        gave (``actor_id`` of an actor), else the first ``*_id`` that refers to nothing."""
        for key, value in data.items():
            if key.endswith("_id") and self._title is not None and value == self._title:
                return key
        for key, value in data.items():
            if key.endswith("_id") and isinstance(value, str) and REFERENCES.get(key) is None:
                if key not in ("icon_id",):
                    return key
        return None

    def _nested(self, section, parent, key, value):
        if isinstance(value, dict):
            if _number_map(value) and value:
                self._field(section, parent, key, value, label="")
            elif _text_map(value) and value:
                self._field(section, parent, key, value, label="")
            else:
                inner = _SubForm(self, value, key)
                section.add_wide(inner)
        else:
            section.add_wide(CardList(self, parent, key, value))

    def _field(self, section, data, key, value, *, label=None):
        widget = self.widget_for(data, key, value)
        if widget is None:
            return
        text = label_for(key) if label is None else label
        help_text = HELP.get(str(key), "")
        source = self._reference(data, str(key)) if isinstance(value, str) else None
        about = self.vocabulary.description(source, value) if source else ""
        if about:  # what the picked skill / item does, under its picker
            help_text = f"{help_text}  ·  {about}" if help_text else about
        if not text:
            section.add_wide(widget)
        elif (
            _empty_optional(value)
            and not section.keeps_empty
            and section.toggle.text() != "Advanced"
        ):
            section.add_empty(text, widget, help_text=help_text, key=str(key))
        else:
            section.add_row(text, widget, help_text=help_text, key=str(key))

    # -- one field ----------------------------------------------------------------------------
    def widget_for(self, data, key, value):
        """The editing widget for ``data[key]``; edits write back into ``data``."""
        skey = str(key)
        source = self._reference(data, skey)
        if isinstance(value, bool):
            box = QCheckBox("Yes")
            box.setChecked(value)
            box.toggled.connect(lambda on: self._set(data, key, bool(on)))
            return box
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            box = NumberBox(value, integer=isinstance(value, int), percent=is_chance_field(skey))
            box.valueChanged.connect(lambda _v, b=box: self._set(data, key, b.number()))
            return box
        if skey == "icon_id" and self.icon_library is not None:
            from .game_systems_widget import _IconPicker

            picker = _IconPicker(self.icon_library)
            picker.setText(str(value or ""))
            picker.changed.connect(lambda p=picker: self._set(data, key, p.text()))
            return picker
        if (isinstance(value, str) or value is None) and skey in _CLIP_KEYS.get(self.category, ()):
            # a pose names one of the sheet's animations: offer them, in words
            picker = Picker(self.vocabulary.choices("clips"), value or "", allow_none=True)
            picker.picked.connect(lambda p=picker: self._set(data, key, p.value()))
            return picker
        if isinstance(value, str) or value is None:
            if source is not None or skey in self.field_choices:
                choices = self._choices(source, skey)
                picker = Picker(choices, value or "", icons=self.icon)
                picker.picked.connect(lambda p=picker: self._set(data, key, p.value() or ""))
                return picker
            from .record_vocabulary import engine_enums

            fixed = _ENUMS.get(skey) or engine_enums().get(skey)
            if is_trigger_field(skey):  # a moment in the battle, in words
                from .record_vocabulary import TRIGGERS, Choice

                used = self.vocabulary.values_for(skey)
                known = dict.fromkeys(fixed or (*TRIGGERS, *used))
                if value:  # the record's own moment is always one of the choices
                    known.setdefault(str(value), None)
                choices = [Choice(t, trigger_label(t)) for t in known]
                picker = Picker(choices, value or "", allow_none=True)
                picker.picked.connect(lambda p=picker: self._set(data, key, p.value()))
                return picker
            if fixed or _closed_set(skey, self.vocabulary.values_for(skey)):
                from .record_vocabulary import Choice

                options = fixed or self.vocabulary.values_for(skey)
                choices = [Choice(v, words(v)) for v in options]
                picker = Picker(choices, value or "", allow_none=True)
                picker.picked.connect(lambda p=picker: self._set(data, key, p.value()))
                return picker
            if skey.endswith("color") or skey.endswith("colour"):
                button = ColorButton(value)
                button.edited.connect(lambda b=button: self._set(data, key, b.color))
                return button
            if skey in ("description", "text", "message", "body") or len(str(value or "")) > 60:
                edit = QPlainTextEdit(str(value or ""))
                edit.setFixedHeight(64)
                edit.textChanged.connect(lambda e=edit: self._set(data, key, e.toPlainText()))
                return edit
            edit = QLineEdit(str(value or ""))
            edit.textEdited.connect(lambda text: self._set(data, key, text))
            return edit
        if isinstance(value, list) and _scalar_list(skey, value):
            if value and all(isinstance(v, (int, float)) for v in value):
                edit = QLineEdit(", ".join(f"{v:g}" for v in value))
                edit.setToolTip("Numbers separated by commas")
                edit.textEdited.connect(lambda text: self._set(data, key, _numbers(text)))
                return edit
            if is_tag_field(skey):
                choices = self.vocabulary_tags()
                noun = "tag"
            else:
                if source or skey in self.field_choices:
                    choices = self._choices(source, skey)
                else:
                    choices = self._value_choices(skey)
                noun = _noun(skey)
            namer = None
            if noun == "tag":
                names = self.vocabulary.names()
                namer = lambda tag, n=names: tag_label(tag, n)  # noqa: E731
            chips = ChipList(value, choices, icons=self.icon, noun=noun, namer=namer)
            chips.edited.connect(lambda c=chips: self._set(data, key, list(c.values)))
            return chips
        if isinstance(value, dict) and _number_map(value):
            kind = map_source(skey)
            choices = self.vocabulary.choices(kind) if kind else ()
            noun = {"resources": "resource", "stats": "stat", "items": "item"}.get(kind) or _noun(
                skey
            )
            table = AmountTable(value, choices, percent=False, noun=noun)
            table.edited.connect(lambda t=table: self._set(data, key, dict(t.values)))
            return table
        if isinstance(value, dict) and _text_map(value):
            table = TextTable(value)
            table.edited.connect(lambda t=table: self._set(data, key, t.value()))
            return table
        if isinstance(value, dict):
            return _SubForm(self, value, key)
        if isinstance(value, list):
            return CardList(self, data, key, value)
        return QLabel(str(value))

    def vocabulary_tags(self):
        from .record_vocabulary import Choice

        names = self.vocabulary.names()
        return [Choice(t, tag_label(t, names)) for t in self.vocabulary.tags()]

    def _value_choices(self, key):
        from .record_vocabulary import Choice

        # values in words: a stat by its name ("STR", "Critical Rate"), else the id in words
        return [Choice(v, label_for(v)) for v in self.vocabulary.values_for(key)]

    def _reference(self, data, key):
        if key == "key" and isinstance(data.get("source"), str):
            return TERM_KEY_SOURCES.get(data["source"])
        if key == "target" and data.get("kind") in ("resource_delta", "resource_set"):
            return "resources"
        if key == "target" and data.get("kind") == "stat_delta":
            return "stats"
        if key in NOT_REFERENCES.get(self.category, ()):
            return None
        return REFERENCES.get(key)

    def _choices(self, source, key):
        from .record_vocabulary import Choice

        if key in self.field_choices:
            return [Choice(str(v), str(v)) for v, _icon in self.field_choices[key]()]
        return self.vocabulary.choices(source) if source else ()

    def icon(self, icon_id):
        """A QIcon for an icon id (a project picture or ``forged:<kind>``), cached."""
        if not icon_id:
            return None
        if icon_id in self._icons:
            return self._icons[icon_id]
        icon = None
        try:
            if icon_id.startswith("forged:"):
                from .image_tools import forged_qicon

                icon = forged_qicon(icon_id)
            else:
                from .image_tools import project_root

                path = Path(icon_id)
                if not path.is_absolute() and self.document is not None:
                    path = project_root(self.document) / path
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    icon = QIcon(pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.FastTransformation))
        except Exception:  # noqa: BLE001 - a missing picture shows no icon
            icon = None
        self._icons[icon_id] = icon
        return icon

    # -- writing back ---------------------------------------------------------------------------
    def _set(self, container, key, value):
        container[key] = value
        self.changed.emit()

    def restructure(self):
        """A list gained or lost an entry: rebuild the form (the data is already changed)."""
        self._rebuild()
        self.changed.emit()

    def _apply_style(self):
        """The look comes from the editor theme (theme._form_rules), shared by every page."""


class _SubForm(QWidget):
    """The fields of a nested part, laid out like a section's body."""

    def __init__(self, form, data, key):
        super().__init__()
        self.section = Section(label_for(key), compact=True, columns=3)
        self.section.toggle.hide()
        self.section.setObjectName("FormSubSection")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.section)
        for k, v in data.items():
            if k in FORMAT_KEYS:
                continue
            if isinstance(v, list) and not _scalar_list(k, v):
                self.section.add_row(label_for(k), CardList(form, data, k, v), key=str(k))
            else:
                form._field(self.section, data, k, v)


FOLD_AFTER = 8  # a list with more entries than this opens one entry at a time


class CardList(QWidget):
    """A list of entries as cards; each card holds the entry's fields."""

    def __init__(self, form, parent, key, entries):
        super().__init__()
        self.form, self.parent_data, self.key = form, parent, key
        self.entries = entries
        self.names = form.vocabulary.names()  # card titles show names, not ids
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        noun = _noun(key)
        # a long list (a skill tree's nodes) shows each entry as its title line; its fields
        # are built when it is opened - building every card at once took many seconds
        self.folded = len(entries) > FOLD_AFTER
        if not entries:
            layout.addWidget(_small(f"No {label_for(key).lower()} yet."))
        elif self.folded:
            layout.addWidget(_small(f"{len(entries)} entries - click ▸ to open one."))
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
        title = QLabel(f"<b>{index + 1}.</b>  {_entry_title(entry, noun, self.names)}")
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
            hidden = 0
            for key, value in entry.items():
                if key in FORMAT_KEYS:
                    continue
                folded = key in TECHNICAL or _empty_optional(value)
                hidden += folded
                target = extra if folded else section
                if isinstance(value, list) and not _scalar_list(key, value):
                    target.add_row(label_for(key), CardList(self.form, entry, key, value))
                else:
                    self.form._field(target, entry, key, value)
            body.addWidget(section)
            if extra.form.count():
                extra.toggle.setText(f"More ({hidden})")
                body.addWidget(extra)
        else:
            body.addWidget(self.form.widget_for(self.entries, index, entry))

    def add(self):
        if self.entries:
            entry = deepcopy(self.entries[-1])
        else:
            entry = _engine_template(self.key) or deepcopy(_LIST_TEMPLATES.get(str(self.key)))
            if entry is None:
                return  # nothing known to start from (copy an entry from another record)
        self.entries.append(_fresh_ids(entry, self.entries, self.form))
        self._opened().add((id(self.entries), len(self.entries) - 1))  # a new one opens
        self.form.restructure()

    def duplicate(self, index):
        entry = _fresh_ids(deepcopy(self.entries[index]), self.entries, self.form)
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


# -- helpers ----------------------------------------------------------------------------------
_IDENTIFIER = re.compile(r"^[a-z0-9_.:\-]+$")
FREE_TEXT = {"label", "name", "title", "text", "description", "message", "prefix", "suffix"}


def _closed_set(key, values):
    """A text field whose values across the project are a few id-like words (a mode, a
    target...) becomes a drop-down of them."""
    if key in FREE_TEXT or key.endswith("_id") or key.endswith("_label"):
        return False
    return 1 < len(values) <= 24 and all(_IDENTIFIER.match(v) for v in values)


def _scalar_list(key, value):
    """A list of plain values (tags, ids), not of entries; an empty list counts as entries
    when its field is known to hold them."""
    if not value:
        return str(key) not in RECORD_LISTS
    return all(isinstance(v, _SCALARS) for v in value)


def _empty_optional(value):
    """Nothing written yet: an empty list, table or text (numbers and switches always show)."""
    return value in ("", None) or value == [] or value == {}


def _empty(value):
    return value in ("", None, 0, 0.0, False) or value == [] or value == {}


def _number_map(value):
    return isinstance(value, dict) and all(
        isinstance(v, (int, float)) and not isinstance(v, bool) for v in value.values()
    )


def _text_map(value):
    return isinstance(value, dict) and all(isinstance(v, str) for v in value.values())


def _nested_record(value):
    return any(k in FORMAT_KEYS for k in value)


def _numbers(text):
    out = []
    for part in re.split(r"[,\s]+", text.strip()):
        try:
            out.append(float(part))
        except ValueError:
            continue
    return out


_CLIP_KEYS = {"combatant_visuals": ("clip_role", "state_id", "fallback_state_id")}


def _noun(key):
    """What one entry of a list field is, for "+ Add …": its label when that is one word
    ("Jobs" -> job), else the key's last word ("gain_rules" -> rule)."""
    label = label_for(key)
    if label and " " not in label.strip():
        return _singular(label.lower())
    word = str(key).replace("-", "_").split("_")[-1].lower()
    special = {"operations": "step", "impacts": "rule", "entries": "entry", "members": "member"}
    if word in special:
        return special[word]
    return _singular(word) if word and word not in ("ids", "id") else "entry"


def _plural(noun):
    """``currency`` -> "currencies", ``entry`` -> "entries", ``stat`` -> "stats"."""
    noun = str(noun)
    if noun.endswith("y") and noun[-2:-1] not in "aeiou":
        return noun[:-1] + "ies"
    if noun.endswith(("s", "x", "ch", "sh")):
        return noun + "es"
    return noun + "s"


def _singular(text):
    """``stats`` -> "stat"; a phrase ("what it does") is an "entry"."""
    text = str(text).strip()
    if " " in text:
        return "entry"
    for suffix, replacement in (("ies", "y"), ("ses", "s"), ("s", "")):
        if text.endswith(suffix) and len(text) > 3:
            return text[: -len(suffix)] + replacement
    return text


def _first_line_height(widget):
    """The height of a field's first line: a box's own height, a chip row's, else a box's."""
    if isinstance(widget, ChipList):
        chip = widget.findChild(QToolButton)
        return max(22, chip.sizeHint().height() if chip is not None else 24)
    if isinstance(widget, (QLineEdit, QComboBox, QDoubleSpinBox, QCheckBox, QPushButton)):
        return max(22, widget.sizeHint().height())
    return QLineEdit().sizeHint().height()


def _is_wide(widget):
    """A field that needs a whole row: a list, a table, long text."""
    wide = (ChipList, AmountTable, TextTable, CardList, _SubForm, QPlainTextEdit, Section)
    return isinstance(widget, wide)


def _entry_title(entry, noun, names=None):
    """A card's title: the entry's name, or what it refers to by its display name (``Brave``
    for ``class_id: brave``)."""
    names = names or {}
    title = _entry_name(entry, noun, names)
    if isinstance(entry, dict) and isinstance(entry.get("trigger"), str) and entry["trigger"]:
        moment = trigger_label(entry["trigger"])  # a rule also says the moment it reacts to
        return moment if title == noun.title() else f"{title}  ·  {moment}"
    return title


def _entry_name(entry, noun, names):
    if isinstance(entry, dict):
        for key in ("display_name", "name", "label", "state", "stat", "ability_id", "class_id",
                    "item_id", "resource", "command", "socket_id", "form_id", "key",
                    "kind"):  # fmt: skip
            value = entry.get(key)
            if isinstance(value, str) and value:
                extra = ""
                if isinstance(entry.get("value"), (int, float)) and entry["value"]:
                    extra = f"  {entry['value']:+g}"
                if "to" in entry and isinstance(entry["to"], str):
                    extra += f"  → {names.get(entry['to'], entry['to'])}"
                return f"{names.get(value) or words(value)}{extra}"
        for key, value in entry.items():
            if key.endswith("_id") and isinstance(value, str) and value:
                return names.get(value) or words(value)
    elif isinstance(entry, (str, int, float)):
        return str(entry)
    return noun.title()


def _fresh_ids(entry, siblings, form):
    """A new entry's own ids (``modifier_id``, ``socket_id``...) are made unique."""
    if not isinstance(entry, dict):
        return entry
    for key, value in list(entry.items()):
        if not key.endswith("_id") or REFERENCES.get(key) not in (None,):
            continue
        if key in ("icon_id",):
            continue
        used = {str(s.get(key)) for s in siblings if isinstance(s, dict)}
        base = re.sub(r"[._-]?\d+$", "", str(value or key[:-3])) or key[:-3]
        n = len(siblings) + 1
        while f"{base}{n}" in used:
            n += 1
        entry[key] = f"{base}{n}"
    return entry
