import copy

import pytest

from asteria.rpg import (
    ActorDefinition,
    ClassDefinition,
    ProgressionAllocationRuntime,
    ProgressionGraphDefinition,
    ProgressionNodeDefinition,
    ProgressionNodeRequirement,
    ProgressionNodeReward,
    RpgDatabase,
    RpgRuntimeState,
)


def graph_definition():
    return ProgressionGraphDefinition(
        "aria_board",
        "Aria Growth Board",
        nodes=[
            ProgressionNodeDefinition(
                "strength",
                "Strength Training",
                max_rank=3,
                rank_costs=[{"ap": 1}, {"ap": 2}, {"ap": 3}],
                rewards=[
                    ProgressionNodeReward(stat_bonuses={"attack": 2}),
                    ProgressionNodeReward(stat_bonuses={"attack": 3}),
                    ProgressionNodeReward(stat_bonuses={"attack": 5}),
                ],
            ),
            ProgressionNodeDefinition(
                "power_strike",
                "Power Strike",
                rank_costs={"ap": 2},
                prerequisites=[ProgressionNodeRequirement("strength", 2)],
                rewards=ProgressionNodeReward(granted_abilities=["power_strike"]),
            ),
            ProgressionNodeDefinition(
                "counter_path",
                "Counter Path",
                rank_costs={"jp": 2},
                prerequisites=[ProgressionNodeRequirement("power_strike")],
                exclusive_group="warrior_branch",
                rewards=ProgressionNodeReward(unlocked_passives=["counter"]),
            ),
            ProgressionNodeDefinition(
                "guard_path",
                "Guard Path",
                rank_costs={"jp": 2},
                prerequisites=[ProgressionNodeRequirement("power_strike")],
                exclusive_group="warrior_branch",
                rewards=ProgressionNodeReward(granted_tags=["style.guard"]),
            ),
        ],
    )


def make_db():
    from asteria.rpg import PassiveDefinition

    db = RpgDatabase()
    db.add_class(ClassDefinition("warrior"))
    db.add_actor(ActorDefinition("aria", class_id="warrior", base_stats={"attack": 10}))
    db.add_passive(PassiveDefinition("counter"))
    db.add_progression_graph(graph_definition())
    return db


def test_graph_roundtrip_and_database_v7_persistence():
    db = make_db()
    raw = db.to_data()
    assert raw["version"] == 25
    loaded = RpgDatabase.from_data(copy.deepcopy(raw))
    assert loaded.progression_graphs["aria_board"].require_node("strength").max_rank == 3

    old = copy.deepcopy(raw)
    old["version"] = 6
    del old["progression_graphs"]
    loaded_old = RpgDatabase.from_data(old)
    assert loaded_old.progression_graphs == {}


def test_ranked_node_cost_preview_and_allocation():
    runtime = ProgressionAllocationRuntime([graph_definition()], balances={"ap": 10})
    preview = runtime.preview_allocate("aria_board", "strength", 2)
    assert preview.allowed
    assert preview.costs == {"ap": 3.0}
    runtime.allocate("aria_board", "strength", 2)
    assert runtime.rank("aria_board", "strength") == 2
    assert runtime.balance("ap") == 7
    assert runtime.contribution().stat_bonuses["attack"] == 5


def test_prerequisite_and_insufficient_currency_reasons_are_explainable():
    runtime = ProgressionAllocationRuntime([graph_definition()], balances={"ap": 1})
    preview = runtime.preview_allocate("aria_board", "power_strike")
    assert not preview.allowed
    assert "requires strength rank 2" in preview.reasons
    runtime.allocate("aria_board", "strength", 1)
    preview = runtime.preview_allocate("aria_board", "strength", 1)
    assert not preview.allowed
    assert any("insufficient ap" in x for x in preview.reasons)


def test_multiple_cost_currencies_and_branch_exclusivity():
    runtime = ProgressionAllocationRuntime([graph_definition()], balances={"ap": 10, "jp": 4})
    runtime.allocate("aria_board", "strength", 2)
    runtime.allocate("aria_board", "power_strike")
    runtime.allocate("aria_board", "counter_path")
    assert "counter" in runtime.contribution().unlocked_passives
    blocked = runtime.preview_allocate("aria_board", "guard_path")
    assert not blocked.allowed
    assert any("exclusive with counter_path" in x for x in blocked.reasons)


def test_refund_blocks_breaking_dependent_nodes_and_supports_partial_refund_policy():
    runtime = ProgressionAllocationRuntime([graph_definition()], balances={"ap": 10})
    runtime.allocate("aria_board", "strength", 2)
    runtime.allocate("aria_board", "power_strike")
    with pytest.raises(ValueError, match="refund rejected"):
        runtime.refund("aria_board", "strength", 1)
    refund = runtime.refund("aria_board", "power_strike", refund_ratio=0.5)
    assert refund == {"ap": 1.0}
    assert runtime.rank("aria_board", "power_strike") == 0


def test_actor_resolution_can_consume_allocation_rewards_without_mutating_intrinsic_stats():
    db = make_db()
    actor = db.build_actor("aria")
    runtime = ProgressionAllocationRuntime(db.progression_graphs.values(), balances={"ap": 10})
    runtime.allocate("aria_board", "strength", 2)
    runtime.allocate("aria_board", "power_strike")
    assert actor.stats.get("attack") == 10
    assert actor.effective_stats(allocations=runtime).get("attack") == 15
    result = actor.resolve_abilities(allocations=runtime)
    assert "power_strike" in result.abilities
    assert result.sources_for("power_strike")[0].source_kind == "allocation"
    assert actor.stats.get("attack") == 10


def test_runtime_state_v3_roundtrip_persists_allocation_state_and_v2_is_readable():
    db = make_db()
    allocation = ProgressionAllocationRuntime(db.progression_graphs.values(), balances={"ap": 5})
    allocation.allocate("aria_board", "strength")
    state = RpgRuntimeState(
        progression_allocations={"actor:aria": allocation},
        progression=__import__("asteria.rpg", fromlist=["ProgressionRuntime"]).ProgressionRuntime(db.progression_tracks.values()),
    )
    raw = state.to_data()
    assert raw["version"] == 7
    loaded = RpgRuntimeState.from_data(copy.deepcopy(raw), db)
    assert loaded.progression_allocations["actor:aria"].rank("aria_board", "strength") == 1
    assert loaded.progression_allocations["actor:aria"].balance("ap") == 4

    old = copy.deepcopy(raw)
    old["version"] = 2
    del old["progression_allocations"]
    del old["actor_progression"]
    del old["party_active_actor_ids"]
    del old["party_placements"]
    del old["shop_stock"]
    del old["quests"]
    del old["world"]
    loaded_old = RpgRuntimeState.from_data(old, db)
    assert loaded_old.progression_allocations == {}


def test_graph_rejects_unknown_prerequisite_and_cycles():
    with pytest.raises(ValueError, match="unknown prerequisite"):
        ProgressionGraphDefinition(
            "bad",
            nodes=[ProgressionNodeDefinition("a", prerequisites=[ProgressionNodeRequirement("missing")])],
        )
    with pytest.raises(ValueError, match="cycle"):
        ProgressionGraphDefinition(
            "cycle",
            nodes=[
                ProgressionNodeDefinition("a", prerequisites=[ProgressionNodeRequirement("b")]),
                ProgressionNodeDefinition("b", prerequisites=[ProgressionNodeRequirement("a")]),
            ],
        )


def test_database_validation_rejects_unknown_passive_reward_reference():
    db = RpgDatabase()
    db.add_progression_graph(ProgressionGraphDefinition(
        "bad_passive",
        nodes=[ProgressionNodeDefinition(
            "node", rewards=ProgressionNodeReward(unlocked_passives=["missing_passive"])
        )],
    ))
    with pytest.raises(ValueError, match="unknown passive"):
        db.validate()
