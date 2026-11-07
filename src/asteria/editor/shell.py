"""Asteria Editor's main window: it builds the docks and pages and starts the editor; the
window's behaviour lives in the ``asteria.editor.window`` mixins."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from asteria.editor.events.editor_widget import EventEditorWidget
from asteria.editor.project.model import EditorDocument
from asteria.editor.project.project_workspace import ProjectWorkspaceController
from asteria.editor.project.workspace import EditorWorkspace, WorkspaceMode
from asteria.editor.records.hub import FamilyHostWidget
from asteria.editor.rpg.game_flow_overview_widget import GameFlowOverviewWidget
from asteria.editor.rpg.integrated_authoring import IntegratedAuthoringControllers
from asteria.editor.scene.panel_switch import PANELS, PanelSwitch
from asteria.editor.scene.tool_strip import ToolStrip
from asteria.editor.tools.code_workspace import CodeWorkspaceWidget
from asteria.editor.ui.i18n import use_project
from asteria.editor.ui.icons import icon as workspace_icon
from asteria.editor.ui.scrolling_tabs import ScrollingTabWidget, WrappingTabWidget

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QKeySequence, QShortcut
    from PySide6.QtWidgets import (
        QApplication,
        QDockWidget,
        QListWidget,
        QMainWindow,
        QScrollArea,
        QTabBar,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    QApplication = None
    QMainWindow = object
    Qt = None


from asteria.editor.animation.skeleton_page import SkeletonWorkspacePage
from asteria.editor.animation.skeleton_widget import SkeletonViewerWidget
from asteria.editor.scene.tile_layers_widget import TileLayersWidget
from asteria.editor.scene.tile_palette_widget import TilePaletteWidget
from asteria.editor.scene.viewport_widget import SceneViewportWidget
from asteria.editor.ui.theme import apply_asteria_theme
from asteria.editor.ui.widgets import InspectorWidget, ProjectTreeWidget
from asteria.editor.window.actions import WindowActionsMixin
from asteria.editor.window.assets import AssetPanelMixin
from asteria.editor.window.events import EventEditingMixin
from asteria.editor.window.files import ProjectFilesMixin
from asteria.editor.window.layout import WindowLayoutMixin
from asteria.editor.window.placement import PlacementMixin
from asteria.editor.window.play import PlayTestMixin
from asteria.editor.window.scene_editing import SceneEditingMixin
from asteria.editor.window.support import _dock_card, _dock_scrollable, _scene_dock_scrollable
from asteria.editor.window.workspaces import WorkspaceSwitchMixin


class AsteriaEditorWindow(
    WindowLayoutMixin,
    WorkspaceSwitchMixin,
    WindowActionsMixin,
    PlacementMixin,
    SceneEditingMixin,
    EventEditingMixin,
    AssetPanelMixin,
    ProjectFilesMixin,
    PlayTestMixin,
    QMainWindow,
):
    def __init__(self, project=None, component_registry=None):
        if QApplication is None:
            raise RuntimeError("PySide6 is required for Asteria Editor")
        super().__init__()
        self.document = EditorDocument(project, component_registry=component_registry)
        use_project(self.document.project)  # its own words, before the first page is built
        self.play_session = None
        self._workspace_stamps = {}  # each page's data stamp when it was last refreshed
        self._workspace_dock_states = {}  # each workspace's saved dock layout
        self._focus_hidden = []  # the docks focus mode hid, shown again when it ends
        self.runtime_process = None
        self.runtime_monitor = QTimer(self)
        self.runtime_monitor.setInterval(250)
        self.runtime_monitor.timeout.connect(self._poll_runtime_process)
        self.runtime_monitor.start()
        self.setWindowTitle("Asteria Editor")
        self.setDocumentMode(True)
        self.resize(1280, 800)
        self.setMinimumSize(1000, 640)  # below this the panels squeeze text (audited sizes)

        self._build_pages()
        left, palette_dock, layers_dock = self._build_scene_docks()
        self._build_skeleton_page()
        self._connect_scene_tools()
        right, bottom, console, debugger_dock, profiler_dock = self._build_side_docks()
        # Default dock sizes: wide enough that panel tables (Inspector Property / Value / Type)
        # and the project tree read without clipping; the central workspace keeps the rest.
        right.setMinimumWidth(260)
        self._default_dock_sizes = ([left, right], [240, 300], [bottom], [200])
        self._layout_restored = False

        # The native macOS tab base draws a redundant rounded line behind
        # tabified docks. Individual tabs retain their own visual states.
        for dock_tabs in self.findChildren(QTabBar):
            dock_tabs.setDrawBase(False)
        from asteria.editor.ui.dock_title import decorate_dock

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
        # the left panels' switch: coloured squares (P / T / L) in each panel's title bar, in
        # place of its icon
        self.panel_switches = []
        for dock in (left, palette_dock, layers_dock):
            bar = dock.titleBarWidget()
            switch = PanelSwitch(self, bar)
            bar.icon_label.hide()
            bar.layout().insertWidget(1, switch)
            self.panel_switches.append(switch)
        for dock in self.findChildren(QDockWidget):
            dock.dockLocationChanged.connect(self._schedule_dock_tab_cleanup)
            dock.topLevelChanged.connect(self._schedule_dock_tab_cleanup)
        self._schedule_dock_tab_cleanup()

        self._build_actions()
        QApplication.instance().focusChanged.connect(self._focus_changed)
        left.raise_()
        self._workspace_mode_changed(self.workspace.mode.value)
        self.refresh_all()
        QTimer.singleShot(0, self.viewport, self.viewport.frame_initial)
        # the big workspaces are built one after another once the window is up, so the first
        # switch to Game Data, Battle or Presentation is as quick as any later one
        self._warm = [WorkspaceMode.RPG, WorkspaceMode.BATTLE, WorkspaceMode.UI]
        QTimer.singleShot(400, self, self._warm_next_workspace)

    def _build_pages(self):
        """The workspaces and their pages, in the window's centre."""
        self.viewport = SceneViewportWidget(self.document)
        self.code_workspace = CodeWorkspaceWidget(self.document, self)
        self.event_editor = EventEditorWidget(self)

        self.authoring_controllers = IntegratedAuthoringControllers(self.document)
        self.project_workspace_controller = ProjectWorkspaceController(self.document)

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
        from asteria.editor.rpg.game_systems_authoring import GameSystemsAuthoringController
        from asteria.editor.rpg.game_systems_widget import GameSystemsEditorWidget

        self.game_systems_editor = GameSystemsEditorWidget(
            GameSystemsAuthoringController(self.document), self
        )
        self.game_systems_editor.changed.connect(self.refresh_all)
        self.game_systems_editor.pause.open_layout = self.open_menu_layout  # D98
        self.rpg_workspace.addTab(self.game_systems_editor, "Game Systems")
        from asteria.editor.combat.enemy_ai_widget import EnemyAIEditorWidget

        self.enemy_ai_editor = EnemyAIEditorWidget(self.document, self)
        self.enemy_ai_editor.changed.connect(self.refresh_all)
        self.rpg_workspace.addTab(self.enemy_ai_editor, "Enemy AI")
        from asteria.editor.combat.behavior_tree_widget import BehaviorTreeEditorWidget

        self.behavior_tree_editor = BehaviorTreeEditorWidget(self.document, self)
        self.behavior_tree_editor.changed.connect(self.refresh_all)
        self.rpg_workspace.addTab(self.behavior_tree_editor, "Behavior Trees")
        from asteria.editor.combat.workspace import CombatWorkspace

        # D22 A9: attacks, projectiles, loot rarities and affixes with live previews
        self.combat_editor = CombatWorkspace(self.document, self)
        self.rpg_workspace.addTab(self.combat_editor, "Real-Time Combat")
        from asteria.editor.rpg.game_start_authoring import GameStartAuthoringController
        from asteria.editor.rpg.game_start_widget import GameStartEditorWidget

        self.game_start_editor = GameStartEditorWidget(
            GameStartAuthoringController(self.document), self
        )
        self.game_start_editor.changed.connect(self.refresh_all)
        self.rpg_workspace.addTab(self.game_start_editor, "Game Start")
        from asteria.editor.rpg.input_map_widget import InputMapWidget

        # the game's keys and buttons: a setting of the game, beside where it starts (not a
        # page of how the game looks)
        self.input_map_editor = InputMapWidget(self.document, self)
        self.input_map_editor.changed.connect(self.refresh_all)
        self.rpg_workspace.addTab(self.input_map_editor, "Controls")
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
        from asteria.editor.menus.layout_widget import MenuLayoutWorkspace

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
        from asteria.editor.animation.editor_widget import AnimationEditorWidget
        from asteria.editor.animation.timeline_widget import ActionTimelineWidget

        self.animation_editor = AnimationEditorWidget(self.document, self)
        self.ui_workspace.addTab(self.animation_editor, "Sprite Animation")
        from asteria.editor.animation.state_machine_widget import AnimationStateMachineWidget

        self.state_machine_editor = AnimationStateMachineWidget(self.document, self)
        self.state_machine_editor.changed.connect(self.refresh_all)
        self.ui_workspace.addTab(self.state_machine_editor, "Animation States")
        from asteria.editor.animation.composition_widget import CharacterCompositionWidget

        self.composition_editor = CharacterCompositionWidget(self.document, self)
        self.composition_editor.changed.connect(self.refresh_all)
        self.ui_workspace.addTab(self.composition_editor, "Character Composition")
        self.action_timeline_editor = ActionTimelineWidget(self.document, self)
        self.ui_workspace.addTab(self.action_timeline_editor, "Ability Timelines")
        from asteria.editor.combat.vfx_widget import VFXEditorWidget

        self.vfx_editor = VFXEditorWidget(self.document, self)
        self.vfx_editor.changed.connect(self.refresh_all)
        self.vfx_editor.openTimeline.connect(self._open_action_timeline)
        self.vfx_editor.openAnimation.connect(self._open_animation_sheet)
        self.ui_workspace.addTab(self.vfx_editor, "Battle Effects")
        from asteria.editor.combat.particle_effect_widget import ParticleEffectWidget

        self.particle_editor = ParticleEffectWidget(self.document, self)
        self.particle_editor.changed.connect(self.refresh_all)
        self.ui_workspace.addTab(self.particle_editor, "Particle Effects")

        self.game_flow_overview = GameFlowOverviewWidget(self.document, self)
        self.events_workspace = ScrollingTabWidget(self)
        self.events_workspace.setObjectName("EventsWorkspaceTabs")
        self.events_workspace.tabBar().setObjectName("EventsWorkspaceTabBar")
        self.events_workspace.tabBar().setDrawBase(True)
        self.events_workspace.addTab(self.event_editor, "Entity Events")
        self.events_workspace.addTab(self.game_flow_overview, "Interaction Overview")
        from asteria.editor.events.flow_widget import EventFlowWidget

        self.event_flow_editor = EventFlowWidget(self.document, self)
        self.event_flow_editor.changed.connect(self.refresh_all)
        self.events_workspace.addTab(self.event_flow_editor, "Common && Battle Events")

        from asteria.editor.tools.multiplayer_workspace import MultiplayerWorkspaceWidget

        self.multiplayer_workspace = MultiplayerWorkspaceWidget(self.document, self)

        from asteria.editor.scene.tabs import SceneTabs, with_scene_tabs

        self.scene_tabs = SceneTabs(self.document, self.show_scene, self)
        self.workspace = EditorWorkspace(
            {
                WorkspaceMode.SCENE: with_scene_tabs(self.viewport, self.scene_tabs),
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
        for mode, tabs in self._WORKSPACE_TABS.items():
            getattr(self, tabs).currentChanged.connect(
                lambda _index, mode=mode: self._workspace_tab_opened(mode)
            )
        self.setCentralWidget(self.workspace)

    def _build_scene_docks(self):
        """The left panels: the project tree, the tile palette and the tile layers."""
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
        return left, palette_dock, layers_dock

    def _build_skeleton_page(self):
        """Presentation ▸ Skeleton."""
        self.skeleton_viewer = SkeletonViewerWidget(
            self, command_stack=self.document.commands, document=self.document
        )
        self.skeleton_viewer.changed.connect(self.refresh_all)
        self.skeleton_page = SkeletonWorkspacePage(self.skeleton_viewer, self)
        skeleton_tab = self.ui_workspace.addTab(self.skeleton_page, "Skeleton")
        self.ui_workspace.setTabIcon(skeleton_tab, workspace_icon("animation"))
        self.ui_workspace.currentChanged.connect(lambda _index: self._polish_presentation_pages())
        self._polish_presentation_pages()

    def _connect_scene_tools(self):
        """The left panels' keys, the tools over the map, and the Events and Code pages."""
        # the left panels' keys (P / T / L) and the tools over the map; the panels' switch is
        # built with their title bars below
        self.panel_shortcuts = []
        for name, _drawing, key, _words in PANELS:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(lambda n=name: self.show_left_panel(n))
            self.panel_shortcuts.append(shortcut)
        self.tool_strip = ToolStrip(
            self.viewport, self.tile_palette, on_character=self.place_default_character
        )
        self.viewport.characterToolRequested.connect(self.place_default_character)
        self.viewport.placementCancelled.connect(self.cancel_character_placement)

        self.event_editor.bindingRequested.connect(self._event_add_binding)
        self.event_editor.entityPicked.connect(self._event_entity_picked)
        self.event_editor.bindingChanged.connect(self._event_binding_changed)
        self.event_editor.addConditionRequested.connect(self._event_add_condition)
        self.event_editor.addCommandRequested.connect(self._event_add_command)
        self.event_editor.removeCommandRequested.connect(self._event_remove_command)
        self.event_editor.moveCommandRequested.connect(self._event_move_command)
        self.event_editor.editCommandRequested.connect(self._event_edit_command)
        self.code_workspace.saved.connect(self._code_script_saved)
        self.code_workspace.runRequested.connect(self._run_authoring_script)

    def _build_side_docks(self):
        """The Inspector on the right; Assets, Console, Debugger, Profiler and Problems below."""
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
        from asteria.editor.tools.debugger_widget import DebuggerWidget

        self.debugger_widget = DebuggerWidget(self)
        debugger_dock = QDockWidget("Debugger", self)
        debugger_dock.setObjectName("DebuggerDock")
        debugger_dock.setWidget(_dock_card(self.debugger_widget))
        self.addDockWidget(Qt.BottomDockWidgetArea, debugger_dock)
        self.tabifyDockWidget(bottom, debugger_dock)
        from asteria.editor.tools.profiler_widget import ProfilerWidget

        self.profiler_widget = ProfilerWidget(lambda: self.debugger_widget.client, self)
        profiler_dock = QDockWidget("Profiler", self)
        profiler_dock.setObjectName("ProfilerDock")
        profiler_dock.setWidget(_dock_scrollable(self.profiler_widget))
        self.addDockWidget(Qt.BottomDockWidgetArea, profiler_dock)
        self.tabifyDockWidget(bottom, profiler_dock)
        from asteria.editor.project.problems_widget import ProblemsWidget

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
        # the Console starts closed (it is empty) and opens itself the first time it is written to
        bottom.raise_()
        console.hide()
        self._console_waits = True
        self.console.textChanged.connect(self._console_written)
        return right, bottom, console, debugger_dock, profiler_dock

    # the workspaces with tabs: the tab widget, and the pages rebuilt from the project (the other
    # tabs read it themselves when shown). Only the tab on screen is rebuilt; the others wait
    # until they are opened.
    _WORKSPACE_TABS = {
        WorkspaceMode.RPG: "rpg_workspace",
        WorkspaceMode.UI: "ui_workspace",
        WorkspaceMode.EVENT: "events_workspace",
    }
    _WORKSPACE_PAGES = {
        WorkspaceMode.RPG: (
            "rpg_authoring",
            "game_systems_editor",
            "game_start_editor",
            "input_map_editor",
            "enemy_ai_editor",
            "behavior_tree_editor",
        ),
        WorkspaceMode.UI: (
            "presentation_authoring",
            "menu_layout_editor",
            "animation_editor",
            "state_machine_editor",
            "composition_editor",
            "action_timeline_editor",
            "vfx_editor",
        ),
        WorkspaceMode.EVENT: ("game_flow_overview", "event_flow_editor"),
    }
    _PAGES_WITHOUT_PROJECT = ("rpg_authoring", "presentation_authoring", "menu_layout_editor")

    layout_settings = (
        None  # a QSettings; set by launch_editor so tests never touch the user's layout
    )
    LAYOUT_VERSION = 1

    LEFT_TITLES = {
        "Project": "ProjectSceneDock",
        "Tiles": "TilePaletteDock",
        "Layers": "LayersDock",
    }

    # Panels a workspace starts without (it keeps whatever the user opens or closes afterwards).
    # The database, battle, presentation, event and code editors use the whole window, the way RPG
    # Maker's database does; the Scene workspace keeps the Project tree, the Inspector and the
    # bottom panels.
    WORKSPACE_HIDDEN_DOCKS = (
        "ProjectSceneDock",
        "InspectorDock",
        "AssetsDock",
        "ConsoleDock",
        "DebuggerDock",
        "ProfilerDock",
        "ProblemsDock",
        "TilePaletteDock",
        "LayersDock",
    )


def starter_fingerprint(template_id="basic_rpg"):
    """A short hash of what the starter is made from: when it changes, a starter made earlier
    is out of date."""

    from asteria.editor.project import basic_rpg_map, basic_rpg_template
    from asteria.editor.project import templates as project_templates

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

    from asteria.editor.project.templates import create_from_template

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
    from PySide6.QtCore import QSettings, QStandardPaths

    from asteria.editor.ui.theme import palette_name

    app = QApplication.instance() or QApplication(sys.argv)
    settings = QSettings("Asteria", "Editor")
    apply_asteria_theme(app, palette_name(settings))
    from asteria.editor.ui.i18n import install, language_name

    install(app, language_name(settings))  # before any window: its text is drawn translated
    window = AsteriaEditorWindow(project)
    window.restore_layout(settings)
    if project is None:
        from asteria.editor.project.templates import TEMPLATES
        from asteria.project import Project

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
