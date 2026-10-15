"""ATB / CTB: turn gauges, the predicted turn order and the wait modes of an ATB clock."""

import pytest

from asteria.gameplay import GameplaySubject, ResourcePool, StatBlock, TagSet
from asteria.rpg import PartyMember
from asteria.rpg.battle_scheduler import (
    ATBClock,
    BattleScheduler,
    BattleSchedulerDefinition,
)


def _member(name, side, speed):
    subject = GameplaySubject(StatBlock({}), ResourcePool(), TagSet())
    return PartyMember(name, side, subject, initiative=speed)


def _scheduler(mode="continuous", speeds=(("a", 50), ("b", 25))):
    members = [_member(n, "x", s) for n, s in speeds]
    return BattleScheduler(members, BattleSchedulerDefinition("atb", mode=mode)), members


def test_gauge_fills_as_the_timeline_advances():
    scheduler, _ = _scheduler()  # a is ready at t=2, b at t=4
    assert scheduler.gauge("a") == 0.0
    scheduler.advance_time(1.0)
    assert scheduler.gauge("a") == pytest.approx(0.5)
    assert scheduler.gauge("b") == pytest.approx(0.25)
    scheduler.advance_time(2.0)
    assert scheduler.gauge("a") == 1.0
    assert scheduler.gauges() == {"a": 1.0, "b": 0.5}


def test_gauge_restarts_after_the_member_acts():
    scheduler, _ = _scheduler()
    scheduler.advance_time(2.0)
    scheduler.pop()  # a acts; its next turn is at t=4
    assert scheduler.gauge("a") == 0.0
    scheduler.advance_time(3.0)
    assert scheduler.gauge("a") == pytest.approx(0.5)


def test_gauge_is_zero_outside_continuous_mode_and_for_strangers():
    scheduler, _ = _scheduler("speed_ordered")
    assert scheduler.gauge("a") == 0.0 and scheduler.gauge("nobody") == 0.0


def test_preview_order_is_the_charge_time_bar_and_changes_nothing():
    scheduler, _ = _scheduler()
    before = scheduler.to_data()
    order = scheduler.preview_order(5)
    assert [m for m, _ in order] == ["a", "a", "b", "a", "a"]
    assert [round(t, 6) for _, t in order] == [2.0, 4.0, 4.0, 6.0, 8.0]
    assert scheduler.to_data() == before
    assert scheduler.preview_order(0) == ()


def test_preview_order_follows_speed_changes():
    scheduler, members = _scheduler()
    first = [m for m, _ in scheduler.preview_order(4)]
    members[1] = _member("b", "x", 100)  # b is hasted
    scheduler.replace_member(members[1])
    hasted = [m for m, _ in scheduler.preview_order(4)]
    assert first[:1] == hasted[:1] == ["a"]
    assert hasted.count("b") >= first.count("b")  # a hasted b comes up more often


def test_preview_order_for_round_modes_repeats_the_round():
    scheduler, _ = _scheduler("speed_ordered")
    assert [m for m, _ in scheduler.preview_order(5)] == ["a", "b", "a", "b", "a"]


def test_scheduler_data_round_trips_with_charge_starts():
    scheduler, members = _scheduler()
    scheduler.advance_time(2.0)
    scheduler.pop()
    restored = BattleScheduler.from_data(scheduler.to_data(), members)
    assert restored.gauges() == scheduler.gauges()
    assert restored.preview_order(4) == scheduler.preview_order(4)


def test_atb_clock_returns_the_ready_turn_and_waits_for_it():
    scheduler, _ = _scheduler()
    clock = ATBClock(scheduler)
    assert clock.tick(1.0) is None and scheduler.current_time == 1.0
    ready = clock.tick(5.0)
    assert ready.member_id == "a" and scheduler.current_time == 2.0  # stops at the ready turn
    assert clock.tick(1.0).member_id == "a"  # still waiting for its actor
    assert scheduler.current_time == 2.0
    scheduler.pop()
    assert clock.tick(1.0) is None and scheduler.current_time == 3.0


@pytest.mark.parametrize(
    "mode, choosing, runs",
    [
        ("active", "target", True),
        ("active", "submenu", True),
        ("semi", "submenu", False),
        ("semi", "target", True),
        ("wait", "submenu", False),
        ("wait", "target", False),
        ("wait", "command", True),
        ("wait", "", True),
    ],
)
def test_wait_modes_decide_when_time_stops(mode, choosing, runs):
    scheduler, _ = _scheduler()
    clock = ATBClock(scheduler, wait_mode=mode)
    clock.tick(0.5, choosing=choosing)
    assert (scheduler.current_time > 0) is runs


def test_clock_rate_scales_time_and_validates():
    scheduler, _ = _scheduler()
    ATBClock(scheduler, rate=2.0).tick(0.5)
    assert scheduler.current_time == pytest.approx(1.0)
    round_based, _ = _scheduler("round")
    with pytest.raises(ValueError):
        ATBClock(round_based)
    with pytest.raises(ValueError):
        ATBClock(scheduler, wait_mode="turbo")
    with pytest.raises(ValueError):
        ATBClock(scheduler, rate=0)
