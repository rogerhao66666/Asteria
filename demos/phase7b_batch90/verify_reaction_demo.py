from asteria.gameplay import (
    AbilityDefinition, AbilityEffect, AbilityRegistry, AbilityRuntime, AbilityTargetMode,
    Effect, EffectOperation, EffectOperationKind, GameplaySubject, ResourcePool, StatBlock,
    TagSet, TargetingRule,
)
from asteria.rpg import BattleAction, BattleRuntime, Party, PartyMember, ReactionDefinition


def subject():
    resources = ResourcePool(); resources.define("hp", 100)
    return GameplaySubject(StatBlock(), resources, TagSet())

registry = AbilityRegistry()
registry.register(AbilityDefinition(
    "hit", targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=False),
    effects=[AbilityEffect(AbilityTargetMode.SELECTED, Effect("hit", [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", -10)]))],
))
registry.register(AbilityDefinition(
    "counter", targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=False),
    effects=[AbilityEffect(AbilityTargetMode.SELECTED, Effect("counter", [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", -7)]))],
))
hero = PartyMember("Aria", "heroes", subject(), ability_ids=("hit", "counter"), initiative=20)
ally = PartyMember("Bram", "heroes", subject(), ability_ids=("counter",), initiative=15)
enemy = PartyMember("Iron Beetle", "enemies", subject(), ability_ids=("counter",), initiative=10)
reactions = (
    ReactionDefinition("counter", "rpg.battle.after_action", "event_targets", target_selector="event_source", ability_id="counter", blocked_tags=("reaction",), priority=10),
    ReactionDefinition("cover", "rpg.battle.before_action", "allies_of_targets_except_targets", action_target_policy="replace_event_targets_with_reactor", priority=20),
)
battle = BattleRuntime([Party("heroes", [hero, ally]), Party("enemies", [enemy])], AbilityRuntime(registry), reaction_definitions=reactions)
result, chain = battle.execute_with_reactions(BattleAction("Aria", "hit", ("Iron Beetle",)))
assert result.execution_result.executed
assert enemy.subject.resources.current("hp") == 90
assert hero.subject.resources.current("hp") == 93
assert [x.reaction_id for x in chain.requests] == ["counter"]
print("Batch 90 reaction demo: PASS")
print("reaction order:", [x.reaction_id for x in chain.requests])
print("Aria HP:", hero.subject.resources.current("hp"))
print("Iron Beetle HP:", enemy.subject.resources.current("hp"))
