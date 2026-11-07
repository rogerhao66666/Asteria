"""Small layout helpers shared by editor widgets."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QLayout,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionComboBox,
    QWidget,
)


def fit_combo_to_items(combo, *, cap=360):
    """Make ``combo`` wide enough for its longest item, its icon and its arrow (up to ``cap``),
    measured with the themed frame, so a chosen name is never cut off."""
    combo.ensurePolished()  # the themed font and padding, not the system ones
    option = QStyleOptionComboBox()
    combo.initStyleOption(option)
    field = combo.style().subControlRect(
        QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxEditField, combo
    )
    frame = combo.width() - field.width()  # padding, border and the arrow
    metrics = combo.fontMetrics()
    widest = max(
        (metrics.horizontalAdvance(combo.itemText(i)) for i in range(combo.count())),
        default=0,
    )
    # icons the decorator adds later ("decorate") take room as well
    if combo.property("decorate") or any(
        not combo.itemIcon(i).isNull() for i in range(combo.count())
    ):
        widest += combo.iconSize().width() + 6
    combo.setMinimumWidth(max(combo.minimumWidth(), min(cap, widest + frame + 2)))


def fit_combo_boxes(root, *, cap=260, padding=44):
    """Give every combo box under ``root`` the width of its longest item (up to ``cap``), so a
    chosen id is never cut off. Call it again after the items change."""
    for combo in root.findChildren(QComboBox):
        metrics = combo.fontMetrics()
        widest = max(
            (metrics.horizontalAdvance(combo.itemText(i)) for i in range(combo.count())),
            default=0,
        )
        combo.setMinimumWidth(min(cap, widest + padding))


def fit_list_to_width(view):
    """A list whose long ids shorten in the middle ("battle.com…crimson_warlord") instead of
    scrolling sideways; hovering an item shows its whole text."""
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    view.setItemDelegate(_ViewWidthDelegate(view))

    def add_tooltips(_parent, first, last):
        for row in range(first, last + 1):
            item = view.item(row)
            if item is not None and not item.toolTip():
                item.setToolTip(item.text())

    view.model().rowsInserted.connect(add_tooltips)
    add_tooltips(None, 0, view.count() - 1)


class _ViewWidthDelegate(QStyledItemDelegate):
    """Items no wider than the list, so a long one is elided in the middle (its distinct end
    stays) rather than scrolled to."""

    def initStyleOption(self, option, index):  # noqa: N802 - Qt API
        super().initStyleOption(option, index)
        option.textElideMode = Qt.ElideMiddle

    def sizeHint(self, option, index):  # noqa: N802 - Qt API
        size = super().sizeHint(option, index)
        size.setWidth(min(size.width(), max(1, self.parent().viewport().width() - 2)))
        return size


def fill_named(listing, ids, namer):
    """Fill a record list with names in words (``namer(id)``); each row keeps its id as its
    data, so the list reads like the game while the editor works on ids."""
    from asteria.editor.ui.i18n import translate

    listing.clear()
    for key in ids:
        item = QListWidgetItem(translate(namer(key) or str(key)))  # drawn as given
        item.setData(Qt.UserRole, key)
        listing.addItem(item)


def named_id(item):
    """The id behind a row filled by ``fill_named`` (a plain row: its text)."""
    if item is None:
        return None
    return item.data(Qt.UserRole) or item.text()


def layout_widgets(layout):
    """The widgets placed directly in ``layout``, in order.

    Found without ``layout.itemAt``: PySide gives every item ``itemAt`` returns a Python
    wrapper that the layout keeps alive. When Qt later deletes that item on its own (its widget
    is deleted, or moved to another layout) the wrapper still claims the freed address, and the
    next object Qt allocates there crashes the editor (a segfault far from the cause)."""
    owner = layout.parentWidget()
    if owner is None:
        return []
    found = [
        (layout.indexOf(widget), widget)
        for widget in owner.findChildren(QWidget, options=Qt.FindDirectChildrenOnly)
    ]
    return [widget for index, widget in sorted(found, key=lambda pair: pair[0]) if index >= 0]


def layout_children(layout):
    """The layouts nested directly in ``layout``, in order (without ``itemAt``, see
    ``layout_widgets``)."""
    found = [
        (layout.indexOf(child), child) for child in layout.children() if isinstance(child, QLayout)
    ]
    return [child for index, child in sorted(found, key=lambda pair: pair[0]) if index >= 0]


def _claim_item_wrappers(layout):
    """Every wrapper of an item in ``layout`` goes with ``layout``: ``itemAt`` moves it here."""
    for index in range(layout.count()):
        nested = layout.itemAt(index).layout()
        if nested is not None:
            _claim_item_wrappers(nested)


def retire_layout(layout):
    """Delete ``layout``, already taken out of the layout that held it, with its item wrappers.

    ``addLayout`` of a filled layout wraps every item in it and keeps the wrappers on the OUTER
    layout, which lives on. The items left here (a stretch, a spacing) are freed with this
    layout while their wrappers still claim the address; a widget Qt allocates there then comes
    back from Python as a QSpacerItem, and Python crashes (a segfault far from the cause)."""
    _claim_item_wrappers(layout)
    layout.deleteLater()


def swap_scroll_page(scroll, page):
    """Show ``page`` in ``scroll`` and retire the page it replaces safely: ``setWidget`` (or a
    ``takeWidget`` left to Python) frees the old page at once, even while a click on one of its
    buttons is still being handled - a use-after-free that crashes later. The old page is
    hidden, held and deleted once the event in hand is over."""
    old = scroll.takeWidget()
    scroll.setWidget(page)
    if old is not None and old is not page:
        old.hide()
        scroll._retired_page = old  # held (not a child, so it is never found among them)
        old.deleteLater()


class WordCombo(QComboBox):
    """A drop-down of engine values shown in words ("ease_in" reads "Ease In"); its API is
    the values': ``addItems``, ``currentText`` and ``setCurrentText`` take and give them."""

    def addItems(self, values):  # noqa: N802 - Qt API
        from asteria.editor.records.vocabulary import words

        for value in values:
            value = str(value)
            self.addItem(words(value), value)
            self.setItemData(self.count() - 1, value, Qt.ToolTipRole)

    def currentText(self):  # noqa: N802 - Qt API
        value = self.currentData()
        return super().currentText() if value is None else str(value)

    def setCurrentText(self, text):  # noqa: N802 - Qt API
        index = self.findData(str(text))
        if index >= 0:
            self.setCurrentIndex(index)
        else:
            super().setCurrentText(text)


class ValueCombo(WordCombo):
    """A drop-down of ``(value, words)``: ``currentText`` and ``setCurrentText`` take and give
    the value. A value not on the list (a name from older data) joins it rather than being
    lost. Editable, it also takes a name of the author's own; ``offer_new`` adds an entry that
    makes one with a click, ready to use as it is or to rename."""

    NEW = "\0new"  # the data of the entry that makes a new name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._new = None
        self.currentIndexChanged.connect(self._maybe_new)

    def offer_new(self, label, stem):
        self._new = (label, stem)

    def _maybe_new(self, _index=0):
        if self._new is None or self.currentData() != self.NEW:
            return
        taken = {self.itemData(i) for i in range(self.count())}
        stem, name, number = self._new[1], self._new[1], 1
        while name in taken:
            number += 1
            name = f"{stem}_{number}"
        self.setCurrentText(name)

    def set_choices(self, pairs, *, none=None):
        """The list, keeping the value held; ``none``: the words of the empty value."""
        held = self.currentText() if self.count() or self.isEditable() else ""
        held = "" if held == self.NEW else held
        self.blockSignals(True)
        self.clear()
        if none is not None:
            self.addItem(none, "")
        for value, shown in pairs:
            self.addItem(str(shown), str(value))
            self.setItemData(self.count() - 1, str(value), Qt.ToolTipRole)
        if self._new is not None:
            self.addItem(f"+ {self._new[0]}", self.NEW)
        if self.currentData() == self.NEW:  # nothing but that entry: it isn't made until clicked
            self.setCurrentIndex(-1)
        self.blockSignals(False)
        if held:
            self.setCurrentText(held)

    def currentText(self):  # noqa: N802 - Qt API
        if not self.isEditable():
            value = super().currentText()
            return "" if value == self.NEW else value
        shown = QComboBox.currentText(self).strip()
        found = self.findText(shown)
        value = str(self.itemData(found)) if found >= 0 else shown
        return "" if value == self.NEW else value

    def setCurrentText(self, text):  # noqa: N802 - Qt API
        from asteria.editor.records.vocabulary import words

        found = self.findData(str(text))
        if found < 0:
            at = self.findData(self.NEW)  # the entry that makes a new one stays last
            at = self.count() if at < 0 else at
            blocked = self.blockSignals(True)  # the entry moving down is not a click on it
            self.insertItem(at, words(text), str(text))
            self.blockSignals(blocked)
            found = at
        self.setCurrentIndex(found)


def pick_choice(parent, title, label, pairs):
    """One of ``pairs`` (``(value, name)``) chosen by its name in a small list; the value, or
    None when cancelled or there is nothing to choose."""
    from PySide6.QtWidgets import QInputDialog

    pairs = list(pairs)
    if not pairs:
        return None
    names = [name for _value, name in pairs]
    name, ok = QInputDialog.getItem(parent, title, label, names, 0, False)
    return pairs[names.index(name)][0] if ok and name in names else None
