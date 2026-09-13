import pytest

from asteria.core import Scene
from asteria.editor import EditorDocument
from asteria.editor.rpg_battle_rules_authoring import (
    RpgBattleRulesAuthoringController,
    RpgBattleRulesAuthoringError,
)
from asteria.editor.rpg_battle_rules_workspace import RpgBattleRulesWorkspaceModel
from asteria.gameplay import AbilityDefinition
from asteria.project import Project
from asteria.rpg import (
    ActionSequenceDefinition, ActionSequenceStep,
    ActionTimingDefinition, ActionTransactionPolicy,
    BattleEscapeRule, BattleObjectiveCondition, BattleObjectiveDefinition,
    BattleResourceDefinition, BattleSchedulerDefinition, BattleStatePolicy,
    BattleTargetingDefinition, GaugeCompositionDefinition, GaugeImpactRule,
    GaugeThresholdRule, InteractionRule, OutcomeCheckDefinition,
    ReactionDefinition,
)


def make():
    p=Project("Game"); p.add_scene(Scene("Main"))
    for aid in ("hit","heal","meteor","counter"):
        p.gameplay_library.add_ability(AbilityDefinition(aid))
    doc=EditorDocument(p)
    return p,doc,RpgBattleRulesAuthoringController(doc)


def sample_definitions():
    return {
        "resources": BattleResourceDefinition(
            "stagger",minimum=0,maximum=100,start_mode="maximum"
        ),
        "states": BattleStatePolicy(
            "broken",blocked_ability_tags=("ability.magic",),tick_trigger="round.end"
        ),
        "interactions": InteractionRule(
            "weak_fire",source_tags_all=("damage.fire",),target_tags_all=("weak.fire",),
            multiplier=1.5,outcome_tags=("outcome.weak",)
        ),
        "outcome_checks": OutcomeCheckDefinition(
            "crit",0.1,source_stat_terms={"luck":0.01},
            success_tags=("outcome.crit",),failure_tags=("outcome.normal",)
        ),
        "targeting": BattleTargetingDefinition(
            "hit",relation="opponent",selection_mode="manual",
            minimum_targets=1,maximum_targets=2
        ),
        "schedulers": BattleSchedulerDefinition(
            "ct",mode="continuous",timeline_scale=100
        ),
        "timing": ActionTimingDefinition(
            "meteor",startup=1,cast_time=3,recovery=2,priority=7
        ),
        "sequences": ActionSequenceDefinition(
            "triple",(ActionSequenceStep("hit",repeat=3),),
            min_participants=1,max_participants=1
        ),
        "gauges": GaugeCompositionDefinition(
            "stagger_break",
            impacts=(GaugeImpactRule("pressure","stagger","battle.hit",delta=-20),),
            thresholds=(GaugeThresholdRule(
                "broken","stagger","at_or_below",0,state_id="broken"
            ),),
        ),
        "reactions": ReactionDefinition(
            "counter","rpg.battle.after_action","event_targets",
            target_selector="event_source",ability_id="counter",max_per_chain=1
        ),
        "objectives": BattleObjectiveDefinition(
            "win",
            success_conditions=(BattleObjectiveCondition("side_active_count","enemies","==",0),),
            winning_sides=("heroes",),defeated_sides=("enemies",)
        ),
        "escape": BattleEscapeRule(
            "run","heroes",base_chance=0.5,source_stat="speed",source_scale=0.01
        ),
        "transactions": ActionTransactionPolicy(
            "meteor",cost_commit="start",interrupt_cost="refund"
        ),
    }


def seed_dependencies(c):
    values=sample_definitions()
    c.create("resources",values["resources"])
    c.create("states",values["states"])
    return values


def test_all_current_battle_rule_kinds_are_authorable():
    p,doc,c=make()
    values=sample_definitions()
    c.create("resources",values.pop("resources"))
    c.create("states",values.pop("states"))
    for kind,value in values.items():
        created=c.create(kind,value)
        assert created is value
        assert len(c.definitions(kind))==1
    assert len(c.information_architecture.kinds)==13


def test_every_mutation_is_undoable_and_redoable():
    p,doc,c=make()
    c.create("resources",BattleResourceDefinition("rage",minimum=0,maximum=10))
    assert "rage" in p.rpg_database.battle_resources
    assert doc.undo()
    assert "rage" not in p.rpg_database.battle_resources
    assert doc.redo()
    assert "rage" in p.rpg_database.battle_resources


def test_edit_replaces_canonical_definition_atomically():
    p,doc,c=make()
    c.create("resources",BattleResourceDefinition("rage",minimum=0,maximum=10))
    c.edit("resources","rage",BattleResourceDefinition(
        "rage",minimum=0,maximum=100,start_mode="fixed",start_value=20
    ))
    assert p.rpg_database.battle_resources["rage"].maximum==100
    assert doc.undo()
    assert p.rpg_database.battle_resources["rage"].maximum==10


def test_ability_linked_rules_reject_unknown_abilities():
    _,_,c=make()
    with pytest.raises(RpgBattleRulesAuthoringError):
        c.create("targeting",BattleTargetingDefinition("missing"))
    with pytest.raises(RpgBattleRulesAuthoringError):
        c.create("timing",ActionTimingDefinition("missing"))
    with pytest.raises(RpgBattleRulesAuthoringError):
        c.create("transactions",ActionTransactionPolicy("missing"))
    with pytest.raises(RpgBattleRulesAuthoringError):
        c.create("reactions",ReactionDefinition(
            "bad","x","event_targets",ability_id="missing"
        ))
    with pytest.raises(RpgBattleRulesAuthoringError):
        c.create("sequences",ActionSequenceDefinition(
            "bad",(ActionSequenceStep("missing"),)
        ))


def test_gauge_references_require_authored_resources_and_states():
    _,_,c=make()
    gauge=sample_definitions()["gauges"]
    with pytest.raises(RpgBattleRulesAuthoringError):
        c.create("gauges",gauge)
    c.create("resources",sample_definitions()["resources"])
    with pytest.raises(RpgBattleRulesAuthoringError):
        c.create("gauges",gauge)
    c.create("states",sample_definitions()["states"])
    c.create("gauges",gauge)
    assert c.definitions("gauges")[0].composition_id=="stagger_break"


def test_resource_and_state_delete_protect_gauge_references():
    _,_,c=make()
    seed_dependencies(c)
    c.create("gauges",sample_definitions()["gauges"])
    with pytest.raises(RpgBattleRulesAuthoringError):
        c.delete("resources","stagger")
    with pytest.raises(RpgBattleRulesAuthoringError):
        c.delete("states","broken")


def test_serialized_data_can_be_used_for_authoring():
    _,_,c=make()
    raw=BattleResourceDefinition(
        "heat",minimum=0,maximum=100,start_mode="fixed",start_value=0
    ).to_data()
    value=c.create("resources",raw)
    assert isinstance(value,BattleResourceDefinition)
    assert value.resource_id=="heat"


def test_information_architecture_groups_complexity_in_two_levels():
    _,_,c=make()
    ia=c.information_architecture
    assert ia.primary_navigation=="rule_group_sidebar"
    assert ia.secondary_navigation=="rule_kind_tabs"
    assert len(ia.groups)==5
    assert ia.group("combat_model").kind_ids==(
        "resources","states","interactions","outcome_checks","targeting"
    )
    assert ia.progressive_disclosure
    assert not ia.show_all_rule_kinds_simultaneously
    assert not ia.show_all_details_simultaneously


def test_workspace_group_switch_does_not_show_every_rule_kind():
    _,_,c=make()
    c.create("resources",BattleResourceDefinition("hp"))
    c.create("schedulers",BattleSchedulerDefinition("turns"))
    w=RpgBattleRulesWorkspaceModel(c)
    assert w.snapshot().group_id=="combat_model"
    assert w.snapshot().kind_id=="resources"
    assert w.snapshot().visible_ids==("hp",)
    w.set_group("turn_flow")
    assert w.snapshot().kind_id=="schedulers"
    assert w.snapshot().visible_ids==("turns",)


def test_workspace_contextual_child_focus_for_sequence_and_gauge():
    _,_,c=make()
    c.create("sequences",sample_definitions()["sequences"])
    w=RpgBattleRulesWorkspaceModel(c)
    w.set_group("action_logic")
    w.set_kind("sequences")
    w.select("triple")
    w.focus_child("step:0")
    assert w.snapshot().focused_child_id=="step:0"
    w.set_kind("reactions")
    assert w.snapshot().focused_child_id is None
    with pytest.raises(RuntimeError):
        w.focus_child("anything")


def test_search_filters_current_rule_kind_only():
    _,_,c=make()
    c.create("resources",BattleResourceDefinition("stagger"))
    c.create("resources",BattleResourceDefinition("boost"))
    w=RpgBattleRulesWorkspaceModel(c)
    w.set_query("stag")
    assert w.visible_ids()==("stagger",)


def test_current_project_roundtrip_preserves_all_battle_rule_types():
    p,doc,c=make()
    values=sample_definitions()
    c.create("resources",values.pop("resources"))
    c.create("states",values.pop("states"))
    for kind,value in values.items():
        c.create(kind,value)
    raw=p.to_data()
    clone=Project.from_data(raw,doc.component_registry)
    assert clone.to_data()==raw
    assert len(clone.rpg_database.gauge_compositions)==1
    assert len(clone.rpg_database.reactions)==1
    assert len(clone.rpg_database.action_transactions)==1


def test_project_level_validation_checks_editor_only_battle_references():
    _,_,c=make()
    c.create("resources",BattleResourceDefinition("stagger"))
    c.create("states",BattleStatePolicy("broken"))
    c.create("gauges",sample_definitions()["gauges"])
    assert c.validate()==()


def test_kind_identity_key_cannot_be_changed_during_edit():
    _,_,c=make()
    c.create("resources",BattleResourceDefinition("rage"))
    with pytest.raises(RpgBattleRulesAuthoringError):
        c.edit("resources","rage",BattleResourceDefinition("focus"))


def test_unknown_rule_kind_is_rejected():
    _,_,c=make()
    with pytest.raises(KeyError):
        c.create("break_system",{"x":1})
