import shutil
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

from asteria.assets.character_visual import CharacterVisualSet

from .authoring_hub_widget import FamilyHostWidget
from .clipboard import build_duplicate_entity_command, build_paste_entity_command
from .code_workspace import CodeWorkspaceWidget
from .commands import CommandTransaction, SetAttributeCommand
from .component_picker import build_component_choices
from .create_character_command import CreateCharacterCommand
from .editing import EditError, build_set_component_field_command
from .event_editing import (
    AddEventBindingCommand,
    AddEventProgramCommand,
    ReplaceEventBindingCommand,
    ReplaceEventProgramCommand,
    bindings_for_scene,
    parse_world_args,
    program_with_insert,
    program_with_move,
    program_with_remove,
    replace_binding_fields,
)
from .event_editor_widget import EventEditorWidget
from .game_flow_overview_widget import GameFlowOverviewWidget
from .hierarchy import build_reorder_entity_command
from .inspector import build_inspector_fields
from .integrated_authoring import IntegratedAuthoringControllers
from .model import EditorDocument
from .playmode import PlayModeError, create_play_session
from .playtest_profiles import PlaytestProfileLibrary
from .project_workspace import ProjectWorkspaceController
from .runtime_launcher import RuntimeLaunchError, launch_play_session
from .scenes import (
    SceneEditError,
    build_add_scene_command,
    build_remove_scene_command,
    build_reorder_scene_command,
)
from .storage import EditorStorageError, load_document, save_document
from .structure import (
    StructureEditError,
    build_add_component_command,
    build_add_entity_command,
    build_remove_component_command,
    build_remove_entity_command,
    build_rename_command,
)
from .workspace import EditorWorkspace, WorkspaceMode

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QAction, QKeySequence
    from PySide6.QtWidgets import (
        QApplication,
        QDockWidget,
        QFileDialog,
        QInputDialog,
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
from asteria.core.ids import new_id
from asteria.events import (
    EventBinding,
    EventCondition,
    EventInstruction,
    EventProgram,
    EventTriggerCondition,
    EventTriggerKind,
)
from asteria.graphics import TileLayer
from asteria.runtime.world_command_handlers import WORLD_COMMAND_ARGUMENTS

from .animation_widget import AnimationWidget
from .authoring_context import animation_context, scene_authoring_source
from .resource_resolver import EditorResourceError, resolve_project_resources
from .theme import apply_asteria_theme
from .tile_edit import (
    AddTileLayerCommand,
    RemoveTileLayerCommand,
    ReorderTileLayerCommand,
    SetTileLayerPropertyCommand,
    TileEditError,
)
from .tile_layers_widget import TileLayersWidget
from .tile_palette_widget import TilePaletteWidget
from .viewport_widget import SceneViewportWidget
from .widgets import InspectorWidget, ProjectTreeWidget


@lru_cache(maxsize=1)
def _discover_mv_generator_catalog(reference_root):
    """Share the immutable MV file index while keeping each recipe independent."""
    from asteria.assets.rpg_maker_mv_generator import RPGMakerMVGeneratorCatalog

    return RPGMakerMVGeneratorCatalog.discover(reference_root)


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

        self.rpg_authoring = FamilyHostWidget("RPG Authoring", self.authoring_controllers.rpg_categories, self)
        from pathlib import Path

        from asteria.assets.character_generator import CharacterGeneratorCatalog
        from asteria.assets.local_reference import resolve_rpg_maker_mv_root

        from .character_generator_widget import CharacterGeneratorWidget
        from .character_generator_workspace import CharacterGeneratorWorkspace

        reference_root = resolve_rpg_maker_mv_root(Path(__file__).resolve().parents[3])
        if reference_root is None:
            character_workspace = CharacterGeneratorWorkspace.create(CharacterGeneratorCatalog())
        else:
            character_workspace = CharacterGeneratorWorkspace.create_mv(_discover_mv_generator_catalog(reference_root))
        self.character_creator = CharacterGeneratorWidget(character_workspace, self)
        self.character_creator.generated.connect(
            lambda bundle: self.begin_character_placement(bundle, self.character_creator)
        )
        self.viewport.characterCellClicked.connect(self._place_generated_character_at)
        self.rpg_workspace = QTabWidget(self)
        self.rpg_workspace.addTab(self.rpg_authoring, "Database")
        from .game_systems_authoring import GameSystemsAuthoringController
        from .game_systems_widget import GameSystemsEditorWidget

        self.game_systems_editor = GameSystemsEditorWidget(GameSystemsAuthoringController(self.document), self)
        self.game_systems_editor.changed.connect(self.refresh_all)
        self.rpg_workspace.addTab(self.character_creator, "Character Creator")
        self.rpg_workspace.addTab(self.game_systems_editor, "Game Systems")
        self.battle_authoring = FamilyHostWidget("Battle Rules", self.authoring_controllers.battle_categories, self)
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
        from .action_timeline_widget import ActionTimelineWidget
        from .animation_editor_widget import AnimationEditorWidget

        self.animation_editor = AnimationEditorWidget(self.document, self)
        self.ui_workspace.addTab(self.animation_editor, "Animation Editor")
        self.action_timeline_editor = ActionTimelineWidget(self.document, self)
        self.ui_workspace.addTab(self.action_timeline_editor, "Action Timeline")

        self.game_flow_overview = GameFlowOverviewWidget(self.document, self)
        self.events_workspace = QTabWidget(self)
        self.events_workspace.addTab(self.event_editor, "Event Program")
        self.events_workspace.addTab(self.game_flow_overview, "Field / Game Flow")

        self.workspace = EditorWorkspace(
            {
                WorkspaceMode.SCENE: self.viewport,
                WorkspaceMode.RPG: self.rpg_workspace,
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
        left = QDockWidget("Project / Scene", self)
        left.setWidget(self.project_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, left)

        self.tile_palette = TilePaletteWidget(self)
        palette_dock = QDockWidget("Tile Palette", self)
        palette_dock.setWidget(self.tile_palette)
        self.addDockWidget(Qt.LeftDockWidgetArea, palette_dock)
        self.tabifyDockWidget(left, palette_dock)
        self.tile_palette.modeChanged.connect(self.viewport.set_tile_mode)
        self.tile_palette.tileSelected.connect(self.viewport.set_selected_tile)

        self.tile_layers = TileLayersWidget(self)
        layers_dock = QDockWidget("Layers", self)
        layers_dock.setWidget(self.tile_layers)
        self.addDockWidget(Qt.LeftDockWidgetArea, layers_dock)
        self.tabifyDockWidget(left, layers_dock)
        self.tile_layers.layerSelected.connect(self._select_tile_layer)
        self.tile_layers.addRequested.connect(self._add_tile_layer)
        self.tile_layers.removeRequested.connect(self._remove_tile_layer)
        self.tile_layers.moveRequested.connect(self._move_tile_layer)
        self.tile_layers.visibilityChanged.connect(self._set_tile_layer_visible)
        self.tile_layers.collisionChanged.connect(self._set_tile_layer_collision)

        self.event_editor.bindingRequested.connect(self._event_add_binding)
        self.event_editor.bindingChanged.connect(self._event_binding_changed)
        self.event_editor.addConditionRequested.connect(self._event_add_condition)
        self.event_editor.addCommandRequested.connect(self._event_add_command)
        self.event_editor.removeCommandRequested.connect(self._event_remove_command)
        self.event_editor.moveCommandRequested.connect(self._event_move_command)
        self.code_workspace.saved.connect(self._code_script_saved)
        self.code_workspace.runRequested.connect(self._run_authoring_script)

        self.inspector = InspectorWidget(self.document)
        right = QDockWidget("Inspector", self)
        right.setWidget(self.inspector)
        self.addDockWidget(Qt.RightDockWidgetArea, right)

        self.asset_list = QListWidget()
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
        from .debugger_widget import DebuggerWidget

        self.debugger_widget = DebuggerWidget(self)
        debugger_dock = QDockWidget("Debugger", self)
        debugger_dock.setObjectName("DebuggerDock")
        debugger_dock.setWidget(self.debugger_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, debugger_dock)
        self.tabifyDockWidget(console, debugger_dock)
        console.raise_()

        # The native macOS tab base draws a redundant rounded line behind
        # tabified docks. Individual tabs retain their own visual states.
        for dock_tabs in self.findChildren(QTabBar):
            dock_tabs.setDrawBase(False)

        self._build_actions()
        QApplication.instance().focusChanged.connect(self._focus_changed)
        self._load_playtest_profiles()
        left.raise_()
        self._workspace_mode_changed(self.workspace.mode.value)
        self.refresh_all()
        QTimer.singleShot(0, self.viewport.frame_game_camera)

    def begin_character_placement(self, bundle, status_widget=None):
        """Switch to Scene and wait for one map-cell click to place a bundle."""
        status_widget = status_widget or self.character_creator
        project = self.document.project
        scene = self.viewport.current_scene()
        if project is None or scene is None:
            status_widget.status.setText("Open a project and select a scene before creating a character")
            return None
        self._pending_character_bundle = bundle
        self._placement_status_widget = status_widget
        self.workspace.set_mode(WorkspaceMode.SCENE)
        self.viewport.begin_character_placement()
        status_widget.status.setText("Click a map cell to place this character")
        return bundle

    def _status_sink(self):
        """Object with ``.status.setText`` that reports to the window status bar."""
        bar = self.statusBar()
        return SimpleNamespace(status=SimpleNamespace(setText=lambda text: bar.showMessage(text, 6000)))

    def place_character_from_sheet(self, path=None, name=None):
        """Place a playable character from any 3x4 walking sheet (rows down/left/right/up).

        The sheet is copied next to a saved project so the project stays
        portable; for an unsaved project it is referenced where it is.
        """
        project = self.document.project
        if project is None:
            return None
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Walking Sprite Sheet", "", "Images (*.png)")
            if not path:
                return None
        if name is None:
            name, ok = QInputDialog.getText(self, "Character", "Name:", text=Path(path).stem)
            if not ok or not name.strip():
                return None
        source = Path(path)
        try:
            key = CharacterVisualSet.from_walking_sheet(source, key=name).key
            uri = source
            if self.document.file_path is not None:
                target = self.document.file_path.parent / "characters" / f"{key}.png"
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.resolve() != target.resolve():
                    shutil.copyfile(source, target)
                uri = target.relative_to(self.document.file_path.parent)
                source = target
            visual = CharacterVisualSet.from_walking_sheet(source, key=key, uri=uri)
        except (OSError, ValueError) as exc:
            self.statusBar().showMessage(f"Cannot use sprite sheet: {exc}", 6000)
            return None
        self._pending_character_name = name.strip()
        return self.begin_character_placement(visual, self._status_sink())

    def set_actor_appearance(self, actor_id=None, sprite_sheet_asset_id=None):
        """Give an Actor a field sprite and push it onto every map entity linked to it."""
        from .actor_appearance import apply_actor_appearance

        project = self.document.project
        if project is None:
            return False
        actors = project.rpg_database.actors
        if actor_id is None:
            labels = [f"{actors[a].display_name} ({a})" for a in sorted(actors)]
            if not labels:
                self.statusBar().showMessage("The project has no actors", 6000)
                return False
            label, ok = QInputDialog.getItem(self, "Actor Appearance", "Actor:", labels, 0, False)
            if not ok:
                return False
            actor_id = sorted(actors)[labels.index(label)]
        if sprite_sheet_asset_id is None:
            sheets = list(self.document.asset_views.sprite_sheet_ids())
            if not sheets:
                self.statusBar().showMessage("No sprite sheets are loaded", 6000)
                return False
            sprite_sheet_asset_id, ok = QInputDialog.getItem(
                self, "Actor Appearance", "Sprite sheet:", sheets, 0, False
            )
            if not ok:
                return False
        applied = apply_actor_appearance(self.document, actor_id, sprite_sheet_asset_id)
        self.refresh_all()
        return applied

    def _selected_entity(self):
        sel = self.document.selection
        if sel.multiple or sel.value is None:
            return None
        if sel.kind == "entity":
            return sel.value
        if sel.kind == "component":
            return sel.value.entity
        return None

    def _run_prefab_command(self, command, message):
        from asteria.core.prefab import PrefabError

        try:
            self.document.execute(command)
        except (PrefabError, ValueError, KeyError) as exc:
            self.statusBar().showMessage(f"Prefab: {exc}", 6000)
            return None
        self.statusBar().showMessage(message, 6000)
        self.refresh_all()
        return command

    def create_prefab_from_selection(self, prefab_id=None):
        from .prefab_commands import CreatePrefabFromEntityCommand

        entity = self._selected_entity()
        if entity is None or self.document.project is None:
            self.statusBar().showMessage("Select one entity to make a prefab", 6000)
            return None
        if prefab_id is None:
            prefab_id, ok = QInputDialog.getText(
                self, "Create Prefab", "Prefab id:", text=entity.name.lower().replace(" ", "_")
            )
            if not ok or not prefab_id.strip():
                return None
        command = CreatePrefabFromEntityCommand(self.document.project, entity, prefab_id.strip())
        return self._run_prefab_command(command, f"Created prefab {prefab_id.strip()}")

    def place_prefab(self, prefab_id=None, x=None, y=None):
        from .prefab_commands import InstantiatePrefabCommand

        project, scene = self.document.project, self.viewport.current_scene()
        if project is None or scene is None:
            return None
        if prefab_id is None:
            ids = list(project.prefabs.ids())
            if not ids:
                self.statusBar().showMessage("The project has no prefabs", 6000)
                return None
            prefab_id, ok = QInputDialog.getItem(self, "Place Prefab", "Prefab:", ids, 0, False)
            if not ok:
                return None
        if x is None or y is None:
            cx, cy = self.viewport.width() / 2, self.viewport.height() / 2
            x, y = self.viewport.camera.screen_to_world(cx, cy)
        command = InstantiatePrefabCommand(project, self.document.component_registry, scene, prefab_id, x, y)
        result = self._run_prefab_command(command, f"Placed {prefab_id}")
        if result is not None:
            self.document.select_entity(command.entity)
            self.refresh_all()
        return result

    def apply_instance_to_prefab(self):
        from asteria.core.prefab import PrefabInstanceComponent

        from .prefab_commands import apply_instance_to_prefab_command

        entity = self._selected_entity()
        if entity is None or not entity.has(PrefabInstanceComponent):
            self.statusBar().showMessage("Select a prefab instance", 6000)
            return None
        command = apply_instance_to_prefab_command(self.document.project, self.document.component_registry, entity)
        return self._run_prefab_command(command, "Prefab updated; other instances kept their overrides")

    def revert_instance_to_prefab(self):
        from asteria.core.prefab import PrefabInstanceComponent

        from .prefab_commands import RevertInstanceCommand

        entity = self._selected_entity()
        if entity is None or not entity.has(PrefabInstanceComponent):
            self.statusBar().showMessage("Select a prefab instance", 6000)
            return None
        command = RevertInstanceCommand(self.document.project, self.document.component_registry, entity)
        return self._run_prefab_command(command, f"{entity.name} matches its prefab again")

    def _place_generated_character_at(self, cell):
        """Commit the pending generated bundle using the cell clicked in Scene."""
        bundle = getattr(self, "_pending_character_bundle", None)
        if bundle is None:
            return None
        project = self.document.project
        scene = self.viewport.current_scene()
        status_widget = getattr(self, "_placement_status_widget", None) or self.character_creator
        if project is None or scene is None:
            self.viewport.end_character_placement()
            self._pending_character_bundle = None
            self._placement_status_widget = None
            status_widget.status.setText("Character placement cancelled: no active scene")
            return None
        cell = (
            int(cell[0]),
            int(cell[1]),
        )
        try:
            if isinstance(bundle, CharacterVisualSet):
                command = CreateCharacterCommand(
                    bundle,
                    project,
                    scene,
                    cell,
                    display_name=getattr(self, "_pending_character_name", None),
                )
            else:
                command = self.character_creator.workspace.create_character_command(
                    bundle,
                    project,
                    scene,
                    cell,
                    display_name=self.character_creator.name_edit.text().strip() or None,
                )
            self.document.execute(command)
        except Exception as exc:
            status_widget.status.setText(f"Character creation failed: {exc}")
            return None
        self._pending_character_bundle = None
        self._placement_status_widget = None
        self.viewport.end_character_placement()
        self.document.select_entity(command.created.entity)
        status_widget.status.setText(f"Created {command.created.actor.display_name} at map cell {cell[0]}, {cell[1]}")
        self.refresh_all()
        return command.created

    def _workspace_mode_changed(self, mode):
        current = WorkspaceMode(mode)
        for action, candidate in (
            (getattr(self, "scene_workspace_action", None), WorkspaceMode.SCENE),
            (getattr(self, "rpg_workspace_action", None), WorkspaceMode.RPG),
            (getattr(self, "battle_workspace_action", None), WorkspaceMode.BATTLE),
            (getattr(self, "ui_workspace_action", None), WorkspaceMode.UI),
            (getattr(self, "event_workspace_action", None), WorkspaceMode.EVENT),
            (getattr(self, "code_workspace_action", None), WorkspaceMode.CODE),
        ):
            if action is not None:
                action.setChecked(current == candidate)
        if current == WorkspaceMode.CODE:
            self.code_workspace.refresh_project_context()
        elif current == WorkspaceMode.RPG:
            self.rpg_authoring.rebuild()
            self._refresh_game_systems()
        elif current == WorkspaceMode.BATTLE:
            self.battle_authoring.rebuild()
        elif current == WorkspaceMode.UI:
            self.presentation_authoring.rebuild()
            self.runtime_ui_authoring.rebuild()
            self._refresh_game_systems()
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
        self.console.setText(result.stdout.rstrip() if result.stdout else "Script completed successfully")
        self.statusBar().showMessage("Authoring script completed", 3000)
        self.refresh_all()

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
        file_menu.addActions([self.open_action, self.save_action, self.save_as_action])

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
        self.place_sheet_character_action.triggered.connect(lambda: self.place_character_from_sheet())
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
        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.reset_view_action)

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
        self.scene_workspace_action = QAction("Scene", self)
        self.rpg_workspace_action = QAction("RPG", self)
        self.battle_workspace_action = QAction("Battle", self)
        self.ui_workspace_action = QAction("UI", self)
        self.event_workspace_action = QAction("Events", self)
        self.code_workspace_action = QAction("Code", self)
        for action, mode in (
            (self.scene_workspace_action, WorkspaceMode.SCENE),
            (self.rpg_workspace_action, WorkspaceMode.RPG),
            (self.battle_workspace_action, WorkspaceMode.BATTLE),
            (self.ui_workspace_action, WorkspaceMode.UI),
            (self.event_workspace_action, WorkspaceMode.EVENT),
            (self.code_workspace_action, WorkspaceMode.CODE),
        ):
            action.setCheckable(True)
            action.triggered.connect(lambda checked=False, m=mode: self.workspace.set_mode(m))
            toolbar.addAction(action)
        toolbar.addSeparator()
        toolbar.addAction(self.play_action)
        toolbar.addAction(self.stop_action)
        toolbar.addAction(self.reset_view_action)
        self.addToolBar(Qt.TopToolBarArea, toolbar)
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
            "Undo" + (f" {self.document.commands.undo_label}" if self.document.commands.undo_label else "")
        )
        self.redo_action.setText(
            "Redo" + (f" {self.document.commands.redo_label}" if self.document.commands.redo_label else "")
        )

        project = self.document.project
        sel = self.document.selection
        self.save_action.setEnabled(project is not None)
        self.save_as_action.setEnabled(project is not None)
        self.rename_action.setEnabled(sel.kind in {"project", "scene", "entity"} and not sel.multiple)
        self.add_scene_action.setEnabled(project is not None)
        self.set_startup_scene_action.setEnabled(sel.kind == "scene" and not sel.multiple and sel.value is not None)
        self.move_up_action.setEnabled(sel.kind in {"scene", "entity"} and not sel.multiple and sel.value is not None)
        self.move_down_action.setEnabled(sel.kind in {"scene", "entity"} and not sel.multiple and sel.value is not None)
        self.delete_scene_action.setEnabled(
            sel.kind == "scene" and not sel.multiple and project is not None and len(project.scenes()) > 1
        )
        self.add_entity_action.setEnabled(sel.kind in {"scene", "entity"} and not sel.multiple)
        self.delete_action.setEnabled(
            sel.kind == "component" and not sel.multiple or sel.kind == "entity" and bool(sel.values)
        )
        self.add_component_action.setEnabled(sel.kind == "entity" and not sel.multiple)
        self.copy_action.setEnabled(sel.kind == "entity" and not sel.multiple)
        self.duplicate_action.setEnabled(sel.kind == "entity" and bool(sel.values))
        self.toggle_entity_enabled_action.setEnabled(
            sel.kind == "entity" and not sel.multiple and sel.value is not None
        )
        self.cut_action.setEnabled(sel.kind == "entity" and not sel.multiple)
        self.paste_action.setEnabled(
            self.document.clipboard.has_entity() and sel.kind in {"scene", "entity"} and not sel.multiple
        )
        if self._focused_record_family() is not None:  # the shortcuts act on the focused record list
            for action in (self.cut_action, self.copy_action, self.paste_action, self.delete_action):
                action.setEnabled(True)
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
        self._sync_scene_authoring_context()
        self._sync_animation_context()

    def _sync_scene_authoring_context(self):
        self.set_tilemap_render_source(scene_authoring_source(self.document))

    def _sync_animation_context(self):
        clip_set, current = animation_context(self.document)
        if clip_set is None:
            self.animation_widget.set_clips(())
            self.animation_widget.set_status(
                "No animation selected" if current is None else f"Missing animation asset for {current}"
            )
            return
        names = tuple(clip_set.clips)
        self.animation_widget.set_clips(names, current)
        self.animation_widget.set_status(f"{len(names)} clips available")

    def refresh_selection_context(self):
        self.refresh_inspector()
        self._sync_scene_authoring_context()
        self._sync_animation_context()
        self._sync_event_context()
        self.code_workspace.refresh_project_context()
        self._refresh_actions()

    def _selected_event_entity(self):
        sel = self.document.selection
        if sel.kind == "entity" and sel.value is not None and not sel.multiple:
            return sel.value
        if sel.kind == "component" and sel.value is not None and not sel.multiple:
            try:
                return sel.value.entity
            except RuntimeError:
                return None
        return None

    def _selected_event_scene(self):
        entity = self._selected_event_entity()
        return entity.scene if entity is not None else None

    def _sync_event_context(self):
        project = self.document.project
        entity = self._selected_event_entity()
        scene = self._selected_event_scene()
        if project is None or entity is None or scene is None:
            self.event_editor.show_empty("Select an Entity to edit events")
            return
        bindings = bindings_for_scene(project, scene)
        self.event_editor.set_entity_context(entity, bindings, project.event_programs)

    def _current_event_binding(self):
        project = self.document.project
        scene = self._selected_event_scene()
        if project is None or scene is None:
            return None, None
        bindings = bindings_for_scene(project, scene)
        binding_id = self.event_editor.selected_binding_id()
        return bindings, bindings.bindings.get(binding_id) if binding_id else None

    def _event_add_binding(self):
        project = self.document.project
        entity = self._selected_event_entity()
        scene = self._selected_event_scene()
        if project is None or entity is None or scene is None:
            return
        name, ok = QInputDialog.getText(self, "New Event", "Event name:", text="Interaction")
        if not ok:
            return
        program_id = new_id()
        binding_id = new_id()
        program = EventProgram([], name=name.strip() or "Interaction")
        binding = EventBinding(binding_id, entity.id, program_id, trigger=EventTriggerKind.ACTION)
        bindings = bindings_for_scene(project, scene)
        from .commands import CommandTransaction

        tx = CommandTransaction("Add Event")
        tx.add(AddEventProgramCommand(project.event_programs, program_id, program))
        tx.add(AddEventBindingCommand(bindings, binding))
        self.document.execute(tx)
        self.refresh_all()

    def _event_binding_changed(self, field, value):
        if field == "select":
            bindings, binding = self._current_event_binding()
            if binding is not None:
                self.event_editor._refreshing = True
                try:
                    self.event_editor._show_binding(binding, self.document.project.event_programs)
                finally:
                    self.event_editor._refreshing = False
            return
        bindings, binding = self._current_event_binding()
        if binding is None:
            return
        if field == "trigger":
            replacement = replace_binding_fields(binding, trigger=EventTriggerKind(value))
        elif field == "program_id":
            replacement = replace_binding_fields(binding, program_id=value)
        else:
            return
        self.document.execute(ReplaceEventBindingCommand(bindings, replacement, binding))
        self.refresh_all()

    def _event_add_condition(self):
        bindings, binding = self._current_event_binding()
        if binding is None:
            return
        name, ok = QInputDialog.getText(self, "Event Condition", "Switch name:", text="quest_started")
        if not ok or not name.strip():
            return
        cond = EventTriggerCondition(EventCondition("switch", name.strip(), "==", True))
        replacement = replace_binding_fields(binding, conditions=tuple(binding.conditions) + (cond,))
        self.document.execute(ReplaceEventBindingCommand(bindings, replacement, binding))
        self.refresh_all()

    def _event_make_instruction(self, kind):
        if kind == "dialogue":
            text, ok = QInputDialog.getText(self, "Dialogue", "Text:")
            if not ok:
                return None
            speaker, ok = QInputDialog.getText(self, "Dialogue", "Speaker:")
            if not ok:
                return None
            return EventInstruction("DIALOGUE", {"speaker": speaker, "text": text})
        if kind == "choice":
            prompt, ok = QInputDialog.getText(self, "Choice", "Prompt:")
            if not ok:
                return None
            return EventInstruction(
                "CHOICE",
                {
                    "prompt": prompt,
                    "choices": [
                        {"text": "Option 1", "value": 1},
                        {"text": "Option 2", "value": 2},
                    ],
                    "variable_name": "choice",
                },
            )
        if kind == "if":
            name, ok = QInputDialog.getText(self, "If", "Switch name:")
            if not ok or not name.strip():
                return None
            condition = EventCondition("switch", name.strip(), "==", True).to_data()
            return EventInstruction("JUMP_IF", {"condition": condition, "label": "target"})
        if kind == "switch":
            name, ok = QInputDialog.getText(self, "Set Switch", "Switch name:")
            if not ok or not name.strip():
                return None
            return EventInstruction("SET_SWITCH", {"name": name.strip(), "value": True})
        if kind == "variable":
            name, ok = QInputDialog.getText(self, "Set Variable", "Variable name:")
            if not ok or not name.strip():
                return None
            value, ok = QInputDialog.getText(self, "Set Variable", "Value:")
            if not ok:
                return None
            return EventInstruction("SET_VARIABLE", {"name": name.strip(), "value": value})
        if kind == "world":
            command, ok = QInputDialog.getText(self, "World Command", "Command:", text="TRANSFER")
            if not ok or not command.strip():
                return None
            raw_args, ok = QInputDialog.getText(
                self,
                "World Command",
                "Arguments (key=value, ...):",
                text=", ".join(f"{name}=" for name in WORLD_COMMAND_ARGUMENTS.get(command.strip().upper(), ())),
            )
            if not ok:
                return None
            try:
                args = parse_world_args(raw_args)
            except ValueError as exc:
                QMessageBox.warning(self, "World Command", str(exc))
                return None
            return EventInstruction("WORLD", {"command": command.strip().upper(), "args": args})
        return None

    def _event_add_command(self, kind):
        project = self.document.project
        _, binding = self._current_event_binding()
        if project is None or binding is None:
            return
        program = project.event_programs.get(binding.program_id)
        if program is None:
            return
        instruction = self._event_make_instruction(kind)
        if instruction is None:
            return
        row = self.event_editor.selected_command_index()
        index = len(program.instructions) if row < 0 else row + 1
        new_program = program_with_insert(program, index, instruction)
        self.document.execute(
            ReplaceEventProgramCommand(project.event_programs, binding.program_id, new_program, program)
        )
        self.refresh_all()

    def _event_remove_command(self, index):
        project = self.document.project
        _, binding = self._current_event_binding()
        if project is None or binding is None:
            return
        program = project.event_programs.require(binding.program_id)
        if not 0 <= index < len(program.instructions):
            return
        new_program = program_with_remove(program, index)
        self.document.execute(
            ReplaceEventProgramCommand(project.event_programs, binding.program_id, new_program, program)
        )
        self.refresh_all()

    def _event_move_command(self, old_index, new_index):
        project = self.document.project
        _, binding = self._current_event_binding()
        if project is None or binding is None:
            return
        program = project.event_programs.require(binding.program_id)
        new_program = program_with_move(program, old_index, new_index)
        self.document.execute(
            ReplaceEventProgramCommand(project.event_programs, binding.program_id, new_program, program)
        )
        self.refresh_all()

    def set_animation_clip_set_view(self, clip_set_id, clip_set):
        self.document.asset_views.set_clip_set(clip_set_id, clip_set)
        self.animation_widget.set_clips(tuple(clip_set.clips))
        self.animation_widget.set_status(f"{len(clip_set.clips)} clips available")

    def set_sprite_sheet_view(self, asset_id, sprite_sheet):
        self.document.asset_views.set_sprite_sheet(asset_id, sprite_sheet)
        self.viewport.texture_cache.clear()
        self.viewport.refresh()

    def set_tilemap_render_source(self, source):
        self.viewport.set_render_source(source)
        self.tile_palette.set_tileset(source.tileset if source is not None else None)
        layer = self.viewport.tile_tools.active_layer if source is not None else None
        self.tile_palette.set_layer(layer)
        self.tile_layers.set_tilemap(source.tilemap if source is not None else None, layer)

    def _select_tile_layer(self, layer):
        self.viewport.set_active_tile_layer(layer)
        self.tile_palette.set_layer(layer)

    def _add_tile_layer(self):
        source = self.viewport.render_source
        if source is None:
            return
        names = {l.name for l in source.tilemap.layers}
        index = 1
        name = "Layer"
        while name in names:
            index += 1
            name = f"Layer {index}"
        layer = TileLayer(name, order=len(source.tilemap.layers))
        self.document.execute(AddTileLayerCommand(source.tilemap, layer))
        self.viewport.set_active_tile_layer(layer)
        self.refresh_all()

    def _remove_tile_layer(self, layer):
        source = self.viewport.render_source
        if source is None:
            return
        try:
            self.document.execute(RemoveTileLayerCommand(source.tilemap, layer))
        except TileEditError:
            return
        self.viewport.tile_tools.active_layer = source.tilemap.layers[0]
        self.refresh_all()

    def _move_tile_layer(self, layer, index):
        source = self.viewport.render_source
        if source is None:
            return
        self.document.execute(ReorderTileLayerCommand(source.tilemap, layer, index))
        self.refresh_all()

    def _set_tile_layer_visible(self, layer, value):
        self.document.execute(SetTileLayerPropertyCommand(layer, "visible", bool(value)))
        self.refresh_all()

    def _set_tile_layer_collision(self, layer, value):
        self.document.execute(SetTileLayerPropertyCommand(layer, "collision_enabled", bool(value)))
        self.refresh_all()

    def _refresh_game_systems(self):
        if self.document.project is None:
            return
        for name in ("game_systems_editor", "animation_editor", "action_timeline_editor"):
            editor = getattr(self, name, None)
            if editor is not None:
                editor.refresh()

    def refresh_all(self):
        self.project_tree.refresh()
        self.refresh_asset_list()
        self.refresh_inspector()
        self._sync_scene_authoring_context()
        self._sync_animation_context()
        self._sync_event_context()
        self.code_workspace.refresh_project_context()
        self.rpg_authoring.rebuild()
        self._refresh_game_systems()
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
            self.set_tilemap_render_source(None)
        self.code_workspace.load_default_script()
        self.refresh_all()
        QTimer.singleShot(0, self.viewport.frame_game_camera)

    def refresh_asset_list(self):
        from .asset_thumbnails import ImageCache, asset_thumbnail, canonical_asset_thumbnail

        self.asset_list.clear()
        if self.document.project is None:
            return
        cache = ImageCache()
        for record in self.document.project.assets.records():
            item = QListWidgetItem(f"{record.kind}: {record.source_path}")
            icon = asset_thumbnail(self.document, record, cache)
            if icon is not None:
                item.setIcon(icon)
            self.asset_list.addItem(item)
        for asset in self.document.project.assets.snapshot():
            item = QListWidgetItem(f"{asset.kind}: {asset.source.uri}")
            icon = canonical_asset_thumbnail(self.document, asset, cache)
            if icon is not None:
                item.setIcon(icon)
            self.asset_list.addItem(item)

    def refresh_inspector(self):
        sel = self.document.selection
        if sel.kind == "none" or sel.value is None:
            if sel.multiple:
                self.inspector.show_properties(f"{len(sel.values)} selected", (("Count", len(sel.values), "int"),))
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
            self.inspector.show_component(type(obj).__name__, build_inspector_fields(obj))
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

    def _execute_structure(self, command, selection_kind=None, selection_value=None):
        self.document.execute(command)
        if selection_kind is not None:
            self.document.selection.set_single(selection_kind, selection_value)
        self.refresh_all()

    def rename_selected(self):
        sel = self.document.selection
        if sel.kind not in {"project", "scene", "entity"} or sel.value is None or sel.multiple:
            return False
        name, ok = QInputDialog.getText(self, "Rename", "Name:", text=sel.value.name)
        if not ok:
            return False
        try:
            command = build_rename_command(sel.value, name)
        except StructureEditError as exc:
            QMessageBox.warning(self, "Rename", str(exc))
            return False
        if command.new_name == command.old_name:
            return True
        self._execute_structure(command, sel.kind, sel.value)
        return True

    def add_scene(self):
        if self.document.project is None:
            return False
        name, ok = QInputDialog.getText(self, "Add Scene", "Name:", text="Scene")
        if not ok:
            return False
        try:
            command = build_add_scene_command(self.document.project, name)
        except SceneEditError as exc:
            QMessageBox.warning(self, "Add Scene", str(exc))
            return False
        self._execute_structure(command, "scene", command.scene)
        return True

    def delete_scene(self):
        sel = self.document.selection
        if sel.kind != "scene" or sel.value is None or sel.multiple or self.document.project is None:
            return False
        try:
            command = build_remove_scene_command(self.document.project, sel.value)
        except SceneEditError as exc:
            QMessageBox.warning(self, "Delete Scene", str(exc))
            return False
        self.document.execute(command)
        self.document.selection.set_single("scene", self.document.project.scenes()[0])
        self.refresh_all()
        return True

    def set_startup_scene(self):
        sel = self.document.selection
        project = self.document.project
        if project is None or sel.kind != "scene" or sel.multiple or sel.value is None:
            return False
        scene = sel.value
        if project.startup_scene_id == scene.id:
            return True
        self.document.execute(
            SetAttributeCommand(
                project,
                "startup_scene_id",
                scene.id,
                project.startup_scene_id,
                f"Set Startup Scene {scene.name}",
            )
        )
        self.refresh_all()
        return True

    def move_selected(self, delta):
        sel = self.document.selection
        if sel.multiple or sel.value is None:
            return False
        try:
            if sel.kind == "scene":
                project = self.document.project
                old = project.scene_index(sel.value)
                new = max(0, min(old + int(delta), len(project.scenes()) - 1))
                if new == old:
                    return True
                command = build_reorder_scene_command(project, sel.value, new)
            elif sel.kind == "entity":
                scene = sel.value.scene
                old = scene.entity_index(sel.value)
                new = max(0, min(old + int(delta), len(scene.entities()) - 1))
                if new == old:
                    return True
                command = build_reorder_entity_command(sel.value, new)
            else:
                return False
        except (SceneEditError, ValueError) as exc:
            QMessageBox.warning(self, "Move", str(exc))
            return False
        self.document.execute(command)
        self.refresh_all()
        return True

    def toggle_selected_entity_enabled(self):
        sel = self.document.selection
        if sel.kind != "entity" or sel.multiple or sel.value is None:
            return False
        entity = sel.value
        self.document.execute(
            SetAttributeCommand(
                entity,
                "enabled",
                not entity.enabled,
                entity.enabled,
                f"{'Disable' if entity.enabled else 'Enable'} Entity {entity.name}",
            )
        )
        self.refresh_all()
        return True

    def add_entity(self):
        sel = self.document.selection
        scene = (
            sel.value if sel.kind == "scene" else getattr(sel.value, "scene", None) if sel.kind == "entity" else None
        )
        if scene is None or sel.multiple:
            return False
        name, ok = QInputDialog.getText(self, "Add Entity", "Name:", text="Entity")
        if not ok:
            return False
        try:
            command = build_add_entity_command(scene, name)
        except StructureEditError as exc:
            QMessageBox.warning(self, "Add Entity", str(exc))
            return False
        self._execute_structure(command, "entity", command.entity)
        return True

    def add_component(self):
        sel = self.document.selection
        if sel.kind != "entity" or sel.value is None or sel.multiple:
            return False
        choices = [c for c in build_component_choices(self.document.component_registry, sel.value) if c.addable]
        if not choices:
            QMessageBox.information(self, "Add Component", "No addable registered components.")
            return False
        labels = [c.display_name for c in choices]
        label, ok = QInputDialog.getItem(self, "Add Component", "Component:", labels, 0, False)
        if not ok:
            return False
        choice = choices[labels.index(label)]
        try:
            command = build_add_component_command(sel.value, choice.component_type)
        except StructureEditError as exc:
            QMessageBox.warning(self, "Add Component", str(exc))
            return False
        self._execute_structure(command, "component", command.component)
        return True

    def _focused_record_family(self):
        """The authoring record list that has keyboard focus, if any (record copy/cut/paste/delete)."""
        from .authoring_hub_widget import AdapterFamilyWidget

        widget = QApplication.focusWidget()
        while widget is not None and not isinstance(widget, AdapterFamilyWidget):
            widget = widget.parentWidget()
        return widget

    def cut_selected(self):
        family = self._focused_record_family()
        if family is not None:
            return family.cut_selected()
        sel = self.document.selection
        if sel.kind != "entity" or sel.value is None or sel.multiple:
            return False
        self.document.clipboard.copy_entity(sel.value)
        return self.delete_selected()

    def copy_selected(self):
        family = self._focused_record_family()
        if family is not None:
            return bool(family.copy_selected())
        sel = self.document.selection
        if sel.kind != "entity" or sel.value is None or sel.multiple:
            return False
        self.document.clipboard.copy_entity(sel.value)
        self._refresh_actions()
        return True

    def duplicate_selected(self):
        sel = self.document.selection
        if sel.kind != "entity" or not sel.values:
            return False
        commands = [build_duplicate_entity_command(value, self.document.component_registry) for value in sel.values]
        if len(commands) == 1:
            self._execute_structure(commands[0], "entity", commands[0].duplicate_entity)
        else:
            tx = CommandTransaction(f"Duplicate {len(commands)} Entities", commands)
            self.document.execute(tx)
            self.document.selection.set_many("entity", tuple(command.duplicate_entity for command in commands))
            self.refresh_all()
        return True

    def paste_entity(self):
        family = self._focused_record_family()
        if family is not None:
            return bool(family.paste())
        sel = self.document.selection
        scene = (
            sel.value if sel.kind == "scene" else getattr(sel.value, "scene", None) if sel.kind == "entity" else None
        )
        if scene is None or sel.multiple:
            return False
        try:
            command = build_paste_entity_command(scene, self.document.clipboard, self.document.component_registry)
        except ValueError as exc:
            QMessageBox.warning(self, "Paste", str(exc))
            return False
        self._execute_structure(command, "entity", command.entity)
        return True

    def delete_selected(self):
        family = self._focused_record_family()
        if family is not None:
            return family.delete_selected()
        sel = self.document.selection
        try:
            if sel.kind == "entity" and sel.values:
                entities = tuple(sel.values)
                scenes = {id(entity.scene): entity.scene for entity in entities}
                commands = [build_remove_entity_command(entity) for entity in entities]
                if len(commands) == 1:
                    self.document.execute(commands[0])
                else:
                    self.document.execute(CommandTransaction(f"Delete {len(commands)} Entities", commands))
                if len(scenes) == 1:
                    self.document.selection.set_single("scene", next(iter(scenes.values())))
                else:
                    self.document.selection.set_single("project", self.document.project)
                self.refresh_all()
                return True
            if sel.kind == "component" and sel.value is not None and not sel.multiple:
                entity = sel.value.entity
                self._execute_structure(build_remove_component_command(sel.value), "entity", entity)
                return True
        except StructureEditError as exc:
            QMessageBox.warning(self, "Delete", str(exc))
        return False

    def edit_selected_component_field(self, field_name, raw_value):
        sel = self.document.selection
        if sel.kind != "component" or sel.value is None or sel.multiple:
            return False, "No single component selected"
        try:
            command = build_set_component_field_command(sel.value, field_name, raw_value)
            if command.new_value == command.old_value:
                return True, None
            self.document.execute(command)
        except EditError as exc:
            return False, str(exc)
        self._refresh_actions()
        self._refresh_title()
        self.viewport.refresh()
        return True, None

    def undo(self):
        if not self.document.undo():
            return False
        self.document.selection.set_single("project" if self.document.project else "none", self.document.project)
        self.refresh_all()
        return True

    def redo(self):
        if not self.document.redo():
            return False
        self.document.selection.set_single("project" if self.document.project else "none", self.document.project)
        self.refresh_all()
        return True

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
        self.refresh_all()
        return True

    def open_project(self):
        if self.document.dirty:
            answer = QMessageBox.question(
                self,
                "Unsaved Changes",
                "This project has unsaved changes. Open another project anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return False
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Asteria Project", "", "Asteria Project (*.asteria.json *.json)"
        )
        if not path:
            return False
        try:
            load_document(self.document, path)
            self._resolve_project_resources()
        except (EditorStorageError, EditorResourceError) as exc:
            QMessageBox.critical(self, "Open Project", str(exc))
            return False
        self.play_session = None
        self._load_playtest_profiles()
        self.refresh_all()
        QTimer.singleShot(0, self.viewport.frame_game_camera)
        return True

    def _load_playtest_profiles(self):
        if not hasattr(self, "playtest_profile_combo"):
            return
        self.playtest_profile_combo.clear()
        self.playtest_profile_library = None
        if self.document.project is None or self.document.file_path is None:
            self.playtest_profile_combo.addItem("Default", "")
            return
        library = PlaytestProfileLibrary(self.document.file_path.resolve().parent)
        self.playtest_profile_library = library
        profiles = library.profiles()
        if not profiles:
            self.playtest_profile_combo.addItem("Default", "")
            return
        default_index = 0
        for index, profile in enumerate(profiles):
            self.playtest_profile_combo.addItem(profile.display_name, profile.profile_id)
            if profile.default:
                default_index = index
        self.playtest_profile_combo.setCurrentIndex(default_index)

    def selected_playtest_profile_id(self):
        if not hasattr(self, "playtest_profile_combo"):
            return None
        value = self.playtest_profile_combo.currentData()
        return str(value) if value else None

    def _start_play(self, *, from_start, spawn=None, title="Run Project"):
        """Launch the play-test with the debug channel and log capture (EDT-10, EDT-11)."""
        try:
            self.play_session = create_play_session(self.document, from_start=from_start)
            self.runtime_process = launch_play_session(self.play_session, debug=True, capture_log=True, spawn=spawn)
        except (PlayModeError, RuntimeLaunchError) as exc:
            if self.play_session is not None:
                self.play_session.stop()
            self.play_session = None
            self.runtime_process = None
            QMessageBox.warning(self, title, str(exc))
            return False
        self._last_play = {"from_start": from_start, "spawn": spawn, "title": title}
        self._shown_log = ""
        if self.runtime_process.debug_port is not None:
            self.debugger_widget.attach(self.runtime_process.debug_port, self.runtime_process.debug_token)
        where = "" if spawn is None else f" from ({spawn[0]:g}, {spawn[1]:g})"
        self.console.setText(f"Runtime preview: {self.play_session.runtime_scene.name}{where}")
        self.statusBar().showMessage(f"Playing — {self.play_session.runtime_scene.name}{where}")
        self._refresh_actions()
        return True

    def play_project(self):
        return self._start_play(from_start=True)

    def play_current_scene(self):
        return self._start_play(from_start=False, title="Play")

    def play_from_selection(self):
        """Play the current scene with the player starting at the selected entity's position."""
        from asteria.core import Transform

        entity = self._selected_entity()
        if entity is None or not entity.has(Transform):
            QMessageBox.information(self, "Play from Selection", "Select an entity in the scene first.")
            return False
        t = entity.get(Transform)
        return self._start_play(from_start=False, spawn=(t.x, t.y), title="Play from Selection")

    def restart_play(self):
        """Fast restart: stop the running play-test and launch it again the same way."""
        last = getattr(self, "_last_play", None)
        if last is None:
            return self.play_project()
        if self.play_session is not None and self.play_session.active:
            self.stop_play()
        return self._start_play(**last)

    def stop_play(self):
        if self.play_session is None or not self.play_session.active:
            return False
        self._flush_runtime_log()
        self.debugger_widget.detach()
        if self.runtime_process is not None:
            self.runtime_process.stop()
            self.runtime_process = None
        self.play_session.stop()
        self.console.setText("Play session stopped")
        self.statusBar().showMessage("Play session stopped", 2000)
        self._refresh_actions()
        return True

    def _flush_runtime_log(self):
        """Show what the game printed so far in the Console (play-test log panel)."""
        if self.runtime_process is None:
            return
        text = self.runtime_process.read_log()
        if text and text != getattr(self, "_shown_log", ""):
            self._shown_log = text
            self.console.setText(text)

    def _poll_runtime_process(self):
        if self.runtime_process is None:
            return
        flush = getattr(self, "_flush_runtime_log", None)
        if flush is not None:
            flush()
        if self.runtime_process.running:
            return
        debugger = getattr(self, "debugger_widget", None)
        if debugger is not None:
            debugger.detach()
        self.runtime_process.stop()
        self.runtime_process = None
        if self.play_session is not None and self.play_session.active:
            self.play_session.stop()
        if getattr(self, "_shown_log", ""):
            self.console.append("Runtime preview closed")  # keep the play-test log visible
        else:
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


def launch_editor(project=None):
    import sys

    app = QApplication.instance() or QApplication(sys.argv)
    apply_asteria_theme(app)
    window = AsteriaEditorWindow(project)
    window.show()
    return app.exec()
