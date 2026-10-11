"""D19: the editor never shows a duplicate dock tab strip (the stale "Assets / Console" bar Qt 6 leaves
behind when a second dock group is tabified)."""

import pytest

pytest.importorskip("PySide6")


def _visible_groups(window):
    from PySide6.QtWidgets import QTabBar

    return [
        [bar.tabText(i) for i in range(bar.count())]
        for bar in window.findChildren(QTabBar)
        if bar.parent() is window and bar.count() and bar.isVisible()
    ]


def _settle(app):
    for _ in range(10):
        app.processEvents()


def test_every_dock_appears_in_exactly_one_visible_tab_strip():
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    try:
        window.resize(1280, 800)
        window.show()
        _settle(app)
        for _round in range(2):  # stays clean after a resize and after switching tabs
            groups = _visible_groups(window)
            titles = [t for g in groups for t in g]
            assert len(titles) == len(set(titles)), groups
            assert any("Console" in g for g in groups) and any("Assets" in g for g in groups)
            window.resize(1440, 900)
            window.findChild(type(window.problems_dock), "DebuggerDock").raise_()
            _settle(app)
    finally:
        window.close()
        window.deleteLater()


def test_dock_layout_persists_and_resets(tmp_path):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication, QDockWidget

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "layout.ini"), QSettings.IniFormat)
    names = lambda w: sorted(d.objectName() for d in w.findChildren(QDockWidget))  # noqa: E731
    first = AsteriaEditorWindow()
    assert all(names(first)), "every dock needs an objectName for saveState"
    assert len(set(names(first))) == len(names(first))
    assert not first.restore_layout(settings)  # nothing saved yet: default layout
    first.show()
    _settle(app)
    first.findChild(QDockWidget, "InspectorDock").hide()
    _settle(app)
    first.close()
    _settle(app)
    second = AsteriaEditorWindow()
    try:
        assert second.restore_layout(settings)
        second.show()
        _settle(app)
        inspector = second.findChild(QDockWidget, "InspectorDock")
        assert not inspector.isVisible()  # the closed panel stays closed
        second.reset_layout()
        _settle(app)
        assert inspector.isVisible()
        groups = _visible_groups(second)
        titles = [t for g in groups for t in g]
        assert len(titles) == len(set(titles)), groups
    finally:
        second.close()
        second.deleteLater()
        first.deleteLater()


def test_each_workspace_keeps_its_own_panels():
    from PySide6.QtWidgets import QApplication, QDockWidget

    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.workspace import WorkspaceMode

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    try:
        window.show()
        _settle(app)
        inspector = window.findChild(QDockWidget, "InspectorDock")
        console = window.findChild(QDockWidget, "ConsoleDock")
        assert inspector.isVisible() and console.isVisible()  # Scene keeps the Inspector and the bottom panels
        window.workspace.set_mode(WorkspaceMode.RPG)
        _settle(app)
        assert not inspector.isVisible() and not console.isVisible()  # the database uses the whole window
        console.show()  # the user opens the console in the Database workspace...
        window.workspace.set_mode(WorkspaceMode.SCENE)
        _settle(app)
        assert inspector.isVisible()
        window.workspace.set_mode(WorkspaceMode.RPG)
        _settle(app)
        assert console.isVisible() and not inspector.isVisible()  # ...and it stays open there
        assert window.rpg_workspace_action.text() == "Database"
        assert window.ui_workspace_action.text() == "Presentation"
    finally:
        window.close()
        window.deleteLater()
