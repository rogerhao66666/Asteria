"""Docks and layout of the main window: left tabs, panel switches, focus mode, default sizes,
saved layouts, theme and language."""

from __future__ import annotations

from asteria.editor.project.workspace import WorkspaceMode
from asteria.editor.ui.i18n import english

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import (
        QApplication,
        QDockWidget,
        QMainWindow,
        QProxyStyle,
        QStyle,
        QTabBar,
    )
except ImportError:
    QApplication = None
    QMainWindow = object
    Qt = None
from asteria.editor.ui.theme import apply_asteria_theme

if QApplication is not None:

    class DockTabStyle(QProxyStyle):  # the panels' tabs start at the left, as a strip
        def styleHint(self, hint, option=None, widget=None, returnData=None):
            if hint == QStyle.StyleHint.SH_TabBar_Alignment:
                return int(Qt.AlignmentFlag.AlignLeft)
            return super().styleHint(hint, option, widget, returnData)


class WindowLayoutMixin:
    """Docks and layout of the main window."""

    def _schedule_dock_tab_cleanup(self, *_):
        QTimer.singleShot(0, self, self.hide_stale_dock_tab_bars)

    def hide_stale_dock_tab_bars(self):
        """Drop dock tab bars Qt left behind.

        Qt 6 (QMainWindowLayout) keeps tab bars it made while tab groups were being tabified or a
        layout was restored; they stay visible listing an earlier subset of a group's docks (the
        duplicate "Assets / Console" strip). Hiding every dock tab bar and invalidating the layout
        lets Qt show again exactly the bars its layout still uses."""
        bars = [bar for bar in self.findChildren(QTabBar) if bar.parent() is self]
        icons = {dock.windowTitle(): dock.windowIcon() for dock in self.findChildren(QDockWidget)}
        for bar in bars:
            bar.setDrawBase(False)
            titles = {english(bar.tabText(index)) for index in range(bar.count())}
            if "Assets" in titles:
                bar.setObjectName("BottomPanelDockTabs")
            elif "Project" in titles:
                bar.setObjectName("LeftSceneDockTabs")
            if bar.objectName() == "LeftSceneDockTabs":
                # the panel switch above the panels is the strip; Qt's bar stays, as tall as
                # nothing, so the docks keep their tab group
                bar.setMaximumHeight(0)
                if not bar.property("_switch_synced"):
                    bar.setProperty("_switch_synced", True)
                    bar.currentChanged.connect(lambda _index: self._sync_panel_switches())
            if bar.objectName() in {"BottomPanelDockTabs", "LeftSceneDockTabs"}:
                if not isinstance(bar.style(), DockTabStyle):
                    # a QProxyStyle owns the style it wraps: give it its own base, made from
                    # the application style's name. Wrapping the shared application style
                    # deleted it with the window, and QApplication then crashed on exit.
                    style = DockTabStyle(QApplication.style().name())
                    style.setParent(self)
                    bar.setStyle(style)
            bar.setUsesScrollButtons(bar.objectName() != "LeftSceneDockTabs")
            bar.setElideMode(Qt.ElideNone)
            for index in range(bar.count()):
                if bar.tabText(index) in icons:
                    bar.setTabIcon(index, icons[bar.tabText(index)])
            bar.hide()
        self.layout().invalidate()
        return bars

    def _left_tab_bar(self):
        for bar in self.findChildren(QTabBar):
            titles = {english(bar.tabText(i)) for i in range(bar.count())}
            if bar.parent() is self and set(self.LEFT_TITLES) <= titles:
                return bar
        return None

    def current_left_tab(self, default="ProjectSceneDock"):
        """The object name of the left dock tab showing now (Project, Tiles or Layers)."""
        bar = self._left_tab_bar()
        if bar is None or bar.currentIndex() < 0:
            return default
        return self.LEFT_TITLES.get(english(bar.tabText(bar.currentIndex())), default)

    def show_left_tab(self, name):
        bar = self._left_tab_bar()
        if bar is None or str(name) not in self.LEFT_TITLES.values():
            return
        for index in range(bar.count()):
            if self.LEFT_TITLES.get(english(bar.tabText(index))) == str(name):
                bar.setCurrentIndex(index)
        self._sync_panel_switches()

    def show_left_panel(self, name):
        """Open one of the left panels (Project, Tiles, Layers) by its dock's object name: the
        panel switch's buttons and the P / T / L keys."""
        dock = self.findChild(QDockWidget, str(name))
        if dock is None:
            return
        dock.show()
        dock.raise_()
        self.show_left_tab(name)

    def _sync_panel_switches(self):
        current = self.current_left_tab()
        for switch in getattr(self, "panel_switches", ()):
            switch.sync(current)

    def _switch_workspace_docks(self, mode):
        states = self._workspace_dock_states
        previous = getattr(self, "_docks_mode", None)
        if previous == mode or not hasattr(self, "_default_dock_state"):
            self._docks_mode = mode
            return
        if previous is not None:
            states[previous] = self.saveState(self.LAYOUT_VERSION)
        self._docks_mode = mode
        if mode in states:
            self.restoreState(states[mode], self.LAYOUT_VERSION)
        elif mode != WorkspaceMode.SCENE:
            for name in self.WORKSPACE_HIDDEN_DOCKS:
                dock = self.findChild(QDockWidget, name)
                if dock is not None and not dock.isFloating():
                    dock.hide()
        self.hide_stale_dock_tab_bars()

    def set_focus_mode(self, on):
        """Fold away the panels on both sides - the docks left and right of the map, and a
        record page's list and preview (``sidePanel``) - or bring back the ones it folded."""
        from PySide6.QtWidgets import QWidget

        on = bool(on)
        hidden = self._focus_hidden
        if on == bool(hidden) and on == getattr(self, "_focus_on", False):
            return
        self._focus_on = on
        if on:
            sides = (Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea)
            for dock in self.findChildren(QDockWidget):
                if dock.isVisible() and not dock.isFloating():
                    if self.dockWidgetArea(dock) in sides:
                        hidden.append(dock)
            for panel in self.findChildren(QWidget):
                side = panel.property("sidePanel") or panel.objectName() == "AuthoringPreviewCard"
                if side and panel.isVisible():
                    hidden.append(panel)
            for widget in hidden:
                widget.hide()
        else:
            while hidden:
                widget = hidden.pop()
                try:
                    widget.show()
                except RuntimeError:  # deleted while folded (a page rebuilt)
                    pass
            self.hide_stale_dock_tab_bars()
        action = getattr(self, "focus_mode_action", None)
        if action is not None and action.isChecked() != on:
            action.blockSignals(True)
            action.setChecked(on)
            action.blockSignals(False)

    def _apply_default_dock_sizes(self):
        horizontal, widths, vertical, heights = self._default_dock_sizes
        self.resizeDocks(horizontal, widths, Qt.Horizontal)
        self.resizeDocks(vertical, heights, Qt.Vertical)

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_shown_once", False):
            self._shown_once = True
            # the left panel opens on Project: once the docks are laid out (a restored layout
            # picks its own tab while the window first appears), and again after a moment
            for delay in (0, 250):
                QTimer.singleShot(delay, self, lambda: self.show_left_tab("ProjectSceneDock"))
            if (
                not self._layout_restored
            ):  # dock sizes only apply once the window has its real size
                QTimer.singleShot(0, self, self._apply_default_dock_sizes)

    def set_language(self, name):
        """Switch the editor language live (English or Traditional Chinese) and remember it."""
        from asteria.editor.ui.i18n import set_language

        set_language(name)
        self.refresh_all()  # trees and forms built from the editor's words, built again
        if name in getattr(self, "language_actions", {}):
            self.language_actions[name].setChecked(True)
        if self.layout_settings is not None:
            self.layout_settings.setValue("editor/language", name)

    def set_theme(self, name):
        """Switch the editor palette live and remember it."""

        apply_asteria_theme(QApplication.instance(), name)
        if name in getattr(self, "theme_actions", {}):
            self.theme_actions[name].setChecked(True)
        if self.layout_settings is not None:
            self.layout_settings.setValue("editor/theme", name)

    def reset_layout(self):
        """Back to the default dock arrangement (every panel docked and visible)."""
        for dock in self.findChildren(QDockWidget):
            dock.setFloating(False)
            dock.show()
        self.restoreState(self._default_dock_state, self.LAYOUT_VERSION)
        self._apply_default_dock_sizes()
        self.hide_stale_dock_tab_bars()

    def restore_layout(self, settings):
        """Restore the window geometry and each workspace's dock layout saved when the editor
        last closed; the workspace shown now gets its layout at once, the others when opened."""
        self.layout_settings = settings
        geometry = settings.value("editor/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        states = self._workspace_dock_states
        for mode in WorkspaceMode:
            state = settings.value(f"editor/dock_state/{mode.value}")
            if state is not None:
                states[mode] = state
        # a layout saved before each workspace kept its own: it is the one of the workspace it
        # was saved in
        state = settings.value("editor/dock_state")
        saved_mode = settings.value("editor/dock_mode")
        if state is not None and saved_mode in {mode.value for mode in WorkspaceMode}:
            states.setdefault(WorkspaceMode(saved_mode), state)
        own = states.get(self.workspace.mode)
        restored = own is not None and self.restoreState(own, self.LAYOUT_VERSION)
        if own is not None and not restored:
            self.restoreState(self._default_dock_state, self.LAYOUT_VERSION)
        self._layout_restored = bool(restored)
        # the left panel always opens on Project, whichever tab the last session ended on
        QTimer.singleShot(0, self, lambda: self.show_left_tab("ProjectSceneDock"))
        self.hide_stale_dock_tab_bars()
        return restored

    def save_layout(self):
        settings = self.layout_settings
        settings.setValue("editor/geometry", self.saveGeometry())
        states = dict(self._workspace_dock_states)
        states[self.workspace.mode] = self.saveState(self.LAYOUT_VERSION)
        for mode, state in states.items():  # each workspace's own arrangement of panels
            settings.setValue(f"editor/dock_state/{WorkspaceMode(mode).value}", state)
        settings.setValue("editor/dock_state", states[self.workspace.mode])
        settings.setValue("editor/dock_mode", self.workspace.mode.value)

    def set_combat_boxes_visible(self, visible):
        self.viewport.show_combat_boxes = bool(visible)
        self.viewport.update()

    def _console_written(self):
        """The Console opens itself the first time something is written to it."""
        if not getattr(self, "_console_waits", False) or not self.console.toPlainText().strip():
            return
        self._console_waits = False
        dock = self.findChild(QDockWidget, "ConsoleDock")
        if dock is not None:
            dock.show()
            dock.raise_()
