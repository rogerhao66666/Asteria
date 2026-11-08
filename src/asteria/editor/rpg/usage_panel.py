"""The Game Systems "Usage" card drawn (D108): ``usage_model.Usage`` as a summary box, then a
section per heading with a row per kind of thing - its icon, what it is, how many records,
the range of their numbers, a button opening its page and one showing every record behind it.
The records, shown, are buttons too: each opens its own record.

Opening goes through the window's ``navigate_to_problem`` (the Problems list's targets), so
a row opens the same page a problem about it would.
"""

from __future__ import annotations

from html import escape
from types import SimpleNamespace

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from asteria.editor.rpg.usage_model import Usage
from asteria.editor.ui.flow_layout import FlowLayout
from asteria.editor.ui.i18n import translate
from asteria.editor.ui.icons import icon

ICONS = {  # a row's icon by what its records are
    "actor": "actor", "enemy": "enemy", "job": "class", "gear": "armor",
    "attachment": "item", "passive": "skill", "skill": "skill", "node": "flow",
    "track": "trophy", "record": "list", "rule": "battle",
}  # fmt: skip


class UsagePanel(QFrame):
    """Shows a ``Usage``; ``set_usage`` takes one (or the old plain words, or nothing)."""

    opened = Signal(tuple)  # a navigate target, as it is opened

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("UsagePanel")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self.usage = Usage()

    def text(self):
        return self.usage.text()

    def set_usage(self, usage):
        if not isinstance(usage, Usage):
            usage = Usage((str(usage),) if usage else ())
        self.usage = usage
        while self._layout.count():
            old = self._layout.takeAt(0).widget()
            if old is not None:  # gone now, not at the next event loop turn
                old.setParent(None)  # (the layout item forgets it here: ask it only once)
                old.deleteLater()
        if usage.summary:
            summary = QLabel("\n".join(usage.summary))
            summary.setObjectName("FormInfo")
            summary.setWordWrap(True)
            summary.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # wraps, not widens
            summary.setContentsMargins(10, 8, 10, 8)  # margins: counted in the wrapped height
            summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._layout.addWidget(summary)
        for section in usage.sections:
            self._layout.addWidget(self._section(section))

    def _section(self, section):
        box = QFrame()
        box.setObjectName("UsageSection")
        grid = QGridLayout(box)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(3)
        grid.setColumnStretch(2, 1)
        grid.setColumnMinimumWidth(0, 18)  # the step number or the icon
        title = QLabel(section.title)
        title.setObjectName("CardTitle")
        title.setWordWrap(True)
        title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        grid.addWidget(title, 0, 0, 1, 4)
        if not section.rows:
            empty = QLabel(section.empty)
            empty.setObjectName("CardHint")
            empty.setWordWrap(True)
            empty.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            grid.addWidget(empty, 1, 0, 1, 4)
        line = 1
        for number_, row in enumerate(section.rows, 1):
            line = self._row(grid, line, row, f"{number_}." if section.numbered else "")
        return box

    def _row(self, grid, line, row, step):
        mark = QLabel()
        if step:
            mark.setText(step)
            mark.setObjectName("UsageStep")
        else:
            mark.setPixmap(icon(ICONS.get(row.noun, "target")).pixmap(16, 16))
        grid.addWidget(mark, line, 0, Qt.AlignVCenter)
        what = QLabel(self._words(row))
        what.setWordWrap(True)
        what.setTextInteractionFlags(Qt.TextSelectableByMouse)
        what.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # wraps, never widens
        if row.page:
            what.setToolTip(row.page)
        grid.addWidget(what, line, 1, 1, 2)
        buttons = QWidget()
        side = QGridLayout(buttons)
        side.setContentsMargins(0, 0, 0, 0)
        side.setHorizontalSpacing(2)
        if row.opens():
            tip = translate("Open {0}").format(row.page or row.what)
            go = self._button("eye", tip)
            go.setObjectName("UsageOpen")
            go.clicked.connect(lambda _=False, target=row.opens(): self.open(target))
            side.addWidget(go, 0, 1)
        grid.addWidget(buttons, line, 3, Qt.AlignVCenter | Qt.AlignRight)
        if not row.links:
            return line + 1
        records = QWidget()  # filled the first time it is shown: a stat has a hundred skills
        records.hide()
        grid.addWidget(records, line + 1, 1, 1, 3)
        more = self._button("list", translate("Show every record"))
        more.setObjectName("UsageMore")
        more.setCheckable(True)
        more.toggled.connect(lambda shown, w=records, r=row: self._show_records(w, r, shown))
        side.addWidget(more, 0, 0)
        return line + 2

    def _words(self, row):
        """The row's sentence, then how many and the range, dimmed: one label, so a narrow
        window wraps it instead of widening the card."""
        numbers = " · ".join(x for x in (row.count(), row.span()) if x)
        if not numbers:
            return row.what
        dim = self.palette().color(QPalette.PlaceholderText).name()
        return (
            f"{escape(row.what)}&nbsp;&nbsp; <span style='color:{dim}; font-weight:600'>"
            f"{escape(numbers)}</span>"
        )

    def _button(self, icon_name, tip):
        """A small icon button; what it does is in its tool tip."""
        button = QToolButton()
        button.setIcon(icon(icon_name))
        button.setToolTip(tip)
        button.setAutoRaise(True)
        button.setCursor(Qt.PointingHandCursor)
        return button

    def _show_records(self, widget, row, shown):
        if shown and widget.layout() is None:
            flow = FlowLayout(widget, spacing=4)
            for link in row.links:
                button = QToolButton()
                button.setObjectName("UsageRecord")
                button.setText(link.text())
                button.setCursor(Qt.PointingHandCursor if link.target else Qt.ArrowCursor)
                button.setEnabled(bool(link.target))
                button.clicked.connect(lambda _=False, target=link.target: self.open(target))
                flow.addWidget(button)
        widget.setVisible(shown)

    def open(self, target):
        """Opens ``target`` in the editor window (when there is one around this panel)."""
        self.opened.emit(tuple(target))
        navigate = getattr(self.window(), "navigate_to_problem", None)
        if navigate is not None:
            navigate(SimpleNamespace(target=tuple(target)))


__all__ = ["ICONS", "UsagePanel"]
