"""D19 UI polish: drawn icons, button roles, labelled tabs and dock title bars."""

import pytest

pytest.importorskip("PySide6")


def test_every_icon_draws_something():
    from PySide6.QtWidgets import QApplication

    from asteria.editor.icons import DRAWINGS, icon, pixmap

    QApplication.instance() or QApplication([])
    for name in DRAWINGS:
        image = pixmap(name, 24, ratio=1.0).toImage()
        painted = sum(1 for x in range(0, 24, 2) for y in range(0, 24, 2) if image.pixelColor(x, y).alpha() > 0)
        assert painted >= 4, name
        assert not icon(name).isNull()
    assert icon("no-such-icon").isNull()


def test_button_and_label_rules():
    from asteria.editor.decor import button_style, label_icon

    assert button_style("Delete") == ("delete", "danger")
    assert button_style("Apply Changes") == ("apply", "primary")
    assert button_style("Run") == ("play", "success")
    assert button_style("+ Condition")[0] == "add"
    assert button_style("Frobnicate") == (None, "")
    assert label_icon("Animation States") == "state_machine"
    assert label_icon("Enemy AI") == "behavior_tree"
    assert label_icon("Enemies") == "enemy"
    assert label_icon("Skills") == "skill"


def test_editor_has_icons_roles_and_titled_docks():
    from PySide6.QtWidgets import QApplication, QDockWidget, QPushButton

    from asteria.editor.decor import decorate
    from asteria.editor.dock_title import DockTitleBar
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.theme import apply_asteria_theme

    app = QApplication.instance() or QApplication([])
    apply_asteria_theme(app)
    window = AsteriaEditorWindow()
    try:
        decorate(window)
        for dock in window.findChildren(QDockWidget):
            bar = dock.titleBarWidget()
            assert isinstance(bar, DockTitleBar), dock.objectName()
            assert bar.title.text() == dock.windowTitle() and not dock.windowIcon().isNull()
        window.problems_dock.setWindowTitle("Problems (3)")
        assert window.problems_dock.titleBarWidget().title.text() == "Problems (3)"
        for action in (window.scene_workspace_action, window.play_action, window.stop_action):
            assert not action.icon().isNull()
        roles = {b.text(): b.property("role") for b in window.findChildren(QPushButton)}
        assert roles.get("Delete") == "danger" and roles.get("Apply Changes") == "primary"
        assert all(not window.ui_workspace.tabIcon(i).isNull() for i in range(window.ui_workspace.count()))
    finally:
        window.close()
        window.deleteLater()
