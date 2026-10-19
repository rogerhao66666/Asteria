"""An outcome check can be blocked by tags: a broken foe cannot guard."""

import random

from asteria.gameplay import ResourcePool, StatBlock, TagSet
from asteria.rpg.interactions import InteractionResolver, OutcomeCheckDefinition


class _Subject:
    def __init__(self, *tags):
        self.stats, self.resources, self.tags = StatBlock({}), ResourcePool(), TagSet(tags)


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
