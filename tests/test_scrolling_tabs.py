import pytest


def test_overflow_buttons_are_separate_and_scroll_in_their_arrow_direction():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel, QToolButton, QVBoxLayout, QWidget

    from asteria.editor.scrolling_tabs import ScrollingTabWidget

    app = QApplication.instance() or QApplication([])
    window = QWidget()
    tabs = ScrollingTabWidget(window)
    layout = QVBoxLayout(window)
    layout.addWidget(tabs)
    for index in range(12):
        tabs.addTab(QLabel(f"Page {index}"), f"Long Page {index}")
    window.resize(430, 140)
    window.show()
    app.processEvents()

    try:
        buttons = {
            button.objectName(): button for button in tabs.tabBar().findChildren(QToolButton)
        }
        left = buttons["ScrollLeftButton"]
        right = buttons["ScrollRightButton"]
        assert left.arrowType() == Qt.NoArrow
        assert right.arrowType() == Qt.NoArrow
        assert left.text() == "‹"
        assert right.text() == "›"
        assert left.geometry().right() < right.geometry().left()
        assert left.toolTip() == "Show earlier tabs"
        assert right.toolTip() == "Show later tabs"

        bar = tabs.tabBar()
        QTest.mouseClick(right, Qt.LeftButton)
        app.processEvents()
        assert any(bar.tabRect(i).x() < 0 for i in range(tabs.count()))

        QTest.mouseClick(left, Qt.LeftButton)
        app.processEvents()
        assert bar.tabRect(0).x() == 0
    finally:
        window.close()
        app.processEvents()


def test_rpg_presentation_and_event_pages_have_scoped_tab_bars():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    try:
        expected = (
            (window.rpg_workspace, "DatabaseWorkspaceTabs", "DatabaseWorkspaceTabBar"),
            (window.ui_workspace, "PresentationWorkspaceTabs", "PresentationWorkspaceTabBar"),
            (window.events_workspace, "EventsWorkspaceTabs", "EventsWorkspaceTabBar"),
        )
        for tabs, widget_name, bar_name in expected:
            assert tabs.objectName() == widget_name
            assert tabs.tabBar().objectName() == bar_name
    finally:
        window.close()
        app.processEvents()
