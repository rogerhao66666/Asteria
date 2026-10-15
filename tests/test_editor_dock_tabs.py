"""D19: the editor never shows a duplicate dock tab strip (the stale "Assets / Console" bar Qt 6
leaves
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


def test_bottom_panel_tabs_have_a_dedicated_tab_bar_identity():
    from PySide6.QtWidgets import QApplication, QTabBar

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    try:
        window.show()
        _settle(app)
        assert window.documentMode()
        bars = [
            bar
            for bar in window.findChildren(QTabBar)
            if bar.parent() is window
            and bar.isVisible()
            and "Assets" in [bar.tabText(i) for i in range(bar.count())]
        ]
        assert len(bars) == 1
        assert bars[0].objectName() == "BottomPanelDockTabs"
        assert not bars[0].drawBase()
    finally:
        window.close()
        window.deleteLater()


def test_bottom_panel_tabs_remain_centered_in_their_original_position():
    from PySide6.QtWidgets import QApplication, QTabBar

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    try:
        window.resize(1440, 900)
        window.show()
        _settle(app)
        bar = next(
            bar
            for bar in window.findChildren(QTabBar)
            if bar.parent() is window
            and bar.isVisible()
            and "Assets" in [bar.tabText(i) for i in range(bar.count())]
        )
        first = bar.tabRect(0)
        last = bar.tabRect(bar.count() - 1)
        tab_center = (first.left() + last.right()) / 2
        assert abs(tab_center - bar.width() / 2) <= 1
    finally:
        window.close()
        window.deleteLater()


def test_scene_sidebar_tabs_have_a_dedicated_tab_bar_identity():
    from PySide6.QtWidgets import QApplication, QTabBar

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    try:
        window.show()
        _settle(app)
        bars = [
            bar
            for bar in window.findChildren(QTabBar)
            if bar.parent() is window
            and bar.isVisible()
            and "Project" in [bar.tabText(i) for i in range(bar.count())]
        ]
        assert len(bars) == 1
        assert bars[0].objectName() == "LeftSceneDockTabs"
        assert not bars[0].drawBase()
    finally:
        window.close()
        window.deleteLater()


def test_scene_sidebar_tabs_remain_centered_in_their_original_position():
    from PySide6.QtWidgets import QApplication, QTabBar

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    try:
        window.resize(1440, 900)
        window.show()
        _settle(app)
        bar = next(
            bar
            for bar in window.findChildren(QTabBar)
            if bar.parent() is window
            and bar.isVisible()
            and "Project" in [bar.tabText(i) for i in range(bar.count())]
        )
        first = bar.tabRect(0)
        last = bar.tabRect(bar.count() - 1)
        tab_center = (first.left() + last.right()) / 2
        assert abs(tab_center - bar.width() / 2) <= 1
    finally:
        window.close()
        window.deleteLater()


def test_dock_scroll_content_has_a_card_and_clearance_before_tabs():
    from PySide6.QtWidgets import QApplication, QFrame, QScrollArea

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    try:
        window.show()
        _settle(app)
        scroll = window.findChild(QScrollArea, "TilePaletteWidgetScroll")
        assert scroll is not None
        card = scroll.widget()
        assert isinstance(card, QFrame)
        assert card.objectName() == "DockContentCard"
        assert scroll.viewportMargins().bottom() >= 14
    finally:
        window.close()
        window.deleteLater()


def test_scene_dock_cards_share_a_square_inset_and_scroll_as_one_page():
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtWidgets import QApplication, QDockWidget, QFrame, QScrollArea

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    try:
        window.resize(1440, 900)
        window.show()
        _settle(app)
        expected = {
            "ProjectSceneDock": "ProjectTreeWidgetScroll",
            "TilePaletteDock": "TilePaletteWidgetScroll",
            "LayersDock": "TileLayersWidgetScroll",
        }
        cards = []
        viewports = []
        for dock_name, scroll_name in expected.items():
            dock = window.findChild(QDockWidget, dock_name)
            assert dock is not None
            dock.raise_()
            _settle(app)
            scroll = dock.findChild(QScrollArea, scroll_name)
            assert scroll is not None
            margins = scroll.viewportMargins()
            assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
                12,
                12,
                12,
                16,
            )
            assert scroll.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
            assert scroll.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded
            assert not scroll.verticalScrollBar().isVisible()
            card = scroll.widget()
            assert isinstance(card, QFrame)
            assert card.objectName() == "DockContentCard"
            cards.append(card)
            viewports.append(scroll.viewport())

        _settle(app)
        assert len({card.width() for card in cards}) == 1
        assert len({viewport.width() for viewport in viewports}) == 1

        window.findChild(QDockWidget, "TilePaletteDock").raise_()
        _settle(app)
        tile_scroll = window.findChild(QScrollArea, "TilePaletteWidgetScroll")
        tile_card = tile_scroll.widget()
        bar = tile_scroll.verticalScrollBar()
        assert bar.maximum() > 0
        initial_y = tile_card.mapTo(tile_scroll.viewport(), QPoint(0, 0)).y()
        bar.setValue(min(24, bar.maximum()))
        _settle(app)
        assert tile_card.mapTo(tile_scroll.viewport(), QPoint(0, 0)).y() < initial_y
    finally:
        window.close()
        window.deleteLater()


def test_debugger_actions_card_keeps_content_inside_its_frame():
    from PySide6.QtWidgets import QApplication, QGroupBox

    from asteria.editor.shell import AsteriaEditorWindow

    QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    try:
        actions = window.findChild(QGroupBox, "DebugActionsCard")
        assert actions is not None
        margins = actions.layout().contentsMargins()
        assert margins.left() >= 10
        assert margins.right() >= 10
    finally:
        window.close()
        window.deleteLater()


def test_debug_actions_frame_stays_in_view_and_scrolls_its_own_content():
    from PySide6.QtWidgets import QApplication, QGroupBox, QScrollArea

    from asteria.editor.debugger_widget import DebuggerWidget

    app = QApplication.instance() or QApplication([])
    widget = DebuggerWidget()
    try:
        widget.resize(900, 180)
        widget.show()
        _settle(app)
        actions = widget.findChild(QGroupBox, "DebugActionsCard")
        assert actions is not None
        assert actions.geometry().bottom() < widget.rect().bottom()
        scroll = actions.findChild(QScrollArea, "DebugActionsScroll")
        assert scroll is not None
        assert scroll.verticalScrollBar().maximum() > 0
    finally:
        widget.close()
        widget.deleteLater()


def test_debug_actions_frame_has_clearance_before_bottom_tabs():
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication, QDockWidget, QGroupBox, QTabBar

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    try:
        window.resize(1440, 900)
        window.show()
        _settle(app)
        dock = window.findChild(QDockWidget, "DebuggerDock")
        dock.raise_()
        _settle(app)
        tabs = next(
            bar
            for bar in window.findChildren(QTabBar)
            if bar.objectName() == "BottomPanelDockTabs" and bar.isVisible()
        )
        actions = dock.findChild(QGroupBox, "DebugActionsCard")
        action_bottom = actions.mapTo(window, QPoint(0, actions.height())).y()
        tabs_top = tabs.mapTo(window, QPoint(0, 0)).y()
        assert tabs_top - action_bottom >= 24
    finally:
        window.close()
        window.runtime_monitor.stop()
        window.deleteLater()


def test_scene_sidebar_tabs_stay_joined_and_visible_without_scroll_buttons():
    from PySide6.QtWidgets import QApplication, QTabBar

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    try:
        window.resize(1470, 800)
        window.show()
        _settle(app)
        bars = window.findChildren(QTabBar)
        bar = next(bar for bar in bars if bar.objectName() == "LeftSceneDockTabs")
        assert not bar.usesScrollButtons()
        assert bar.tabRect(bar.count() - 1).right() < bar.width()
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


@pytest.mark.parametrize("saved_mode", [None, "rpg"])
def test_non_scene_saved_layout_does_not_hide_scene_docks(tmp_path, saved_mode):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication, QDockWidget

    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.workspace import WorkspaceMode

    app = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "layout.ini"), QSettings.IniFormat)
    source = AsteriaEditorWindow()
    source.show()
    source.workspace.set_mode(WorkspaceMode.RPG)
    _settle(app)
    settings.setValue("editor/dock_state", source.saveState(source.LAYOUT_VERSION))
    if saved_mode is None:
        settings.remove("editor/dock_mode")
    else:
        settings.setValue("editor/dock_mode", saved_mode)
    settings.sync()
    source.close()
    _settle(app)

    target = AsteriaEditorWindow()
    try:
        assert not target.restore_layout(settings)
        target.show()
        _settle(app)
        for name in (
            "ProjectSceneDock",
            "TilePaletteDock",
            "LayersDock",
            "InspectorDock",
            "AssetsDock",
            "ConsoleDock",
        ):
            dock = target.findChild(QDockWidget, name)
            assert dock is not None and not dock.isHidden(), name
        groups = _visible_groups(target)
        assert any({"Project", "Tiles", "Layers"}.issubset(group) for group in groups)
    finally:
        target.close()
        target.deleteLater()
        source.deleteLater()


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
        assert (
            inspector.isVisible() and console.isVisible()
        )  # Scene keeps the Inspector and the bottom panels
        window.workspace.set_mode(WorkspaceMode.RPG)
        _settle(app)
        assert (
            not inspector.isVisible() and not console.isVisible()
        )  # the database uses the whole window
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
