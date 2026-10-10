import pytest

from asteria.core import Scene
from asteria.editor import EditorDocument
from asteria.editor.rpg_progression_authoring import (
    RpgProgressionAuthoringController,
    RpgProgressionAuthoringError,
)
from asteria.gameplay import AbilityDefinition
from asteria.project import Project
from asteria.rpg import (
    ClassAssignment,
    ProgressionMilestone,
    ProgressionNodeDefinition,
    ProgressionNodeRequirement,
    ProgressionNodeReward,
)


def make():
    p = Project("Game")
    p.add_scene(Scene("Main"))
    doc = EditorDocument(p)
    c = RpgProgressionAuthoringController(doc)
    for aid in ("slash", "fire", "heal", "slash_plus"):
        c.create_ability(AbilityDefinition(aid))
    return p, doc, c


def test_information_architecture_does_not_flatten_complexity():
    _, _, c = make()
    ia = c.information_architecture
    assert ia.primary_navigation == "category_sidebar"
    assert ia.browser_pattern == "search_filter_list"
    assert ia.inspector_pattern == "contextual_detail"
    assert ia.progressive_disclosure
    assert ia.graph_focus
    assert not ia.show_all_details_simultaneously
    assert ia.section("graphs").mode == "graph_detail"
    assert "Selected Node" in ia.section("graphs").detail_groups


def test_ability_create_edit_delete_undo_redo():
    p, doc, c = make()
    ab = AbilityDefinition("guard", tags=("defense",))
    c.create_ability(ab)
    assert p.gameplay_library.abilities.require("guard").tags == ("defense",)
    c.edit_ability("guard", AbilityDefinition("guard", tags=("tank",)))
    assert p.gameplay_library.abilities.require("guard").tags == ("tank",)
    assert doc.undo()
    assert p.gameplay_library.abilities.require("guard").tags == ("defense",)
    c.delete_ability("guard")
    assert p.gameplay_library.abilities.get("guard") is None
    assert doc.undo()
    assert p.gameplay_library.abilities.get("guard") is not None


def test_passive_all_fields():
    p, doc, c = make()
    passive = c.create_passive(
        "battle_mage",
        "Battle Mage",
        tags=("hybrid",),
        granted_abilities=("fire", "heal"),
    )
    assert passive.granted_abilities == ("fire", "heal")
    edited = c.edit_passive(
        "battle_mage",
        display_name="Arcane Knight",
        tags=("magic", "melee"),
        granted_abilities=("slash", "fire"),
    )
    assert edited.display_name == "Arcane Knight"
    assert edited.tags == ("magic", "melee")
    assert doc.undo()
    assert p.rpg_database.passives["battle_mage"].display_name == "Battle Mage"


def test_progression_track_complete_milestones():
    p, doc, c = make()
    track = c.create_track(
        "level",
        "Level",
        milestones=(
            ProgressionMilestone(1, 0, stat_bonuses={"hp": 10}, granted_abilities=("slash",)),
            ProgressionMilestone(
                2, 100, stat_bonuses={"hp": 20}, granted_abilities=("fire",), granted_tags=("veteran",)
            ),
        ),
    )
    assert len(track.milestones) == 2
    assert track.milestones[1].required_total == 100
    c.edit_track("level", display_name="Character Level")
    assert p.rpg_database.progression_tracks["level"].display_name == "Character Level"


def test_skill_tree_nodes_cover_costs_prereqs_rewards_exclusive_and_tags():
    p, doc, c = make()
    c.create_passive("counter")
    root = ProgressionNodeDefinition(
        "root",
        "Root",
        max_rank=2,
        rank_costs=({"ap": 1}, {"ap": 2}),
        rewards=(
            ProgressionNodeReward(granted_abilities=("slash",)),
            ProgressionNodeReward(stat_bonuses={"power": 2}, unlocked_passives=("counter",)),
        ),
        tags=("offense",),
    )
    branch = ProgressionNodeDefinition(
        "branch",
        "Branch",
        prerequisites=(ProgressionNodeRequirement("root", 2),),
        rank_costs={"ap": 3},
        rewards=ProgressionNodeReward(
            resource_bonuses={"mp": 5},
            granted_tags=("advanced",),
            granted_abilities=("slash_plus",),
            granted_capabilities=("dual_cast",),
        ),
        exclusive_group="path",
        tags=("advanced",),
    )
    graph = c.create_graph("warrior_tree", "Warrior Tree", nodes=(root, branch), tags=("job",))
    assert graph.require_node("root").max_rank == 2
    assert graph.require_node("branch").prerequisites[0].minimum_rank == 2
    reward = graph.require_node("branch").reward_for_rank(1)
    assert reward.granted_capabilities == ("dual_cast",)
    assert reward.resource_bonuses == {"mp": 5.0}


def test_graph_node_edit_and_delete_protect_dependencies():
    p, doc, c = make()
    root = ProgressionNodeDefinition("root", nodes=None) if False else ProgressionNodeDefinition("root")
    branch = ProgressionNodeDefinition("branch", prerequisites=(ProgressionNodeRequirement("root"),))
    c.create_graph("tree", nodes=(root, branch))
    edited = ProgressionNodeDefinition(
        "branch", "Branch+", prerequisites=(ProgressionNodeRequirement("root"),), tags=("x",)
    )
    c.edit_graph_node("tree", "branch", edited)
    assert p.rpg_database.progression_graphs["tree"].require_node("branch").display_name == "Branch+"
    with pytest.raises(RpgProgressionAuthoringError):
        c.delete_graph_node("tree", "root")
    c.delete_graph_node("tree", "branch")
    assert p.rpg_database.progression_graphs["tree"].node("branch") is None


def test_graph_rejects_cycles_through_canonical_definition():
    _, _, c = make()
    a = ProgressionNodeDefinition("a", prerequisites=(ProgressionNodeRequirement("b"),))
    b = ProgressionNodeDefinition("b", prerequisites=(ProgressionNodeRequirement("a"),))
    with pytest.raises(ValueError):
        c.create_graph("bad", nodes=(a, b))


def test_reward_references_are_validated():
    _, _, c = make()
    bad = ProgressionNodeDefinition("n", rewards=ProgressionNodeReward(granted_abilities=("missing",)))
    with pytest.raises(RpgProgressionAuthoringError):
        c.create_graph("tree", nodes=(bad,))
    bad2 = ProgressionNodeDefinition("n", rewards=ProgressionNodeReward(unlocked_passives=("missing",)))
    with pytest.raises(RpgProgressionAuthoringError):
        c.create_graph("tree2", nodes=(bad2,))


def test_ability_evolution_complete_fields():
    p, doc, c = make()
    c.create_track("level", milestones=(ProgressionMilestone(1, 0), ProgressionMilestone(2, 100)))
    rule = c.create_evolution(
        "slash_mastery",
        "slash",
        "slash_plus",
        progression_track_id="level",
        minimum_rank=2,
        priority=7,
        retain_source=True,
    )
    assert rule.minimum_rank == 2
    assert rule.priority == 7
    assert rule.retain_source
    edited = c.edit_evolution("slash_mastery", minimum_rank=1, retain_source=False)
    assert edited.minimum_rank == 1 and not edited.retain_source
    assert doc.undo()


def test_delete_track_protects_actor_assignment_and_evolution_refs():
    p, doc, c = make()
    c.create_track("job", milestones=(ProgressionMilestone(1, 0),))
    from asteria.rpg import ActorDefinition, ClassDefinition

    p.rpg_database.add_class(ClassDefinition("mage"))
    p.rpg_database.add_actor(
        ActorDefinition("hero", class_assignments=(ClassAssignment("mage", progression_track_ids=("job",)),))
    )
    with pytest.raises(RpgProgressionAuthoringError):
        c.delete_track("job")


def test_delete_ability_protects_progression_reference():
    _, _, c = make()
    node = ProgressionNodeDefinition("n", rewards=ProgressionNodeReward(granted_abilities=("slash",)))
    c.create_graph("tree", nodes=(node,))
    with pytest.raises(RpgProgressionAuthoringError):
        c.delete_ability("slash")


def test_project_validation_after_complex_authoring():
    p, _, c = make()
    c.create_passive("counter", granted_abilities=("slash",))
    c.create_track(
        "level",
        milestones=(
            ProgressionMilestone(1, 0, granted_abilities=("slash",)),
            ProgressionMilestone(2, 100, granted_abilities=("fire",)),
        ),
    )
    root = ProgressionNodeDefinition(
        "root",
        max_rank=2,
        rank_costs=({"ap": 1}, {"ap": 2}),
        rewards=(
            ProgressionNodeReward(granted_abilities=("heal",)),
            ProgressionNodeReward(unlocked_passives=("counter",)),
        ),
    )
    c.create_graph("tree", nodes=(root,))
    c.create_evolution("evo", "slash", "slash_plus", progression_track_id="level", minimum_rank=2)
    assert c.validate() == ()
    assert p.validate()
