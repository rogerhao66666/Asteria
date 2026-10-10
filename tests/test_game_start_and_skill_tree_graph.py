from asteria.core import ComponentRegistry, Scene, Entity
from asteria.project import Project
from asteria.rpg import ProgressionGraphDefinition, ProgressionNodeDefinition, ProgressionNodeRequirement
from asteria.runtime.game_start import GameStartDefinition


def test_project_v8_owns_canonical_game_start_and_fresh_run_state():
    p = Project("Start")
    s = Scene("Start Scene")
    e = Entity("Player")
    s.add_entity(e)
    p.add_scene(s)
    p.game_start = GameStartDefinition(s.id, e.id, "right", (12, 8))
    raw = p.to_data()
    assert raw["version"] == 10 and raw["game_start"]["schema"] == "asteria.game_start"
    clone = Project.from_data(raw, ComponentRegistry())
    a = clone.game_start.instantiate(clone)
    b = clone.game_start.instantiate(clone)
    assert a.scene_id == s.id and a.player_entity_id == e.id and a.player_position == (12.0, 8.0)
    a.event_context.set_variable("changed", True)
    assert b.event_context.get_variable("changed") is None


def test_skill_tree_graph_v2_persists_designer_view_and_positions():
    root = ProgressionNodeDefinition("root", "Root")
    branch = ProgressionNodeDefinition("branch", "Branch", prerequisites=[ProgressionNodeRequirement("root")])
    g = ProgressionGraphDefinition(
        "tree",
        "Tree",
        nodes=[root, branch],
        editor_view="graph",
        node_positions={"root": (10, 20), "branch": (220, 90)},
    )
    raw = g.to_data()
    assert raw["version"] == 2 and raw["editor_view"] == "graph"
    clone = ProgressionGraphDefinition.from_data(raw)
    assert clone.node_positions["branch"] == (220.0, 90.0)
    assert clone.require_node("branch").prerequisites[0].node_id == "root"


def test_skill_tree_v1_remains_readable():
    g = ProgressionGraphDefinition("tree", nodes=[ProgressionNodeDefinition("root")])
    raw = g.to_data()
    raw["version"] = 1
    raw.pop("editor_view")
    raw.pop("node_positions")
    clone = ProgressionGraphDefinition.from_data(raw)
    assert clone.editor_view == "list" and clone.node_positions == {}
