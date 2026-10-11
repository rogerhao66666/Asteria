import pytest

from asteria.rpg import ActionSequenceDefinition, ActionSequenceRuntime, ActionSequenceStep, RpgDatabase


def test_multi_hit_plan_is_deterministic():
    d = ActionSequenceDefinition("triple", [ActionSequenceStep("slash", repeat=3)])
    p = ActionSequenceRuntime([d]).plan("triple", ["hero"], ["enemy"])
    assert [(x.actor_id, x.ability_id, x.hit_index) for x in p.steps] == [
        ("hero", "slash", 0),
        ("hero", "slash", 1),
        ("hero", "slash", 2),
    ]


def test_cooperative_n_person_sequence():
    d = ActionSequenceDefinition(
        "duet",
        [
            ActionSequenceStep("fire", participant_index=0, emitted_tags=("heated",)),
            ActionSequenceStep("wind", participant_index=1, required_previous_tags=("heated",)),
        ],
        min_participants=2,
        max_participants=None,
    )
    p = ActionSequenceRuntime([d]).plan("duet", ["mage", "rogue"], ["boss"])
    assert [x.actor_id for x in p.steps] == ["mage", "rogue"]


def test_missing_participant_and_duplicate_rejected():
    d = ActionSequenceDefinition(
        "duet", [ActionSequenceStep("a", participant_index=1)], min_participants=2, max_participants=3
    )
    r = ActionSequenceRuntime([d])
    with pytest.raises(ValueError):
        r.plan("duet", ["a"])
    with pytest.raises(ValueError):
        r.plan("duet", ["a", "a"])


def test_step_tag_prerequisite_is_authored_not_hardcoded():
    good = ActionSequenceDefinition(
        "x",
        [
            ActionSequenceStep("a", emitted_tags=("element.fire",)),
            ActionSequenceStep("b", required_previous_tags=("element.fire",)),
        ],
    )
    assert len(ActionSequenceRuntime([good]).plan("x", ["h"]).steps) == 2
    bad = ActionSequenceDefinition("y", [ActionSequenceStep("b", required_previous_tags=("element.fire",))])
    with pytest.raises(ValueError):
        ActionSequenceRuntime([bad]).plan("y", ["h"])


def test_definition_roundtrip_preserves_open_policy_strings():
    d = ActionSequenceDefinition(
        "x",
        [ActionSequenceStep("a", target_policy="project.chain")],
        participant_policy="project.reserve",
        interruption_policy="project.keep_going",
        tags=("combo",),
    )
    assert ActionSequenceDefinition.from_data(d.to_data()) == d


def test_database_v16_owns_sequences_and_v15_backwards_reads():
    db = RpgDatabase()
    db.add_action_sequence(ActionSequenceDefinition("x", [ActionSequenceStep("a")]))
    data = db.to_data()
    assert data["version"] == 29 and data["action_sequences"][0]["sequence_id"] == "x"
    restored = RpgDatabase.from_data(data)
    assert "x" in restored.action_sequences
    old = dict(data)
    old["version"] = 15
    old.pop("action_sequences")
    assert RpgDatabase.from_data(old).action_sequences == {}


def test_unlimited_participants_has_no_engine_cap():
    d = ActionSequenceDefinition(
        "raid", [ActionSequenceStep("a", participant_index=127)], min_participants=128, max_participants=None
    )
    p = ActionSequenceRuntime([d]).plan("raid", [f"p{i}" for i in range(128)])
    assert p.steps[0].actor_id == "p127"


def test_battle_executes_multi_hit_sequence_through_normal_ability_runtime():
    from asteria.gameplay import (
        AbilityDefinition,
        AbilityEffect,
        AbilityRegistry,
        AbilityRuntime,
        AbilityTargetMode,
        Effect,
        EffectOperation,
        EffectOperationKind,
        GameplaySubject,
        ResourcePool,
        StatBlock,
        TagSet,
        TargetingRule,
    )
    from asteria.rpg import BattleRuntime, Party, PartyMember

    def subj():
        r = ResourcePool()
        r.define("hp", 100, current=100)
        return GameplaySubject(StatBlock(), r, TagSet())

    reg = AbilityRegistry()
    reg.register(
        AbilityDefinition(
            "slash",
            targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=False),
            effects=[
                AbilityEffect(
                    AbilityTargetMode.SELECTED,
                    Effect("hit", [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", -7)]),
                )
            ],
        )
    )
    hero = PartyMember("hero", "h", subj(), ability_ids=("slash",))
    enemy = PartyMember("enemy", "e", subj())
    seq = ActionSequenceDefinition("triple", [ActionSequenceStep("slash", repeat=3)])
    battle = BattleRuntime(
        [Party("h", [hero]), Party("e", [enemy])], AbilityRuntime(reg), action_sequence_definitions=(seq,)
    )
    plan, results, failures = battle.execute_sequence("triple", ["hero"], ["enemy"])
    assert len(results) == 3 and not failures and enemy.subject.resources.current("hp") == 79
