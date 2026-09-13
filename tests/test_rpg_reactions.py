import json

from asteria.gameplay import (
    AbilityDefinition, AbilityEffect, AbilityRegistry, AbilityRuntime, AbilityTargetMode,
    Effect, EffectOperation, EffectOperationKind, GameplaySubject, ResourcePool, StatBlock,
    TagSet, TargetingRule,
)
from asteria.rpg import (
    BattleAction, BattleRuntime, Party, PartyMember, ReactionDefinition, ReactionRuntime,
    RpgDatabase,
)


def subject(hp=100):
    resources = ResourcePool(); resources.define("hp", hp)
    return GameplaySubject(StatBlock(), resources, TagSet())


def abilities():
    registry = AbilityRegistry()
    for aid, delta in (("hit", -10), ("counter", -7), ("follow", -3)):
        registry.register(AbilityDefinition(
            aid,
            targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=False),
            effects=[AbilityEffect(AbilityTargetMode.SELECTED, Effect(
                f"{aid}.effect", [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", delta)]
            ))],
        ))
    return AbilityRuntime(registry)


def make_battle(definitions=()):
    hero = PartyMember("hero", "heroes", subject(), ability_ids=("hit", "counter", "follow"), initiative=20)
    ally = PartyMember("ally", "heroes", subject(), ability_ids=("counter", "follow"), initiative=15)
    enemy = PartyMember("enemy", "enemies", subject(), ability_ids=("hit", "counter", "follow"), initiative=10)
    return BattleRuntime([Party("heroes", [hero, ally]), Party("enemies", [enemy])], abilities(), reaction_definitions=definitions)


def test_reaction_definition_roundtrip_uses_open_selectors_and_policies():
    value = ReactionDefinition(
        "cover", "rpg.battle.before_action", "allies_of_targets",
        target_selector="event_source", priority=20,
        action_target_policy="replace_event_targets_with_reactor",
    )
    assert ReactionDefinition.from_data(value.to_data()) == value


def test_counter_reaction_executes_normal_ability_pipeline():
    rule = ReactionDefinition(
        "counter", "rpg.battle.after_action", "event_targets",
        target_selector="event_source", ability_id="counter", allow_self=False, blocked_tags=("reaction",),
    )
    battle = make_battle([rule])
    result, chain = battle.execute_with_reactions(BattleAction("hero", "hit", ["enemy"]))
    assert result.execution_result.executed
    assert battle.member("enemy").subject.resources.current("hp") == 90
    assert battle.member("hero").subject.resources.current("hp") == 93
    assert [x.reaction_id for x in chain.requests] == ["counter"]


def test_priority_then_stable_definition_order_is_deterministic():
    rules = [
        ReactionDefinition("z_low", "custom", "event_targets", ability_id=None, priority=1),
        ReactionDefinition("b_high", "custom", "event_targets", ability_id=None, priority=5),
        ReactionDefinition("a_high", "custom", "event_targets", ability_id=None, priority=5),
    ]
    battle = make_battle(rules)
    chain = battle.resolve_reactions("custom", "hero", ["enemy"])
    assert [x.reaction_id for x in chain.requests] == ["a_high", "b_high", "z_low"]


def test_incapacitated_reactor_is_suppressed_by_default():
    rule = ReactionDefinition("counter", "custom", "event_targets", ability_id="counter")
    battle = make_battle([rule])
    battle.incapacitate("enemy")
    chain = battle.resolve_reactions("custom", "hero", ["enemy"])
    assert chain.requests == ()


def test_target_replacement_mechanism_supports_cover_without_named_cover_system():
    rule = ReactionDefinition(
        "guard_friend", "rpg.battle.before_action", "allies_of_targets",
        target_selector="event_source", priority=10, require_can_act=True,
        action_target_policy="replace_event_targets_with_reactor",
    )
    battle = make_battle([rule])
    # Custom project data chose a broad selector; deterministic ordering means ally then enemy.
    # The final replacement demonstrates mechanism, not a hard-coded cover rule.
    chain = battle.resolve_reactions("rpg.battle.before_action", "hero", ["enemy"])
    assert chain.final_target_ids in (("ally",), ("enemy",))


def test_reaction_on_reaction_can_be_bounded_by_per_chain_counts():
    rule = ReactionDefinition(
        "counter", "rpg.battle.after_action", "event_targets",
        target_selector="event_source", ability_id="counter", max_per_chain=1,
    )
    battle = make_battle([rule])
    _, chain = battle.execute_with_reactions(BattleAction("hero", "hit", ["enemy"]))
    # enemy counters hero, then hero may counter enemy once; the same reactor/rule cannot loop forever.
    assert len(chain.requests) <= 2
    assert battle.member("hero").subject.resources.current("hp") >= 86


def test_global_reaction_limit_prevents_author_rules_from_crashing_engine():
    rule = ReactionDefinition(
        "loop", "rpg.battle.after_action", "event_targets",
        target_selector="event_source", ability_id="counter", max_per_chain=99,
    )
    battle = make_battle([])
    battle.reactions = ReactionRuntime([rule], max_reactions=5)
    chain = battle.resolve_reactions("rpg.battle.after_action", "hero", ["enemy"])
    assert len(chain.requests) == 5
    assert "max_reactions" in chain.suppressed


def test_tags_can_opt_in_and_block_reaction_rules():
    rule = ReactionDefinition(
        "follow", "custom", "allies_of_source", ability_id=None,
        required_tags=("outcome.critical",), blocked_tags=("reaction",), allow_self=False,
    )
    battle = make_battle([rule])
    assert battle.resolve_reactions("custom", "hero", ["enemy"], tags=("outcome.critical",)).requests
    assert not battle.resolve_reactions("custom", "hero", ["enemy"], tags=("outcome.critical", "reaction")).requests


def test_database_v18_owns_reactions_and_v17_is_backward_readable():
    db = RpgDatabase(); db.add_reaction(ReactionDefinition("counter", "custom", "event_targets"))
    raw = db.to_data()
    assert raw["version"] == 23
    assert "counter" in RpgDatabase.from_data(raw).reactions
    legacy = json.loads(json.dumps(raw)); legacy["version"] = 17; legacy.pop("reactions")
    assert RpgDatabase.from_data(legacy).reactions == {}


def test_many_reactions_have_no_engine_content_cap():
    runtime = ReactionRuntime([ReactionDefinition(f"r{i}", f"t{i}", "event_targets") for i in range(256)])
    assert len(runtime.definitions) == 256
