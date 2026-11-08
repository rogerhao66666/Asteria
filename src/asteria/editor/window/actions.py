"""The window's menus and toolbar actions: building them, enabling them for what is selected, the
title, and the Controls and About boxes."""

from __future__ import annotations

from asteria.editor.project.workspace import WorkspaceMode
from asteria.editor.ui.icons import icon as workspace_icon
from asteria.editor.ui.icons import switch_icon

try:
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QAction, QKeySequence
    from PySide6.QtWidgets import (
        QApplication,
        QDockWidget,
        QMainWindow,
        QMessageBox,
        QSizePolicy,
        QToolBar,
        QWidget,
    )
except ImportError:
    QApplication = None
    QMainWindow = object
    Qt = None
from asteria.editor.window.support import WORKSPACE_ICONS, draw_overflow_buttons


class WindowActionsMixin:
    """The window's menus and toolbar actions."""

    def _build_actions(self):
        self.menuBar().setNativeMenuBar(False)
        file_menu = self.menuBar().addMenu("&File")
        self.open_action = QAction("Open Project…", self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.open_action.triggered.connect(self.open_project)
        self.save_action = QAction("Save", self)
        self.save_action.setShortcut(QKeySequence.Save)
        self.save_action.triggered.connect(self.save_project)
        self.save_as_action = QAction("Save As…", self)
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.save_as_action.triggered.connect(self.save_project_as)
        self.new_template_action = QAction("New Project…", self)
        self.new_template_action.setShortcut("Ctrl+N")
        self.new_template_action.triggered.connect(self.new_from_template_dialog)
        file_menu.addAction(self.new_template_action)
        file_menu.addActions([self.open_action, self.save_action, self.save_as_action])
        file_menu.addSeparator()
        self.import_mv_action = QAction("Import RPG Maker MV Project…", self)
        self.import_mv_action.triggered.connect(self.import_mv_project_dialog)
        file_menu.addAction(self.import_mv_action)
        self.import_library_action = QAction("Import from Asset Library…", self)
        self.import_library_action.triggered.connect(lambda: self.import_from_asset_library())
        file_menu.addAction(self.import_library_action)
        self.export_action = QAction("Export Game…", self)
        self.export_action.triggered.connect(self.export_game_dialog)
        file_menu.addAction(self.export_action)

        edit = self.menuBar().addMenu("&Edit")
        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.triggered.connect(self.undo)
        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut(QKeySequence.Redo)
        self.redo_action.triggered.connect(self.redo)
        edit.addActions([self.undo_action, self.redo_action])
        edit.addSeparator()

        self.rename_action = QAction("Rename…", self)
        self.rename_action.setShortcut("F2")
        self.rename_action.triggered.connect(self.rename_selected)
        self.add_scene_action = QAction("Add Scene…", self)
        self.add_scene_action.triggered.connect(self.add_scene)
        self.delete_scene_action = QAction("Delete Scene", self)
        self.delete_scene_action.triggered.connect(self.delete_scene)
        self.set_startup_scene_action = QAction("Set as Startup Scene", self)
        self.set_startup_scene_action.triggered.connect(self.set_startup_scene)
        self.move_up_action = QAction("Move Up", self)
        self.move_up_action.setShortcut("Alt+Up")
        self.move_up_action.triggered.connect(lambda: self.move_selected(-1))
        self.move_down_action = QAction("Move Down", self)
        self.move_down_action.setShortcut("Alt+Down")
        self.move_down_action.triggered.connect(lambda: self.move_selected(1))
        self.add_entity_action = QAction("Add Entity…", self)
        self.add_entity_action.triggered.connect(self.add_entity)
        self.place_sheet_character_action = QAction("Place Character from Sprite Sheet…", self)
        self.place_sheet_character_action.triggered.connect(
            lambda: self.place_character_from_sheet()
        )
        self.actor_appearance_action = QAction("Set Actor Appearance…", self)
        self.actor_appearance_action.triggered.connect(lambda: self.set_actor_appearance())
        self.delete_action = QAction("Delete Selected", self)
        self.delete_action.setShortcut(QKeySequence.Delete)
        self.delete_action.triggered.connect(self.delete_selected)
        self.add_component_action = QAction("Add Component…", self)
        self.add_component_action.triggered.connect(self.add_component)
        self.copy_action = QAction("Copy Entity", self)
        self.copy_action.setShortcut(QKeySequence.Copy)
        self.copy_action.triggered.connect(self.copy_selected)
        self.cut_action = QAction("Cut Entity", self)
        self.cut_action.setShortcut(QKeySequence.Cut)
        self.cut_action.triggered.connect(self.cut_selected)
        self.paste_action = QAction("Paste Entity", self)
        self.paste_action.setShortcut(QKeySequence.Paste)
        self.paste_action.triggered.connect(self.paste_entity)
        self.duplicate_action = QAction("Duplicate Entity", self)
        self.duplicate_action.setShortcut("Ctrl+D")
        self.duplicate_action.triggered.connect(self.duplicate_selected)
        self.toggle_entity_enabled_action = QAction("Enable / Disable Entity", self)
        self.toggle_entity_enabled_action.setShortcut("Ctrl+E")
        self.toggle_entity_enabled_action.triggered.connect(self.toggle_selected_entity_enabled)
        for action in (
            self.rename_action,
            self.add_scene_action,
            self.delete_scene_action,
            self.set_startup_scene_action,
            self.move_up_action,
            self.move_down_action,
            self.add_entity_action,
            self.place_sheet_character_action,
            self.actor_appearance_action,
            self.add_component_action,
            self.cut_action,
            self.copy_action,
            self.paste_action,
            self.duplicate_action,
            self.toggle_entity_enabled_action,
            self.delete_action,
        ):
            edit.addAction(action)

        self.play_action = QAction("Run Project", self)
        self.play_action.setShortcut("F6")
        self.play_action.triggered.connect(self.play_project)
        self.stop_action = QAction("Stop", self)
        self.stop_action.setShortcut("Shift+F6")
        self.stop_action.triggered.connect(self.stop_play)
        self.reset_view_action = QAction("Reset View", self)
        self.reset_view_action.setShortcut("Ctrl+0")
        self.reset_view_action.triggered.connect(self.viewport.reset_view)
        view_menu = self.view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.reset_view_action)
        # both sides folded away for the map or the form alone; the same key brings them back
        self.focus_mode_action = QAction("Focus Mode", self, checkable=True)
        self.focus_mode_action.setShortcut("Ctrl+\\")
        self.focus_mode_action.setToolTip("Hide the panels on both sides (again: back)")
        self.focus_mode_action.toggled.connect(self.set_focus_mode)
        view_menu.addAction(self.focus_mode_action)
        self.search_action = QAction("Search Everything…", self)
        self.search_action.setShortcut("Ctrl+K")
        self.search_action.setToolTip("Find a page, a record, a scene or an entity by name or id")
        self.search_action.triggered.connect(self.open_global_search)
        view_menu.addAction(self.search_action)
        # back and forward through the jumps (a usage card's record, a problem, a search) (D108)
        self.back_action = QAction("Back", self)
        self.back_action.setShortcut("Ctrl+[")
        self.back_action.triggered.connect(self.go_back)
        self.forward_action = QAction("Forward", self)
        self.forward_action.setShortcut("Ctrl+]")
        self.forward_action.triggered.connect(self.go_forward)
        view_menu.addActions([self.back_action, self.forward_action])
        self._refresh_history_actions()
        # attack reach and hit areas of real-time combat: a debug view, off by default
        self.combat_boxes_action = QAction("Show Hit && Hurt Boxes", self, checkable=True)
        self.combat_boxes_action.setChecked(self.viewport.show_combat_boxes)
        self.combat_boxes_action.toggled.connect(self.set_combat_boxes_visible)
        view_menu.addAction(self.combat_boxes_action)
        panels_menu = view_menu.addMenu("Panels")  # reopen a closed dock
        for dock in self.findChildren(QDockWidget):
            panels_menu.addAction(dock.toggleViewAction())
        self._default_dock_state = self.saveState(self.LAYOUT_VERSION)
        self.reset_layout_action = QAction("Reset Layout", self)
        self.reset_layout_action.triggered.connect(self.reset_layout)
        view_menu.addAction(self.reset_layout_action)
        from PySide6.QtGui import QActionGroup

        from asteria.editor.ui.theme import CURRENT, PALETTES

        theme_menu = view_menu.addMenu("Theme")
        group = QActionGroup(self)
        self.theme_actions = {}
        for key, palette in PALETTES.items():
            action = QAction(palette.name, self, checkable=True)
            action.setChecked(CURRENT["palette"] is palette)
            action.triggered.connect(lambda checked=False, k=key: self.set_theme(k))
            group.addAction(action)
            theme_menu.addAction(action)
            self.theme_actions[key] = action

        from asteria.editor.ui.i18n import CURRENT as LANGUAGE
        from asteria.editor.ui.i18n import LANGUAGES

        language_menu = view_menu.addMenu("Language")
        group = QActionGroup(self)
        self.language_actions = {}
        for key, name in LANGUAGES.items():  # each named in its own language
            action = QAction(name, self, checkable=True)
            action.setChecked(LANGUAGE["language"] == key)
            action.triggered.connect(lambda checked=False, k=key: self.set_language(k))
            group.addAction(action)
            language_menu.addAction(action)
            self.language_actions[key] = action

        prefab_menu = self.menuBar().addMenu("&Prefab")
        self.create_prefab_action = QAction("Create Prefab from Selected Entity…", self)
        self.create_prefab_action.triggered.connect(lambda: self.create_prefab_from_selection())
        self.place_prefab_action = QAction("Place Prefab…", self)
        self.place_prefab_action.triggered.connect(lambda: self.place_prefab())
        self.apply_prefab_action = QAction("Apply Instance Changes to Prefab", self)
        self.apply_prefab_action.triggered.connect(lambda: self.apply_instance_to_prefab())
        self.revert_prefab_action = QAction("Revert Instance to Prefab", self)
        self.revert_prefab_action.triggered.connect(lambda: self.revert_instance_to_prefab())
        prefab_menu.addActions(
            [
                self.create_prefab_action,
                self.place_prefab_action,
                self.apply_prefab_action,
                self.revert_prefab_action,
            ]
        )

        run_menu = self.menuBar().addMenu("&Run")
        run_menu.addAction(self.play_action)
        self.play_scene_action = QAction("Run Current Scene", self)
        self.play_scene_action.setShortcut("Ctrl+F6")
        self.play_scene_action.triggered.connect(self.play_current_scene)
        run_menu.addAction(self.play_scene_action)
        self.play_selection_action = QAction("Play from Selection", self)
        self.play_selection_action.setShortcut("Shift+F5")
        self.play_selection_action.triggered.connect(self.play_from_selection)
        run_menu.addAction(self.play_selection_action)
        self.restart_play_action = QAction("Restart Play", self)
        self.restart_play_action.setShortcut("Ctrl+Shift+F5")
        self.restart_play_action.triggered.connect(self.restart_play)
        run_menu.addAction(self.restart_play_action)
        run_menu.addAction(self.stop_action)
        run_menu.addSeparator()
        run_menu.addAction(  # the game folder's own settings file, in a settings tree
            "Game Folder Settings…", lambda: self.menu_layout_editor.edit_game_folder_settings()
        )

        help_menu = self.menuBar().addMenu("&Help")
        self.controls_action = QAction("Controls and Shortcuts", self)
        self.controls_action.triggered.connect(self.show_controls)
        self.about_action = QAction("About Asteria", self)
        self.about_action.triggered.connect(self.show_about)
        help_menu.addActions([self.controls_action, self.about_action])
        toolbar = QToolBar("Run", self)
        toolbar.setObjectName("AsteriaRunToolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toolbar.setIconSize(QSize(18, 18))
        self.scene_workspace_action = QAction("Scene", self)
        self.rpg_workspace_action = QAction("Database", self)
        self.battle_workspace_action = QAction("Battle", self)
        self.ui_workspace_action = QAction("Presentation", self)
        self.event_workspace_action = QAction("Events", self)
        self.code_workspace_action = QAction("Code", self)
        self.multiplayer_workspace_action = QAction("Multiplayer", self)
        for action, mode in (
            (self.scene_workspace_action, WorkspaceMode.SCENE),
            (self.rpg_workspace_action, WorkspaceMode.RPG),
            (self.battle_workspace_action, WorkspaceMode.BATTLE),
            (self.ui_workspace_action, WorkspaceMode.UI),
            (self.event_workspace_action, WorkspaceMode.EVENT),
            (self.code_workspace_action, WorkspaceMode.CODE),
            (self.multiplayer_workspace_action, WorkspaceMode.MULTIPLAYER),
        ):
            action.setCheckable(True)
            action.triggered.connect(lambda checked=False, m=mode: self.workspace.set_mode(m))
            action.setIcon(switch_icon(WORKSPACE_ICONS[mode]))
            toolbar.addAction(action)
            toolbar.widgetForAction(action).setProperty("workspace", WORKSPACE_ICONS[mode])
        workspace_menu = self.view_menu.addMenu("Workspace")
        for number, action in enumerate(
            (
                self.scene_workspace_action,
                self.rpg_workspace_action,
                self.battle_workspace_action,
                self.ui_workspace_action,
                self.event_workspace_action,
                self.code_workspace_action,
                self.multiplayer_workspace_action,
            ),
            start=1,
        ):
            action.setShortcut(f"Ctrl+{number}")
            action.setToolTip(f"{action.text()} workspace (Ctrl+{number})")
            workspace_menu.addAction(action)
        # The toolbar switches workspaces; the workspace's own tab strip repeated the same seven
        # buttons
        # and took the central area's width, so it stays hidden.
        self.workspace.tabs.hide()
        # workspaces on the left, the run controls apart on the right (a stretch between)
        spacer = QWidget(toolbar)
        spacer.setObjectName("ToolbarSpacer")
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)
        self.play_action.setIcon(workspace_icon("play"))
        self.stop_action.setIcon(workspace_icon("stop"))
        self.reset_view_action.setIcon(workspace_icon("target"))
        self.play_action.setToolTip("Run Project (F6)")
        self.stop_action.setToolTip("Stop (Shift+F6)")
        self.reset_view_action.setToolTip("Reset View (Ctrl+0)")
        from asteria.editor.ui.icons import icon as _icon

        self.search_action.setIcon(_icon("search", "#c9ccd4"))
        self.search_action.setToolTip("Search Everything (Ctrl+K)")
        self.back_action.setIcon(_icon("back", "#c9ccd4"))
        self.forward_action.setIcon(_icon("forward", "#c9ccd4"))
        self.back_action.setToolTip("Back to where you jumped from (Ctrl+[)")
        self.forward_action.setToolTip("Forward again (Ctrl+])")
        toolbar.addAction(self.back_action)
        toolbar.addAction(self.forward_action)
        toolbar.addAction(self.search_action)
        toolbar.addAction(self.reset_view_action)
        toolbar.addSeparator()
        toolbar.addAction(self.play_action)
        toolbar.addAction(self.stop_action)
        toolbar.widgetForAction(self.play_action).setObjectName("PlayButton")
        for action, name in (
            (self.stop_action, "StopButton"),
            (self.reset_view_action, "ResetViewButton"),
            (self.search_action, "SearchButton"),
            (self.back_action, "BackButton"),
            (self.forward_action, "ForwardButton"),
        ):  # icon only: the tool tip names them
            button = toolbar.widgetForAction(action)
            button.setObjectName(name)
            button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.addToolBar(Qt.TopToolBarArea, toolbar)
        draw_overflow_buttons(toolbar, self.menuBar())
        self._refresh_actions()

    def show_controls(self):
        QMessageBox.information(
            self,
            "Asteria Controls and Shortcuts",
            "Scene Viewport\n"
            "• Click an object, then use arrow keys to move it by 1 unit.\n"
            "• Hold Shift with an arrow key to move it by 10 units.\n"
            "• Click empty space, then use arrow keys to move the view.\n"
            "• Two-finger drag pans the view.\n"
            "• Two-finger pinch zooms around the view center.\n"
            "• Command+0 resets the view.\n\n"
            "Project\n"
            "• Command+S saves.\n"
            "• Command+Z undoes; Command+Shift+Z redoes.\n"
            "• F2 renames the selected item.\n\n"
            "Play\n"
            "• F6 runs the Project from its canonical Game Start.\n"
            "• Ctrl+F6 runs the current scene for local testing.\n"
            "• Shift+F6 stops Play.\n"
            "• WASD or arrow keys move the player.\n"
            "• Escape closes the Preview window.",
        )

    def show_about(self):
        QMessageBox.about(
            self,
            "About Asteria",
            "Asteria Editor\nCanonical Phase 1–7 development build",
        )

    def _focus_changed(self, _old, _new):
        self._refresh_actions()

    def _refresh_actions(self):
        if not hasattr(self, "undo_action"):
            return
        self.undo_action.setEnabled(self.document.commands.can_undo)
        self.redo_action.setEnabled(self.document.commands.can_redo)
        self.undo_action.setText(
            "Undo"
            + (
                f" {self.document.commands.undo_label}"
                if self.document.commands.undo_label
                else ""
            )
        )
        self.redo_action.setText(
            "Redo"
            + (
                f" {self.document.commands.redo_label}"
                if self.document.commands.redo_label
                else ""
            )
        )

        project = self.document.project
        sel = self.document.selection
        self.save_action.setEnabled(project is not None)
        self.save_as_action.setEnabled(project is not None)
        self.rename_action.setEnabled(
            sel.kind in {"project", "scene", "entity"} and not sel.multiple
        )
        self.add_scene_action.setEnabled(project is not None)
        self.set_startup_scene_action.setEnabled(
            sel.kind == "scene" and not sel.multiple and sel.value is not None
        )
        self.move_up_action.setEnabled(
            sel.kind in {"scene", "entity"} and not sel.multiple and sel.value is not None
        )
        self.move_down_action.setEnabled(
            sel.kind in {"scene", "entity"} and not sel.multiple and sel.value is not None
        )
        self.delete_scene_action.setEnabled(
            sel.kind == "scene"
            and not sel.multiple
            and project is not None
            and len(project.scenes()) > 1
        )
        self.add_entity_action.setEnabled(sel.kind in {"scene", "entity"} and not sel.multiple)
        self.delete_action.setEnabled(
            sel.kind == "component"
            and not sel.multiple
            or sel.kind == "entity"
            and bool(sel.values)
        )
        self.add_component_action.setEnabled(sel.kind == "entity" and not sel.multiple)
        self.copy_action.setEnabled(sel.kind == "entity" and not sel.multiple)
        self.duplicate_action.setEnabled(sel.kind == "entity" and bool(sel.values))
        self.toggle_entity_enabled_action.setEnabled(
            sel.kind == "entity" and not sel.multiple and sel.value is not None
        )
        self.cut_action.setEnabled(sel.kind == "entity" and not sel.multiple)
        self.paste_action.setEnabled(
            self.document.clipboard.has_entity()
            and sel.kind in {"scene", "entity"}
            and not sel.multiple
        )
        if (
            self._focused_record_family() is not None
        ):  # the shortcuts act on the focused record list
            for action in (
                self.cut_action,
                self.copy_action,
                self.paste_action,
                self.delete_action,
            ):
                action.setEnabled(True)
        active = self.play_session is not None and self.play_session.active
        self.play_action.setEnabled(project is not None and not active)
        self.stop_action.setEnabled(active)

    def _refresh_title(self):
        name = self.document.project.name if self.document.project else "No Project"
        dirty = " *" if self.document.dirty else ""
        self.setWindowTitle(f"Asteria Editor — {name}{dirty}")
