from asteria.presentation import ProgressionScreenProfile, ProgressionScreenRuntime
from asteria.rpg.progression_graph import (
    ProgressionAllocationRuntime,
    ProgressionGraphDefinition,
    ProgressionNodeDefinition,
    ProgressionNodeRequirement,
)


def _graphs():
    g1 = ProgressionGraphDefinition(
        "alchemy",
        "Alchemy",
        nodes=(
            ProgressionNodeDefinition(
                "mixing", "Mixing", max_rank=2, rank_costs=({"ap": 1}, {"ap": 2}), tags=("craft",)
            ),
            ProgressionNodeDefinition(
                "catalyst",
                "Catalyst",
                prerequisites=(ProgressionNodeRequirement("mixing", 1),),
                rank_costs={"ap": 2},
                tags=("craft",),
            ),
        ),
    )
    g2 = ProgressionGraphDefinition(
        "blade",
        "Blade",
        nodes=(
            ProgressionNodeDefinition("stance", "Stance", rank_costs={"sp": 1}, tags=("combat",)),
        ),
    )
    return g1, g2


def _runtime():
    g1, g2 = _graphs()
    return ProgressionAllocationRuntime((g1, g2), balances={"ap": 5, "sp": 2}), (g1, g2)


def test_projects_graphs_nodes_balances_and_costs_read_only():
    runtime, graphs = _runtime()
    before = runtime.to_data()
    view = ProgressionScreenRuntime().project(runtime, graphs)
    assert {x.graph_id for x in view.graphs} == {"alchemy", "blade"}
    mixing = next(x for x in view.nodes if x.node_id == "mixing")
    assert mixing.rank == 0 and mixing.max_rank == 2 and mixing.next_costs == (("ap", 1.0),)
    assert runtime.to_data() == before


def test_prerequisites_and_locked_reason_come_from_canonical_preview():
    runtime, graphs = _runtime()
    view = ProgressionScreenRuntime().project(runtime, graphs)
    catalyst = next(x for x in view.nodes if x.node_id == "catalyst")
    assert catalyst.allocatable is False
    assert catalyst.prerequisites[0].node_id == "mixing"
    assert any("mixing" in reason for reason in catalyst.reasons)


def test_after_canonical_allocation_projection_updates_without_allocating_itself():
    runtime, graphs = _runtime()
    runtime.allocate("alchemy", "mixing")
    view = ProgressionScreenRuntime().project(runtime, graphs)
    assert next(x for x in view.nodes if x.node_id == "mixing").rank == 1
    assert next(x for x in view.nodes if x.node_id == "catalyst").allocatable is True


def test_project_owned_labels_and_arbitrary_graph_names():
    profile = ProgressionScreenProfile(
        graph_labels={"alchemy": "Formula Web"}, node_labels={"mixing": "Mixture Theory"}
    )
    runtime, graphs = _runtime()
    view = ProgressionScreenRuntime(profile).project(runtime, graphs)
    assert next(x for x in view.graphs if x.graph_id == "alchemy").label == "Formula Web"
    assert next(x for x in view.nodes if x.node_id == "mixing").label == "Mixture Theory"


def test_query_is_presentation_only():
    runtime, graphs = _runtime()
    screen = ProgressionScreenRuntime()
    screen.set_query("combat")
    view = screen.project(runtime, graphs)
    assert [x.node_id for x in view.nodes] == ["stance"]


def test_visible_limit_does_not_cap_canonical_graph():
    nodes = tuple(ProgressionNodeDefinition(f"n{i}", rank_costs={"p": 1}) for i in range(12))
    graph = ProgressionGraphDefinition("huge", nodes=nodes)
    runtime = ProgressionAllocationRuntime((graph,), balances={"p": 20})
    view = ProgressionScreenRuntime(ProgressionScreenProfile(visible_limits={"huge": 4})).project(
        runtime, (graph,)
    )
    assert len(view.nodes) == 12 and len(view.graphs[0].node_ids) == 4


def test_selection_and_snapshot_are_presentation_only():
    runtime, graphs = _runtime()
    before = runtime.to_data()
    screen = ProgressionScreenRuntime()
    screen.project(runtime, graphs)
    screen.select_graph("blade")
    screen.project(runtime, graphs)
    screen.select_node("stance")
    snap = screen.snapshot()
    restored = ProgressionScreenRuntime()
    restored.restore(snap)
    assert restored.snapshot() == snap and runtime.to_data() == before


def test_profile_roundtrip():
    profile = ProgressionScreenProfile(
        graph_labels={"g": "Graph"}, node_labels={"n": "Node"}, visible_limits={"g": 7}
    )
    assert ProgressionScreenProfile.from_data(profile.to_data()) == profile
