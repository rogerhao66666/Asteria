"""Chip lists: the values of a list field as chips, added by picking (tags, ids, choices)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from asteria.editor.records.form_controls import (
    ElidedLabel,
    combo_text_width,
    hint_label,
    show_start,
    wheel_guard,
)
from asteria.editor.records.form_shapes import plural
from asteria.editor.records.vocabulary import (
    Choice,
)
from asteria.editor.ui.i18n import translate


class ChipList(QWidget):
    """A list of values as a table (as RPG Maker's Traits: a tag's kind and what it is, or a
    record's name and id), ✕ on a row removes it, Add opens a picker."""

    edited = Signal()
    ROW = 30  # a row's height (a drop-down fits): the table is as tall as its rows
    SPLIT = 8  # more rows than this: the list in two halves side by side
    TWO_HALVES_FROM = 640  # narrower, each half's drop-downs would be cut: one long list
    SECOND_LEAST = 140  # the room the column beside the first keeps, when narrow
    EFFECT_FROM = 270  # a narrower second column: a tag's drop-down, its words in a tooltip

    def __init__(
        self,
        values,
        choices,
        *,
        icons=None,
        allow_new=True,
        noun="entry",
        namer=None,
        meaning=None,
        detail=None,
    ):
        super().__init__()
        self.detail = detail  # a record row's second column in words, instead of its id
        self.namer = namer  # words for a value that is not a listed choice (a new tag)
        self.meaning = meaning  # a tag -> what carrying it does, beside its drop-downs
        self.values = [str(v) for v in values]
        self.choices = tuple(choices)
        self.icons = icons
        self.allow_new = allow_new
        self.noun = noun
        self.word = "property" if noun == "tag" else noun  # what the buttons call it
        self._labels = {c.value: c for c in self.choices}
        self._pending = False  # a new tag row waiting for its pick
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        self.table = QTableWidget(0, 3, self)
        self.table.setObjectName("FormListTable")
        second = "When" if detail else ""
        self.heads = ("Type", "Content") if noun == "tag" else (noun.title(), second)
        self.table.setHorizontalHeaderLabels([*self.heads, ""])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.ClickFocus)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.verticalHeader().setDefaultSectionSize(self.ROW)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.installEventFilter(self)
        self.table.wheelEvent = lambda event: event.ignore()  # the form scrolls, not it
        column.addWidget(self.table)
        self.empty = hint_label(f"No {plural(self.word)} yet.")
        column.addWidget(self.empty)
        add = QToolButton()
        add.setObjectName("FormAddChip")
        add.setText(f"+ Add {self.word}")
        add.clicked.connect(self._add)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addStretch(1)
        column.addLayout(row)
        self._build()

    def eventFilter(self, watched, event):  # noqa: N802 - Qt API: Delete removes the rows
        if (
            watched is self.table
            and event.type() == QEvent.KeyPress
            and event.key() in (Qt.Key_Delete, Qt.Key_Backspace)
        ):
            spots = {(i.row(), i.column() // 3) for i in self.table.selectedIndexes()}
            places = [band * self.table.rowCount() + row for row, band in spots]
            gone = {self.values[p] for p in places if p < len(self.values)}
            if gone:
                self.values = [v for v in self.values if v not in gone]
                self._build()
                self.edited.emit()
            return True
        return super().eventFilter(watched, event)

    def cells(self, value):
        """The row's two cells in words: a tag's kind and what it is; a record's name (and its
        detail, when the list has one)."""
        choice = self._labels.get(value)
        shown = choice.label if choice else (self.namer(value) if self.namer else value)
        if self.noun != "tag":
            return shown, (self.detail(value) if self.detail else "")
        head, mark, rest = shown.partition(": ")
        return (head, rest) if mark else ("Category", shown)

    def _groups(self):
        """``{type: [(value, content)]}`` of every tag on offer and in the list (the rows'
        drop-downs: a type, then a tag of that type)."""
        groups = {}
        for value in dict.fromkeys([*(c.value for c in self.choices), *self.values]):
            head, rest = self.cells(value)
            groups.setdefault(head, []).append((value, rest))
        return groups

    def _record_picker(self, row, base, value):
        """A record row's drop-down (a skill, an item…), with icons; typing narrows it.
        ``value`` None: the new row "+ Add" opened, kept out until one is picked."""
        box = QComboBox()
        box.setObjectName("FormRecordPick")
        box.setEditable(True)
        box.setInsertPolicy(QComboBox.NoInsert)
        wheel_guard(box)
        box.setFixedHeight(self.ROW - 2)
        if value is None:
            box.addItem(translate("Choose…"), None)

        taken = set(self.values) - {value}
        offered = [c for c in self.choices if c.value not in taken]
        if value is not None and value not in {c.value for c in offered}:
            offered.insert(0, self._labels.get(value) or Choice(value, self.cells(value)[0]))
        for choice in offered:
            icon = self.icons(choice.icon) if choice.icon and self.icons else None
            box.addItem(icon or QIcon(), translate(choice.label), choice.value)
            box.setItemData(box.count() - 1, choice.value, Qt.ToolTipRole)
        box.completer().setFilterMode(Qt.MatchContains)
        box.completer().setCompletionMode(QCompleter.PopupCompletion)
        box.setCurrentIndex(max(0, box.findData(value)) if value is not None else 0)
        show_start(box)

        def picked(_index=None):
            picked_value = box.currentData()
            typed = box.currentText().strip()
            if box.findText(typed) < 0 and typed and self.allow_new:
                picked_value = typed  # typed: a new value
            if not picked_value or picked_value == value or picked_value in self.values:
                return
            if value is None:
                self._pending = False
                self.add_values([picked_value])
            else:
                self.values[self.values.index(value)] = picked_value
                self._build()
                self.edited.emit()

        box.activated.connect(picked)
        self.table.setCellWidget(row, base, box)
        return box

    def _pickers(self, row, base, value, groups):
        """A tag row's two drop-downs: its type and, of that type, which tag. ``value`` None:
        the new row "+ Add tag" opened, kept out of the list until a tag is picked."""
        kind = QComboBox()
        kind.setObjectName("FormTagType")
        for head in sorted(groups, key=lambda h: (h != "Category", translate(h).lower())):
            kind.addItem(translate(head), head)
        content = QComboBox()
        content.setObjectName("FormTagContent")
        content.setEditable(self.allow_new)  # a new tag can be typed when the field allows
        for box in (kind, content):
            wheel_guard(box)
            box.setFixedHeight(self.ROW - 2)
        head = self.cells(value)[0] if value is not None else None
        kind.setCurrentIndex(max(0, kind.findData(head)) if head else 0)

        def fill(keep=None):
            content.blockSignals(True)
            content.clear()
            if keep is None:
                content.addItem(translate("Choose…"), None)
            taken = set(self.values) - {keep}
            for tag, shown in groups.get(kind.currentData(), ()):
                if tag not in taken:
                    content.addItem(translate(shown), tag)
                    content.setItemData(content.count() - 1, tag, Qt.ToolTipRole)
            content.setCurrentIndex(max(0, content.findData(keep)) if keep else 0)
            content.blockSignals(False)
            show_start(content)

        def picked(_index):
            tag = content.currentData()
            if tag is None and self.allow_new and content.currentText().strip():
                tag = content.currentText().strip()  # typed: a new tag
            if not tag or tag in self.values:
                return
            if value is None:
                self._pending = False
                self.add_values([tag])
            else:
                self.values[self.values.index(value)] = tag
                self._build()
                self.edited.emit()

        fill(value)
        kind.currentIndexChanged.connect(lambda _i: fill(None))
        content.activated.connect(picked)
        self.table.setCellWidget(row, base, kind)
        effect = self.meaning(value) if self.meaning and value is not None else ""
        if not effect:
            self.table.setCellWidget(row, base + 1, content)
            return content
        cell = QWidget()  # the pick, then what it does in plain words
        line = QHBoxLayout(cell)
        line.setContentsMargins(0, 0, 8, 0)
        line.setSpacing(12)
        content.setMinimumWidth(160)
        # its whole value (as decor gives every drop-down), then what the tag does: where the
        # words beside it have no room, a hover still says it
        content.setProperty("full_text_tip", True)
        content.setToolTip(f"{content.currentText()}\n{translate(effect)}")
        line.addWidget(content, 1)
        said = ElidedLabel(translate(effect))
        said.setObjectName("FormTagEffect")
        said.setToolTip(effect)
        line.addWidget(said, 2)
        self._effects.append(said)
        self.table.setCellWidget(row, base + 1, cell)
        return content

    def _bands(self):
        count = len(self.values) + (1 if self._pending else 0)
        if count <= self.SPLIT:
            return 1
        sized = self.testAttribute(Qt.WA_Resized)
        return 1 if sized and self.width() < self.TWO_HALVES_FROM else 2

    def _first_column_width(self):
        """The first column of each half: its usual width (more, when a name needs it); when
        narrow, as wide as its names need, so the column beside it keeps its room."""
        bands = self._bands()
        records = self.noun != "tag" and self.detail is not None
        usual = (320 if bands == 1 else 220) if records else (180 if bands == 1 else 120)
        if not self.testAttribute(Qt.WA_Resized):
            return usual
        need = self._first_column_need()
        room = self.width() // bands - 30 - self.SECOND_LEAST
        if max(usual, need) <= room:
            return max(usual, need)
        return max(90, min(need, room))

    def _first_column_need(self):
        """The width the first column's drop-downs need to show what they hold whole."""
        need = 0
        for first in range(0, self.table.columnCount(), 3):
            for row in range(self.table.rowCount()):
                box = self.table.cellWidget(row, first)
                if isinstance(box, QComboBox):
                    need = max(need, combo_text_width(box, box.currentText()))
        return need

    def _size_first_columns(self):
        first_width = self._first_column_width()
        for first in range(0, self.table.columnCount(), 3):
            self.table.setColumnWidth(first, first_width)
        # what a tag does, beside its drop-down, only where a few words of it fit (else its
        # drop-down's tooltip says it)
        second = self.width() // self._bands() - 30 - first_width
        sized = self.testAttribute(Qt.WA_Resized)
        for said in self._effects:
            said.setVisible(not sized or second >= self.EFFECT_FROM)

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if self._bands() != self.table.columnCount() // 3:
            self._build()
        elif event.size().width() != event.oldSize().width():
            self._size_first_columns()

    def _shape(self):
        """A long list (more than SPLIT rows) in two halves side by side, where the width holds
        them: half as tall."""
        count = len(self.values) + (1 if self._pending else 0)
        table, bands = self.table, self._bands()
        table.setColumnCount(3 * bands)
        table.setHorizontalHeaderLabels([*self.heads, ""] * bands)
        header = table.horizontalHeader()
        for band in range(bands):
            first = 3 * band
            names_only = self.noun != "tag" and self.detail is None  # the name fills the row
            header.setSectionResizeMode(
                first, QHeaderView.Stretch if names_only else QHeaderView.Interactive
            )
            header.setSectionResizeMode(first + 1, QHeaderView.Stretch)
            header.setSectionResizeMode(first + 2, QHeaderView.Fixed)
            header.resizeSection(first, self._first_column_width())
            header.resizeSection(first + 2, 30)
        rows = -(-count // bands)
        table.setRowCount(rows)
        return rows

    def _build(self):
        table = self.table
        table.clearContents()
        self._effects = []  # each row's words on what its tag does
        rows = self._shape()
        groups = self._groups() if self.noun == "tag" else None
        for index, value in enumerate(self.values):
            band, row = divmod(index, rows) if rows else (0, 0)
            base = 3 * band
            first, second = self.cells(value)
            left = QTableWidgetItem(translate(first))
            right = QTableWidgetItem(translate(second) if self.noun == "tag" else second)
            for item in (left, right):
                item.setToolTip(f"{self.noun.title()}: {value}")
            choice = self._labels.get(value)
            # a record row's drop-down shows its icon itself: none drawn again beneath it
            if groups is not None and choice is not None and choice.icon and self.icons:
                icon = self.icons(choice.icon)
                if icon is not None:
                    left.setIcon(icon)
            if self.noun != "tag":
                right.setForeground(QColor("#8b8e98"))  # the id, quieter than the name
            table.setItem(row, base, left)
            table.setItem(row, base + 1, right)
            remove = QToolButton()
            remove.setObjectName("FormRowRemove")
            remove.setText("✕")
            remove.setAutoRaise(True)
            remove.setToolTip(f"Remove {first if self.noun != 'tag' else second}")
            remove.clicked.connect(lambda _c=False, v=value: self._remove(v))
            table.setCellWidget(row, base + 2, remove)
            if groups is not None:  # a tag: its type, then which one, from lists
                self._pickers(row, base, value, groups)
            else:  # a record: picked from the list of them
                self._record_picker(row, base, value)
        if self._pending:
            index = len(self.values)
            band, row = divmod(index, rows) if rows else (0, 0)
            if groups is not None:
                self._pickers(row, 3 * band, None, groups).setFocus()
            else:
                self._record_picker(row, 3 * band, None).setFocus()
            cancel = QToolButton()  # a row not picked yet goes away as any other
            cancel.setObjectName("FormRowRemove")
            cancel.setText("✕")
            cancel.setAutoRaise(True)
            cancel.setToolTip("Remove")
            cancel.clicked.connect(self._cancel)
            table.setCellWidget(row, 3 * band + 2, cancel)
        if self.noun != "tag":
            for first in range(0, table.columnCount(), 3):
                # a record row is its name: no second column for the id
                table.setColumnHidden(first + 1, self.detail is None)
        if self.noun == "tag" or self.detail is not None:
            self._size_first_columns()  # the drop-downs are there now: what they need
        table.setVisible(bool(self.values) or self._pending)
        self.empty.setVisible(not self.values and not self._pending)
        table.setFixedHeight(table.horizontalHeader().height() + self.ROW * rows + 4)

    def _cancel(self):
        self._pending = False
        self._build()

    def _remove(self, value):
        self.values = [v for v in self.values if v != value]
        self._build()
        self.edited.emit()

    def _add(self):
        """A new row: its value picked from lists (a tag's type, then the tag; a record by
        name); nothing is added until then."""
        self._pending = True
        self._build()

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


def load_record_icon(document, icon_id):
    """A QIcon for an icon id (a project picture or ``forged:<kind>``); None if it can't load."""
    try:
        if icon_id.startswith("forged:"):
            from asteria.editor.assets.image_tools import forged_qicon

            return forged_qicon(icon_id)
        from asteria.editor.assets.image_tools import project_root

        path = Path(icon_id)
        if not path.is_absolute() and document is not None:
            path = project_root(document) / path
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            return QIcon(pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.FastTransformation))
    except Exception:  # noqa: BLE001 - a missing picture shows no icon
        pass
    return None
