import json

from asteria.events import (
    EventContext,
    EventInstruction,
    EventProgram,
    EventProgramRegistry,
    EventRunner,
)


def make_registry():
    registry = EventProgramRegistry()
    registry.register(
        "common",
        EventProgram(
            [
                EventInstruction("SET_VARIABLE", {"name": "common_ran", "value": True}),
                EventInstruction("END"),
            ]
        ),
    )
    registry.register(
        "root",
        EventProgram(
            [
                EventInstruction("SET_VARIABLE", {"name": "before", "value": 1}),
                EventInstruction("CALL", {"program_id": "common"}),
                EventInstruction("SET_VARIABLE", {"name": "after", "value": 2}),
                EventInstruction("END"),
            ]
        ),
    )
    return registry


def test_call_runs_callee_then_returns_to_exact_next_instruction():
    ctx = EventContext()
    runner = EventRunner(make_registry(), context=ctx)
    runner.start("root", source_entity_id="npc", local_scope_id="npc-1")
    runner.update()

    assert ctx.get_variable("before") == 1
    assert ctx.get_variable("common_ran") is True
    assert ctx.get_variable("after") == 2
    assert runner.vm.completed
    assert runner.call_stack == []


def test_nested_calls_work_as_stack():
    registry = EventProgramRegistry()
    registry.register(
        "c",
        EventProgram(
            [
                EventInstruction("SET_VARIABLE", {"name": "c", "value": 1}),
                EventInstruction("END"),
            ]
        ),
    )
    registry.register(
        "b",
        EventProgram(
            [
                EventInstruction("CALL", {"program_id": "c"}),
                EventInstruction("SET_VARIABLE", {"name": "b", "value": 1}),
                EventInstruction("END"),
            ]
        ),
    )
    registry.register(
        "a",
        EventProgram(
            [
                EventInstruction("CALL", {"program_id": "b"}),
                EventInstruction("SET_VARIABLE", {"name": "a", "value": 1}),
                EventInstruction("END"),
            ]
        ),
    )
    ctx = EventContext()
    runner = EventRunner(registry, context=ctx)
    runner.start("a")
    runner.update()

    assert ctx.get_variable("a") == 1
    assert ctx.get_variable("b") == 1
    assert ctx.get_variable("c") == 1


def test_explicit_return_exits_callee_early():
    registry = EventProgramRegistry()
    registry.register(
        "common",
        EventProgram(
            [
                EventInstruction("SET_VARIABLE", {"name": "inside", "value": 1}),
                EventInstruction("RETURN"),
                EventInstruction("SET_VARIABLE", {"name": "never", "value": 1}),
            ]
        ),
    )
    registry.register(
        "root",
        EventProgram(
            [
                EventInstruction("CALL", {"program_id": "common"}),
                EventInstruction("SET_VARIABLE", {"name": "root_done", "value": 1}),
                EventInstruction("END"),
            ]
        ),
    )
    ctx = EventContext()
    runner = EventRunner(registry, context=ctx)
    runner.start("root")
    runner.update()

    assert ctx.get_variable("inside") == 1
    assert ctx.get_variable("never") is None
    assert ctx.get_variable("root_done") == 1


def test_call_inherits_local_scope_by_default():
    registry = EventProgramRegistry()
    registry.register(
        "common",
        EventProgram(
            [
                EventInstruction("SET_LOCAL", {"name": "seen", "value": True}),
                EventInstruction("END"),
            ]
        ),
    )
    registry.register(
        "root",
        EventProgram(
            [
                EventInstruction("CALL", {"program_id": "common"}),
                EventInstruction("END"),
            ]
        ),
    )
    ctx = EventContext()
    runner = EventRunner(registry, context=ctx)
    runner.start("root", source_entity_id="npc", local_scope_id="npc-self")
    runner.update()

    assert ctx.get_local("npc-self", "seen") is True


def test_call_can_use_callee_specific_scope():
    registry = EventProgramRegistry()
    registry.register(
        "common",
        EventProgram(
            [
                EventInstruction("SET_LOCAL", {"name": "count", "value": 7}),
                EventInstruction("END"),
            ]
        ),
    )
    registry.register(
        "root",
        EventProgram(
            [
                EventInstruction(
                    "CALL",
                    {
                        "program_id": "common",
                        "scope": "callee",
                        "local_scope_id": "common-global",
                    },
                ),
                EventInstruction("END"),
            ]
        ),
    )
    ctx = EventContext()
    runner = EventRunner(registry, context=ctx)
    runner.start("root", local_scope_id="npc-self")
    runner.update()

    assert ctx.get_local("common-global", "count") == 7
    assert ctx.get_local("npc-self", "count") is None


def test_snapshot_restore_mid_nested_call_preserves_stack():
    registry = EventProgramRegistry()
    registry.register(
        "common",
        EventProgram(
            [
                EventInstruction("WAIT", {"seconds": 2}),
                EventInstruction("SET_VARIABLE", {"name": "common_done", "value": True}),
                EventInstruction("END"),
            ]
        ),
    )
    registry.register(
        "root",
        EventProgram(
            [
                EventInstruction("CALL", {"program_id": "common"}),
                EventInstruction("SET_VARIABLE", {"name": "root_done", "value": True}),
                EventInstruction("END"),
            ]
        ),
    )

    ctx = EventContext()
    runner = EventRunner(registry, context=ctx)
    runner.start("root", source_entity_id="npc", local_scope_id="npc-scope")
    runner.update()
    assert runner.waiting
    assert len(runner.call_stack) == 1

    data = json.loads(json.dumps(runner.snapshot()))
    restored = EventRunner(registry, context=ctx)
    restored.restore(data)

    assert len(restored.call_stack) == 1
    assert restored.active.program_id == "common"
    restored.update(2.0)

    assert ctx.get_variable("common_done") is True
    assert ctx.get_variable("root_done") is True


def test_v1_active_event_snapshot_still_restores():
    registry = EventProgramRegistry()
    registry.register("root", EventProgram([EventInstruction("END")]))
    runner = EventRunner(registry)
    legacy = {
        "schema": "asteria.active_event",
        "version": 1,
        "program_id": "root",
        "source_entity_id": "npc",
        "local_scope_id": "npc",
        "vm_state": {
            "schema": "asteria.event_vm_state",
            "version": 1,
            "pc": 0,
            "status": "running",
            "wait_remaining": 0.0,
        },
    }
    runner.restore(legacy)
    assert runner.call_stack == []
    assert runner.active.program_id == "root"
