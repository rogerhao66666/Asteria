"""Event timers: countdown / count-up, pause, adding time, expiry programs, and saving."""

import pytest

from asteria.events.context import EventContext
from asteria.events.timers import EventTimers, TimerFinished


def _timers():
    return EventTimers(EventContext())


def test_countdown_finishes_once_and_reports_its_program():
    timers = _timers()
    timers.start("bomb", 3, on_expire="boom")
    assert timers.update(1.0) == () and timers.remaining("bomb") == 2.0
    assert timers.update(2.5) == (TimerFinished("bomb", "boom"),)
    assert not timers.exists("bomb") and timers.update(5) == ()
    assert timers.context.get_switch("timer.bomb.expired")


def test_restarting_clears_the_expired_flag():
    timers = _timers()
    timers.start("t", 1)
    timers.update(2)
    timers.start("t", 5)
    assert not timers.context.get_switch("timer.t.expired") and timers.remaining("t") == 5


def test_pause_and_resume():
    timers = _timers()
    timers.start("t", 10)
    timers.pause("t")
    timers.update(4)
    assert timers.remaining("t") == 10 and not timers.running("t")
    timers.resume("t")
    timers.update(4)
    assert timers.remaining("t") == 6
    timers.pause("missing")  # no timer: ignored


def test_count_up_with_and_without_a_limit():
    timers = _timers()
    timers.start("race", 5, count_up=True, on_expire="late")
    timers.update(3)
    assert timers.elapsed("race") == 3 and timers.remaining("race") == 2
    assert timers.update(2) == (TimerFinished("race", "late"),)
    timers.start("clock", 0, count_up=True)
    timers.update(100)
    assert timers.elapsed("clock") == 100 and timers.remaining("clock") is None
    assert timers.exists("clock")  # no limit: never finishes


def test_add_time_and_floor_at_zero():
    timers = _timers()
    timers.start("t", 10)
    timers.add("t", 5)
    assert timers.remaining("t") == 15
    timers.add("t", -100)
    assert timers.remaining("t") == 0
    with pytest.raises(KeyError):
        timers.add("none", 1)


def test_display_lists_visible_timers_in_minutes_and_seconds():
    timers = _timers()
    timers.start("b", 125)
    timers.start("a", 0, count_up=True)
    timers.update(61)
    timers.start("hidden", 9, show=False)
    assert timers.display() == (("a", "01:01"), ("b", "01:04"))


def test_state_is_in_the_event_context_so_a_save_round_trips_it():
    timers = _timers()
    timers.start("t", 30, on_expire="done")
    timers.update(10)
    restored = EventTimers(EventContext.from_data(timers.context.to_data()))
    assert restored.remaining("t") == 20 and restored.active() == ("t",)
    assert restored.update(25) == (TimerFinished("t", "done"),)


def test_stop_removes_everything_and_ids_are_checked():
    timers = _timers()
    timers.start("t", 5)
    timers.stop("t")
    assert timers.active() == () and not [k for k in timers.context.variables if "timer" in k]
    for bad in ("", "a.b"):
        with pytest.raises(ValueError):
            timers.start(bad, 1)
    with pytest.raises(ValueError):
        timers.start("t", -1)
