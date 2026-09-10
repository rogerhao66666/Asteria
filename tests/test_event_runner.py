import json

import pytest

from asteria.events import (
    EventContext,
    EventInstruction,
    EventProgram,
    EventProgramRegistry,
    EventRunner,
    EventRunnerError,
    EventVMStatus,
)
from asteria.runtime import InteractionTrigger


def build_registry():
    registry = EventProgramRegistry()
    registry.register(
        "event-npc",
        EventProgram(
            [
                EventInstruction("SET_LOCAL", {"name": "talked", "value": True}),
                EventInstruction("WAIT", {"seconds": 1.0}),
                EventInstruction("CUSTOM", {"kind": "dialogue-placeholder"}),
                EventInstruction("END"),
            ],
            name="NPC",
        ),
    )
    return registry


def test_registry_uses_stable_ids_and_rejects_duplicates():
    registry = EventProgramRegistry()
    p = EventProgram([EventInstruction("END")])
    registry.register("event-a", p)
    assert registry.require("event-a") is p
    with pytest.raises(ValueError):
        registry.register("event-a", p)
    with pytest.raises(KeyError):
        registry.require("missing")


def test_interaction_trigger_starts_real_event_vm():
    runner = EventRunner(build_registry())
    trigger = InteractionTrigger(
        source_entity_id="npc-entity",
        event_program_id="event-npc",
        local_scope_id="npc-scope",
    )
    vm = runner.start_trigger(trigger)
    assert vm is runner.vm
    assert runner.active.program_id == "event-npc"
    assert runner.active.local_scope_id == "npc-scope"


def test_runner_executes_intrinsics_then_blocks_on_wait():
    context = EventContext()
    runner = EventRunner(build_registry(), context=context)
    runner.start("event-npc", source_entity_id="npc", local_scope_id="npc-scope")

    yielded = runner.update(0.0)
    assert yielded == ()
    assert runner.waiting
    assert context.get_local("npc-scope", "talked") is True


def test_runner_resumes_after_wait_and_yields_host_command():
    runner = EventRunner(build_registry())
    runner.start("event-npc", source_entity_id="npc", local_scope_id="npc-scope")
    runner.update(0.0)

    yielded = runner.update(1.0)
    assert [x.opcode for x in yielded] == ["CUSTOM"]
    assert runner.vm.state.status == EventVMStatus.COMPLETED
    assert runner.clear_completed() is True
    assert runner.vm is None
    assert runner.active is None


def test_runner_refuses_second_foreground_event_without_replace():
    registry = build_registry()
    registry.register("event-b", EventProgram([EventInstruction("END")]))
    runner = EventRunner(registry)
    runner.start("event-npc")
    with pytest.raises(EventRunnerError):
        runner.start("event-b")


def test_runner_snapshot_restore_preserves_exact_vm_and_context_seam():
    registry = build_registry()
    context = EventContext()
    runner = EventRunner(registry, context=context)
    runner.start("event-npc", source_entity_id="npc", local_scope_id="npc-scope")
    runner.update(0.0)
    runner.vm.update_wait(0.25)

    data = json.loads(json.dumps(runner.snapshot()))

    restored = EventRunner(registry, context=context)
    restored.restore(data)

    assert restored.active.program_id == "event-npc"
    assert restored.active.source_entity_id == "npc"
    assert restored.active.local_scope_id == "npc-scope"
    assert restored.vm.state.pc == runner.vm.state.pc
    assert restored.vm.state.status == EventVMStatus.WAITING
    assert restored.vm.state.wait_remaining == pytest.approx(0.75)

    yielded = restored.update(0.75)
    assert [x.opcode for x in yielded] == ["CUSTOM"]
    assert restored.vm.state.status == EventVMStatus.COMPLETED
