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
from asteria.rpg import (
    BattleAction,
    BattleRuntime,
    Party,
    PartyMember,
    TurnQueue,
)


def subject(hp=100):
    resources = ResourcePool()
    resources.define("hp", hp)
    return GameplaySubject(StatBlock(), resources, TagSet())


def ability_runtime():
    registry = AbilityRegistry()
    registry.register(
        AbilityDefinition(
            "hit",
            targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=False),
            effects=[
                AbilityEffect(
                    AbilityTargetMode.SELECTED,
                    Effect(
                        "damage",
                        [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", -10)],
                    ),
                )
            ],
        )
    )
    return AbilityRuntime(registry)


def test_party_rejects_wrong_side():
    p = Party("player")
    try:
        p.add(PartyMember("e", "enemy", subject()))
    except ValueError:
        pass
    else:
        raise AssertionError("expected side mismatch")


def test_turn_queue_is_deterministic_and_tie_breaks_by_id():
    a = PartyMember("b", "p", subject(), initiative=10)
    b = PartyMember("a", "p", subject(), initiative=10)
    c = PartyMember("c", "p", subject(), initiative=5)
    q = TurnQueue([a, b, c])
    assert [x.member_id for x in q.pending()] == ["a", "b", "c"]


def test_turn_queue_snapshot_resume():
    members = [
        PartyMember("a", "p", subject(), initiative=2),
        PartyMember("b", "p", subject(), initiative=1),
    ]
    q = TurnQueue(members)
    q.pop()
    restored = TurnQueue.from_data(q.to_data(), members)
    assert restored.round_index == q.round_index
    assert [x.member_id for x in restored.pending()] == ["b"]


def test_battle_executes_phase6_ability_without_rpg_damage_rules():
    hero = PartyMember("hero", "player", subject(), ability_ids=["hit"], initiative=10)
    slime = PartyMember("slime", "enemy", subject(30), ability_ids=["hit"], initiative=5)
    battle = BattleRuntime([Party("player", [hero]), Party("enemy", [slime])], ability_runtime())
    result = battle.execute(BattleAction("hero", "hit", ["slime"]))
    assert result.execution_result.executed
    assert slime.subject.resources.current("hp") == 20


def test_unknown_or_unowned_ability_rejected():
    hero = PartyMember("hero", "player", subject(), ability_ids=[], initiative=1)
    slime = PartyMember("slime", "enemy", subject(), ability_ids=["hit"], initiative=0)
    battle = BattleRuntime([Party("player", [hero]), Party("enemy", [slime])], ability_runtime())
    try:
        battle.execute(BattleAction("hero", "hit", ["slime"]))
    except ValueError:
        pass
    else:
        raise AssertionError("expected unowned ability rejection")


def test_party_side_names_are_project_defined():
    left = PartyMember("l", "heroes.guild", subject(), ability_ids=["hit"], initiative=3)
    right = PartyMember("r", "moon.court", subject(), ability_ids=["hit"], initiative=2)
    battle = BattleRuntime([Party("heroes.guild", [left]), Party("moon.court", [right])], ability_runtime())
    assert battle.next_actor().member_id == "l"
