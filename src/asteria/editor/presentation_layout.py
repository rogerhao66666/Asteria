"""Shared layout rules for the editor's authoring pages."""

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLayout,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTabWidget,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)


class _SectionHeightGuard(QObject):
    def __init__(self, group):
        super().__init__(group)
        self.adjusting = False
        group.installEventFilter(self)

    def fit(self):
        group = self.parent()
        layout = group.layout()
        if self.adjusting or layout is None:
            return
        self.adjusting = True
        try:
            # QGroupBox keeps a native title inset even after setTitle("").
            # The outer layout already supplies all padding for our inset heading.
            group.setContentsMargins(0, 0, 0, 0)
            height = max(
                layout.minimumSize().height(),
                layout.totalHeightForWidth(max(group.width(), 220)),
            )
            if group.minimumHeight() != height:
                group.setMinimumHeight(height)
        finally:
            self.adjusting = False

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Resize, QEvent.LayoutRequest):
            self.fit()
        return False


def polish_presentation_page(page):
    """Keep section titles inset and let long pages grow rather than crush their fields."""
    page.setProperty("presentationPage", True)
    for group in page.findChildren(QGroupBox):
        if group.property("presentationSection") or group.isCheckable():
            continue
        if not group.title() or group.layout() is None:
            continue
        title = group.title()
        group.setTitle("")
        group.setProperty("presentationSection", True)
        group.setAttribute(Qt.WA_StyledBackground, True)
        body = QWidget()
        body.setLayout(group.layout())
        body.layout().setContentsMargins(0, 0, 0, 0)
        body.layout().setSizeConstraint(QLayout.SetMinimumSize)
        outer = QVBoxLayout(group)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)
        short_title, separator, detail = title.partition(" (")
        if not separator:
            short_title, separator, detail = title.partition(" — ")
        heading = QLabel(short_title if separator else title)
        heading.setProperty("presentationHeading", True)
        heading.setWordWrap(True)
        outer.addWidget(heading)
        if separator:
            hint = QLabel(detail.removesuffix(")"))
            hint.setObjectName("MutedLabel")
            hint.setWordWrap(True)
            outer.addWidget(hint)
        outer.addWidget(body, 1)
        group._presentation_height_guard = _SectionHeightGuard(group)

    for form in page.findChildren(QFormLayout):
        if not form.property("stackFields"):
            form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(12)
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.LabelRole)
            if item is not None and isinstance(item.widget(), QLabel):
                item.widget().setWordWrap(True)

    for area in page.findChildren(QScrollArea):
        area.setFrameShape(QScrollArea.NoFrame)
        area.setViewportMargins(0, 0, 10, 0)
        area.setMinimumHeight(max(area.minimumHeight(), 220))

    for table in page.findChildren(QWidget):
        if not isinstance(table, (QTreeWidget, QTableWidget, QListWidget)):
            continue
        if table.maximumHeight() >= 140:
            table.setMinimumHeight(max(table.minimumHeight(), 140))
        table.setTextElideMode(Qt.ElideRight)
        header = getattr(table, "horizontalHeader", lambda: None)()
        if header is not None and not table.property("presentationHeaders"):
            table.setProperty("presentationHeaders", True)
            for column in range(table.model().columnCount()):
                text = str(table.model().headerData(column, Qt.Horizontal) or "")
                width = header.fontMetrics().horizontalAdvance(text) + 28
                header.resizeSection(column, max(header.sectionSize(column), width))

    for button in page.findChildren(QPushButton):
        button.setMinimumHeight(max(button.minimumHeight(), 28))
    for combo in page.findChildren(QComboBox):
        combo.setMinimumContentsLength(8)
        combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)

    for tabs in page.findChildren(QTabWidget):
        tabs.setProperty("presentationInnerTabs", True)
        tabs.tabBar().setProperty("presentationInnerTabs", True)

    for split in page.findChildren(QSplitter):
        split.setChildrenCollapsible(False)
        if split.orientation() != Qt.Horizontal or not split.count():
            continue
        # Pane wrappers must start on the same edge as adjacent views/cards.
        # Section cards and sidebars supply their own internal padding.
        split.setHandleWidth(12)
        for index in range(split.count()):
            pane = split.widget(index)
            pane_layout = pane.layout()
            if (
                pane_layout is not None
                and not isinstance(pane, QGroupBox)
                and not pane.property("presentationSidebar")
                and pane.objectName() not in ("AuthoringSidebarCard", "AuthoringPreviewCard")
            ):
                pane_layout.setContentsMargins(0, 0, 0, 0)
        sidebar = split.widget(0)
        layout = sidebar.layout()
        if layout is None or not layout.count() or not sidebar.findChildren(QListWidget):
            continue
        heading = layout.itemAt(0).widget()
        if not isinstance(heading, QLabel):
            continue
        sidebar.setProperty("presentationSidebar", True)
        sidebar.setAttribute(Qt.WA_StyledBackground, True)
        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(280)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        heading.setProperty("presentationHeading", True)
        heading.setWordWrap(True)

    # New properties must take effect even when the project rebuilt an already visible page.
    for widget in [page, *page.findChildren(QWidget)]:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
    for group in page.findChildren(QGroupBox):
        guard = getattr(group, "_presentation_height_guard", None)
        if guard is not None:
            guard.fit()
