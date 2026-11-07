"""Switching and refreshing the editor's workspaces and pages, and jumping to a problem, a
search result or a page."""

from __future__ import annotations

from pathlib import Path

from asteria.editor.project.commands import CommandTransaction
from asteria.editor.project.workspace import WorkspaceMode
from asteria.editor.ui.i18n import use_project

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication, QMainWindow
except ImportError:
    QApplication = None
    QMainWindow = object
    Qt = None
from asteria.authoring import run_authoring_script


class WorkspaceSwitchMixin:
    """Switching and refreshing workspaces and pages."""

    # defaults until something sets them (code may read them first)
    _refresh_epoch = 0
    _warm = None
    battle_workspace_action = None
    code_workspace_action = None
    event_workspace_action = None
    multiplayer_workspace_action = None
    panel_shortcuts = ()
    problems_widget = None
    rpg_workspace_action = None
    scene_workspace_action = None
    ui_workspace_action = None
    workspace = None

    def _warm_next_workspace(self):
        if not self._warm or self.document.project is None:
            return
        self._ensure_workspace_fresh(self._warm.pop(0), every_tab=True)
        if self._warm:
            QTimer.singleShot(150, self, self._warm_next_workspace)

    def _workspace_mode_changed(self, mode):
        current = WorkspaceMode(mode)
        for action, candidate in (
            (self.scene_workspace_action, WorkspaceMode.SCENE),
            (self.rpg_workspace_action, WorkspaceMode.RPG),
            (self.battle_workspace_action, WorkspaceMode.BATTLE),
            (self.ui_workspace_action, WorkspaceMode.UI),
            (self.event_workspace_action, WorkspaceMode.EVENT),
            (self.code_workspace_action, WorkspaceMode.CODE),
            (
                self.multiplayer_workspace_action,
                WorkspaceMode.MULTIPLAYER,
            ),
        ):
            if action is not None:
                action.setChecked(current == candidate)
        for shortcut in self.panel_shortcuts:  # P / T / L: Scene's keys
            shortcut.setEnabled(current == WorkspaceMode.SCENE)
        self.set_focus_mode(False)  # each workspace keeps its own panels
        self._switch_workspace_docks(current)
        # rebuilt only when something changed since it was last shown: switching back and
        # forth between Game Data and Battle no longer rebuilds every page each time
        self._ensure_workspace_fresh(current)

    def _rebuild_workspace(self, mode):
        """A workspace of one page."""
        if mode == WorkspaceMode.CODE:
            self.code_workspace.refresh_project_context()
            self._polish_presentation_pages(mode)
        elif mode == WorkspaceMode.BATTLE:
            self.battle_authoring.rebuild()
        elif mode == WorkspaceMode.MULTIPLAYER:
            self.multiplayer_workspace.refresh_profile()

    def _rebuild_page(self, name):
        page = getattr(self, name, None)
        if name in self._PAGES_WITHOUT_PROJECT:  # with no project: they say to open one
            page.rebuild()
        elif name == "game_flow_overview" or self.document.project is not None:
            if page is not None:
                page.refresh()

    def _ensure_workspace_fresh(self, mode, *, force=False, every_tab=False):
        """Rebuild what ``mode`` shows if the project changed (an edit, an undo, a refresh) since
        it was last built: of a workspace with tabs the tab on screen, or all of them
        (``every_tab``: none may wait, another project was opened)."""
        mode = WorkspaceMode(mode)
        stamp = (
            id(self.document.project),
            self.document.revision,
            self._refresh_epoch,
        )
        fresh = self._workspace_stamps
        tabs = getattr(self, self._WORKSPACE_TABS.get(mode, ""), None)
        if tabs is None:
            if force or fresh.get(mode) != stamp:
                self._rebuild_workspace(mode)
                fresh[mode] = stamp
            return
        shown = tabs.currentWidget()
        rebuilt = False
        for name in self._WORKSPACE_PAGES[mode]:
            if not every_tab and getattr(self, name, None) is not shown:
                continue
            if force or fresh.get(name) != stamp:
                self._rebuild_page(name)
                fresh[name] = stamp
                rebuilt = True
        if rebuilt and mode != WorkspaceMode.RPG:
            self._polish_presentation_pages(mode)

    def _workspace_tab_opened(self, mode):
        """A tab came to the front. In a workspace not on screen it waits until that one opens."""
        if self.workspace.mode == mode:
            self._ensure_workspace_fresh(mode)

    def _code_script_saved(self, path):
        self.statusBar().showMessage(f"Saved script {path}", 3000)

    def _run_authoring_script(self, source, filename):
        tx = CommandTransaction("Run Authoring Script")

        def apply(command):
            command.redo()
            tx.add(command)

        sel = self.document.selection
        result = run_authoring_script(
            source,
            self.document.project,
            execute=apply,
            filename=filename,
            selection_kind=sel.kind if not sel.multiple else "none",
            selection_value=sel.value if not sel.multiple else None,
        )
        self.code_workspace.show_result(result)
        if not result.success:
            tx.undo()
            message = result.stdout + result.diagnostic
            self.console.setText(message)
            self.code_workspace.jump_to_diagnostic(result.line, result.column)
            location = f" line {result.line}" if result.line is not None else ""
            self.statusBar().showMessage(f"Script failed{location} — changes rolled back", 5000)
            self.refresh_all()
            return

        if tx.commands:
            self.document.commands.record_applied(tx)
        self.console.setText(
            result.stdout.rstrip() if result.stdout else "Script completed successfully"
        )
        self.statusBar().showMessage("Script finished", 3000)
        self.refresh_all()

    def _refresh_game_systems(self):
        if self.document.project is None:
            return
        for name in (
            "game_systems_editor",
            "game_start_editor",
            "enemy_ai_editor",
            "behavior_tree_editor",
            "animation_editor",
            "state_machine_editor",
            "composition_editor",
            "action_timeline_editor",
            "vfx_editor",
            "event_flow_editor",
            "input_map_editor",
        ):
            editor = getattr(self, name, None)
            if editor is not None:
                editor.refresh()

    def _polish_presentation_pages(self, mode=None):
        """Inset titles and growing pages; only the workspace given (all when ``None``):
        walking every widget of every page on each refresh cost a tenth of a second."""
        from asteria.editor.ui.page_layout import polish_presentation_page

        if mode in (None, WorkspaceMode.UI):
            for index in range(self.ui_workspace.count()):
                polish_presentation_page(self.ui_workspace.widget(index))
        if mode in (None, WorkspaceMode.EVENT):
            for index in range(self.events_workspace.count()):
                polish_presentation_page(self.events_workspace.widget(index))
        if mode in (None, WorkspaceMode.CODE):
            polish_presentation_page(self.code_workspace)

    def refresh_all(self):
        project = getattr(self.document, "project", None)
        use_project(project)  # a renamed record, a new translation: read when next shown
        database = getattr(project, "rpg_database", None)
        if database is not None and set(database.doodads) != set(self.tile_palette._doodads):
            self.tile_palette.set_doodads(database.doodads)
        if self.problems_widget is not None:
            self.problems_widget.schedule_refresh()
        self.project_tree.refresh()
        self.refresh_asset_list()
        self.refresh_inspector()
        self._sync_scene_authoring_context()
        self._sync_event_context()
        # the page on screen is rebuilt now; the others when they are next opened
        self._refresh_epoch = self._refresh_epoch + 1
        workspace = self.workspace
        if workspace is not None:
            self._ensure_workspace_fresh(workspace.mode, force=True)
        self.viewport.refresh()
        if self.viewport.render_source is not None:
            self.tile_layers.set_tilemap(
                self.viewport.render_source.tilemap,
                self.viewport.tile_tools.active_layer,
            )
            self.tile_palette.set_layer(self.viewport.tile_tools.active_layer)
        self._refresh_actions()
        self._refresh_title()
        self.scene_tabs.sync(self.viewport.current_scene())

    def show_scene(self, scene):
        """Show ``scene`` on the map (a scene tab, the tabs' ▾ list)."""
        if scene is None or self.viewport.current_scene() is scene:
            return
        self.document.selection.set_single("scene", scene)
        self.refresh_all()
        QTimer.singleShot(0, self.viewport, self.viewport.frame_initial)

    def navigate_to_problem(self, problem):
        """Open the editor that owns ``problem.target`` and select the offending item (EDT-15)."""

        target = tuple(problem.target)
        if not target or self.document.project is None:
            return False
        kind = target[0]
        project = self.document.project
        if kind == "record":
            _, family, category_id, record_id = target
            mode, tabs, host = {
                "rpg": (WorkspaceMode.RPG, self.rpg_workspace, self.rpg_authoring),
                "battle": (WorkspaceMode.BATTLE, None, self.battle_authoring),
                "presentation": (WorkspaceMode.UI, self.ui_workspace, self.presentation_authoring),
            }[family]
            self.workspace.set_mode(mode)
            if tabs is not None:
                tabs.setCurrentWidget(host)
            host.rebuild()
            child = host.child
            index = child.category.findData(category_id)
            if index < 0:
                return False
            child.category.setCurrentIndex(index)
            child.search.clear()
            child.select_ids([record_id])
            return child.selected_ids == [record_id]
        if kind == "game_system":
            _, kind_id, record_id = target
            self.workspace.set_mode(WorkspaceMode.RPG)
            self.rpg_workspace.setCurrentWidget(self.game_systems_editor)
            return self.game_systems_editor.show_record(kind_id, record_id)
        if kind in ("scene", "entity"):
            scene = next((s for s in project.scenes() if s.id == target[1]), None)
            if scene is None:
                return False
            self.workspace.set_mode(WorkspaceMode.SCENE)
            value = scene if kind == "scene" else scene.get_entity(target[2])
            if value is None:
                return False
            self.document.selection.set_single(kind, value)
            self.refresh_all()
            return True
        if kind == "sprite":
            self.workspace.set_mode(WorkspaceMode.UI)
            self.ui_workspace.setCurrentWidget(self.animation_editor)
            self.animation_editor.refresh(sheet=target[1])
            return self.animation_editor.sheet == target[1]
        if kind == "sequence":
            self.workspace.set_mode(WorkspaceMode.UI)
            self.ui_workspace.setCurrentWidget(self.action_timeline_editor)
            self.action_timeline_editor.refresh(select=target[1])
            return self.action_timeline_editor.sequence_id == target[1]
        if kind == "combat":
            self.workspace.set_mode(WorkspaceMode.RPG)
            self.rpg_workspace.setCurrentWidget(self.combat_editor)
            self.combat_editor.show_kind(target[1])
            self.combat_editor.select_id(target[2])
            return self.combat_editor.record_id == target[2]
        if kind == "behavior_tree":
            self.workspace.set_mode(WorkspaceMode.RPG)
            self.rpg_workspace.setCurrentWidget(self.behavior_tree_editor)
            return True
        if kind == "script":
            self.workspace.set_mode(WorkspaceMode.CODE)
            self.code_workspace.open_script(Path(target[1]).name)
            return self.code_workspace.jump_to_diagnostic(target[2], None)
        return False

    def _focused_record_family(self):
        """The authoring record list that has keyboard focus, if any (record
        copy/cut/paste/delete)."""
        from asteria.editor.records.hub import AdapterFamilyWidget

        widget = QApplication.focusWidget()
        while widget is not None and not isinstance(widget, AdapterFamilyWidget):
            widget = widget.parentWidget()
        return widget

    def open_global_search(self, *, run=True):
        """The search over everything (⌘K); ``run=False`` returns it without waiting."""
        from asteria.editor.project.global_search import GlobalSearchDialog

        dialog = GlobalSearchDialog(self)
        if run:
            dialog.exec()
        return dialog

    def _open_action_timeline(self, sequence_id):
        self.workspace.set_mode(WorkspaceMode.UI)
        self.ui_workspace.setCurrentWidget(self.action_timeline_editor)
        self.action_timeline_editor.refresh(select=sequence_id)
        return self.action_timeline_editor.sequence_id == sequence_id

    def _open_animation_sheet(self, asset_id):
        self.workspace.set_mode(WorkspaceMode.UI)
        self.ui_workspace.setCurrentWidget(self.animation_editor)
        self.animation_editor.refresh(sheet=asset_id)
        return self.animation_editor.sheet == asset_id

    def open_pause_menu(self, entry=None):
        """Game Systems ▸ Pause Menu, on ``entry`` (Menu Screens ▸ Layout links to it, D98)."""
        self.workspace.set_mode(WorkspaceMode.RPG)
        self.rpg_workspace.setCurrentWidget(self.game_systems_editor)
        self.game_systems_editor.set_kind("pause_menu")
        self.game_systems_editor.pause.refresh(entry)
        return self.game_systems_editor.pause.selected

    def open_menu_layout(self, screen_id):
        """Presentation ▸ Menu Screens ▸ Layout, on ``screen_id`` (a menu page links to the
        screen it is drawn on, D98)."""
        self.workspace.set_mode(WorkspaceMode.UI)
        self.ui_workspace.setCurrentWidget(self.menu_layout_editor)
        return self.menu_layout_editor.show_screen(screen_id)
