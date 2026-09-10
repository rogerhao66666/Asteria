import json

from asteria.events import (
    EventCondition,
    EventContext,
    EventInstruction,
    EventProgram,
    EventVM,
    EventVMStatus,
)


def test_context_roundtrip_preserves_global_and_local_state():
    ctx = EventContext()
    ctx.set_switch("door_open", True)
    ctx.set_variable("gold", 42)
    ctx.set_local("npc-1", "talked", True)

    restored = EventContext.from_data(json.loads(json.dumps(ctx.to_data())))
    assert restored.get_switch("door_open")
    assert restored.get_variable("gold") == 42
    assert restored.get_local("npc-1", "talked") is True


def test_conditions_support_switch_variable_and_local_sources():
    ctx = EventContext()
    ctx.set_switch("ready", True)
    ctx.set_variable("level", 8)
    ctx.set_local("chest-1", "opened", False)

    assert EventCondition("switch", "ready", "==", True).evaluate(ctx)
    assert EventCondition("variable", "level", ">=", 5).evaluate(ctx)
    assert EventCondition("local", "opened", "==", False, scope_id="chest-1").evaluate(
        ctx
    )


def test_vm_state_intrinsics_update_context_without_host_dispatch():
    ctx = EventContext()
    program = EventProgram(
        [
            EventInstruction("SET_SWITCH", {"name": "bridge", "value": True}),
            EventInstruction("SET_VARIABLE", {"name": "score", "value": 10}),
            EventInstruction("SET_LOCAL", {"name": "used", "value": True}),
            EventInstruction("END"),
        ]
    )
    vm = EventVM(program, context=ctx, local_scope_id="lever-1")
    yielded = vm.run_until_blocked()

    assert yielded == ()
    assert ctx.get_switch("bridge") is True
    assert ctx.get_variable("score") == 10
    assert ctx.get_local("lever-1", "used") is True
    assert vm.completed


def test_if_false_skip_skips_exact_number_of_instructions():
    ctx = EventContext()
    ctx.set_switch("has_key", False)
    cond = EventCondition("switch", "has_key", "==", True).to_data()
    program = EventProgram(
        [
            EventInstruction("IF_FALSE_SKIP", {"condition": cond, "count": 1}),
            EventInstruction("SET_SWITCH", {"name": "door_open", "value": True}),
            EventInstruction("SET_SWITCH", {"name": "checked", "value": True}),
        ]
    )
    vm = EventVM(program, context=ctx)
    vm.run_until_blocked()

    assert ctx.get_switch("door_open") is False
    assert ctx.get_switch("checked") is True
    assert vm.state.status == EventVMStatus.COMPLETED


def test_vm_restore_can_resume_with_shared_context():
    ctx = EventContext()
    program = EventProgram(
        [
            EventInstruction("SET_VARIABLE", {"name": "counter", "value": 1}),
            EventInstruction("WAIT", {"seconds": 1}),
            EventInstruction("SET_SWITCH", {"name": "done", "value": True}),
        ]
    )
    vm = EventVM(program, context=ctx)
    vm.run_until_blocked()
    assert ctx.get_variable("counter") == 1

    restored = EventVM.restore(program, vm.snapshot().to_data(), context=ctx)
    restored.update_wait(1.0)
    restored.run_until_blocked()

    assert ctx.get_switch("done") is True
