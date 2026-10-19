"""Editor pages that scroll instead of growing the window.

A QTabWidget / QStackedWidget is as large as its largest page's minimum size, so one tall editor
(Character Composition) made the whole editor window taller than a laptop screen. Pages here sit
in a
resizable scroll area: they fill the space when it is large enough and scroll when it is not.

``ScrollingTabWidget`` keeps the page objects as the tab API sees them (``widget``,
``currentWidget``,
``indexOf``, ``setCurrentWidget`` take and return the page, not its scroll area), so callers do
not change.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QScrollArea,
    QStackedWidget,
    QStyle,
    QStyleOptionTabWidgetFrame,
    QTabWidget,
    QToolButton,
    QWidget,
)

from .flow_layout import FlowLayout


def scrollable(page, parent=None):
    """``page`` inside a borderless, resizable scroll area."""
    area = QScrollArea(parent)
    area.setObjectName(f"{page.objectName() or page.metaObject().className()}Scroll")
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setViewportMargins(0, 0, 6, 0)  # a gap between the page and its scroll bar
    area.setWidget(page)
    return area


class ScrollingTabWidget(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setUsesScrollButtons(
            True
        )  # macOS defaults to off: nine tab titles set the window's minimum width
        self.setElideMode(Qt.ElideNone)  # full titles; the bar scrolls instead of truncating them
        self._page_of = {}  # scroll area -> page
        self._area_of = {}  # page -> scroll area
        self.tabBar().installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self.tabBar() and event.type() == QEvent.Resize:
            # with ``self`` as the context the call is dropped once the widget is gone
            QTimer.singleShot(0, self, self._align_scroll_buttons)
        return super().eventFilter(watched, event)

    def _align_scroll_buttons(self):
        bar = self.tabBar()
        buttons = {button.objectName(): button for button in bar.findChildren(QToolButton)}
        left = buttons.get("ScrollLeftButton")
        right = buttons.get("ScrollRightButton")
        if left is None or right is None:
            return

        left.setArrowType(Qt.NoArrow)
        left.setText("‹")
        left.setToolButtonStyle(Qt.ToolButtonTextOnly)
        left.setToolTip("Show earlier tabs")
        right.setArrowType(Qt.NoArrow)
        right.setText("›")
        right.setToolButtonStyle(Qt.ToolButtonTextOnly)
        right.setToolTip("Show later tabs")

        button_width = min(left.width(), right.width(), bar.width() // 2)
        if button_width <= 0:
            return
        left.setGeometry(
            bar.width() - button_width * 2,
            left.y(),
            button_width,
            left.height(),
        )
        right.setGeometry(
            bar.width() - button_width,
            right.y(),
            button_width,
            right.height(),
        )
        left.raise_()
        right.raise_()

    def _schedule_scroll_button_alignment(self):
        QTimer.singleShot(0, self, self._align_scroll_buttons)

    def _wrap(self, page):
        area = scrollable(page, self)
        self._page_of[area] = page
        self._area_of[page] = area
        return area

    def addTab(self, page, *args):
        index = super().addTab(self._wrap(page), *args)
        self._schedule_scroll_button_alignment()
        return index

    def insertTab(self, index, page, *args):
        result = super().insertTab(index, self._wrap(page), *args)
        self._schedule_scroll_button_alignment()
        return result

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
        self._schedule_scroll_button_alignment()


class WrappingTabWidget(ScrollingTabWidget):
    """Tabs on as many rows as their titles need, so every page is one click away.

    A page with many tabs (Presentation has eleven) no longer hides some behind scroll arrows:
    the native tab bar stays for the tab API but is hidden, and a strip of checkable buttons
    above the page shows each tab's icon and title, wrapping to a new row when the page is
    narrow.
    """

    _GAP = 8  # between the tab strip and the page below it

    def __init__(self, parent=None):
        self._strip = self._stack = None
        super().__init__(parent)
        self._strip = QWidget(self)
        self._strip.setObjectName("WrappingTabStrip")
        self._strip_layout = FlowLayout(self._strip, spacing=4)
        self._buttons = QButtonGroup(self)
        self._buttons.setExclusive(True)
        self._buttons.idClicked.connect(self.setCurrentIndex)
        self.currentChanged.connect(self._check_current)
        self.tabBar().hide()
        self._stack = self.findChild(QStackedWidget)
        self._stack.installEventFilter(self)

    def eventFilter(self, watched, event):
        if (
            self._strip is not None
            and watched is self._stack
            and event.type() in (QEvent.Move, QEvent.Resize)
        ):
            self._place_strip()  # the tab widget laid its page out again: keep it below the strip
        return super().eventFilter(watched, event)

    def _rebuild_strip(self):
        if self._stack is None:
            return
        for button in self._buttons.buttons():
            self._buttons.removeButton(button)
            self._strip_layout.removeWidget(button)
            button.hide()  # off screen at once; Qt deletes it on the next event loop pass
            button.deleteLater()
        for index in range(self.count()):
            button = QToolButton(self._strip)
            button.setObjectName("WrappingTabButton")
            button.setText(self.tabText(index))
            button.setIcon(self.tabIcon(index))
            button.setToolTip(self.tabToolTip(index))
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            button.setCheckable(True)
            button.setChecked(index == self.currentIndex())
            self._buttons.addButton(button, index)
            self._strip_layout.addWidget(button)
        self._place_strip()

    def _check_current(self, index):
        button = self._buttons.button(index)
        if button is not None:
            button.setChecked(True)

    def _place_strip(self):
        option = QStyleOptionTabWidgetFrame()
        self.initStyleOption(option)
        area = self.style().subElementRect(QStyle.SE_TabWidgetTabContents, option, self)
        height = self._strip_layout.heightForWidth(area.width())
        strip = QRect(area.x(), area.y(), area.width(), height)
        page = area.adjusted(0, height + self._GAP, 0, 0)
        if self._strip.geometry() != strip:
            self._strip.setGeometry(strip)
        if self._stack.geometry() != page:
            self._stack.setGeometry(page)

    def tabInserted(self, index):
        super().tabInserted(index)
        self._rebuild_strip()

    def tabRemoved(self, index):
        super().tabRemoved(index)
        self._rebuild_strip()

    def setTabText(self, index, text):
        super().setTabText(index, text)
        self._rebuild_strip()

    def setTabIcon(self, index, icon):
        super().setTabIcon(index, icon)
        self._rebuild_strip()

    def setTabToolTip(self, index, tip):
        super().setTabToolTip(index, tip)
        self._rebuild_strip()
