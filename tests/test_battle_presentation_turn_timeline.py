from copy import deepcopy

from asteria.gameplay import GameplaySubject, ResourcePool, StatBlock, TagSet
from asteria.presentation import BattleTurnTimelineRuntime
from asteria.rpg import (
    ActionTimingDefinition,
    BattleAction,
    BattleActionTimingRuntime,
    BattleScheduler,
    BattleSchedulerDefinition,
    PartyMember,
)


def subject():
    return GameplaySubject(StatBlock(), ResourcePool(), TagSet())


def member(mid, side, speed):
    return PartyMember(mid, side, subject(), initiative=speed)


def test_speed_ordered_timeline_mirrors_scheduler_without_mutation():
    members = [member("hero", "heroes", 10), member("mimic", "enemies", 5)]
    scheduler = BattleScheduler(members, BattleSchedulerDefinition("speed", mode="speed_ordered"))
    before = deepcopy(scheduler.to_data())
    view = BattleTurnTimelineRuntime().sync(scheduler, current_member_id="hero")
    assert [x.member_id for x in view.turns] == ["hero", "mimic"]
    assert view.turns[0].is_current and not view.turns[1].is_current
    assert scheduler.to_data() == before


def test_continuous_timeline_exposes_canonical_ready_times():
    members = [member("hero", "heroes", 100), member("mimic", "enemies", 25)]
    scheduler = BattleScheduler(members, BattleSchedulerDefinition("ct", mode="continuous", timeline_scale=100))
    view = BattleTurnTimelineRuntime().sync(scheduler)
    assert [(x.member_id, x.ready_time) for x in view.turns] == [("hero", 1.0), ("mimic", 4.0)]


def test_cast_view_mirrors_pending_action_progress_without_resolving_it():
    members = [member("hero", "heroes", 100)]
    scheduler = BattleScheduler(members, BattleSchedulerDefinition("ct", mode="continuous", timeline_scale=100))
    scheduler.advance_time(2)
    timing = BattleActionTimingRuntime([ActionTimingDefinition("meteor", startup=1, cast_time=3, priority=7)])
    timing.begin(BattleAction("hero", "meteor", ("mimic",)), current_time=2)
    before = deepcopy(timing.to_data())
    scheduler.advance_time(4)
    view = BattleTurnTimelineRuntime().sync(scheduler, timing)
    cast = view.casts[0]
    assert cast.ability_id == "meteor"
    assert cast.target_ids == ("mimic",)
    assert cast.resolve_at == 6
    assert cast.remaining == 2
    assert cast.progress == 0.5
    assert timing.to_data() == before


def test_timeline_without_pending_timing_has_no_invented_casts():
    members = [member("hero", "heroes", 10)]
    scheduler = BattleScheduler(members)
    view = BattleTurnTimelineRuntime().sync(scheduler)
    assert view.casts == ()


def test_timeline_max_turns_is_presentation_only():
    members = [member(str(i), "side", 10 - i) for i in range(5)]
    scheduler = BattleScheduler(members)
    view = BattleTurnTimelineRuntime(max_turns=2).sync(scheduler)
    assert len(view.turns) == 2
    assert len(scheduler.pending()) == 5


def test_snapshot_restore_is_deterministic():
    members = [member("hero", "heroes", 10), member("mimic", "enemies", 5)]
    scheduler = BattleScheduler(members)
    runtime = BattleTurnTimelineRuntime(max_turns=4)
    runtime.sync(scheduler, current_member_id="hero")
    snapshot = runtime.snapshot()
    restored = BattleTurnTimelineRuntime()
    restored.restore(snapshot)
    assert restored.snapshot() == snapshot
