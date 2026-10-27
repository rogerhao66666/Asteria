"""Form-based Qt editors for shops, quests, factions, achievements, equipment sets and capture
rules (CB10h).

Forms are generated from :data:`asteria.editor.game_systems_authoring.FORMS`
and edit canonical record data; every Apply goes through
:class:`GameSystemsAuthoringController`, the same API scripts use.
"""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .authoring_sidebar import authoring_sidebar
from .game_systems_authoring import FORMS, KINDS, GameSystemsAuthoringError, new_row
from .i18n import translate
from .project_empty_state import ProjectEmptyState
from .record_form import Picker
from .responsive_form import ResponsiveForm, ResponsiveSplit
from .ui_fit import fit_combo_to_items
from .undo_buttons import UndoRedoButtons

_BIG = 1_000_000_000


class _KeyValueTable(QWidget):
    """Two-column table with Add / Remove rows (``amounts`` and ``pairs`` fields)."""

    def __init__(self, headers, parent=None):
        super().__init__(parent)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(list(headers))
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumHeight(90)
        self.table.setMaximumHeight(
            150
        )  # a few rows; more scroll inside the table, not the whole page
        add, remove = QPushButton("Add"), QPushButton("Remove")
        add.clicked.connect(lambda: self.add_row("", ""))
        remove.clicked.connect(self.remove_row)
        buttons = QHBoxLayout()
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

    def add_row(self, a, b):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(a)))
        self.table.setItem(row, 1, QTableWidgetItem(str(b)))
        return row

    def remove_row(self):
        row = self.table.currentRow()
        if row < 0:
            row = self.table.rowCount() - 1
        if row >= 0:
            self.table.removeRow(row)

    def rows(self):
        out = []
        for row in range(self.table.rowCount()):
            a = self.table.item(row, 0)
            b = self.table.item(row, 1)
            out.append(((a.text() if a else "").strip(), (b.text() if b else "").strip()))
        return [r for r in out if r[0] or r[1]]


class _RefList(QListWidget):
    """Checkable list of references; keeps the authored order of checked entries. A choice is an
    id, or ``(id, name)``: the list shows the name and keeps the id."""

    def __init__(self, choices, parent=None):
        super().__init__(parent)
        pairs = [c if isinstance(c, tuple) else (c, c) for c in choices]
        self.choices = tuple(str(value) for value, _ in pairs)
        self.labels = {str(value): str(label) for value, label in pairs}
        self.setMinimumHeight(70)

    def set_values(self, values):
        self.clear()
        values = [str(v) for v in values]
        for choice in list(dict.fromkeys(values + list(self.choices))):
            item = QListWidgetItem(self.labels.get(choice, f"{choice} (missing)"))
            item.setData(Qt.UserRole, choice)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if choice in values else Qt.Unchecked)
            self.addItem(item)

    def _value(self, index):
        value = self.item(index).data(Qt.UserRole)
        return self.item(index).text() if value is None else str(value)

    def values(self):
        return [
            self._value(i) for i in range(self.count()) if self.item(i).checkState() == Qt.Checked
        ]

    def set_checked(self, value, checked=True):
        for i in range(self.count()):
            if self._value(i) == value:
                self.item(i).setCheckState(Qt.Checked if checked else Qt.Unchecked)
                return True
        return False


class _TableField(QGroupBox):
    """Master–detail editor for a list of nested records."""

    changed = Signal()

    def __init__(self, label, fields, references, parent=None, *, icons=None):
        # untitled: its name is the form's caption above it, like every other field's
        super().__init__("", parent)
        self.label = label
        self.setProperty("untitled", True)
        self.fields = fields
        self.rows = []
        self._current = -1
        self.list = QListWidget()
        self.list.setMinimumHeight(90)
        self.list.currentRowChanged.connect(self._select)
        self.detail = RecordForm(
            fields, references, column_width=200, icons=icons
        )  # nested rows: narrower columns
        self.detail.setEnabled(False)
        self.detail.changed.connect(self._detail_changed)
        add, remove = QPushButton("+ Add"), QPushButton("Remove")
        add.clicked.connect(lambda: (self.add_row(), self.changed.emit()))
        remove.clicked.connect(lambda: (self.remove_row(), self.changed.emit()))
        up, down = QPushButton("↑"), QPushButton("↓")  # rows in order (D96: a page's blocks)
        up.setToolTip("Move Up")
        down.setToolTip("Move Down")
        up.clicked.connect(lambda: self.move_row(-1))
        down.clicked.connect(lambda: self.move_row(1))
        buttons = QHBoxLayout()
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addWidget(up)
        buttons.addWidget(down)
        buttons.addStretch(1)
        rows = QWidget()
        column = QVBoxLayout(rows)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(self.list, 1)
        column.addLayout(buttons)
        layout = QVBoxLayout(self)
        # the row list sits beside the selected row's form when there is room
        self.split = ResponsiveSplit(rows, self.detail, side_by_side_at=520)
        layout.addWidget(self.split)

    def hasHeightForWidth(self):  # noqa: N802 - Qt API
        # the wrapping hints inside would give a height-for-width below what the rows need,
        # squeezing them; the box asks for its plain minimum height instead
        return False

    def _detail_changed(self):
        self._commit()
        self.changed.emit()

    def _label(self, row):
        """The row in words: a condition as "festival == true", a reference by its name
        (Healing Herb, not "Item: healing_herb"), else the first field's value."""
        if {"name", "operator", "value"} <= set(row):
            name = str(row.get("name") or "(no name yet)")
            return f"{row.get('source', '')} {name} {row.get('operator', '==')} {row['value']}"
        first = self.fields[0]
        value = row.get(first.key, "")
        if first.kind in ("ref", "optional_ref") and value:
            for choice in self.detail._reference_choices(first):
                if choice.value == str(value):
                    return choice.label
        if value in ("", None):
            return f"(new {first.label.lower()})"
        if first.kind == "choice":  # a kind of thing (a menu block): in words, with its place
            from .i18n import translate
            from .record_vocabulary import words

            text = translate(_choice_words(value, words))
            second = self.fields[1] if len(self.fields) > 1 else None
            if second is not None and second.kind == "choice" and row.get(second.key):
                text += f"  ·  {translate(_choice_words(row[second.key], words))}"
            return text
        return str(value)

    def _commit(self):
        if 0 <= self._current < len(self.rows):
            self.rows[self._current] = self.detail.data()
            item = self.list.item(self._current)
            if item is not None:
                item.setText(self._label(self.rows[self._current]))

    def _select(self, row):
        self._commit()
        self._current = row
        if 0 <= row < len(self.rows):
            self.detail.set_data(self.rows[row])
            self.detail.setEnabled(True)
        else:
            self.detail.setEnabled(False)

    def set_rows(self, rows):
        self._current = -1
        self.rows = [copy.deepcopy(r) for r in rows]
        self.list.blockSignals(True)
        self.list.clear()
        for row in self.rows:
            self.list.addItem(self._label(row))
        self.list.blockSignals(False)
        self.detail.setEnabled(False)
        if self.rows:
            self.list.setCurrentRow(0)

    def add_row(self):
        self._commit()
        self.rows.append(new_row(self.fields))
        self.list.addItem(self._label(self.rows[-1]))
        self.list.setCurrentRow(len(self.rows) - 1)
        return self.detail

    def move_row(self, step):
        """Move the chosen row ``step`` places (-1 up, 1 down)."""
        self._commit()
        row = self.list.currentRow()
        to = row + step
        if not (0 <= row < len(self.rows) and 0 <= to < len(self.rows)):
            return
        self.rows[row], self.rows[to] = self.rows[to], self.rows[row]
        self.list.blockSignals(True)
        for index in (row, to):
            self.list.item(index).setText(self._label(self.rows[index]))
        self._current = to
        self.list.setCurrentRow(to)
        self.list.blockSignals(False)
        self.detail.set_data(self.rows[to])
        self.changed.emit()

    def remove_row(self):
        row = self.list.currentRow()
        if 0 <= row < len(self.rows):
            self._current = -1
            del self.rows[row]
            self.list.takeItem(row)
            if self.rows:
                self.list.setCurrentRow(min(row, len(self.rows) - 1))
            else:
                self.detail.setEnabled(False)

    def values(self):
        self._commit()
        return [copy.deepcopy(r) for r in self.rows]


# text fields that name something in the project: the names offered (a "+" joins sources)
_TEXT_SOURCES = {
    "currency": "currencies",
    "currency_id": "currencies",
    "fee_currency": "currencies",
    "repair_currency": "currencies",
    "damage_resource": "resources",
    "resource": "resources",
    "check_stat": "stats",
    "lifesteal_stat": "stats",
    "stat": "stats",
    "sprite_sheet_asset_id": "assets:sprite_sheet",
    "battle_background": "assets:texture",
    "target": "enemies+items",
    "target_key": "enemies",
}
_SWITCH_KEYS = (
    "enabled_switch", "visible_switch", "failure_switch", "success_switch", "required_switch",
    "switch", "unlock_switch",
)  # fmt: skip
_VALUE_KEYS = {  # a field offering the values another field uses
    "side": "side",
    "event": "event",
    "default_difficulty": "difficulty_id",
    "default_locale": "locale",
}


class _TextPicker(Picker):
    """A text field as a drop-down of the project's names (any other text can be typed); the
    API of the line edit it replaces: ``text``, ``setText``, ``textEdited``."""

    textEdited = Signal(str)

    def __init__(self, choices):
        super().__init__(choices, "", allow_none=True)
        self.picked.connect(lambda: self.textEdited.emit(self.value()))

    def set_value(self, value):
        value = "" if value is None else str(value)
        if value not in self._values:  # a name typed by hand stays as it is
            name = value.rsplit("/", 1)[-1]
            if "/" in value and "." in name:  # a file path: its name, the path in the tip
                self.addItem(name, value)
                self.setItemData(self.count() - 1, value, Qt.ToolTipRole)
            else:
                self.addItem(value, value)
            self._values.append(value)
        self.setCurrentIndex(self._values.index(value))

    def text(self):
        return self.value()

    def setText(self, text):  # noqa: N802 - the line edit's API
        self.set_value(text)


def _choice_words(choice, words):
    """A fixed choice as players read it: "defeat_enemy" -> "Defeat Enemy"; operators and
    symbols stay as they are (==, <=)."""
    text = str(choice)
    return words(text) if text[:1].isalpha() else text


class _Decimal(QDoubleSpinBox):
    """A number shown without trailing zeros (1, 0.25, 12.5 - not 1.000)."""

    def textFromValue(self, value):  # noqa: N802 - Qt API
        text = f"{value:.{self.decimals()}f}".rstrip("0").rstrip(".")
        return "0" if text in ("", "-0") else text


class _Group(QGroupBox):
    """A group of fields (named by the caption above it); sized by its plain minimum height
    (see ``_TableField``)."""

    def __init__(self, label="", parent=None):
        super().__init__("", parent)
        self.label = label
        self.setProperty("untitled", True)

    def hasHeightForWidth(self):  # noqa: N802 - Qt API
        return False


_FLAT_KINDS = ("text", "int", "float", "bool", "choice", "ref", "optional_ref", "optional_int")


def _flat(fields):
    """A small table of plain fields (a condition, an objective; a price rule with its own
    conditions): each row is a card of its own instead of a list beside a form."""
    return len(fields) <= 6 and all(
        f.kind in _FLAT_KINDS or (f.kind == "table" and _flat(f.fields)) for f in fields
    )


class _InlineTable(QGroupBox):
    """Rows of a small table as cards, one under another: the row's fields side by side, ✕
    removes it, "+ Add" below the last. Same API as ``_TableField``."""

    changed = Signal()

    def __init__(self, label, fields, references, parent=None, *, icons=None):
        # untitled: its name is the form's caption above it, like every other field's
        super().__init__("", parent)
        self.label = label
        self.setProperty("untitled", True)
        self.fields, self.references, self.icons = fields, references, icons
        self.forms = []
        self.body = QVBoxLayout()
        self.body.setSpacing(6)
        self.empty = QLabel("None yet.")
        self.empty.setObjectName("FieldHint")
        add = QPushButton("+ Add")
        add.setObjectName("FormAddButton")
        add.clicked.connect(lambda: (self.add_row(), self.changed.emit()))
        buttons = QHBoxLayout()
        buttons.addWidget(add)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 14, 10, 10)
        layout.addWidget(self.empty)
        layout.addLayout(self.body)
        layout.addLayout(buttons)

    def hasHeightForWidth(self):  # noqa: N802 - Qt API
        # the wrapping hints inside would give a height-for-width below what the rows need,
        # squeezing them; the box asks for its plain minimum height instead
        return False

    @property
    def rows(self):
        return [form.data() for form in self.forms]

    def _card(self, row):
        card = QFrame()
        card.setObjectName("FormCard")
        line = QHBoxLayout(card)
        line.setContentsMargins(8, 6, 6, 6)
        form = RecordForm(self.fields, self.references, column_width=150, icons=self.icons)
        form.set_data(row)
        form.changed.connect(self.changed.emit)
        remove = QToolButton()
        remove.setText("✕")
        remove.setToolTip("Remove this row")
        remove.clicked.connect(lambda: (self._remove(form), self.changed.emit()))
        line.addWidget(form, 1)
        line.addWidget(remove, 0, Qt.AlignTop)
        form.card = card
        return form

    def _remove(self, form):
        self.forms.remove(form)
        form.card.hide()
        form.card.deleteLater()
        self.empty.setVisible(not self.forms)

    def set_rows(self, rows):
        for form in self.forms:
            form.card.hide()
            form.card.deleteLater()
        self.forms = []
        for row in rows:
            self._append(copy.deepcopy(row))

    def _append(self, row):
        form = self._card(row)
        self.forms.append(form)
        self.body.addWidget(form.card)
        self.empty.setVisible(False)
        return form

    def add_row(self):
        return self._append(new_row(self.fields))

    def remove_row(self):
        if self.forms:
            self._remove(self.forms[-1])

    def values(self):
        return [copy.deepcopy(form.data()) for form in self.forms]


_ICON_TABLES = {}  # id of an icon list -> {icon id: picture}


class _LazyIconCombo(QComboBox):
    """Fills its owner's whole icon list when opened or searched."""

    def __init__(self, owner):
        super().__init__()
        self._owner = owner

    def showPopup(self):  # noqa: N802 - Qt API
        self._owner._fill_all()
        super().showPopup()

    def findData(self, *args, **kwargs):  # noqa: N802 - Qt API
        self._owner._fill_all()
        return super().findData(*args, **kwargs)


class _IconPicker(QWidget):
    """An icon field: a list of the project's icons and the built-in library (each with its
    picture), a preview and Browse… to bring in a picture file of one's own. Paths show as their
    file name; the tooltip has the whole id."""

    changed = Signal()

    def __init__(self, library, parent=None):
        super().__init__(parent)
        self.library = library
        # picture on the left; the list over Browse… so a narrow form column shows a whole id
        row = QGridLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.preview = QLabel()
        self.preview.setObjectName("IconPreview")  # a framed square (theme)
        self.preview.setFixedSize(36, 36)
        self.preview.setAlignment(Qt.AlignCenter)
        self.combo = _LazyIconCombo(self)
        self._filled = False  # the whole list is added when it is first opened
        self.combo.setMaxVisibleItems(12)
        # a long list must not make Qt measure every entry each time the form is laid out
        self.combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.combo.setMinimumContentsLength(14)
        self.browse = QPushButton("Browse…")
        self.browse.setToolTip("Use a picture file of your own as the icon")
        self.browse.clicked.connect(self._browse)
        row.addWidget(self.preview, 0, 0, 2, 1, Qt.AlignTop)
        row.addWidget(self.combo, 0, 1)
        row.addWidget(self.browse, 1, 1, Qt.AlignLeft)
        row.setColumnStretch(1, 1)
        self._fill()
        self.combo.currentIndexChanged.connect(self._shown)

    @staticmethod
    def _label(icon_id):
        if not icon_id:
            return "(none)"
        # "icon.alchemy_salt" shows as "alchemy_salt": the list is all icons already
        return icon_id.rsplit("/", 1)[-1].removeprefix("icon.")

    def _add(self, icon_id, icon=None):
        if icon is not None:
            self.combo.addItem(icon, self._label(icon_id), icon_id)
        else:
            self.combo.addItem(self._label(icon_id), icon_id)
        self.combo.setItemData(self.combo.count() - 1, icon_id, Qt.ToolTipRole)

    def _fill(self):
        """The list: the current icon only until it is opened (a skill tree's form has a
        picker per node; filling each with every icon took seconds)."""
        current = self.text() if self.combo.count() else ""
        self.combo.blockSignals(True)
        self.combo.clear()
        self._add("")
        if self._filled and self.library is not None:
            for icon_id, icon in self.library.choices():
                self._add(icon_id, icon)
        self.combo.blockSignals(False)
        if current:
            self.setText(current)

    def _fill_all(self):
        if self._filled:
            return
        self._filled = True
        self._fill()

    def _icon_of(self, icon_id):
        if self.library is None or not icon_id:
            return None
        choices = self.library.choices()
        table = _ICON_TABLES.get(id(choices))
        if table is None:
            _ICON_TABLES.clear()  # one list at a time: the newest
            table = _ICON_TABLES[id(choices)] = dict(choices)
        icon = table.get(icon_id)
        if icon is None:  # a picture file outside the icon folders (playable_assets/…)
            from PySide6.QtGui import QIcon

            from .image_tools import icon_pixmap

            pixmap = icon_pixmap(getattr(self.library, "document", None), icon_id, 64)
            icon = None if pixmap is None else QIcon(pixmap)
        return icon

    def _shown(self, *_):
        icon = self.combo.itemIcon(self.combo.currentIndex())
        if icon is not None and not icon.isNull():
            side = min(self.preview.width(), self.preview.height()) - 8  # inside its frame
            self.preview.setPixmap(icon.pixmap(side, side))
        else:
            self.preview.setText("None")  # the frame says there is no picture yet
        self.combo.setToolTip(self.text())
        self.changed.emit()

    def _browse(self):
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(self, "Choose an icon", "", "Images (*.png)")
        if path and self.library is not None:
            icon_id = self.library.import_file(path)
            self._fill()
            self.setText(icon_id)

    def text(self):
        return str(self.combo.currentData() or "")

    def setText(self, value):  # noqa: N802 - Qt-style
        value = str(value or "").strip()
        index = QComboBox.findData(self.combo, value)  # the plain search: no full fill
        if index < 0:  # not listed yet (or hand-written data): added with its picture
            self._add(value, self._icon_of(value))
            index = self.combo.count() - 1
        self.combo.blockSignals(True)
        self.combo.setCurrentIndex(index)
        self.combo.blockSignals(False)
        self._shown()


class RecordForm(QWidget):
    """Widgets for one record described by a tuple of FormField specs."""

    changed = Signal()

    def __init__(
        self, fields, references, parent=None, *, column_width=250, icons=None, document=None
    ):
        super().__init__(parent)
        self.document = document  # whose project fills key drop-downs (currencies, stats)
        self.icons = icons  # an ``IconLibrary`` for icon fields (None: a plain editable list)
        self.column_width = column_width
        self.fields = tuple(fields)
        self.references = references
        self.widgets = {}
        self._original = {}
        self._loading = False  # set_data fills the widgets: no change to report
        # fields flow into as many columns as the width allows; groups and tables span the full
        # width
        self.grid = ResponsiveForm(self, column_width=self.column_width)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.grid)
        self._rows = {}  # field key -> its row in the grid (shown or hidden by ``when``)
        for f in self.fields:
            widget = self._build(f)
            self._watch(f, widget)
            self.widgets[f.key] = widget
            if f.kind in ("group", "table", "translations"):  # a caption, the box below it
                self._rows[f.key] = self.grid.add_row(f.label, widget, span=True, help_text=f.help)
            else:
                self._rows[f.key] = self.grid.add_row(
                    f.label,
                    widget,
                    help_text=f.help,
                    # tables and long text (a translation, a description) take a whole row
                    span=f.kind in ("amounts", "pairs", "ref_list", "multiline", "info", "formula")
                    or f.key in ("text", "description", "message", "detail"),
                )

        for key in {f.when[0] for f in self.fields if f.when}:
            control = self.widgets.get(key)
            if isinstance(control, QComboBox):
                control.currentIndexChanged.connect(self._show_when)
        self._show_when()

    def _show_when(self, *_args):
        """Show only the fields whose ``when`` the record's values meet (D96: a menu block
        shows the settings of its own kind)."""
        for f in self.fields:
            if not f.when:
                continue
            key, values = f.when
            control = self.widgets.get(key)
            value = control.currentData() if isinstance(control, QComboBox) else None
            self.grid.set_shown(self._rows[f.key], value in values)

    def _edited(self, *_args):
        if not self._loading:
            self.changed.emit()

    def _watch(self, f, widget):
        """Every edit of the field is reported (the page applies it on its own)."""
        signals = {
            "text": "textEdited",
            "multiline": "textChanged",
            "int": "valueChanged",
            "float": "valueChanged",
            "bool": "toggled",
            "choice": "currentIndexChanged",
            "ref": "currentIndexChanged",
            "optional_ref": "currentIndexChanged",
            "icon": "changed",
            "ref_list": "edited",
            "string_list": "edited",
            "amounts": "edited",
            "group": None,
            "table": "changed",
            "translations": "changed",
            "formula": "edited",
        }
        if f.kind == "optional_int":
            widget.check.toggled.connect(self._edited)
            widget.spin.valueChanged.connect(self._edited)
        elif f.kind == "pairs":
            widget.table.itemChanged.connect(self._edited)
        elif f.kind == "group":
            widget.form.changed.connect(self._edited)
        elif signals.get(f.kind):
            getattr(widget, signals[f.kind]).connect(self._edited)
        if isinstance(widget, (QSpinBox, QDoubleSpinBox, QComboBox)):
            from .record_form import _wheel_guard

            _wheel_guard(widget)  # scrolling the page leaves values alone

    def _vocabulary(self):
        from .record_vocabulary import vocabulary_for

        document = self.document or getattr(self.icons, "document", None)
        return vocabulary_for(document)

    def _noun(self, f):
        """What one entry of a list field is, for its "+ Add …" button: from what it refers to
        (an item, a stat, a quest), else from the field's own name."""
        from .record_vocabulary import map_source

        if "price" in f.key or "currenc" in f.key:
            return "currency"
        source = getattr(f, "source", None) or map_source(f.key) or ""
        nouns = {"items": "item", "stats": "stat", "resources": "resource", "quests": "quest",
                 "abilities": "skill", "equipment": "equipment", "enemies": "enemy",
                 "factions": "faction", "states": "state", "classes": "job",
                 "actors": "character", "currencies": "currency"}  # fmt: skip
        nouns.update({"progression_tracks": "track", "carry_parts": "part"})
        nouns.update({"stat_set_on": "record", "stat_columns": "column"})
        if source in nouns:
            return nouns[source]
        by_key = {"bonuses": "stat", "growth": "stat", "stat_growth": "stat", "stats": "stat",
                  "terms": "stat", "resource_growth": "resource", "resources": "resource",
                  "capacity_by_level": "level", "thresholds": "level",
                  "shared_gauges": "gauge", "required_capabilities": "capability"}  # fmt: skip
        if f.key in by_key:
            return by_key[f.key]
        word = f.label.split("(")[0].strip().split(" ")[-1].lower()
        for suffix, replacement in (("ies", "y"), ("ses", "s"), ("s", "")):
            if word.endswith(suffix) and len(word) > 3:
                return word[: -len(suffix)] + replacement
        return word or "entry"

    def _text_choices(self, key):
        """A text field that names something in the project (a currency, a stat, an enemy, a
        switch...) offers those names; anything else can still be typed."""
        from .record_vocabulary import Choice, words

        vocabulary = self._vocabulary()
        if vocabulary.project is None:
            return []
        source = _TEXT_SOURCES.get(key)
        if source is not None:
            out = []
            for part in source.split("+"):
                out.extend(vocabulary.choices(part))
            return out
        if key in _SWITCH_KEYS:
            used = set()
            for other in _SWITCH_KEYS:
                used.update(vocabulary.values_for(other))
            return [Choice(v, v) for v in sorted(used)]
        if key in _VALUE_KEYS:
            values = vocabulary.values_for(_VALUE_KEYS[key])
            return [Choice(v, words(v)) for v in values]
        return []

    def _reference_choices(self, f):
        from .record_vocabulary import Choice, map_source

        vocabulary = self._vocabulary()
        known = ("items", "actors", "enemies", "equipment", "classes", "abilities", "states",
                 "attachments", "passives", "encounters")  # fmt: skip
        if f.source in known and vocabulary.project is not None:
            return list(vocabulary.choices(f.source))  # names and icons
        if f.source == "goods" and vocabulary.project is not None:  # a shop's wares (D61)
            return [*vocabulary.choices("items"), *vocabulary.choices("equipment")]
        if f.source:
            out = []
            for entry in self.references(f.source):
                value, label = entry if isinstance(entry, tuple) else (entry, entry)
                out.append(Choice(str(value), str(label)))
            return out
        kind = map_source(f.key)
        return list(self._vocabulary().choices(kind)) if kind else []

    def _build(self, f):
        if f.kind == "info":  # worked out by the controller: read, never edited (D91)
            widget = QLabel()
            widget.setObjectName("FormInfo")
            widget.setWordWrap(True)
            # the inset as margins, not stylesheet padding: Qt counts margins when it works out
            # how tall the wrapped text is, so no line is cut off
            widget.setContentsMargins(10, 8, 10, 8)
            widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            return widget
        if f.kind == "id":
            widget = QLineEdit()
            widget.setReadOnly(True)
            return widget
        if f.kind == "formula":  # typed or built with buttons, the declared stats only (D94)
            from .formula_field import FormulaField

            return FormulaField(f.choices, self._vocabulary())
        if f.kind == "text":
            choices = self._text_choices(f.key)
            return _TextPicker(choices) if choices else QLineEdit()
        if f.kind == "multiline":
            widget = QPlainTextEdit()
            widget.setMaximumHeight(70)
            return widget
        if f.kind == "int":
            widget = QSpinBox()
            widget.setRange(-_BIG, _BIG)
            return widget
        if f.kind == "float":
            widget = _Decimal()
            widget.setRange(-_BIG, _BIG)
            widget.setDecimals(3)
            return widget
        if f.kind == "bool":
            return QCheckBox()
        if f.kind == "choice":
            from .record_vocabulary import words

            widget = QComboBox()
            for choice in f.choices:  # in words; the value written is the item's data
                widget.addItem(_choice_words(choice, words), choice)
            return widget
        if f.kind in ("ref", "optional_ref"):
            widget = QComboBox()
            if f.kind == "optional_ref":
                widget.addItem(f.empty_label, "")
            for choice in self._reference_choices(f):  # the name shows; the id is the data
                widget.addItem(str(choice.label), str(choice.value))
            return widget
        if f.kind == "icon":
            return _IconPicker(self.icons)
        if f.kind == "optional_int":
            box = QWidget()
            row = QHBoxLayout(box)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(12)  # the switch's text clear of the number box
            box.check = QCheckBox(f.toggle_label)
            # its whole text, always: squeezed, the text ran into the number box
            box.check.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            box.spin = QSpinBox()
            box.spin.setRange(0, _BIG)
            box.spin.setMinimumWidth(70)  # it narrows in a narrow column, not the gap
            box.check.toggled.connect(box.spin.setEnabled)
            row.addWidget(box.check)
            row.addWidget(box.spin, 1)
            return box
        if f.kind == "ref_list":
            from .record_form import ChipList

            return ChipList((), self._reference_choices(f), allow_new=False, noun=self._noun(f))
        if f.kind == "string_list":
            from .record_form import ChipList
            from .record_vocabulary import Choice, is_tag_field, tag_label

            vocabulary = self._vocabulary()
            words = vocabulary.tags() if is_tag_field(f.key) else ()
            names = vocabulary.names() if words else {}
            namer = (lambda t, n=names: tag_label(t, n)) if words else None
            choices = [Choice(t, tag_label(t, names)) for t in words]
            return ChipList((), choices, noun="tag" if words else self._noun(f), namer=namer)
        if f.kind == "amounts":
            from .record_form import AmountTable

            return AmountTable({}, self._reference_choices(f), noun=self._noun(f))
        if f.kind == "pairs":
            return _KeyValueTable(("Threshold", "Name"))
        if f.kind == "group":
            box = _Group(f.label)
            layout = QVBoxLayout(box)
            box.form = RecordForm(
                f.fields, self.references, icons=self.icons, document=self.document
            )
            layout.addWidget(box.form)
            return box
        if f.kind == "table":
            kind = _InlineTable if _flat(f.fields) else _TableField
            return kind(f.label, f.fields, self.references, icons=self.icons)
        if f.kind == "translations":
            from .translation_table import TranslationTable

            document = self.document or getattr(self.icons, "document", None)
            return TranslationTable(document)
        raise ValueError(f"unknown form field kind: {f.kind}")

    def set_data(self, data):
        self._loading = True
        try:
            self._fill(data)
        finally:
            self._loading = False
        self._show_when()

    def _fill(self, data):
        self._original = copy.deepcopy(data)
        for f in self.fields:
            widget, value = self.widgets[f.key], data.get(f.key, f.default)
            if f.kind in ("id", "text", "icon", "info", "formula"):
                widget.setText("" if value is None else str(value))
            elif f.kind == "multiline":
                widget.setPlainText(str(value or ""))
            elif f.kind == "int":
                widget.setValue(int(value or 0))
            elif f.kind == "float":
                widget.setValue(float(value or 0.0))
            elif f.kind == "bool":
                widget.setChecked(bool(value))
            elif f.kind == "choice":
                text = "" if value is None else str(value)
                if widget.findData(text) < 0:
                    widget.addItem(text, text)
                widget.setCurrentIndex(widget.findData(text))
            elif f.kind in ("ref", "optional_ref"):
                text = "" if value is None else str(value)
                if widget.findData(text) < 0:  # a reference that no longer exists stays visible
                    widget.addItem(f"{text} (missing)", text)
                widget.setCurrentIndex(widget.findData(text))
            elif f.kind == "optional_int":
                widget.check.setChecked(value is not None)
                widget.spin.setEnabled(value is not None)
                widget.spin.setValue(int(value or 0))
            elif f.kind in ("ref_list", "string_list"):
                widget.values = [str(v) for v in value or ()]
                widget._build()
            elif f.kind == "amounts":
                widget.values = {str(k): float(v) for k, v in dict(value or {}).items()}
                widget._build()
            elif f.kind == "pairs":
                widget.table.setRowCount(0)
                for t, n in value or ():
                    widget.add_row(f"{float(t):g}", n)
            elif f.kind == "group":
                widget.form.set_data(value or {})
            elif f.kind == "table":
                widget.set_rows(value or ())
            elif f.kind == "translations":  # the locale picks the engine's translation to offer
                widget.set_rows(value or (), locale=data.get("locale", ""))

    def data(self):
        out = copy.deepcopy(self._original)
        for f in self.fields:
            widget = self.widgets[f.key]
            if f.kind == "info":
                out.pop(f.key, None)  # worked out, not data
            elif f.kind == "formula":
                if not widget.valid():  # shown under the field; the page says not applied
                    raise GameSystemsAuthoringError(f"{f.label}: {widget.problem()}")
                out[f.key] = widget.text()
            elif f.kind in ("id", "text", "icon"):
                out[f.key] = widget.text().strip()
            elif f.kind == "multiline":
                out[f.key] = widget.toPlainText()
            elif f.kind in ("int", "float"):
                out[f.key] = widget.value()
            elif f.kind == "bool":
                out[f.key] = widget.isChecked()
            elif f.kind == "choice":
                value = widget.currentData()
                out[f.key] = widget.currentText() if value is None else str(value)
            elif f.kind in ("ref", "optional_ref"):
                value = widget.currentData()
                out[f.key] = widget.currentText() if value is None else str(value)
            elif f.kind == "optional_int":
                out[f.key] = widget.spin.value() if widget.check.isChecked() else None
            elif f.kind in ("ref_list", "string_list"):
                out[f.key] = list(widget.values)
            elif f.kind == "amounts":
                out[f.key] = {k: float(v) for k, v in widget.values.items()}
            elif f.kind == "pairs":
                out[f.key] = [[_number(t, n), n] for t, n in widget.rows()]
            elif f.kind == "group":
                out[f.key] = widget.form.data()
            elif f.kind in ("table", "translations"):
                out[f.key] = widget.values()
        return out


def _number(text, label):
    try:
        return float(text)
    except ValueError:
        raise GameSystemsAuthoringError(f"{label}: '{text}' is not a number") from None


class GameSystemsEditorWidget(QWidget):
    """Browse, create, duplicate, edit and delete game-system definitions."""

    changed = Signal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.kind_box = QComboBox()
        for kind in KINDS:
            self.kind_box.addItem(kind.label, kind.kind_id)
        self.kind_box.setProperty("decorate", True)  # kind icons (decor.py), as the hub combos
        fit_combo_to_items(self.kind_box)  # "Battle Extras (taunt, steal, TP...)" whole
        self.kind_box.currentIndexChanged.connect(self.refresh)
        self.browser = QListWidget()
        self.browser.setSelectionMode(QAbstractItemView.SingleSelection)
        self.browser.currentRowChanged.connect(self._selected)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setViewportMargins(0, 0, 10, 0)  # fields never touch the scroll bar
        self.form = None
        self._apply_timer = QTimer(self)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.setInterval(350)
        self._apply_timer.timeout.connect(self.auto_apply)
        self._unannounced = False
        self._editing = None
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.used_by = QLabel("")
        buttons = QHBoxLayout()
        for label, slot in (
            ("New…", self._new_clicked),
            ("Duplicate…", self._duplicate_clicked),
            ("Delete", self.delete_selected),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        # a gacha banner: draw 10,000 times and show the real spread (U5)
        self.simulate_button = QPushButton("Simulate 10,000 Pulls")
        self.simulate_button.clicked.connect(self.simulate_selected)
        buttons.addWidget(self.simulate_button)
        self.simulation = QLabel("")
        self.simulation.setWordWrap(True)
        self.simulation.setTextInteractionFlags(Qt.TextSelectableByMouse)
        buttons.addStretch(1)
        buttons.addWidget(UndoRedoButtons())  # edits apply on their own: a step back or on
        split = QSplitter()
        split.addWidget(authoring_sidebar("Game Systems", self.browser, header=self.kind_box))
        split.addWidget(self.scroll)
        split.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.addWidget(split, 1)
        layout.addWidget(self.used_by)
        layout.addWidget(self.simulation)
        layout.addWidget(self.status)
        layout.addLayout(buttons)
        self.refresh()

    @property
    def kind_id(self):
        return self.kind_box.currentData()

    def simulate_selected(self, pulls=10000):
        """Draw ``pulls`` times from the chosen banner (seed 0) and show each rarity's share,
        the most common prizes and how often the pity and the multi-pull guarantee decided."""
        if self.kind_id != "gacha_banners" or self.selected_id is None:
            return None
        self.flush_edits()
        try:
            result = self.controller.simulate_gacha(self.selected_id, pulls)
        except (GameSystemsAuthoringError, KeyError, ValueError) as exc:
            self.simulation.setText(str(exc))
            return None
        banner = self.controller.database.gacha_banners[self.selected_id]
        total = max(1, result["pulls"])
        rate = translate("{name} {share} (rate {chance})")
        rarities = "   ".join(
            rate.format(
                name=r.display_name,
                share=f"{result['rarity'].get(r.rarity_id, 0) / total:.2%}",
                chance=f"{chance:.2%}",
            )
            for r, chance, _p in reversed(banner.rates())
        )
        top = sorted(result["prize"].items(), key=lambda kv: -kv[1])[:5]
        prizes = ", ".join(f"{k} {v}" for k, v in top)
        first = translate("{pulls} pulls (seed 0):  {rarities}")
        second = translate(
            "Pity decided {pity}, the multi-pull guarantee {guaranteed}; longest run without"
            " the top rarity: {dry}.  Most drawn: {prizes}"
        )
        self.simulation.setText(
            first.format(pulls=f"{result['pulls']:,}", rarities=rarities)
            + "\n"
            + second.format(
                pity=result["pity"],
                guaranteed=result["guaranteed"],
                dry=result["longest_dry"],
                prizes=prizes,
            )
        )
        return result

    @property
    def selected_id(self):
        item = self.browser.currentItem()
        return None if item is None else item.data(Qt.UserRole)

    def _record_name(self, key, names):
        """A record as the list shows it: its name, else what it is about (a capture rule by
        its enemy), else its id in words."""
        from .record_vocabulary import words

        try:
            data = self.controller.form_data(self.kind_id, key, info=False)
        except (GameSystemsAuthoringError, KeyError, TypeError, ValueError):
            data = {}
        for field in ("display_name", "name", "label", "title"):
            if isinstance(data.get(field), str) and data[field].strip():
                return data[field]
        if "locale" in data:  # a language: its own name for itself, and its code
            entries = data.get("entries", ())
            own = next((e.get("text") for e in entries if e.get("key") == "language.name"), "")
            return f"{own}  ({key})" if own else str(key)
        return names.get(str(key)) or words(str(key).replace(".", " "))

    def set_kind(self, kind_id):
        self.kind_box.setCurrentIndex(self.kind_box.findData(kind_id))

    def refresh(self, select=None):
        current = select or self.selected_id
        if self.controller.document.project is None:
            self.browser.clear()
            from .ui_fit import swap_scroll_page

            swap_scroll_page(
                self.scroll, ProjectEmptyState("Open a project to edit game systems and settings.")
            )
            self.form = None
            return
        self.flush_edits()
        gacha = self.kind_id == "gacha_banners"
        self.simulate_button.setVisible(gacha)
        self.simulation.setVisible(gacha)
        if not gacha:
            self.simulation.setText("")
        self.form = RecordForm(
            FORMS[self.kind_id],
            self.controller.references,
            icons=self.controller.icon_library,
            document=self.controller.document,
        )
        self.form.changed.connect(self._apply_timer.start)
        from .ui_fit import swap_scroll_page

        swap_scroll_page(self.scroll, self.form)
        self.browser.blockSignals(True)
        self.browser.clear()
        ids = self.controller.ids(self.kind_id)
        from .record_vocabulary import vocabulary_for

        names = vocabulary_for(self.controller.document).names()
        for key in ids:  # the record's name; its id is the row's data and its tooltip
            item = QListWidgetItem(self._record_name(key, names))
            item.setData(Qt.UserRole, key)
            item.setToolTip(f"Internal ID: {key}")
            self.browser.addItem(item)
        self.browser.blockSignals(False)
        self.form.setEnabled(bool(ids))
        if ids:
            self.browser.setCurrentRow(ids.index(current) if current in ids else 0)
        else:
            self.used_by.setText("")

    def _selected(self, row):
        self.flush_edits()
        self.simulation.setText("")  # it was another banner's
        key = self.selected_id
        self._editing = key
        if key is None:
            return
        self.form.set_data(self.controller.form_data(self.kind_id, key))
        self.form.setEnabled(True)
        users = self.controller.where_used(self.kind_id, key)
        self.used_by.setText("Used by: " + ", ".join(users) if users else "")

    def _report(self, text, ok=True):
        self.status.setStyleSheet("" if ok else "color: #d9534f;")
        self.status.setText(text)

    def _attempt(self, action, message, select=None):
        try:
            action()
        except (GameSystemsAuthoringError, ValueError, TypeError, KeyError, AttributeError) as exc:
            self._report(str(exc), ok=False)
            return False
        self._report(message)
        self.changed.emit()
        self.refresh(select)
        return True

    def auto_apply(self):
        """Apply the form to the record being edited without rebuilding the page."""
        key = self._editing
        if key is None or self.form is None:
            return False
        try:
            self.controller.edit(self.kind_id, key, self.form.data())
        except (GameSystemsAuthoringError, ValueError, TypeError, KeyError) as exc:
            self._report("⚠  Not applied: " + str(exc), ok=False)
            return False
        self._report("")
        self._unannounced = True
        return True

    def flush_edits(self):
        if self._apply_timer.isActive():
            self._apply_timer.stop()
            self.auto_apply()
        if self._unannounced:
            self._unannounced = False
            self.changed.emit()

    def hideEvent(self, event):  # noqa: N802 - Qt API
        self.flush_edits()
        super().hideEvent(event)

    def apply(self):
        self._apply_timer.stop()
        key = self.selected_id
        if key is None:
            return False
        return self._attempt(
            lambda: self.controller.edit(self.kind_id, key, self.form.data()),
            f"Applied {key}",
            key,
        )

    def new_record(self, key):
        key = str(key).strip()
        return self._attempt(
            lambda: self.controller.create_new(self.kind_id, key), f"Created {key}", key
        )

    def duplicate_as(self, key):
        source = self.selected_id
        if source is None:
            return False
        key = str(key).strip()
        return self._attempt(
            lambda: self.controller.duplicate(self.kind_id, source, key),
            f"Duplicated as {key}",
            key,
        )

    def delete_selected(self):
        key = self.selected_id
        if key is None:
            return False
        return self._attempt(lambda: self.controller.delete(self.kind_id, key), f"Deleted {key}")

    def _new_clicked(self):
        kind = self.kind_id
        if kind == "capture_rules":
            choices = [
                x
                for x in self.controller.references("enemies")
                if x not in self.controller.ids(kind)
            ]
            key, ok = QInputDialog.getItem(self, "New Capture Rule", "Enemy:", choices, 0, False)
        else:
            from .authoring_hub_widget import _free_id

            noun = self.kind_box.currentText()
            key, ok = QInputDialog.getText(
                self,
                f"New - {noun}",
                "Internal ID - other records refer to it by this, so it stays fixed\n"
                "(lowercase letters, numbers and _; the name players see is set in the form):",
                text=_free_id("", self.controller.ids(kind), "new"),
            )
        if ok and str(key).strip():
            self.new_record(key)

    def _duplicate_clicked(self):
        if self.selected_id is None:
            return
        from .authoring_hub_widget import _free_id

        if self.kind_id == "capture_rules":  # a capture rule belongs to one enemy: pick another
            taken = self.controller.ids(self.kind_id)
            choices = [x for x in self.controller.references("enemies") if x not in taken]
            key, ok = QInputDialog.getItem(self, "Copy to Enemy", "Enemy:", choices, 0, False)
            if ok and str(key).strip():
                self.duplicate_as(key)
            return
        key, ok = QInputDialog.getText(
            self,
            "Duplicate",
            "Internal ID for the copy - other records refer to it by this, so it stays fixed\n"
            "(lowercase letters, numbers and _):",
            text=_free_id(self.selected_id, self.controller.ids(self.kind_id)),
        )
        if ok and key.strip():
            self.duplicate_as(key)
