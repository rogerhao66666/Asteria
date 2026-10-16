"""A side that loses the opening (surprise / preemptive) sits out the first round only, also
under a timeline scheduler: it must act again afterwards."""

import pytest

from asteria.gameplay import GameplaySubject
from asteria.gameplay.stats import ResourcePool, StatBlock
from asteria.gameplay.tags import TagSet
from asteria.rpg.battle import PartyMember
from asteria.rpg.battle_scheduler import (
    BattleScheduler,
    BattleSchedulerDefinition,
    BattleSchedulerMode,
)


def _member(member_id, side, speed):
    subject = GameplaySubject(StatBlock({"speed": speed}), ResourcePool(), TagSet())
    return PartyMember(member_id, side, subject, initiative=speed, initiative_stat="speed")


@pytest.mark.parametrize(
    "mode",
    [BattleSchedulerMode.ROUND, BattleSchedulerMode.SPEED_ORDERED, BattleSchedulerMode.CONTINUOUS],
)
def test_a_member_can_sit_out_one_round_and_comes_back(mode):
    members = [_member("hero", "heroes", 50.0), _member("foe", "enemies", 60.0)]
    scheduler = BattleScheduler(members, BattleSchedulerDefinition("s", mode=mode))
    scheduler.sit_out_round("hero")
    acted = []
    for _ in range(8):
        entry = scheduler.pop()
        if entry is None:
            scheduler.start_next_round()
            continue
        acted.append(entry.member_id)
        if "hero" in acted:
            break
    assert "hero" in acted  # it did return
    assert acted[0] == "foe"  # but not before the foe's first turn
