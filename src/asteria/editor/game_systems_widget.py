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
from .project_empty_state import ProjectEmptyState
from .responsive_form import ResponsiveForm, ResponsiveSplit

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
        super().__init__(label, parent)
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
        buttons = QHBoxLayout()
        buttons.addWidget(add)
        buttons.addWidget(remove)
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


class _Group(QGroupBox):
    """A titled group of fields; sized by its plain minimum height (see ``_TableField``)."""

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
        super().__init__(label, parent)
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
        self.preview.setFixedSize(32, 32)
        self.preview.setAlignment(Qt.AlignCenter)
        self.combo = QComboBox()
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
        self.combo.blockSignals(True)
        self.combo.clear()
        self._add("")
        if self.library is not None:
            for icon_id, icon in self.library.choices():
                self._add(icon_id, icon)
        self.combo.blockSignals(False)

    def _shown(self, *_):
        icon = self.combo.itemIcon(self.combo.currentIndex())
        if icon is not None and not icon.isNull():
            self.preview.setPixmap(icon.pixmap(32, 32))
        else:
            self.preview.clear()
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
        index = self.combo.findData(value)
        if index < 0:  # an id the list does not know (hand-written data): keep it
            self._add(value)
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
        for f in self.fields:
            widget = self._build(f)
            self._watch(f, widget)
            self.widgets[f.key] = widget
            if f.kind in ("group", "table"):
                self.grid.add_wide(widget)
            else:
                self.grid.add_row(
                    f.label, widget, span=f.kind in ("amounts", "pairs", "ref_list", "multiline")
                )

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
        from .record_vocabulary import ProjectVocabulary

        document = self.document or getattr(self.icons, "document", None)
        return ProjectVocabulary(getattr(document, "project", None))

    def _reference_choices(self, f):
        from .record_vocabulary import Choice, map_source

        vocabulary = self._vocabulary()
        known = ("items", "actors", "enemies", "equipment", "classes", "abilities", "states",
                 "attachments", "passives", "encounters")  # fmt: skip
        if f.source in known and vocabulary.project is not None:
            return list(vocabulary.choices(f.source))  # names and icons
        if f.source:
            out = []
            for entry in self.references(f.source):
                value, label = entry if isinstance(entry, tuple) else (entry, entry)
                out.append(Choice(str(value), str(label)))
            return out
        kind = map_source(f.key)
        return list(self._vocabulary().choices(kind)) if kind else []

    def _build(self, f):
        if f.kind == "id":
            widget = QLineEdit()
            widget.setReadOnly(True)
            return widget
        if f.kind == "text":
            return QLineEdit()
        if f.kind == "multiline":
            widget = QPlainTextEdit()
            widget.setMaximumHeight(70)
            return widget
        if f.kind == "int":
            widget = QSpinBox()
            widget.setRange(-_BIG, _BIG)
            return widget
        if f.kind == "float":
            widget = QDoubleSpinBox()
            widget.setRange(-_BIG, _BIG)
            widget.setDecimals(3)
            return widget
        if f.kind == "bool":
            return QCheckBox()
        if f.kind == "choice":
            widget = QComboBox()
            widget.addItems(list(f.choices))
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
            box.check = QCheckBox(f.toggle_label)
            box.spin = QSpinBox()
            box.spin.setRange(0, _BIG)
            box.check.toggled.connect(box.spin.setEnabled)
            row.addWidget(box.check)
            row.addWidget(box.spin, 1)
            return box
        if f.kind == "ref_list":
            from .record_form import ChipList

            return ChipList((), self._reference_choices(f), allow_new=False, noun="entry")
        if f.kind == "string_list":
            from .record_form import ChipList
            from .record_vocabulary import Choice, is_tag_field, tag_label

            vocabulary = self._vocabulary()
            words = vocabulary.tags() if is_tag_field(f.key) else ()
            names = vocabulary.names() if words else {}
            namer = (lambda t, n=names: tag_label(t, n)) if words else None
            choices = [Choice(t, tag_label(t, names)) for t in words]
            return ChipList((), choices, noun="tag" if words else "entry", namer=namer)
        if f.kind == "amounts":
            from .record_form import AmountTable

            noun = "currency" if "price" in f.key or "currenc" in f.key else "entry"
            return AmountTable({}, self._reference_choices(f), noun=noun)
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
        raise ValueError(f"unknown form field kind: {f.kind}")

    def set_data(self, data):
        self._loading = True
        try:
            self._fill(data)
        finally:
            self._loading = False

    def _fill(self, data):
        self._original = copy.deepcopy(data)
        for f in self.fields:
            widget, value = self.widgets[f.key], data.get(f.key, f.default)
            if f.kind in ("id", "text", "icon"):
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
                if widget.findText(text) < 0:
                    widget.addItem(text)
                widget.setCurrentIndex(widget.findText(text))
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

    def data(self):
        out = copy.deepcopy(self._original)
        for f in self.fields:
            widget = self.widgets[f.key]
            if f.kind in ("id", "text", "icon"):
                out[f.key] = widget.text().strip()
            elif f.kind == "multiline":
                out[f.key] = widget.toPlainText()
            elif f.kind in ("int", "float"):
                out[f.key] = widget.value()
            elif f.kind == "bool":
                out[f.key] = widget.isChecked()
            elif f.kind == "choice":
                out[f.key] = widget.currentText()
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
            elif f.kind == "table":
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
        buttons.addStretch(1)
        buttons.addWidget(QLabel("Changes apply as you edit  ·  Ctrl+Z undoes"))
        split = QSplitter()
        split.addWidget(authoring_sidebar("Game Systems", self.browser, header=self.kind_box))
        split.addWidget(self.scroll)
        split.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.addWidget(split, 1)
        layout.addWidget(self.used_by)
        layout.addWidget(self.status)
        layout.addLayout(buttons)
        self.refresh()

    @property
    def kind_id(self):
        return self.kind_box.currentData()

    @property
    def selected_id(self):
        item = self.browser.currentItem()
        return None if item is None else item.text()

    def set_kind(self, kind_id):
        self.kind_box.setCurrentIndex(self.kind_box.findData(kind_id))

    def refresh(self, select=None):
        current = select or self.selected_id
        if self.controller.document.project is None:
            self.browser.clear()
            self.scroll.setWidget(
                ProjectEmptyState("Open a project to edit game systems and settings.")
            )
            self.form = None
            return
        self.flush_edits()
        self.form = RecordForm(
            FORMS[self.kind_id],
            self.controller.references,
            icons=self.controller.icon_library,
            document=self.controller.document,
        )
        self.form.changed.connect(self._apply_timer.start)
        self.scroll.setWidget(self.form)
        self.browser.blockSignals(True)
        self.browser.clear()
        ids = self.controller.ids(self.kind_id)
        self.browser.addItems(list(ids))
        self.browser.blockSignals(False)
        self.form.setEnabled(bool(ids))
        if ids:
            self.browser.setCurrentRow(ids.index(current) if current in ids else 0)
        else:
            self.used_by.setText("")

    def _selected(self, row):
        self.flush_edits()
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
        except (GameSystemsAuthoringError, ValueError, TypeError) as exc:
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
            key, ok = QInputDialog.getText(self, "New", "ID:")
        if ok and str(key).strip():
            self.new_record(key)

    def _duplicate_clicked(self):
        if self.selected_id is None:
            return
        key, ok = QInputDialog.getText(self, "Duplicate", "New ID:")
        if ok and key.strip():
            self.duplicate_as(key)
