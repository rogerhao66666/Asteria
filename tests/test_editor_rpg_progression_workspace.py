import pytest

from asteria.core import Scene
from asteria.editor import EditorDocument
from asteria.editor.rpg_progression_authoring import RpgProgressionAuthoringController
from asteria.editor.rpg_progression_workspace import RpgProgressionWorkspaceModel
from asteria.gameplay import AbilityDefinition
from asteria.project import Project
from asteria.rpg import ProgressionNodeDefinition


def make():
    p=Project("Game"); p.add_scene(Scene("Main"))
    doc=EditorDocument(p)
    c=RpgProgressionAuthoringController(doc)
    c.create_ability(AbilityDefinition("slash",tags=("melee",)))
    c.create_ability(AbilityDefinition("fire",tags=("magic",)))
    c.create_passive("counter","Counter",tags=("melee",))
    c.create_graph(
        "warrior_tree","Warrior Tree",
        nodes=(ProgressionNodeDefinition("root"),ProgressionNodeDefinition("branch")),
        tags=("melee",),
    )
    return c,RpgProgressionWorkspaceModel(c)


def test_workspace_shows_one_category_at_a_time():
    _,w=make()
    assert w.snapshot().section_id=="abilities"
    assert set(w.snapshot().visible_ids)=={"slash","fire"}
    w.set_section("passives")
    s=w.snapshot()
    assert s.section_id=="passives"
    assert s.visible_ids==("counter",)
    assert s.selected_id is None


def test_search_filters_browser_without_touching_data():
    c,w=make()
    w.set_query("magic")
    assert w.visible_ids()==("fire",)
    assert set(c.abilities.ids())=={"slash","fire"}


def test_graph_uses_selected_node_context_not_flat_node_details():
    _,w=make()
    w.set_section("graphs")
    w.select("warrior_tree")
    before=w.snapshot()
    assert before.show_graph
    assert before.selected_node_id is None
    w.select_node("branch")
    after=w.snapshot()
    assert after.selected_node_id=="branch"
    assert "Selected Node" in after.detail_groups


def test_switching_category_clears_contextual_selection():
    _,w=make()
    w.set_section("graphs")
    w.select("warrior_tree")
    w.select_node("root")
    w.set_section("abilities")
    s=w.snapshot()
    assert s.selected_id is None
    assert s.selected_node_id is None


def test_unknown_navigation_and_selection_are_rejected():
    _,w=make()
    with pytest.raises(KeyError):
        w.set_section("everything")
    with pytest.raises(KeyError):
        w.select("missing")
    with pytest.raises(RuntimeError):
        w.select_node("root")
