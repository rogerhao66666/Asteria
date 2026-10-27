import os
import shutil
import sys
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
from .i18n import english
from .icons import icon as workspace_icon
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
from .scrolling_tabs import ScrollingTabWidget, WrappingTabWidget, scrollable
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
    from PySide6.QtCore import QSize, Qt, QTimer
    from PySide6.QtGui import QAction, QKeySequence
    from PySide6.QtWidgets import (
        QApplication,
        QDockWidget,
        QFileDialog,
        QFrame,
        QInputDialog,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QProxyStyle,
        QScrollArea,
        QStyle,
        QTabBar,
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
from .skeleton_widget import SkeletonViewerWidget
from .skeleton_workspace_page import SkeletonWorkspacePage
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
from .widgets import InspectorWidget, ProjectTreeWidget, asset_icon_name

if QApplication is not None:

    class _CenteredDockTabStyle(QProxyStyle):
        def styleHint(self, hint, option=None, widget=None, returnData=None):
            if hint == QStyle.StyleHint.SH_TabBar_Alignment:
                return int(Qt.AlignmentFlag.AlignHCenter)
            return super().styleHint(hint, option, widget, returnData)


def _dock_card(widget):
    host = QWidget()
    host.setObjectName("DockContentHost")
    outer = QVBoxLayout(host)
    outer.setContentsMargins(12, 12, 12, 16)
    outer.setSpacing(0)
    card = QFrame(host)
    card.setObjectName("DockContentCard")
    card.setAttribute(Qt.WA_StyledBackground, True)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(1, 1, 1, 1)
    layout.setSpacing(0)
    area = scrollable(widget)
    area.setProperty("dockContentSurface", True)
    area.viewport().setProperty("dockContentSurface", True)
    widget.setProperty("dockContentSurface", True)
    area.setObjectName(f"{widget.metaObject().className()}Scroll")
    area.setViewportMargins(0, 0, 0, 0)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    layout.addWidget(area)
    outer.addWidget(card)
    return host


def _dock_scrollable(widget):
    return _dock_card(widget)


def _scene_dock_scrollable(widget):
    return _dock_card(widget)


_WORKSPACE_ICON = {
    WorkspaceMode.SCENE: "scene",
    WorkspaceMode.RPG: "rpg",
    WorkspaceMode.BATTLE: "battle",
    WorkspaceMode.UI: "ui",
    WorkspaceMode.EVENT: "events",
    WorkspaceMode.CODE: "code",
    WorkspaceMode.MULTIPLAYER: "multiplayer",
}


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
        self.setDocumentMode(True)
        self.resize(1280, 800)
        self.setMinimumSize(1000, 640)  # below this the panels squeeze text (audited sizes)

        self.viewport = SceneViewportWidget(self.document)
        self.code_workspace = CodeWorkspaceWidget(self.document, self)
        self.event_editor = EventEditorWidget(self)
        self.animation_widget = AnimationWidget(self)

        self.authoring_controllers = IntegratedAuthoringControllers(self.document)
        self.project_workspace_controller = ProjectWorkspaceController(self.document)
        self.playtest_profile_library = None

        self.rpg_authoring = FamilyHostWidget(
            "Game Data", self.authoring_controllers.rpg_categories, self
        )
        # Generic placement: "Place Character from Sprite Sheet…" waits for one map-cell click
        # (CB14).
        self.viewport.characterCellClicked.connect(self._place_character_at)
        self.rpg_workspace = ScrollingTabWidget(self)
        self.rpg_workspace.setObjectName("DatabaseWorkspaceTabs")
        self.rpg_workspace.tabBar().setObjectName("DatabaseWorkspaceTabBar")
        self.rpg_workspace.tabBar().setDrawBase(True)
        self.rpg_workspace.addTab(self.rpg_authoring, "Game Data")
        from .game_systems_authoring import GameSystemsAuthoringController
        from .game_systems_widget import GameSystemsEditorWidget

        self.game_systems_editor = GameSystemsEditorWidget(
            GameSystemsAuthoringController(self.document), self
        )
        self.game_systems_editor.changed.connect(self.refresh_all)
        self.game_systems_editor.pause.open_layout = self.open_menu_layout  # D98
        self.rpg_workspace.addTab(self.game_systems_editor, "Game Systems")
        from .enemy_ai_widget import EnemyAIEditorWidget

        self.enemy_ai_editor = EnemyAIEditorWidget(self.document, self)
        self.enemy_ai_editor.changed.connect(self.refresh_all)
        self.rpg_workspace.addTab(self.enemy_ai_editor, "Enemy AI")
        from .behavior_tree_widget import BehaviorTreeEditorWidget

        self.behavior_tree_editor = BehaviorTreeEditorWidget(self.document, self)
        self.behavior_tree_editor.changed.connect(self.refresh_all)
        self.rpg_workspace.addTab(self.behavior_tree_editor, "Behavior Trees")
        from .combat_workspace import CombatWorkspace

        # D22 A9: attacks, projectiles, loot rarities and affixes with live previews
        self.combat_editor = CombatWorkspace(self.document, self)
        self.rpg_workspace.addTab(self.combat_editor, "Real-Time Combat")
        from .game_start_authoring import GameStartAuthoringController
        from .game_start_widget import GameStartEditorWidget

        self.game_start_editor = GameStartEditorWidget(
            GameStartAuthoringController(self.document), self
        )
        self.game_start_editor.changed.connect(self.refresh_all)
        self.rpg_workspace.addTab(self.game_start_editor, "Game Start")
        self.battle_authoring = FamilyHostWidget(
            "Battle Rules", self.authoring_controllers.battle_categories, self
        )
        self.presentation_authoring = FamilyHostWidget(
            "Battle Presentation", self.authoring_controllers.presentation_categories, self
        )

        # eleven tabs: they wrap onto rows so none hides behind the scroll arrows
        self.ui_workspace = WrappingTabWidget(self)
        self.ui_workspace.setObjectName("PresentationWorkspaceTabs")
        self.ui_workspace.tabBar().setObjectName("PresentationWorkspaceTabBar")
        self.ui_workspace.tabBar().setDrawBase(True)
        self.ui_workspace.addTab(self.presentation_authoring, "Battle Screen")
        from .menu_layout_widget import MenuLayoutWorkspace

        # U2b: every menu screen laid out on a live canvas (D98: the old Menu Records tab is
        # gone: its stat and slot names live in Game Systems ▸ Stats and Equipment Slots)
        self.menu_layout_editor = MenuLayoutWorkspace(
            self.document,
            self,
            open_in_game=self.play_menu_screen,
            open_pause_menu=self.open_pause_menu,
        )
        self.menu_layout_editor.changed.connect(self._refresh_actions)
        self.ui_workspace.addTab(self.menu_layout_editor, "Menu Screens")
        self.ui_workspace.addTab(self.animation_widget, "Animation Preview")
        from .action_timeline_widget import ActionTimelineWidget
        from .animation_editor_widget import AnimationEditorWidget

        self.animation_editor = AnimationEditorWidget(self.document, self)
        self.ui_workspace.addTab(self.animation_editor, "Sprite Animation")
        from .animation_state_machine_widget import AnimationStateMachineWidget

        self.state_machine_editor = AnimationStateMachineWidget(self.document, self)
        self.state_machine_editor.changed.connect(self.refresh_all)
        self.ui_workspace.addTab(self.state_machine_editor, "Animation States")
        from .character_composition_widget import CharacterCompositionWidget

        self.composition_editor = CharacterCompositionWidget(self.document, self)
        self.composition_editor.changed.connect(self.refresh_all)
        self.ui_workspace.addTab(self.composition_editor, "Character Composition")
        self.action_timeline_editor = ActionTimelineWidget(self.document, self)
        self.ui_workspace.addTab(self.action_timeline_editor, "Ability Timelines")
        from .vfx_widget import VFXEditorWidget

        self.vfx_editor = VFXEditorWidget(self.document, self)
        self.vfx_editor.changed.connect(self.refresh_all)
        self.vfx_editor.openTimeline.connect(self._open_action_timeline)
        self.vfx_editor.openAnimation.connect(self._open_animation_sheet)
        self.ui_workspace.addTab(self.vfx_editor, "Battle Effects")
        from .particle_effect_widget import ParticleEffectWidget

        self.particle_editor = ParticleEffectWidget(self.document, self)
        self.particle_editor.changed.connect(self.refresh_all)
        self.ui_workspace.addTab(self.particle_editor, "Particle Effects")
        from .input_map_widget import InputMapWidget

        self.input_map_editor = InputMapWidget(self.document, self)
        self.input_map_editor.changed.connect(self.refresh_all)
        self.ui_workspace.addTab(self.input_map_editor, "Controls")

        self.game_flow_overview = GameFlowOverviewWidget(self.document, self)
        self.events_workspace = ScrollingTabWidget(self)
        self.events_workspace.setObjectName("EventsWorkspaceTabs")
        self.events_workspace.tabBar().setObjectName("EventsWorkspaceTabBar")
        self.events_workspace.tabBar().setDrawBase(True)
        self.events_workspace.addTab(self.event_editor, "Entity Events")
        self.events_workspace.addTab(self.game_flow_overview, "Interaction Overview")
        from .event_flow_widget import EventFlowWidget

        self.event_flow_editor = EventFlowWidget(self.document, self)
        self.event_flow_editor.changed.connect(self.refresh_all)
        self.events_workspace.addTab(self.event_flow_editor, "Common && Battle Events")

        from .multiplayer_workspace import MultiplayerWorkspaceWidget

        self.multiplayer_workspace = MultiplayerWorkspaceWidget(self.document, self)

        self.workspace = EditorWorkspace(
            {
                WorkspaceMode.SCENE: self.viewport,
                WorkspaceMode.RPG: self.rpg_workspace,
                WorkspaceMode.BATTLE: self.battle_authoring,
                WorkspaceMode.UI: self.ui_workspace,
                WorkspaceMode.EVENT: self.events_workspace,
                WorkspaceMode.CODE: self.code_workspace,
                WorkspaceMode.MULTIPLAYER: self.multiplayer_workspace,
            },
            self,
        )
        self.workspace.modeChanged.connect(self._workspace_mode_changed)
        self.setCentralWidget(self.workspace)

        self.project_tree = ProjectTreeWidget(self.document)
        left = QDockWidget("Project", self)
        left.setObjectName("ProjectSceneDock")
        left.setWidget(_scene_dock_scrollable(self.project_tree))
        left.setMinimumWidth(264)  # the three tabs (Project, Tiles, Layers) show whole
        self.addDockWidget(Qt.LeftDockWidgetArea, left)

        self.tile_palette = TilePaletteWidget(self)
        palette_dock = QDockWidget("Tiles", self)
        palette_dock.setObjectName("TilePaletteDock")
        palette_scroll = _scene_dock_scrollable(self.tile_palette)
        self.tile_palette.bind_dock_scroll_area(palette_scroll.findChild(QScrollArea))
        palette_dock.setWidget(palette_scroll)
        self.addDockWidget(Qt.LeftDockWidgetArea, palette_dock)
        self.tabifyDockWidget(left, palette_dock)
        self.tile_palette.modeChanged.connect(self.viewport.set_tile_mode)
        self.tile_palette.tileSelected.connect(self.viewport.set_selected_tile)
        self.tile_palette.stampSelected.connect(
            lambda rows: self.viewport.tile_tools.set_stamp(rows)
        )
        self.tile_palette.brushSizeChanged.connect(
            lambda size: setattr(self.viewport.tile_tools, "brush_size", int(size))
        )
        self.viewport.tilesPicked.connect(self.tile_palette.show_picked)
        self.viewport.toolKeyPressed.connect(self.tile_palette.handle_tool_key)
        self.tile_palette.terrainChanged.connect(self.viewport.set_terrain)
        self.tile_palette.regionChanged.connect(self.viewport.set_region)
        self.tile_palette.areaRuleChanged.connect(self._set_region_rule)
        self.tile_palette.areaRuleRemoved.connect(self._remove_region_rule)
        self.tile_palette.createMapRuleSetRequested.connect(self._create_map_rule_set)
        self.tile_palette.doodadChanged.connect(self.viewport.set_doodad)

        self.skeleton_viewer = SkeletonViewerWidget(
            self, command_stack=self.document.commands, document=self.document
        )
        self.skeleton_viewer.changed.connect(self.refresh_all)
        self.skeleton_page = SkeletonWorkspacePage(self.skeleton_viewer, self)
        skeleton_tab = self.ui_workspace.addTab(self.skeleton_page, "Skeleton")
        self.ui_workspace.setTabIcon(skeleton_tab, workspace_icon("animation"))
        self.ui_workspace.currentChanged.connect(lambda _index: self._polish_presentation_pages())
        self._polish_presentation_pages()

        self.tile_layers = TileLayersWidget(self)
        layers_dock = QDockWidget("Layers", self)
        layers_dock.setObjectName("LayersDock")
        layers_dock.setWidget(_scene_dock_scrollable(self.tile_layers))
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
        self.event_editor.editCommandRequested.connect(self._event_edit_command)
        self.code_workspace.saved.connect(self._code_script_saved)
        self.code_workspace.runRequested.connect(self._run_authoring_script)

        self.inspector = InspectorWidget(self.document)
        right = QDockWidget("Inspector", self)
        right.setObjectName("InspectorDock")
        right.setWidget(self.inspector)
        self.addDockWidget(Qt.RightDockWidgetArea, right)

        self.asset_list = QListWidget()
        self.asset_list.setObjectName("AssetList")
        self.asset_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.asset_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.asset_list.customContextMenuRequested.connect(self._asset_context_menu)
        bottom = QDockWidget("Assets", self)
        bottom.setObjectName("AssetsDock")
        bottom.setWidget(_dock_card(self.asset_list))
        self.addDockWidget(Qt.BottomDockWidgetArea, bottom)

        console_panel = QWidget()
        console_panel.setObjectName("ConsolePanel")
        console_layout = QVBoxLayout(console_panel)
        console_layout.setContentsMargins(0, 0, 0, 0)

        self.console = QTextEdit()
        self.console.setObjectName("ConsoleOutput")
        self.console.setReadOnly(True)
        self.console.setAcceptRichText(False)
        console_layout.addWidget(self.console)

        console = QDockWidget("Console", self)
        console.setObjectName("ConsoleDock")
        console.setWidget(_dock_card(console_panel))
        self.addDockWidget(Qt.BottomDockWidgetArea, console)
        self.tabifyDockWidget(bottom, console)
        from .debugger_widget import DebuggerWidget

        self.debugger_widget = DebuggerWidget(self)
        debugger_dock = QDockWidget("Debugger", self)
        debugger_dock.setObjectName("DebuggerDock")
        debugger_dock.setWidget(_dock_card(self.debugger_widget))
        self.addDockWidget(Qt.BottomDockWidgetArea, debugger_dock)
        self.tabifyDockWidget(bottom, debugger_dock)
        from .profiler_widget import ProfilerWidget

        self.profiler_widget = ProfilerWidget(lambda: self.debugger_widget.client, self)
        profiler_dock = QDockWidget("Profiler", self)
        profiler_dock.setObjectName("ProfilerDock")
        profiler_dock.setWidget(_dock_scrollable(self.profiler_widget))
        self.addDockWidget(Qt.BottomDockWidgetArea, profiler_dock)
        self.tabifyDockWidget(bottom, profiler_dock)
        from .problems_widget import ProblemsWidget

        self.problems_widget = ProblemsWidget(self.document, self)
        self.problems_widget.navigate.connect(self.navigate_to_problem)
        self.problems_dock = QDockWidget("Problems", self)
        self.problems_dock.setObjectName("ProblemsDock")
        self.problems_dock.setWidget(_dock_card(self.problems_widget))
        self.problems_widget.counted.connect(
            lambda n: self.problems_dock.setWindowTitle(f"Problems ({n})" if n else "Problems")
        )
        self.addDockWidget(Qt.BottomDockWidgetArea, self.problems_dock)
        self.tabifyDockWidget(bottom, self.problems_dock)
        console.raise_()
        # Default dock sizes: wide enough that panel tables (Inspector Property / Value / Type) and
        # the
        # project tree read without clipping; the central workspace keeps the rest.
        right.setMinimumWidth(260)
        self._default_dock_sizes = ([left, right], [240, 300], [bottom], [200])
        self._layout_restored = False

        # The native macOS tab base draws a redundant rounded line behind
        # tabified docks. Individual tabs retain their own visual states.
        for dock_tabs in self.findChildren(QTabBar):
            dock_tabs.setDrawBase(False)
        from .dock_title import decorate_dock

        for dock, (icon_name, accent) in {
            left: ("project", "project"),
            palette_dock: ("tiles", "tiles"),
            layers_dock: ("layers", "layers"),
            right: ("inspector", "inspector"),
            bottom: ("assets", "assets"),
            console: ("console", "console"),
            debugger_dock: ("debugger", "debugger"),
            profiler_dock: ("profiler", "profiler"),
            self.problems_dock: ("problems", "problems"),
        }.items():
            decorate_dock(dock, icon_name, accent)
        for dock in self.findChildren(QDockWidget):
            dock.dockLocationChanged.connect(self._schedule_dock_tab_cleanup)
            dock.topLevelChanged.connect(self._schedule_dock_tab_cleanup)
        self._schedule_dock_tab_cleanup()

        self._build_actions()
        QApplication.instance().focusChanged.connect(self._focus_changed)
        self._load_playtest_profiles()
        left.raise_()
        self._workspace_mode_changed(self.workspace.mode.value)
        self.refresh_all()
        QTimer.singleShot(0, self.viewport, self.viewport.frame_initial)
        # the big workspaces are built one after another once the window is up, so the first
        # switch to Game Data, Battle or Presentation is as quick as any later one
        self._warm = [WorkspaceMode.RPG, WorkspaceMode.BATTLE, WorkspaceMode.UI]
        QTimer.singleShot(400, self, self._warm_next_workspace)

    def _warm_next_workspace(self):
        if not getattr(self, "_warm", None) or self.document.project is None:
            return
        self._ensure_workspace_fresh(self._warm.pop(0))
        if self._warm:
            QTimer.singleShot(150, self, self._warm_next_workspace)

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
            if bar.objectName() in {"BottomPanelDockTabs", "LeftSceneDockTabs"}:
                if not isinstance(bar.style(), _CenteredDockTabStyle):
                    # a QProxyStyle owns the style it wraps: give it its own base, made from
                    # the application style's name. Wrapping the shared application style
                    # deleted it with the window, and QApplication then crashed on exit.
                    style = _CenteredDockTabStyle(QApplication.style().name())
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

    def begin_character_placement(self, visual, status_widget=None):
        """Switch to Scene and wait for one map-cell click to place a ``CharacterVisualSet``."""
        status_widget = status_widget or self._status_sink()
        bundle = visual
        project = self.document.project
        scene = self.viewport.current_scene()
        if project is None or scene is None:
            status_widget.status.setText(
                "Open a project and select a scene before creating a character"
            )
            return None
        self._pending_character_visual = bundle
        self._placement_status_widget = status_widget
        self.workspace.set_mode(WorkspaceMode.SCENE)
        self.viewport.begin_character_placement()
        status_widget.status.setText("Click a map cell to place this character")
        return bundle

    def _status_sink(self):
        """Object with ``.status.setText`` that reports to the window status bar."""
        bar = self.statusBar()
        return SimpleNamespace(
            status=SimpleNamespace(setText=lambda text: bar.showMessage(text, 6000))
        )

    def place_character_from_sheet(self, path=None, name=None):
        """Place a playable character from any 3x4 walking sheet (rows down/left/right/up).

        The sheet is copied next to a saved project so the project stays
        portable; for an unsaved project it is referenced where it is.
        """
        project = self.document.project
        if project is None:
            return None
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "Walking Sprite Sheet", "", "Images (*.png)"
            )
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
        command = InstantiatePrefabCommand(
            project, self.document.component_registry, scene, prefab_id, x, y
        )
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
        command = apply_instance_to_prefab_command(
            self.document.project, self.document.component_registry, entity
        )
        return self._run_prefab_command(
            command, "Prefab updated; other instances kept their overrides"
        )

    def revert_instance_to_prefab(self):
        from asteria.core.prefab import PrefabInstanceComponent

        from .prefab_commands import RevertInstanceCommand

        entity = self._selected_entity()
        if entity is None or not entity.has(PrefabInstanceComponent):
            self.statusBar().showMessage("Select a prefab instance", 6000)
            return None
        command = RevertInstanceCommand(
            self.document.project, self.document.component_registry, entity
        )
        return self._run_prefab_command(command, f"{entity.name} matches its prefab again")

    def _place_character_at(self, cell):
        """Commit the pending ``CharacterVisualSet`` at the map cell clicked in Scene."""
        visual = getattr(self, "_pending_character_visual", None)
        if visual is None:
            return None
        project = self.document.project
        scene = self.viewport.current_scene()
        status_widget = getattr(self, "_placement_status_widget", None) or self._status_sink()
        if project is None or scene is None:
            self.viewport.end_character_placement()
            self._pending_character_visual = None
            self._placement_status_widget = None
            status_widget.status.setText("Character placement cancelled: no active scene")
            return None
        cell = (int(cell[0]), int(cell[1]))
        try:
            command = CreateCharacterCommand(
                visual,
                project,
                scene,
                cell,
                display_name=getattr(self, "_pending_character_name", None),
            )
            self.document.execute(command)
        except Exception as exc:
            status_widget.status.setText(f"Character creation failed: {exc}")
            return None
        self._pending_character_visual = None
        self._placement_status_widget = None
        self.viewport.end_character_placement()
        self.document.select_entity(command.created.entity)
        status_widget.status.setText(
            f"Created {command.created.actor.display_name} at map cell {cell[0]}, {cell[1]}"
        )
        # the new sheet joins the sprite sheet choices and draws in Scene
        self._resolve_project_resources()
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
            (
                getattr(self, "multiplayer_workspace_action", None),
                WorkspaceMode.MULTIPLAYER,
            ),
        ):
            if action is not None:
                action.setChecked(current == candidate)
        self._switch_workspace_docks(current)
        # rebuilt only when something changed since it was last shown: switching back and
        # forth between Game Data and Battle no longer rebuilds every page each time
        self._ensure_workspace_fresh(current)

    # each workspace's pages, rebuilt on their own (refresh_all rebuilds only the one shown;
    # the others wait until they are opened)
    _WORKSPACE_EDITORS = {
        WorkspaceMode.RPG: (
            "game_systems_editor",
            "game_start_editor",
            "enemy_ai_editor",
            "behavior_tree_editor",
        ),
        WorkspaceMode.UI: (
            "animation_editor",
            "state_machine_editor",
            "composition_editor",
            "action_timeline_editor",
            "vfx_editor",
            "input_map_editor",
        ),
        WorkspaceMode.EVENT: ("event_flow_editor",),
    }

    def _rebuild_workspace(self, mode):
        if mode == WorkspaceMode.CODE:
            self.code_workspace.refresh_project_context()
        elif mode == WorkspaceMode.RPG:
            self.rpg_authoring.rebuild()
        elif mode == WorkspaceMode.BATTLE:
            self.battle_authoring.rebuild()
        elif mode == WorkspaceMode.UI:
            self.presentation_authoring.rebuild()
            self.menu_layout_editor.rebuild()
        elif mode == WorkspaceMode.EVENT:
            self.game_flow_overview.refresh()
        elif mode == WorkspaceMode.MULTIPLAYER:
            self.multiplayer_workspace.refresh_profile()
        if self.document.project is not None:
            for name in self._WORKSPACE_EDITORS.get(mode, ()):
                editor = getattr(self, name, None)
                if editor is not None:
                    editor.refresh()
        if mode in (WorkspaceMode.UI, WorkspaceMode.EVENT, WorkspaceMode.CODE):
            self._polish_presentation_pages(mode)

    def _ensure_workspace_fresh(self, mode, *, force=False):
        """Rebuild ``mode``'s pages if the project changed (an edit, an undo, a refresh) since
        they were last built for it."""
        mode = WorkspaceMode(mode)
        stamp = (
            id(self.document.project),
            self.document.revision,
            getattr(self, "_refresh_epoch", 0),
        )
        fresh = self.__dict__.setdefault("_workspace_stamps", {})
        if force or fresh.get(mode) != stamp:
            self._rebuild_workspace(mode)
            fresh[mode] = stamp

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
        self.console.setText(
            result.stdout.rstrip() if result.stdout else "Script completed successfully"
        )
        self.statusBar().showMessage("Script finished", 3000)
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

        from .theme import CURRENT, PALETTES

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

        from .i18n import CURRENT as LANGUAGE
        from .i18n import LANGUAGES

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
            action.setIcon(workspace_icon(_WORKSPACE_ICON[mode]))
            toolbar.addAction(action)
            toolbar.widgetForAction(action).setProperty("workspace", _WORKSPACE_ICON[mode])
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
        toolbar.addSeparator()
        self.play_action.setIcon(workspace_icon("play"))
        self.stop_action.setIcon(workspace_icon("stop"))
        self.reset_view_action.setIcon(workspace_icon("target"))
        toolbar.addAction(self.play_action)
        toolbar.addAction(self.stop_action)
        toolbar.addAction(self.reset_view_action)
        toolbar.widgetForAction(self.play_action).setObjectName("PlayButton")
        toolbar.widgetForAction(self.stop_action).setObjectName("StopButton")
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

    def _resolve_project_resources(self):
        resolve_project_resources(self.document)
        self.viewport.texture_cache.clear()
        self._sync_scene_authoring_context()
        self._sync_animation_context()

    def _sync_scene_authoring_context(self):
        self.set_tilemap_render_source(scene_authoring_source(self.document))
        self._sync_region_rule_context()

    def _sync_region_rule_context(self):
        project = self.document.project
        rule_sets = project.rpg_database.map_rule_sets if project is not None else {}
        ruleset = rule_sets[sorted(rule_sets)[0]] if rule_sets else None
        layer_name = ruleset.region_layer if ruleset is not None else "regions"
        self.viewport.set_region_layer_name(layer_name)
        self.tile_palette.set_area_rule_set(ruleset)

    def _create_map_rule_set(self):
        from .map_rule_authoring import MapRuleAuthoringController

        MapRuleAuthoringController(self.document).create_ruleset()
        self.refresh_all()

    def _set_region_rule(self, rule):
        from .map_rule_authoring import MapRuleAuthoringController

        MapRuleAuthoringController(self.document).set_region_rule(rule)
        self.refresh_all()

    def _remove_region_rule(self, region_id):
        from .map_rule_authoring import MapRuleAuthoringController

        if MapRuleAuthoringController(self.document).remove_region_rule(region_id):
            self.refresh_all()

    def _sync_animation_context(self):
        clip_set, current = animation_context(self.document)
        if clip_set is None:
            self.animation_widget.set_clips(())
            self.animation_widget.set_status(
                "Pick a character in the Scene (one with an Animator) to play its animations "
                "here. Sprite Animation edits a sheet's animations directly."
                if current is None
                else f"Missing animation asset for {current}"
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
        name, ok = QInputDialog.getText(
            self, "Event Condition", "Switch name:", text="quest_started"
        )
        if not ok or not name.strip():
            return
        cond = EventTriggerCondition(EventCondition("switch", name.strip(), "==", True))
        replacement = replace_binding_fields(
            binding, conditions=tuple(binding.conditions) + (cond,)
        )
        self.document.execute(ReplaceEventBindingCommand(bindings, replacement, binding))
        self.refresh_all()

    def _sequence_dialog(self, args=None):
        """Modal sequence editor; returns SEQUENCE args or None (tests replace this)."""
        from .event_flow_widget import SequenceEditorDialog

        dialog = SequenceEditorDialog(args, self)
        return dialog.result_args() if dialog.exec() == SequenceEditorDialog.Accepted else None

    def _dialogue_dialog(self, args=None):
        """Modal Dialogue editor (speaker, text, portrait); returns DIALOGUE args or None
        (tests replace this)."""
        from .dialogue_command_dialog import DialogueCommandDialog

        dialog = DialogueCommandDialog(args, document=self.document, parent=self)
        return dialog.result_args() if dialog.exec() == DialogueCommandDialog.Accepted else None

    def _choice_dialog(self, args=None):
        """Modal Choice editor (prompt, options, variable, start, cancel, box); returns CHOICE
        args or None (tests replace this)."""
        from .choice_command_dialog import ChoiceCommandDialog

        dialog = ChoiceCommandDialog(args, parent=self)
        return dialog.result_args() if dialog.exec() == ChoiceCommandDialog.Accepted else None

    def _wait_dialog(self, args=None):
        """Modal Wait editor (seconds, or until a condition); returns WAIT args or None (tests
        replace this)."""
        from .wait_command_dialog import WaitCommandDialog

        dialog = WaitCommandDialog(args, parent=self)
        return dialog.result_args() if dialog.exec() == WaitCommandDialog.Accepted else None

    def _event_edit_command(self, index):
        """Open the specialized editor for dialogue, choice, wait, sequence and picture
        instructions."""
        from .event_flow_authoring import EventFlowAuthoring
        from .picture_command_dialog import PICTURE_COMMANDS, PictureCommandDialog

        project = self.document.project
        _, binding = self._current_event_binding()
        if project is None or binding is None:
            return False
        program = project.event_programs.require(binding.program_id)
        if not 0 <= index < len(program.instructions):
            return False
        instruction = program.instructions[index]
        if instruction.opcode == "SEQUENCE":
            args = self._sequence_dialog(instruction.args)
            if args is None:
                return False
            EventFlowAuthoring(self.document).replace_sequence(
                binding.program_id, index, **_sequence_kwargs(args)
            )
        elif instruction.opcode in ("DIALOGUE", "CHOICE", "WAIT"):
            edit = {
                "DIALOGUE": self._dialogue_dialog,
                "CHOICE": self._choice_dialog,
                "WAIT": self._wait_dialog,
            }[instruction.opcode]
            args = edit(instruction.args)
            if args is None:
                return False
            rows = list(program.instructions)
            rows[index] = EventInstruction(instruction.opcode, args)
            self.document.execute(
                ReplaceEventProgramCommand(
                    project.event_programs,
                    binding.program_id,
                    EventProgram(rows, name=program.name),
                    program,
                )
            )
        elif (
            instruction.opcode == "WORLD"
            and str(instruction.args.get("command", "")).upper() in PICTURE_COMMANDS
        ):
            dialog = PictureCommandDialog(
                instruction.args["command"],
                instruction.args.get("args", {}),
                document=self.document,
                parent=self,
            )
            if not dialog.exec():
                return False
            changed = EventInstruction(
                "WORLD",
                {
                    "command": dialog.command.currentText(),
                    "args": dialog.result_args(),
                },
            )
            rows = list(program.instructions)
            rows[index] = changed
            new_program = EventProgram(rows, name=program.name)
            self.document.execute(
                ReplaceEventProgramCommand(
                    project.event_programs, binding.program_id, new_program, program
                )
            )
        else:
            return False
        self.refresh_all()
        return True

    def _event_make_instruction(self, kind):
        if kind == "sequence":
            args = self._sequence_dialog()
            return None if args is None else EventInstruction("SEQUENCE", args)
        if kind == "dialogue":
            args = self._dialogue_dialog()
            return None if args is None else EventInstruction("DIALOGUE", args)
        if kind == "choice":
            args = self._choice_dialog()
            return None if args is None else EventInstruction("CHOICE", args)
        if kind == "wait":
            args = self._wait_dialog()
            return None if args is None else EventInstruction("WAIT", args)
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
            value, ok = QInputDialog.getText(
                self, "Set Variable", "Value (@name copies that variable):"
            )
            if not ok:
                return None
            if value.startswith("@") and value[1:].strip():
                return EventInstruction(
                    "SET_VARIABLE", {"name": name.strip(), "from_variable": value[1:].strip()}
                )
            return EventInstruction("SET_VARIABLE", {"name": name.strip(), "value": value})
        if kind == "world":
            command, ok = QInputDialog.getText(self, "World Command", "Command:", text="TRANSFER")
            if not ok or not command.strip():
                return None
            from .picture_command_dialog import PICTURE_COMMANDS, PictureCommandDialog

            command = command.strip().upper()
            if command in PICTURE_COMMANDS:
                dialog = PictureCommandDialog(command, document=self.document, parent=self)
                if not dialog.exec():
                    return None
                return EventInstruction(
                    "WORLD", {"command": command, "args": dialog.result_args()}
                )
            raw_args, ok = QInputDialog.getText(
                self,
                "World Command",
                "Arguments (key=value, ...):",
                text=", ".join(f"{name}=" for name in WORLD_COMMAND_ARGUMENTS.get(command, ())),
            )
            if not ok:
                return None
            try:
                args = parse_world_args(raw_args)
            except ValueError as exc:
                QMessageBox.warning(self, "World Command", str(exc))
                return None
            return EventInstruction("WORLD", {"command": command, "args": args})
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
            ReplaceEventProgramCommand(
                project.event_programs, binding.program_id, new_program, program
            )
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
            ReplaceEventProgramCommand(
                project.event_programs, binding.program_id, new_program, program
            )
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
            ReplaceEventProgramCommand(
                project.event_programs, binding.program_id, new_program, program
            )
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
        self.skeleton_viewer._texture_cache.clear()
        self.skeleton_viewer.canvas.update()

    def set_tilemap_render_source(self, source):
        self.viewport.set_render_source(source)
        texture = None
        if source is not None:
            from .scene_render import resolve_texture_source

            texture = resolve_texture_source(self.document, source.sprite_sheet.texture.asset_id)
        self.tile_palette.set_tileset(
            source.tileset if source is not None else None,
            source.sprite_sheet if source is not None else None,
            texture,
        )
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
        from .presentation_layout import polish_presentation_page

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
        database = getattr(project, "rpg_database", None)
        if database is not None and set(database.doodads) != set(self.tile_palette._doodads):
            self.tile_palette.set_doodads(database.doodads)
        if getattr(self, "problems_widget", None) is not None:
            self.problems_widget.schedule_refresh()
        self.project_tree.refresh()
        self.refresh_asset_list()
        self.refresh_inspector()
        self._sync_scene_authoring_context()
        self._sync_animation_context()
        self._sync_event_context()
        # the workspace on screen is rebuilt now; the others when they are next opened
        self._refresh_epoch = getattr(self, "_refresh_epoch", 0) + 1
        workspace = getattr(self, "workspace", None)
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
        # another project: every workspace is rebuilt now (none may keep the old one's records,
        # even before it is opened)
        for mode in WorkspaceMode:
            self._ensure_workspace_fresh(mode)
        QTimer.singleShot(0, self.viewport, self.viewport.frame_initial)

    def refresh_asset_list(self):
        from .asset_thumbnails import ImageCache, asset_thumbnail, canonical_asset_thumbnail

        self.asset_list.clear()
        if self.document.project is None:
            return
        cache = ImageCache()
        for record in self.document.project.assets.records():
            item = QListWidgetItem(f"{record.kind}: {record.source_path}")
            item.setData(Qt.UserRole, str(record.source_path))
            icon = asset_thumbnail(self.document, record, cache)
            item.setIcon(
                icon if icon is not None else workspace_icon(asset_icon_name(record.source_path))
            )
            self.asset_list.addItem(item)
        for asset in self.document.project.assets.snapshot():
            item = QListWidgetItem(f"{asset.kind}: {asset.source.uri}")
            item.setData(Qt.UserRole, str(asset.source.uri))
            icon = canonical_asset_thumbnail(self.document, asset, cache)
            item.setIcon(
                icon if icon is not None else workspace_icon(asset_icon_name(asset.source.uri))
            )
            self.asset_list.addItem(item)

    def selected_asset_images(self):
        """Absolute paths of the selected Asset list entries that are PNG files on disk."""
        from .image_tools import project_root

        root = project_root(self.document)
        paths = []
        for item in self.asset_list.selectedItems():
            source = item.data(Qt.UserRole)
            if not source:
                continue
            path = Path(source)
            path = path if path.is_absolute() else root / path
            if path.suffix.lower() == ".png" and path.is_file():
                paths.append(path)
        return paths

    def _asset_context_menu(self, position):
        from PySide6.QtWidgets import QMenu

        images = self.selected_asset_images()
        menu = QMenu(self.asset_list)
        fix = menu.addAction("Auto-fix Image…", lambda: self.auto_fix_selected_image())
        fix.setEnabled(len(images) == 1)
        pack = menu.addAction("Pack into Atlas…", lambda: self.pack_selected_images())
        pack.setEnabled(len(images) >= 1)
        menu.addSeparator()
        menu.addAction("Import from Asset Library…", lambda: self.import_from_asset_library())
        menu.exec(self.asset_list.viewport().mapToGlobal(position))

    def import_from_asset_library(self, *, dialog_hook=None, root=None):
        """Copy pictures from the engine's asset library into the project (one undo step)."""
        from .asset_library_dialog import AssetLibraryDialog, ImportLibraryAssetsCommand
        from .image_tools import project_root

        if self.document.project is None:
            self.statusBar().showMessage("Open a project to import library assets")
            return ()
        dialog = AssetLibraryDialog(self, root=root)
        accepted = dialog_hook(dialog) if dialog_hook is not None else dialog.exec()
        picks = dialog.picks()
        if not accepted or not picks:
            return ()
        command = ImportLibraryAssetsCommand(
            self.document.project, project_root(self.document), picks
        )
        self.document.execute(command)
        self.refresh_asset_list()
        count = len(command.records)
        self.statusBar().showMessage(f"Imported {count} picture(s) from the library")
        return tuple(command.records)

    def auto_fix_selected_image(self, *, dialog_hook=None):
        """AST-11: preview a safe fix on the selected image and apply it (original kept as
        .bak)."""
        from .image_tools import ImageFixDialog

        images = self.selected_asset_images()
        if len(images) != 1:
            self.statusBar().showMessage("Select one PNG image in Assets to auto-fix")
            return None
        dialog = ImageFixDialog(images[0], self)
        if dialog_hook is not None:
            dialog_hook(dialog)
        else:
            dialog.exec()
        if dialog.applied is not None:
            self.refresh_asset_list()
            self.statusBar().showMessage(
                f"Fixed {images[0].name}; original kept as {images[0].stem}.bak.png"
            )
        return dialog.applied

    def pack_selected_images(self, output=None):
        """AST-11: pack the selected images into one atlas PNG plus a JSON of named regions."""
        from .image_tools import pack_atlas, project_root

        images = self.selected_asset_images()
        if not images:
            self.statusBar().showMessage("Select PNG images in Assets to pack")
            return None
        if output is None:
            output, _ = QFileDialog.getSaveFileName(
                self,
                "Pack into Atlas",
                str(project_root(self.document) / "atlas.png"),
                "PNG (*.png)",
            )
            if not output:
                return None
        try:
            image, meta, report = pack_atlas(images, output)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Pack into Atlas", str(error))
            return None
        size = report.after_size
        self.statusBar().showMessage(
            f"Packed {len(images)} images into {image.name} ({size[0]}x{size[1]})"
        )
        return image, meta

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
            self.inspector.show_entity(obj)
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
        if (
            sel.kind != "scene"
            or sel.value is None
            or sel.multiple
            or self.document.project is None
        ):
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
            sel.value
            if sel.kind == "scene"
            else getattr(sel.value, "scene", None)
            if sel.kind == "entity"
            else None
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
        choices = [
            c
            for c in build_component_choices(self.document.component_registry, sel.value)
            if c.addable
        ]
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

    def navigate_to_problem(self, problem):
        """Open the editor that owns ``problem.target`` and select the offending item (EDT-15)."""
        from pathlib import Path

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
        commands = [
            build_duplicate_entity_command(value, self.document.component_registry)
            for value in sel.values
        ]
        if len(commands) == 1:
            self._execute_structure(commands[0], "entity", commands[0].duplicate_entity)
        else:
            tx = CommandTransaction(f"Duplicate {len(commands)} Entities", commands)
            self.document.execute(tx)
            self.document.selection.set_many(
                "entity", tuple(command.duplicate_entity for command in commands)
            )
            self.refresh_all()
        return True

    def paste_entity(self):
        family = self._focused_record_family()
        if family is not None:
            return bool(family.paste())
        sel = self.document.selection
        scene = (
            sel.value
            if sel.kind == "scene"
            else getattr(sel.value, "scene", None)
            if sel.kind == "entity"
            else None
        )
        if scene is None or sel.multiple:
            return False
        try:
            command = build_paste_entity_command(
                scene, self.document.clipboard, self.document.component_registry
            )
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
                    self.document.execute(
                        CommandTransaction(f"Delete {len(commands)} Entities", commands)
                    )
                if len(scenes) == 1:
                    self.document.selection.set_single("scene", next(iter(scenes.values())))
                else:
                    self.document.selection.set_single("project", self.document.project)
                self.refresh_all()
                return True
            if sel.kind == "component" and sel.value is not None and not sel.multiple:
                entity = sel.value.entity
                self._execute_structure(
                    build_remove_component_command(sel.value), "entity", entity
                )
                return True
        except StructureEditError as exc:
            QMessageBox.warning(self, "Delete", str(exc))
        return False

    def edit_selected_component_field(self, field_name, raw_value):
        sel = self.document.selection
        if sel.kind != "component" or sel.value is None or sel.multiple:
            return False, "No single component selected"
        return self.edit_component_field(sel.value, field_name, raw_value)

    def edit_entity(self, entity, *, name=None, enabled=None):
        """Rename or switch on/off an entity from the Inspector (undoable)."""
        from .commands import RenameCommand, SetAttributeCommand

        if name is not None and str(name).strip() and name != entity.name:
            self.document.execute(RenameCommand(entity, str(name).strip(), entity.name))
        if enabled is not None and bool(enabled) != bool(entity.enabled):
            self.document.execute(
                SetAttributeCommand(entity, "enabled", bool(enabled), entity.enabled)
            )
        self._refresh_actions()
        self._refresh_title()
        self.viewport.refresh()
        return True

    def edit_passability(self, entity, mode):
        """Make an entity passable, block at its feet or block its whole picture (the
        Inspector's Passability, D88; one undo step); (ok, error)."""
        from .image_tools import project_root
        from .passability import build_passability_command, picture_box

        box = picture_box(self.document.project, project_root(self.document), entity)
        try:
            command = build_passability_command(entity, mode, box)
        except ValueError as exc:
            return False, str(exc)
        if command.commands:
            self.document.execute(command)
        self._refresh_actions()
        self._refresh_title()
        self.viewport.refresh()
        # rebuilt after the combo's signal returns: the page holding it is replaced
        QTimer.singleShot(0, lambda e=entity: self.inspector.show_entity(e))
        return True, None

    def edit_component_field(self, component, field_name, raw_value):
        """Set one field of a component from the Inspector (undoable); (ok, error)."""
        try:
            command = build_set_component_field_command(component, field_name, raw_value)
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
        self.document.selection.set_single(
            "project" if self.document.project else "none", self.document.project
        )
        self.refresh_all()
        return True

    def redo(self):
        if not self.document.redo():
            return False
        self.document.selection.set_single(
            "project" if self.document.project else "none", self.document.project
        )
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

    def export_game(self, output, *, name=None, pyz=True, app=False):
        """Save, then package the project (AST-06): game folder, single-file .pyz, optional macOS
        .app."""
        from asteria.project_tools import package_game

        if self.document.project is None or not self.document.file_path:
            raise ValueError("save the project to a file before exporting")
        if self.document.dirty and not self.save_project():
            raise ValueError("the project could not be saved")
        result = package_game(self.document.file_path, output, name=name, pyz=pyz, app=app)
        self.statusBar().showMessage(f"Exported {result['pyz'] or result['folder']}", 5000)
        return result

    def export_game_dialog(self):
        from PySide6.QtWidgets import (
            QCheckBox,
            QDialog,
            QDialogButtonBox,
            QFormLayout,
            QLabel,
            QLineEdit,
        )

        if self.document.project is None:
            return None
        dialog = QDialog(self)
        dialog.setWindowTitle("Export Game")
        name = QLineEdit(self.document.project.name or "Asteria Game")
        pyz = QCheckBox("Single-file game (.pyz)")
        pyz.setChecked(True)
        app = QCheckBox("macOS app (.app)")
        app.setChecked(sys.platform == "darwin")
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form = QFormLayout(dialog)
        form.addRow("Game name", name)
        form.addRow("", pyz)
        form.addRow("", app)
        form.addRow(
            QLabel(
                "The game folder always carries the engine; players need Python 3.12+ with "
                "pygame-ce."
            )
        )
        form.addRow(buttons)
        if dialog.exec() != QDialog.Accepted:
            return None
        output = QFileDialog.getExistingDirectory(self, "Export To Folder")
        if not output:
            return None
        try:
            result = self.export_game(
                output, name=name.text().strip() or None, pyz=pyz.isChecked(), app=app.isChecked()
            )
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Export Game", str(exc))
            return None
        lines = [f"Game folder: {result['folder']}"]
        if result["pyz"]:
            lines.append(f"Single file: {result['pyz']}")
        if result["app"]:
            lines.append(f"macOS app: {result['app']}")
        missing = result["report"].missing
        if missing:
            lines.append("Missing: " + ", ".join(missing))
        lines.extend(result["report"].warnings)
        QMessageBox.information(self, "Export Game", "\n".join(lines))
        return result

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
        QTimer.singleShot(0, self.viewport, self.viewport.frame_initial)
        return True

    def new_from_template(self, template_id, name, folder):
        """Copy a project template into ``folder`` and open it."""
        from .project_templates import create_from_template

        path = create_from_template(template_id, name, folder)
        load_document(self.document, path)
        self._resolve_project_resources()
        self.play_session = None
        self._load_playtest_profiles()
        self.refresh_all()
        QTimer.singleShot(0, self.viewport, self.viewport.frame_initial)
        guide = Path(path).parent / "START_HERE.md"
        if guide.is_file():  # where every rule lives in this project
            self.console.setText(f"New project from a template.\n\n{guide.read_text()}")
        return path

    def new_from_template_dialog(self):
        from PySide6.QtWidgets import QInputDialog

        from .project_templates import available_templates

        templates = available_templates()
        if not templates:
            QMessageBox.information(
                self, "New from Template", "No project templates are installed."
            )
            return None
        if self.document.dirty:
            answer = QMessageBox.question(
                self,
                "Unsaved Changes",
                "This project has unsaved changes. Start a new project anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return None
        titles = [f"{t.title} - {t.description}" for t in templates]
        choice, ok = QInputDialog.getItem(self, "New from Template", "Template:", titles, 0, False)
        if not ok:
            return None
        template = templates[titles.index(choice)]
        name, ok = QInputDialog.getText(
            self, "New from Template", "Project name:", text=template.title.split(" (")[0]
        )
        if not ok or not name.strip():
            return None
        parent = QFileDialog.getExistingDirectory(self, "Folder to create the project in")
        if not parent:
            return None
        folder = Path(parent) / name.strip().replace(" ", "_").lower()
        try:
            return self.new_from_template(template.template_id, name, folder)
        except (OSError, ValueError, EditorStorageError, EditorResourceError) as exc:
            QMessageBox.critical(self, "New from Template", str(exc))
            return None

    def import_mv_project(self, source, output):
        """Import an RPG Maker MV project into a new Asteria project folder and open it (W-18)."""
        from asteria.assets.rpg_maker_mv_project import import_mv_project

        project_path, result = import_mv_project(source, output)
        load_document(self.document, project_path)
        self._resolve_project_resources()
        self.play_session = None
        self._load_playtest_profiles()
        self.refresh_all()
        lines = [f"{issue.code}: {issue.message}" for issue in result.issues]
        self.console.setText(
            f"Imported {len(result.project.scenes())} maps from {source}\n"
            + "\n".join(lines[:200])
        )
        return project_path, result

    def import_mv_project_dialog(self):
        if self.document.dirty:
            answer = QMessageBox.question(
                self,
                "Unsaved Changes",
                "This project has unsaved changes. Import into a new project anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return None
        source = QFileDialog.getExistingDirectory(
            self, "RPG Maker MV Project Folder (contains data/)"
        )
        if not source:
            return None
        output = QFileDialog.getExistingDirectory(self, "New Asteria Project Folder")
        if not output:
            return None
        try:
            project_path, result = self.import_mv_project(source, output)
        except (OSError, ValueError, EditorStorageError, EditorResourceError) as exc:
            QMessageBox.critical(self, "Import RPG Maker MV Project", str(exc))
            return None
        QMessageBox.information(
            self,
            "Import RPG Maker MV Project",
            f"Imported {len(result.project.scenes())} maps into {project_path}.\n"
            f"{len(result.issues)} notes (content kept out or simplified) are listed in the "
            f"Console.",
        )
        return project_path

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
            self.runtime_process = launch_play_session(
                self.play_session, debug=True, capture_log=True, spawn=spawn
            )
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
            self.debugger_widget.attach(
                self.runtime_process.debug_port, self.runtime_process.debug_token
            )
        where = "" if spawn is None else f" from ({spawn[0]:g}, {spawn[1]:g})"
        self.console.setText(f"Playing: {self.play_session.runtime_scene.name}{where}")
        console_dock = self.findChild(QDockWidget, "ConsoleDock")
        # the play log, even in a workspace that keeps its bottom panels closed
        console_dock.show()
        console_dock.raise_()
        self.statusBar().showMessage(f"Playing — {self.play_session.runtime_scene.name}{where}")
        self._refresh_actions()
        return True

    def play_project(self):
        return self._start_play(from_start=True)

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

    def play_menu_screen(self, screen_id):
        """Run the project from its start, opened on one menu screen (Menu Screens ▸ Layout ▸
        Open in game)."""
        os.environ["ASTERIA_OPEN_MENU"] = str(screen_id)
        try:
            return self._start_play(from_start=True, title="Open in Game")
        finally:
            os.environ.pop("ASTERIA_OPEN_MENU", None)

    def play_current_scene(self):
        return self._start_play(from_start=False, title="Play")

    def play_from_selection(self):
        """Play the current scene with the player starting at the selected entity's position."""
        from asteria.core import Transform

        entity = self._selected_entity()
        if entity is None or not entity.has(Transform):
            QMessageBox.information(
                self, "Play from Selection", "Select an entity in the scene first."
            )
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
            self.console.append("Game closed")  # keep the play-test log visible
        else:
            self.console.setText("Game closed")
        self.statusBar().showMessage("Game closed", 2000)
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
        if self.layout_settings is not None:
            self.save_layout()
        self.multiplayer_workspace.shutdown()
        event.accept()

    layout_settings = (
        None  # a QSettings; set by launch_editor so tests never touch the user's layout
    )
    LAYOUT_VERSION = 1

    def set_combat_boxes_visible(self, visible):
        self.viewport.show_combat_boxes = bool(visible)
        self.viewport.update()

    def save_layout(self):
        self.layout_settings.setValue("editor/geometry", self.saveGeometry())
        self.layout_settings.setValue("editor/dock_state", self.saveState(self.LAYOUT_VERSION))
        self.layout_settings.setValue("editor/dock_mode", self.workspace.mode.value)

    LEFT_TITLES = {
        "Project": "ProjectSceneDock",
        "Tiles": "TilePaletteDock",
        "Layers": "LayersDock",
    }

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

    # Panels a workspace starts without (it keeps whatever the user opens or closes afterwards).
    # The database, battle, presentation, event and code editors use the whole window, the way RPG
    # Maker's database does; the Scene workspace keeps the Inspector and the bottom panels.
    WORKSPACE_HIDDEN_DOCKS = (
        "InspectorDock",
        "AssetsDock",
        "ConsoleDock",
        "DebuggerDock",
        "ProfilerDock",
        "ProblemsDock",
        "TilePaletteDock",
        "LayersDock",
    )

    def _switch_workspace_docks(self, mode):
        states = self.__dict__.setdefault("_workspace_dock_states", {})
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
        from .i18n import set_language

        set_language(name)
        self.refresh_all()  # trees and forms built from the editor's words, built again
        if name in getattr(self, "language_actions", {}):
            self.language_actions[name].setChecked(True)
        if self.layout_settings is not None:
            self.layout_settings.setValue("editor/language", name)

    def set_theme(self, name):
        """Switch the editor palette live and remember it."""
        from .theme import apply_asteria_theme

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
        """Restore the dock layout and window geometry saved when the editor last closed."""
        self.layout_settings = settings
        geometry = settings.value("editor/geometry")
        state = settings.value("editor/dock_state")
        saved_mode = settings.value("editor/dock_mode")
        if geometry is not None:
            self.restoreGeometry(geometry)
        mode_matches = saved_mode == self.workspace.mode.value
        restored = (
            state is not None and mode_matches and self.restoreState(state, self.LAYOUT_VERSION)
        )
        if state is not None and not mode_matches:
            self.restoreState(self._default_dock_state, self.LAYOUT_VERSION)
        self._layout_restored = bool(restored)
        # the left panel always opens on Project, whichever tab the last session ended on
        QTimer.singleShot(0, self, lambda: self.show_left_tab("ProjectSceneDock"))
        self.hide_stale_dock_tab_bars()
        return restored


def starter_fingerprint(template_id="basic_rpg"):
    """A short hash of what the starter is made from: when it changes, a starter made earlier
    is out of date."""
    import hashlib

    from . import basic_rpg_map, basic_rpg_template, project_templates

    digest = hashlib.sha256()
    if template_id != "basic_rpg":
        template = next(t for t in project_templates.TEMPLATES if t.template_id == template_id)
        for name in ("project.asteria.json", "playable_test_manifest.json"):
            file = Path(template.source) / name
            if file.exists():
                digest.update(file.read_bytes())
        return digest.hexdigest()[:16]
    for template in project_templates.TEMPLATES:
        if template.template_id in ("party_rpg", "action_rpg", "basic_rpg"):
            for name in ("project.asteria.json", "playable_test_manifest.json"):
                file = Path(template.source) / name
                if file.exists():
                    digest.update(file.read_bytes())
    for module in (basic_rpg_map, basic_rpg_template):
        digest.update(Path(module.__file__).read_bytes())
    return digest.hexdigest()[:16]


def ensure_starter_project(folder, template_id="basic_rpg", name="Basic RPG"):
    """The starter project's file in ``folder``, made if missing. A starter made from an older
    template is replaced: untouched, it is rebuilt in place; edited (or of unknown age), it is
    moved aside to ``<name> (previous)`` first, so nothing the user did is lost."""
    import hashlib
    import json
    import shutil

    from .project_templates import create_from_template

    folder = Path(folder)
    path = folder / "project.asteria.json"
    stamp_file = folder / ".starter.json"
    fingerprint = starter_fingerprint(template_id)
    if path.exists():
        try:
            stamp = json.loads(stamp_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            stamp = {}
        if stamp.get("fingerprint") == fingerprint:
            return path
        untouched = stamp.get("project_sha") == hashlib.sha256(path.read_bytes()).hexdigest()
        if untouched:
            shutil.rmtree(folder)
        else:
            aside = folder.with_name(f"{folder.name} (previous)")
            number = 1
            while aside.exists():
                number += 1
                aside = folder.with_name(f"{folder.name} (previous {number})")
            folder.rename(aside)
    create_from_template(template_id, name, folder)
    stamp_file.write_text(
        json.dumps(
            {
                "fingerprint": fingerprint,
                "project_sha": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    return path


def launch_editor(project=None):
    import sys

    from PySide6.QtCore import QSettings, QStandardPaths

    from .theme import palette_name

    app = QApplication.instance() or QApplication(sys.argv)
    settings = QSettings("Asteria", "Editor")
    apply_asteria_theme(app, palette_name(settings))
    from .i18n import install, language_name

    install(app, language_name(settings))  # before any window: its text is drawn translated
    window = AsteriaEditorWindow(project)
    window.restore_layout(settings)
    if project is None:
        from asteria.project import Project

        from .project_templates import TEMPLATES

        # The project to learn from opens first: Full Verification when the engine has it (a
        # source checkout), else the small Basic RPG. A copy in writable user storage, so edits
        # survive restarts and the reference project itself is never changed.
        full = next(t for t in TEMPLATES if t.template_id == "full_verification")
        template_id, name = (
            ("full_verification", "Full Verification")
            if full.available()
            else ("basic_rpg", "Basic RPG")
        )
        folder = (
            Path(QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation))
            / "Asteria"
            / "Projects"
            / name
        )
        path = ensure_starter_project(folder, template_id, name)
        starter = Project.load_json(path, window.document.component_registry)
        window.set_project(starter, file_path=path)
    window.show()
    return app.exec()


def _sequence_kwargs(args):
    return {
        "tracks": args["tracks"],
        "cutscene": args.get("cutscene", False),
        "skippable": args.get("skippable", False),
        "wait": args.get("wait", "all"),
    }
