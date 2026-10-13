import json

from asteria.events import (
    EventContext,
    EventInstruction,
    EventProgram,
    EventProgramRegistry,
    EventScheduleMode,
    EventScheduler,
    ScheduledEventSpec,
)


def make_registry():
    registry = EventProgramRegistry()
    registry.register(
        "autorun",
        EventProgram(
            [
                EventInstruction("SET_SWITCH", {"name": "autorun_started", "value": True}),
                EventInstruction("WAIT", {"seconds": 1}),
                EventInstruction("SET_SWITCH", {"name": "autorun_done", "value": True}),
                EventInstruction("END"),
            ]
        ),
    )
    registry.register(
        "parallel",
        EventProgram(
            [
                EventInstruction("SET_VARIABLE", {"name": "parallel_tick", "value": 1}),
                EventInstruction("WAIT", {"seconds": 0.5}),
                EventInstruction("END"),
            ]
        ),
    )
    return registry


def test_autorun_starts_automatically_and_blocks_foreground():
    ctx = EventContext()
    scheduler = EventScheduler(make_registry(), context=ctx)
    scheduler.add(
        ScheduledEventSpec(
            "auto-1", "autorun", EventScheduleMode.AUTORUN, local_scope_id="auto-scope"
        )
    )

    assert scheduler.can_start_foreground() is True
    scheduler.update(0)
    assert ctx.get_switch("autorun_started") is True
    assert scheduler.autorun_busy is True
    assert scheduler.can_start_foreground() is False


def test_autorun_completion_releases_foreground():
    ctx = EventContext()
    scheduler = EventScheduler(make_registry(), context=ctx)
    scheduler.add(ScheduledEventSpec("auto-1", "autorun", EventScheduleMode.AUTORUN))
    scheduler.update(0)
    scheduler.update(1.0)

    assert ctx.get_switch("autorun_done") is True
    assert scheduler.instance("auto-1") is None
    assert scheduler.can_start_foreground() is True


def test_enabled_autorun_restarts_on_later_scheduler_update():
    ctx = EventContext()
    scheduler = EventScheduler(make_registry(), context=ctx)
    scheduler.add(ScheduledEventSpec("auto-1", "autorun", EventScheduleMode.AUTORUN))
    scheduler.update(0)
    scheduler.update(1.0)
    assert scheduler.instance("auto-1") is None

    scheduler.update(0)
    assert scheduler.instance("auto-1") is not None
    assert scheduler.autorun_busy is True


def test_parallel_runs_without_blocking_foreground():
    ctx = EventContext()
    scheduler = EventScheduler(make_registry(), context=ctx)
    scheduler.add(ScheduledEventSpec("parallel-1", "parallel", EventScheduleMode.PARALLEL))

    scheduler.update(0)
    assert ctx.get_variable("parallel_tick") == 1
    assert scheduler.can_start_foreground() is True


def test_disabled_spec_does_not_start():
    scheduler = EventScheduler(make_registry())
    scheduler.add(
        ScheduledEventSpec("parallel-1", "parallel", EventScheduleMode.PARALLEL, enabled=False)
    )
    scheduler.update(0)
    assert scheduler.instance("parallel-1") is None


def test_multiple_parallel_instances_are_independent():
    scheduler = EventScheduler(make_registry())
    scheduler.add(ScheduledEventSpec("p1", "parallel", EventScheduleMode.PARALLEL))
    scheduler.add(ScheduledEventSpec("p2", "parallel", EventScheduleMode.PARALLEL))
    scheduler.update(0)
    assert scheduler.instance("p1") is not None
    assert scheduler.instance("p2") is not None
    assert scheduler.instance("p1").runner is not scheduler.instance("p2").runner


def test_scheduler_snapshot_restore_preserves_waiting_instance():
    ctx = EventContext()
    registry = make_registry()
    scheduler = EventScheduler(registry, context=ctx)
    scheduler.add(ScheduledEventSpec("auto-1", "autorun", EventScheduleMode.AUTORUN))
    scheduler.update(0)
    assert scheduler.instance("auto-1").runner.waiting

    data = json.loads(json.dumps(scheduler.snapshot()))
    restored = EventScheduler(registry, context=ctx)
    restored.add(ScheduledEventSpec("auto-1", "autorun", EventScheduleMode.AUTORUN))
    restored.restore(data)

    assert restored.instance("auto-1").runner.waiting
    restored.update(1.0)
    assert ctx.get_switch("autorun_done") is True


def test_stop_removes_runtime_instance_without_deleting_spec():
    scheduler = EventScheduler(make_registry())
    scheduler.add(ScheduledEventSpec("p1", "parallel", EventScheduleMode.PARALLEL))
    scheduler.update(0)
    assert scheduler.stop("p1") is True
    assert scheduler.instance("p1") is None
    assert [x.event_id for x in scheduler.specs()] == ["p1"]
