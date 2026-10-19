"""An outcome check can be blocked by tags: a broken foe cannot guard."""

import random

from asteria.gameplay import ResourcePool, StatBlock, TagSet
from asteria.gameplay.conditions import GameplaySubject
from asteria.rpg.interactions import InteractionResolver, OutcomeCheckDefinition


def _Subject(*tags):
    return GameplaySubject(StatBlock({}), ResourcePool(), TagSet(tags))


def test_a_blocked_target_tag_turns_the_check_off():
    guard = OutcomeCheckDefinition(
        "guard",
        1.0,
        required_target_tags=("trait.guard",),
        blocked_target_tags=("state.broken",),
        success_tags=("outcome.guard",),
    )
    resolver = InteractionResolver((), (guard,))
    rng = random.Random(1)
    assert resolver.check("guard", _Subject(), _Subject("trait.guard"), rng=rng).success
    broken = resolver.check("guard", _Subject(), _Subject("trait.guard", "state.broken"), rng=rng)
    assert not broken.applicable
    data = guard.to_data()
    assert data["blocked_target_tags"] == ["state.broken"]
    assert OutcomeCheckDefinition.from_data(data) == guard


def test_a_multiplier_can_grow_with_the_source_and_target_stats():
    from asteria.rpg.interactions import InteractionRule

    fire = InteractionRule(
        "fire",
        source_tags_all=("damage.fire",),
        multiplier_source_terms={"fire_attack": 0.01},
        multiplier_target_terms={"fire_resist": -0.01},
    )
    resolver = InteractionResolver((fire,), ())
    source, target = _Subject(), _Subject()
    source.stats.set("fire_attack", 30)
    target.stats.set("fire_resist", 50)
    value = resolver.resolve_value(100, source, target, action_tags=("damage.fire",))
    assert round(value.resolved_value, 6) == 80  # x(1 + 0.30 - 0.50)
    assert InteractionRule.from_data(fire.to_data()) == fire
    assert "multiplier_source_terms" not in InteractionRule("plain").to_data()
