import re
from pathlib import Path

from .code_workspace import CodeWorkspaceWidget
from .event_editor_widget import EventEditorWidget
from .inspector import build_inspector_fields
from .model import EditorDocument
from .playmode import PlayModeError, create_play_session
from .runtime_launcher import RuntimeLaunchError, launch_play_session
from .storage import EditorStorageError, load_document, save_document
from .workspace import EditorWorkspace, WorkspaceMode
from .integrated_authoring import IntegratedAuthoringControllers
from .authoring_hub_widget import FamilyHostWidget
from .game_flow_overview_widget import GameFlowOverviewWidget
from .project_workspace import ProjectWorkspaceController
from .playtest_profiles import PlaytestProfileLibrary
from .scene_editing_controller import SceneEditingController
from .event_authoring_controller import EventAuthoringController
from .starter_project import create_new_project

try:
    from PySide6.QtCore import QSettings, Qt, QTimer
    from PySide6.QtGui import QAction, QKeySequence
    from PySide6.QtWidgets import (
        QApplication,
        QDockWidget,
        QFileDialog,
        QInputDialog,
        QComboBox,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QTabBar,
        QTabWidget,
        QTextEdit,
        QToolBar,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    QApplication = None
    QMainWindow = object
    Qt = None

from asteria.authoring import run_authoring_script

from .animation_widget import AnimationWidget
from .authoring_context import animation_context
from .resource_resolver import EditorResourceError, resolve_project_resources
from .theme import apply_asteria_theme
from .tile_layers_widget import TileLayersWidget
from .tile_palette_widget import TilePaletteWidget
from .viewport_widget import SceneViewportWidget
from .widgets import InspectorWidget, ProjectTreeWidget


class AsteriaEditorWindow(QMainWindow):
    def __init__(self, project=None, component_registry=None):
        if QApplication is None:
            raise RuntimeError("PySide6 is required for Asteria Editor")
        super().__init__()
        self.document = EditorDocument(project, component_registry=component_registry)
        self.play_session = None
        self.runtime_process = None
        self.runtime_monitor = QTimer(self)
        self.runtime_monitor.setInterval(250)
        self.runtime_monitor.timeout.connect(self._poll_runtime_process)
        self.runtime_monitor.start()
        self.setWindowTitle("Asteria Editor")
        self.resize(1280, 800)

        self.viewport = SceneViewportWidget(self.document)
        self.code_workspace = CodeWorkspaceWidget(self.document, self)
        self.event_editor = EventEditorWidget(self)
        self.animation_widget = AnimationWidget(self)

        self.authoring_controllers = IntegratedAuthoringControllers(self.document)
        self.project_workspace_controller = ProjectWorkspaceController(self.document)
        self.playtest_profile_library = None

        self.rpg_authoring = FamilyHostWidget(
            "Character", self.authoring_controllers.rpg_categories, self
        )
        self.battle_authoring = FamilyHostWidget(
            "Battle Rules", self.authoring_controllers.battle_categories, self
        )
        self.presentation_authoring = FamilyHostWidget(
            "Battle Presentation", self.authoring_controllers.presentation_categories, self
        )
        self.runtime_ui_authoring = FamilyHostWidget(
            "Runtime RPG UI", self.authoring_controllers.runtime_ui_categories, self
        )

        self.ui_workspace = QTabWidget(self)
        self.ui_workspace.addTab(self.presentation_authoring, "Battle Presentation")
        self.ui_workspace.addTab(self.runtime_ui_authoring, "Runtime RPG UI")
        self.ui_workspace.addTab(self.animation_widget, "Animation")

        self.game_flow_overview = GameFlowOverviewWidget(self.document, self)
        self.events_workspace = QTabWidget(self)
        self.events_workspace.addTab(self.event_editor, "Event Program")
        self.events_workspace.addTab(self.game_flow_overview, "Field / Game Flow")

        self.workspace = EditorWorkspace(
            {
                WorkspaceMode.SCENE: self.viewport,
                WorkspaceMode.RPG: self.rpg_authoring,
                WorkspaceMode.BATTLE: self.battle_authoring,
                WorkspaceMode.UI: self.ui_workspace,
                WorkspaceMode.EVENT: self.events_workspace,
                WorkspaceMode.CODE: self.code_workspace,
            },
            self,
        )
        self.workspace.modeChanged.connect(self._workspace_mode_changed)
        self.setCentralWidget(self.workspace)

        self.project_tree = ProjectTreeWidget(self.document)
        left = QDockWidget("Scenes", self)
        left.setWidget(self.project_tree)

        self.tile_palette = TilePaletteWidget(self)
        self.palette_dock = QDockWidget("Tile Palette", self)
        self.palette_dock.setWidget(self.tile_palette)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.palette_dock)
        self.tile_palette.modeChanged.connect(self.viewport.set_tile_mode)
        self.tile_palette.tileSelected.connect(self.viewport.set_selected_tile)
        # Tile tools on top, scene tree stacked below (RPG Maker's layout:
        # assets above, map tree below) — not tabbed together, so the tree
        # never hides behind whichever tool tab was clicked last. The split
        # must happen before Layers is tabified onto the palette: splitting a
        # dock that is already in a tab group adds the new dock as another tab.
        self.splitDockWidget(self.palette_dock, left, Qt.Vertical)

        self.tile_layers = TileLayersWidget(self)
        self.layers_dock = QDockWidget("Layers", self)
        self.layers_dock.setWidget(self.tile_layers)
        self.tabifyDockWidget(self.palette_dock, self.layers_dock)
        self.palette_dock.raise_()

        self.scene_controller = SceneEditingController(
            self, self.document, self.viewport, self.tile_palette,
            self.tile_layers, self.animation_widget,
        )
        self.event_controller = EventAuthoringController(
            self, self.document, self.event_editor
        )

        self.tile_layers.layerSelected.connect(self.scene_controller._select_tile_layer)
        self.tile_layers.addRequested.connect(self.scene_controller._add_tile_layer)
        self.tile_layers.removeRequested.connect(self.scene_controller._remove_tile_layer)
        self.tile_layers.moveRequested.connect(self.scene_controller._move_tile_layer)
        self.tile_layers.visibilityChanged.connect(self.scene_controller._set_tile_layer_visible)
        self.tile_layers.collisionChanged.connect(self.scene_controller._set_tile_layer_collision)

        self.event_editor.bindingRequested.connect(self.event_controller._event_add_binding)
        self.event_editor.bindingChanged.connect(self.event_controller._event_binding_changed)
        self.event_editor.addConditionRequested.connect(self.event_controller._event_add_condition)
        self.event_editor.addCommandRequested.connect(self.event_controller._event_add_command)
        self.event_editor.removeCommandRequested.connect(self.event_controller._event_remove_command)
        self.event_editor.moveCommandRequested.connect(self.event_controller._event_move_command)
        self.code_workspace.saved.connect(self._code_script_saved)
        self.code_workspace.runRequested.connect(self._run_authoring_script)

        self.inspector = InspectorWidget(self.document)
        right = QDockWidget("Inspector", self)
        right.setWidget(self.inspector)
        self.addDockWidget(Qt.RightDockWidgetArea, right)

        self.asset_list = QListWidget()
        self.asset_list.currentRowChanged.connect(self._asset_selected)
        bottom = QDockWidget("Assets", self)
        bottom.setWidget(self.asset_list)
        self.addDockWidget(Qt.BottomDockWidgetArea, bottom)

        console_panel = QWidget()
        console_panel.setObjectName("ConsolePanel")
        console_layout = QVBoxLayout(console_panel)
        console_layout.setContentsMargins(10, 10, 10, 10)

        self.console = QTextEdit()
        self.console.setObjectName("ConsoleOutput")
        self.console.setReadOnly(True)
        self.console.setAcceptRichText(False)
        console_layout.addWidget(self.console)

        console = QDockWidget("Console", self)
        console.setWidget(console_panel)
        self.addDockWidget(Qt.BottomDockWidgetArea, console)
        self.tabifyDockWidget(bottom, console)

        # The native macOS tab base draws a redundant rounded line behind
        # tabified docks. Individual tabs retain their own visual states.
        for dock_tabs in self.findChildren(QTabBar):
            dock_tabs.setDrawBase(False)

        self.resizeDocks([self.palette_dock, left], [320, 240], Qt.Vertical)
        self.resizeDocks([left, right], [280, 300], Qt.Horizontal)
        self.resizeDocks([bottom], [160], Qt.Vertical)

        self._build_actions()
        self._load_playtest_profiles()
        self._workspace_mode_changed(self.workspace.mode.value)
        self.refresh_all()
        QTimer.singleShot(0, self.viewport.reset_view)

    def _workspace_mode_changed(self, mode):
        current = WorkspaceMode(mode)
        is_scene = current == WorkspaceMode.SCENE
        self.palette_dock.setVisible(is_scene)
        self.layers_dock.setVisible(is_scene)
        self.view_toolbar.setVisible(is_scene)
        if current == WorkspaceMode.CODE:
            self.code_workspace.refresh_project_context()
        elif current == WorkspaceMode.RPG:
            self.rpg_authoring.rebuild()
        elif current == WorkspaceMode.BATTLE:
            self.battle_authoring.rebuild()
        elif current == WorkspaceMode.UI:
            self.presentation_authoring.rebuild()
            self.runtime_ui_authoring.rebuild()
        elif current == WorkspaceMode.EVENT:
            self.game_flow_overview.refresh()

    def _code_script_saved(self, path):
        self.statusBar().showMessage(f"Saved script {path}", 3000)

    def _run_authoring_script(self, source, filename):
        from .commands import CommandTransaction

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
        if not result.success:
            tx.undo()
            message = result.stdout + result.diagnostic
            self.console.setText(message)
            self.code_workspace.jump_to_diagnostic(result.line, result.column)
            location = f" line {result.line}" if result.line is not None else ""
            self.statusBar().showMessage(
                f"Script failed{location} — changes rolled back", 5000
            )
            self.refresh_all()
            return

        if tx.commands:
            self.document.commands.record_applied(tx)
        self.console.setText(
            result.stdout.rstrip() if result.stdout else "Script completed successfully"
        )
        self.statusBar().showMessage("Authoring script completed", 3000)
        self.refresh_all()

    def _build_actions(self):
        self.menuBar().setNativeMenuBar(False)
        file_menu = self.menuBar().addMenu("&File")
        self.new_action = QAction("New Project…", self)
        self.new_action.setShortcut(QKeySequence.New)
        self.new_action.triggered.connect(self.new_project)
        file_menu.addAction(self.new_action)
        self.open_action = QAction("Open Project…", self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.open_action.triggered.connect(self.open_project)
        self.save_action = QAction("Save", self)
        self.save_action.setShortcut(QKeySequence.Save)
        self.save_action.triggered.connect(self.save_project)
        self.save_as_action = QAction("Save As…", self)
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.save_as_action.triggered.connect(self.save_project_as)
        file_menu.addActions([self.open_action, self.save_action, self.save_as_action])

        edit = self.menuBar().addMenu("&Edit")
        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.triggered.connect(self.scene_controller.undo)
        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut(QKeySequence.Redo)
        self.redo_action.triggered.connect(self.scene_controller.redo)
        edit.addActions([self.undo_action, self.redo_action])
        edit.addSeparator()

        self.rename_action = QAction("Rename…", self)
        self.rename_action.setShortcut("F2")
        self.rename_action.triggered.connect(self.scene_controller.rename_selected)
        self.add_scene_action = QAction("Add Scene…", self)
        self.add_scene_action.triggered.connect(self.add_scene)
        self.delete_scene_action = QAction("Delete Scene", self)
        self.delete_scene_action.triggered.connect(self.delete_scene)
        self.set_startup_scene_action = QAction("Set as Startup Scene", self)
        self.set_startup_scene_action.triggered.connect(self.scene_controller.set_startup_scene)
        self.move_up_action = QAction("Move Up", self)
        self.move_up_action.setShortcut("Alt+Up")
        self.move_up_action.triggered.connect(lambda: self.scene_controller.move_selected(-1))
        self.move_down_action = QAction("Move Down", self)
        self.move_down_action.setShortcut("Alt+Down")
        self.move_down_action.triggered.connect(lambda: self.scene_controller.move_selected(1))
        self.add_entity_action = QAction("Add Entity…", self)
        self.add_entity_action.triggered.connect(self.add_entity)
        self.delete_action = QAction("Delete Selected", self)
        self.delete_action.setShortcut(QKeySequence.Delete)
        self.delete_action.triggered.connect(self.delete_selected)
        self.add_component_action = QAction("Add Component…", self)
        self.add_component_action.triggered.connect(self.add_component)
        self.copy_action = QAction("Copy Entity", self)
        self.copy_action.setShortcut(QKeySequence.Copy)
        self.copy_action.triggered.connect(self.scene_controller.copy_selected)
        self.paste_action = QAction("Paste Entity", self)
        self.paste_action.setShortcut(QKeySequence.Paste)
        self.paste_action.triggered.connect(self.scene_controller.paste_entity)
        self.duplicate_action = QAction("Duplicate Entity", self)
        self.duplicate_action.setShortcut("Ctrl+D")
        self.duplicate_action.triggered.connect(self.scene_controller.duplicate_selected)
        self.toggle_entity_enabled_action = QAction("Enable / Disable Entity", self)
        self.toggle_entity_enabled_action.setShortcut("Ctrl+E")
        self.toggle_entity_enabled_action.triggered.connect(
            self.scene_controller.toggle_selected_entity_enabled
        )
        for action in (
            self.rename_action,
            self.add_scene_action,
            self.delete_scene_action,
            self.set_startup_scene_action,
            self.move_up_action,
            self.move_down_action,
            self.add_entity_action,
            self.add_component_action,
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
        self.zoom_in_action = QAction("Zoom In", self)
        self.zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        self.zoom_in_action.triggered.connect(self.viewport.zoom_in)
        self.zoom_out_action = QAction("Zoom Out", self)
        self.zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        self.zoom_out_action.triggered.connect(self.viewport.zoom_out)
        view_menu = self.menuBar().addMenu("&View")
        view_menu.addActions(
            [self.zoom_in_action, self.zoom_out_action, self.reset_view_action]
        )

        run_menu = self.menuBar().addMenu("&Run")
        run_menu.addAction(self.play_action)
        self.play_scene_action = QAction("Run Current Scene", self)
        self.play_scene_action.setShortcut("Ctrl+F6")
        self.play_scene_action.triggered.connect(self.play_current_scene)
        run_menu.addAction(self.play_scene_action)
        run_menu.addAction(self.stop_action)

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
        toolbar.addAction(self.play_action)
        toolbar.addAction(self.stop_action)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        self.view_toolbar = QToolBar("View", self)
        self.view_toolbar.setObjectName("AsteriaViewToolbar")
        self.view_toolbar.setMovable(False)
        self.view_toolbar.setFloatable(False)
        self.view_toolbar.addAction(self.zoom_out_action)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("MutedLabel")
        self.zoom_label.setMinimumWidth(44)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.view_toolbar.addWidget(self.zoom_label)
        self.view_toolbar.addAction(self.zoom_in_action)
        self.view_toolbar.addAction(self.reset_view_action)
        self.addToolBar(Qt.TopToolBarArea, self.view_toolbar)
        self.viewport.zoomChanged.connect(self._update_zoom_label)
        self._update_zoom_label(self.viewport.camera.zoom)
        self._refresh_actions()

    def _update_zoom_label(self, zoom):
        self.zoom_label.setText(f"{round(zoom * 100)}%")

    def show_controls(self):
        QMessageBox.information(
            self,
            "Asteria Controls and Shortcuts",
            "Scene Viewport\n"
            "• Click an object, then use arrow keys to move it by 1 unit.\n"
            "• Hold Shift with an arrow key to move it by 10 units.\n"
            "• Click empty space, then use arrow keys to move the view.\n"
            "• Two-finger drag pans the view.\n"
            "• Mouse wheel zooms toward the cursor.\n"
            "• Two-finger pinch zooms around the view center.\n"
            "• Command+= / Command+- zoom in and out.\n"
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
        self.add_entity_action.setEnabled(
            sel.kind in {"scene", "entity"} and not sel.multiple
        )
        self.delete_action.setEnabled(
            sel.kind == "component" and not sel.multiple
            or sel.kind == "entity" and bool(sel.values)
        )
        self.add_component_action.setEnabled(sel.kind == "entity" and not sel.multiple)
        self.copy_action.setEnabled(sel.kind == "entity" and not sel.multiple)
        self.duplicate_action.setEnabled(sel.kind == "entity" and bool(sel.values))
        self.toggle_entity_enabled_action.setEnabled(
            sel.kind == "entity" and not sel.multiple and sel.value is not None
        )
        self.paste_action.setEnabled(
            self.document.clipboard.has_entity()
            and sel.kind in {"scene", "entity"}
            and not sel.multiple
        )
        active = self.play_session is not None and self.play_session.active
        self.play_action.setEnabled(project is not None and not active)
        self.stop_action.setEnabled(active)

    def _refresh_title(self):
        name = self.document.project.name if self.document.project else "No Project"
        dirty = " *" if self.document.dirty else ""
        self.setWindowTitle(f"Asteria Editor — {name}{dirty}")

    def _resolve_project_resources(self):
        resolve_project_resources(self.document)
        self.viewport.texture_cache.clear()
        self.scene_controller._sync_scene_authoring_context()
        self._sync_animation_context()

    def _sync_animation_context(self):
        clip_set, current = animation_context(self.document)
        if clip_set is None:
            self.animation_widget.set_clips(())
            self.animation_widget.set_status(
                "No animation selected"
                if current is None
                else f"Missing animation asset for {current}"
            )
            return
        names = tuple(clip_set.clips)
        self.animation_widget.set_clips(names, current)
        self.animation_widget.set_status(f"{len(names)} clips available")

    def refresh_selection_context(self):
        self.refresh_inspector()
        self.scene_controller._sync_scene_authoring_context()
        self._sync_animation_context()
        self.event_controller._sync_event_context()
        self.code_workspace.refresh_project_context()
        self._refresh_actions()

    def refresh_all(self):
        self.project_tree.refresh()
        self.refresh_asset_list()
        self.refresh_inspector()
        self.scene_controller._sync_scene_authoring_context()
        self._sync_animation_context()
        self.event_controller._sync_event_context()
        self.code_workspace.refresh_project_context()
        self.rpg_authoring.rebuild()
        self.battle_authoring.rebuild()
        self.presentation_authoring.rebuild()
        self.runtime_ui_authoring.rebuild()
        self.game_flow_overview.refresh()
        self.viewport.refresh()
        if self.viewport.render_source is not None:
            self.tile_layers.set_tilemap(
                self.viewport.render_source.tilemap,
                self.viewport.tile_tools.active_layer,
            )
            self.tile_palette.set_layer(self.viewport.tile_tools.active_layer)
        self._refresh_actions()
        self._refresh_title()

    def set_project(self, project, file_path=None):
        if self.play_session is not None and self.play_session.active:
            self.stop_play()
        self.document.set_project(project, file_path=file_path)
        self.play_session = None
        self.runtime_process = None
        if file_path is not None:
            self._resolve_project_resources()
        else:
            self.document.asset_views.clear()
            self.scene_controller.set_tilemap_render_source(None)
        self.code_workspace.load_default_script()
        self.refresh_all()
        QTimer.singleShot(0, self.viewport.reset_view)

    def refresh_asset_list(self):
        self.asset_list.clear()
        if self.document.project is None:
            return
        for record in self.document.project.assets.records():
            item = QListWidgetItem(f"{record.kind}: {record.source_path}")
            item.setData(Qt.UserRole, record)
            self.asset_list.addItem(item)

    def _asset_selected(self, row):
        item = self.asset_list.item(row)
        record = item.data(Qt.UserRole) if item is not None else None
        if record is None:
            return
        self.document.selection.set_single("asset", record)
        self.refresh_selection_context()

    def refresh_inspector(self):
        sel = self.document.selection
        if sel.kind == "none" or sel.value is None:
            if sel.multiple:
                self.inspector.show_properties(
                    f"{len(sel.values)} selected", (("Count", len(sel.values), "int"),)
                )
            else:
                self.inspector.show_message("Nothing selected")
            return
        if sel.multiple:
            self.inspector.show_properties(
                f"{len(sel.values)} {sel.kind.title()}s selected",
                (("Count", len(sel.values), "int"),),
            )
            return
        obj = sel.value
        if sel.kind == "project":
            startup = obj.scene(obj.startup_scene_id)
            self.inspector.show_properties(
                "Project",
                (
                    ("Name", obj.name, "str"),
                    (
                        "Startup Scene",
                        startup.name if startup is not None else "None",
                        "Scene",
                    ),
                ),
            )
        elif sel.kind == "scene":
            self.inspector.show_properties(
                "Scene",
                (
                    ("Name", obj.name, "str"),
                    ("Entities", len(obj.entities()), "int"),
                ),
            )
        elif sel.kind == "entity":
            self.inspector.show_properties(
                "Entity",
                (
                    ("Name", obj.name, "str"),
                    ("Enabled", obj.enabled, "bool"),
                    ("Components", len(obj.components()), "int"),
                ),
            )
        elif sel.kind == "component":
            self.inspector.show_component(
                type(obj).__name__, build_inspector_fields(obj)
            )
        elif sel.kind == "asset":
            self.inspector.show_properties(
                "Asset",
                (
                    ("Kind", obj.kind, "str"),
                    ("Path", obj.source_path, "path"),
                ),
            )
        else:
            self.inspector.show_message(f"Selected: {sel.kind}")

    def add_scene(self):
        return self.scene_controller.add_scene()

    def delete_scene(self):
        return self.scene_controller.delete_scene()

    def add_entity(self):
        return self.scene_controller.add_entity()

    def add_component(self):
        return self.scene_controller.add_component()

    def delete_selected(self):
        return self.scene_controller.delete_selected()

    def save_project(self):
        if self.document.project is None:
            return False
        if self.document.file_path is None:
            return self.save_project_as()
        try:
            save_document(self.document)
        except EditorStorageError as exc:
            QMessageBox.critical(self, "Save Project", str(exc))
            return False
        self.statusBar().showMessage(f"Saved {self.document.file_path}", 3000)
        self.refresh_all()
        return True

    def save_project_as(self):
        if self.document.project is None:
            return False
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Asteria Project",
            "",
            "Asteria Project (*.asteria.json);;JSON (*.json)",
        )
        if not path:
            return False
        try:
            save_document(self.document, path)
        except EditorStorageError as exc:
            QMessageBox.critical(self, "Save Project", str(exc))
            return False
        self.statusBar().showMessage(f"Saved {self.document.file_path}", 3000)
        remember_last_project(self.document.file_path)
        self.refresh_all()
        return True

    def _confirm_discard_changes(self, question):
        if not self.document.dirty:
            return True
        answer = QMessageBox.question(
            self,
            "Unsaved Changes",
            f"This project has unsaved changes. {question}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def open_project(self):
        if not self._confirm_discard_changes("Open another project anyway?"):
            return False
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Asteria Project", "", "Asteria Project (*.asteria.json *.json)"
        )
        if not path:
            return False
        return self.open_project_path(path)

    def open_project_path(self, path):
        try:
            load_document(self.document, path)
            self._resolve_project_resources()
        except (EditorStorageError, EditorResourceError) as exc:
            QMessageBox.critical(self, "Open Project", str(exc))
            return False
        self.play_session = None
        self._load_playtest_profiles()
        self.refresh_all()
        QTimer.singleShot(0, self.viewport.reset_view)
        remember_last_project(self.document.file_path)
        return True

    def new_project(self):
        if not self._confirm_discard_changes("Create a new project anyway?"):
            return False
        name, ok = QInputDialog.getText(
            self, "New Project", "Project name:", text="New Project"
        )
        if not ok or not name.strip():
            return False
        location = QFileDialog.getExistingDirectory(
            self, "Choose Where to Create the Project"
        )
        if not location:
            return False
        folder = Path(location) / project_folder_name(name)
        if folder.exists() and any(folder.iterdir()):
            QMessageBox.warning(
                self, "New Project", f"{folder} already exists and is not empty."
            )
            return False
        try:
            path = create_new_project(name, folder)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "New Project", str(exc))
            return False
        return self.open_project_path(path)

    def _load_playtest_profiles(self):
        if not hasattr(self,"playtest_profile_combo"):
            return
        self.playtest_profile_combo.clear()
        self.playtest_profile_library=None
        if self.document.project is None or self.document.file_path is None:
            self.playtest_profile_combo.addItem("Default","")
            return
        library=PlaytestProfileLibrary(self.document.file_path.resolve().parent)
        self.playtest_profile_library=library
        profiles=library.profiles()
        if not profiles:
            self.playtest_profile_combo.addItem("Default","")
            return
        default_index=0
        for index,profile in enumerate(profiles):
            self.playtest_profile_combo.addItem(profile.display_name,profile.profile_id)
            if profile.default: default_index=index
        self.playtest_profile_combo.setCurrentIndex(default_index)

    def selected_playtest_profile_id(self):
        if not hasattr(self,"playtest_profile_combo"):
            return None
        value=self.playtest_profile_combo.currentData()
        return str(value) if value else None

    def play_project(self):
        try:
            self.play_session=create_play_session(self.document,from_start=True)
            self.runtime_process=launch_play_session(self.play_session)
        except (PlayModeError,RuntimeLaunchError) as exc:
            if self.play_session is not None:self.play_session.stop()
            self.play_session=None; self.runtime_process=None
            QMessageBox.warning(self,"Run Project",str(exc)); return False
        self.console.setText(f"Runtime preview: {self.play_session.runtime_scene.name}")
        self.statusBar().showMessage(f"Playing — {self.play_session.runtime_scene.name}")
        self._refresh_actions(); return True

    def play_current_scene(self):
        try:
            self.play_session=create_play_session(self.document)
            self.runtime_process = launch_play_session(self.play_session)
        except (PlayModeError, RuntimeLaunchError) as exc:
            if self.play_session is not None:
                self.play_session.stop()
            self.play_session = None
            self.runtime_process = None
            QMessageBox.warning(self, "Play", str(exc))
            return False
        self.console.setText(f"Runtime preview: {self.play_session.runtime_scene.name}")
        self.statusBar().showMessage(
            f"Playing — {self.play_session.runtime_scene.name}"
        )
        self._refresh_actions()
        return True

    def stop_play(self):
        if self.play_session is None or not self.play_session.active:
            return False
        if self.runtime_process is not None:
            self.runtime_process.stop()
            self.runtime_process = None
        self.play_session.stop()
        self.console.setText("Play session stopped")
        self.statusBar().showMessage("Play session stopped", 2000)
        self._refresh_actions()
        return True

    def _poll_runtime_process(self):
        if self.runtime_process is None or self.runtime_process.running:
            return
        self.runtime_process.stop()
        self.runtime_process = None
        if self.play_session is not None and self.play_session.active:
            self.play_session.stop()
        self.console.setText("Runtime preview closed")
        self.statusBar().showMessage("Runtime preview closed", 2000)
        self._refresh_actions()

    def closeEvent(self, event):
        if self.play_session is not None and self.play_session.active:
            self.stop_play()
        if self.document.dirty:
            answer = QMessageBox.question(
                self,
                "Unsaved Changes",
                "Save changes before closing Asteria?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if answer == QMessageBox.Cancel:
                event.ignore()
                return
            if answer == QMessageBox.Save and not self.save_project():
                event.ignore()
                return
        event.accept()


_LAST_PROJECT_KEY = "last_project_path"


def _editor_settings():
    return QSettings("Asteria", "Asteria Editor")


def remember_last_project(path):
    if path is not None:
        _editor_settings().setValue(_LAST_PROJECT_KEY, str(Path(path).resolve()))


def last_project_path():
    value = _editor_settings().value(_LAST_PROJECT_KEY, "")
    path = Path(value) if value else None
    return path if path is not None and path.is_file() else None


def project_folder_name(name):
    folder = re.sub(r"[^\w\- ]+", "_", str(name)).strip(" ._")
    return folder or "New Project"


def launch_editor(project=None):
    import sys

    app = QApplication.instance() or QApplication(sys.argv)
    apply_asteria_theme(app)
    window = AsteriaEditorWindow(project)
    window.show()
    if project is None:
        # Reopen where the user left off instead of an empty "No Project"
        # window. Done here, not in the window constructor, so windows built
        # in tests never touch the user's real last-project setting.
        previous = last_project_path()
        if previous is not None and not window.open_project_path(previous):
            _editor_settings().remove(_LAST_PROJECT_KEY)
    return app.exec()
