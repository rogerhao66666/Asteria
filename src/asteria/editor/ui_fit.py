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
    data and in its tooltip, so the list reads like the game while the editor works on ids."""
    listing.clear()
    for key in ids:
        item = QListWidgetItem(namer(key) or str(key))
        item.setData(Qt.UserRole, key)
        item.setToolTip(f"Internal ID: {key}")
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
