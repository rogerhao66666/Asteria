import pytest

from asteria.core import Scene
from asteria.editor import EditorDocument
from asteria.editor.integrated_authoring import IntegratedAuthoringControllers
from asteria.editor.workspace import WorkspaceMode
from asteria.gameplay import AbilityDefinition
from asteria.project import Project
from asteria.rpg import ClassDefinition, ProgressionMilestone, ProgressionTrackDefinition


def project():
    p=Project("Game"); p.add_scene(Scene("Main")); return p


def test_integrated_controller_bundle_shares_one_canonical_document():
    p=project(); d=EditorDocument(p); c=IntegratedAuthoringControllers(d)
    assert c.actor_class.document is d
    assert c.progression.document is d
    assert c.items.document is d
    assert c.party.document is d
    assert c.enemy.document is d
    assert c.battle.document is d
    assert c.presentation.document is d
    assert c.runtime_ui.document is d
    assert c.flow.document is d


def test_rpg_adapter_edit_hits_canonical_command_stack():
    p=project(); d=EditorDocument(p); c=IntegratedAuthoringControllers(d)
    c.actor_class.create_class("fighter","Fighter")
    adapter=next(x for x in c.rpg_categories() if x.category_id=="classes")
    raw=adapter.encode(adapter.get("fighter"))
    raw["display_name"]="Vanguard"
    adapter.edit("fighter",adapter.decode(raw))
    assert p.rpg_database.classes["fighter"].display_name=="Vanguard"
    assert d.dirty
    assert d.undo()
    assert p.rpg_database.classes["fighter"].display_name=="Fighter"


def test_battle_adapter_edits_existing_canonical_definition():
    from asteria.rpg import BattleResourceDefinition
    p=project(); d=EditorDocument(p); c=IntegratedAuthoringControllers(d)
    c.battle.create("resources",BattleResourceDefinition("focus",minimum=0,maximum=10))
    adapter=next(x for x in c.battle_categories() if x.category_id=="resources")
    raw=adapter.encode(adapter.get("focus")); raw["maximum"]=100
    adapter.edit("focus",adapter.decode(raw))
    assert p.rpg_database.battle_resources["focus"].maximum==100
    assert d.undo()
    assert p.rpg_database.battle_resources["focus"].maximum==10


def test_presentation_and_runtime_ui_adapters_are_separate_families():
    p=project(); d=EditorDocument(p); c=IntegratedAuthoringControllers(d)
    presentation={x.category_id for x in c.presentation_categories()}
    runtime={x.category_id for x in c.runtime_ui_categories()}
    assert presentation
    assert runtime=={
        "rpg_character_screen","rpg_equipment_screen","rpg_ability_screen",
        "rpg_progression_screen","rpg_inventory_screen","rpg_party_screen",
    }
    assert not presentation.intersection(runtime)


def test_shell_declares_complete_top_level_information_architecture():
    assert tuple(x.value for x in WorkspaceMode)==(
        "scene","rpg","battle","ui","event","code"
    )


def test_shell_does_not_expose_player_save_workflow_methods():
    from asteria.editor.shell import AsteriaEditorWindow
    for name in (
        "new_runtime_save","open_runtime_save","save_runtime_state",
        "save_runtime_state_as",
    ):
        assert not hasattr(AsteriaEditorWindow,name),name
    for name in ("play_project","play_current_scene","stop_play"):
        assert callable(getattr(AsteriaEditorWindow,name,None)),name


def test_real_qt_shell_mounts_new_workspaces_when_qt_is_available():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from asteria.editor.shell import AsteriaEditorWindow

    app=QApplication.instance() or QApplication([])
    window=AsteriaEditorWindow(project())
    assert window.workspace.page(WorkspaceMode.RPG) is window.rpg_authoring
    assert window.workspace.page(WorkspaceMode.BATTLE) is window.battle_authoring
    assert window.workspace.page(WorkspaceMode.UI) is window.ui_workspace
    assert window.workspace.page(WorkspaceMode.EVENT) is window.events_workspace
    assert window.ui_workspace.count()==3
    assert window.events_workspace.count()==2
    window.close(); app.processEvents()


def test_real_qt_shell_starts_on_a_paintable_untitled_project():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel
    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    # Launching with no project no longer means "nothing to do": there is an
    # unsaved project with a map, so painting and authoring work right away
    # and the first Save decides where it lands.
    assert window.document.project is not None
    assert window.document.file_path is None
    assert window.viewport.render_source is not None
    assert not isinstance(window.rpg_authoring.child, QLabel)
    window.refresh_all()
    assert window.viewport.render_source is not None
    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_authoring_host_still_shows_a_placeholder_without_any_project():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel

    from asteria.editor.authoring_hub_widget import FamilyHostWidget

    app = QApplication.instance() or QApplication([])
    controllers = IntegratedAuthoringControllers(EditorDocument())
    host = FamilyHostWidget("Character", controllers.rpg_categories)
    assert isinstance(host.child, QLabel)
    host.close()
    app.processEvents()


def test_real_qt_editor_has_no_player_save_actions_when_available():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    all_texts = {action.text() for menu_action in window.menuBar().actions()
                 if menu_action.menu() is not None for action in menu_action.menu().actions()}
    forbidden = {"New Player Save (Advanced)…", "Open Player Save (Advanced)…",
                 "Save Player Runtime State", "Save Player Runtime State As…",
                 "New Runtime Save…", "Open Runtime Save…",
                 "Save Runtime State", "Save Runtime State As…"}
    assert not forbidden.intersection(all_texts)
    window.close()
    app.processEvents()


def test_real_qt_rpg_structured_editor_modifies_canonical_project_when_available():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from asteria.editor.shell import AsteriaEditorWindow

    p=project(); p.rpg_database.add_class(ClassDefinition("fighter","Fighter"))
    app=QApplication.instance() or QApplication([])
    window=AsteriaEditorWindow(p)
    window.workspace.set_mode(WorkspaceMode.RPG)
    hub=window.rpg_authoring.child
    idx=hub.category.findData("classes"); hub.category.setCurrentIndex(idx); hub.refresh()
    assert hub.selected_id=="fighter"
    # Exercise the same UI bridge used by Apply without bypassing canonical controller.
    raw=hub.adapter.encode(hub.adapter.get("fighter")); raw["display_name"]="Vanguard"
    hub.editor.set_record(raw)
    assert hub.apply_selected()
    assert p.rpg_database.classes["fighter"].display_name=="Vanguard"
    assert window.document.commands.can_undo
    window.document.mark_saved()
    window.close(); app.processEvents()


def test_selecting_a_progression_track_updates_its_growth_curve_chart():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from asteria.editor.shell import AsteriaEditorWindow

    p=project()
    p.rpg_database.add_progression_track(
        ProgressionTrackDefinition(
            "fighter_track", "Fighter Growth",
            milestones=(
                ProgressionMilestone(1, 0, stat_bonuses={"hp": 10}),
                ProgressionMilestone(2, 100, stat_bonuses={"hp": 15}),
            ),
        )
    )
    app=QApplication.instance() or QApplication([])
    window=AsteriaEditorWindow(p)
    window.workspace.set_mode(WorkspaceMode.RPG)
    hub=window.rpg_authoring.child
    idx=hub.category.findData("tracks"); hub.category.setCurrentIndex(idx); hub.refresh()
    assert hub.selected_id=="fighter_track"
    assert not hub.curve_chart.isHidden()
    assert hub.curve_chart._series["hp"]==[10.0, 25.0]

    # Live-editing the milestone table (before Apply) refreshes the chart too.
    raw=hub.editor.record()
    raw["milestones"][1]["stat_bonuses"]["hp"]=50
    hub.editor.set_record(raw)
    hub.editor.changed.emit()
    assert hub.curve_chart._series["hp"]==[10.0, 60.0]

    window.close(); app.processEvents()
