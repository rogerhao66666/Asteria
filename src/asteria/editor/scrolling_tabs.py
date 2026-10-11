"""Editor pages that scroll instead of growing the window.

A QTabWidget / QStackedWidget is as large as its largest page's minimum size, so one tall editor
(Character Composition) made the whole editor window taller than a laptop screen. Pages here sit in a
resizable scroll area: they fill the space when it is large enough and scroll when it is not.

``ScrollingTabWidget`` keeps the page objects as the tab API sees them (``widget``, ``currentWidget``,
``indexOf``, ``setCurrentWidget`` take and return the page, not its scroll area), so callers do not change.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QScrollArea, QTabWidget


def scrollable(page, parent=None):
    """``page`` inside a borderless, resizable scroll area."""
    area = QScrollArea(parent)
    area.setObjectName(f"{page.objectName() or page.metaObject().className()}Scroll")
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setWidget(page)
    return area


class ScrollingTabWidget(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setUsesScrollButtons(True)  # macOS defaults to off: nine tab titles set the window's minimum width
        self.setElideMode(Qt.ElideNone)  # full titles; the bar scrolls instead of truncating them
        self._page_of = {}  # scroll area -> page
        self._area_of = {}  # page -> scroll area

    def _wrap(self, page):
        area = scrollable(page, self)
        self._page_of[area] = page
        self._area_of[page] = area
        return area

    def addTab(self, page, *args):
        return super().addTab(self._wrap(page), *args)

    def insertTab(self, index, page, *args):
        return super().insertTab(index, self._wrap(page), *args)

    def widget(self, index):
        area = super().widget(index)
        return self._page_of.get(area, area)

    def currentWidget(self):
        area = super().currentWidget()
        return self._page_of.get(area, area)

    def indexOf(self, page):
        return super().indexOf(self._area_of.get(page, page))

    def setCurrentWidget(self, page):
        super().setCurrentWidget(self._area_of.get(page, page))

    def removeTab(self, index):
        area = super().widget(index)
        page = self._page_of.pop(area, None)
        if page is not None:
            self._area_of.pop(page, None)
        super().removeTab(index)
