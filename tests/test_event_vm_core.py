import json

import pytest

from asteria.events import (
    EventInstruction,
    EventProgram,
    EventVM,
    EventVMError,
    EventVMState,
    EventVMStatus,
)


def test_event_program_roundtrip_is_deterministic():
    program = EventProgram(
        [
            EventInstruction("set_flag", {"name": "door", "value": True}),
            EventInstruction("WAIT", {"seconds": 0.5}),
            EventInstruction("END"),
        ],
        name="Door Event",
    )
    data = program.to_data()
    restored = EventProgram.from_data(json.loads(json.dumps(data)))
    assert restored == program


def test_vm_yields_host_instruction_and_advances_pc():
    program = EventProgram([EventInstruction("CUSTOM", {"value": 7})])
    vm = EventVM(program)
    result = vm.step()
    assert result.instruction.opcode == "CUSTOM"
    assert result.pc_before == 0
    assert result.pc_after == 1
    assert vm.state.status == EventVMStatus.COMPLETED


def test_wait_blocks_without_consuming_next_instruction():
    program = EventProgram(
        [
            EventInstruction("WAIT", {"seconds": 1.0}),
            EventInstruction("CUSTOM"),
        ]
    )
    vm = EventVM(program)
    first = vm.step()
    assert first.instruction.opcode == "WAIT"
    assert vm.waiting
    assert vm.state.pc == 1

    blocked = vm.step()
    assert blocked.instruction is None
    assert vm.state.pc == 1

    vm.update_wait(0.4)
    assert vm.waiting
    assert vm.state.wait_remaining == pytest.approx(0.6)

    vm.update_wait(0.6)
    assert vm.state.status == EventVMStatus.RUNNING
    assert vm.state.pc == 1


def test_wait_snapshot_restore_resumes_exactly():
    program = EventProgram(
        [
            EventInstruction("WAIT", {"seconds": 2.0}),
            EventInstruction("CUSTOM", {"id": 3}),
        ]
    )
    vm = EventVM(program)
    vm.step()
    vm.update_wait(0.75)

    snapshot = vm.snapshot().to_data()
    restored = EventVM.restore(program, snapshot)

    assert restored.state.pc == 1
    assert restored.state.status == EventVMStatus.WAITING
    assert restored.state.wait_remaining == pytest.approx(1.25)

    restored.update_wait(1.25)
    result = restored.step()
    assert result.instruction.args["id"] == 3
    assert restored.completed


def test_end_terminates_without_running_following_instructions():
    program = EventProgram(
        [
            EventInstruction("CUSTOM", {"n": 1}),
            EventInstruction("END"),
            EventInstruction("CUSTOM", {"n": 2}),
        ]
    )
    vm = EventVM(program)
    yielded = vm.run_until_blocked()
    assert [x.args["n"] for x in yielded] == [1]
    assert vm.completed
    assert vm.state.pc == len(program)


def test_stop_and_resume_preserve_program_counter():
    program = EventProgram([EventInstruction("A"), EventInstruction("B")])
    vm = EventVM(program)
    assert vm.step().instruction.opcode == "A"
    vm.stop()
    assert vm.state.status == EventVMStatus.STOPPED
    assert vm.state.pc == 1
    assert vm.step().instruction is None
    vm.resume()
    assert vm.step().instruction.opcode == "B"
    assert vm.completed


def test_invalid_wait_is_rejected():
    vm = EventVM(EventProgram([EventInstruction("WAIT", {"seconds": -1})]))
    with pytest.raises(EventVMError):
        vm.step()


def test_vm_state_schema_rejects_invalid_wait_contract():
    with pytest.raises(ValueError):
        EventVMState(
            pc=1,
            status=EventVMStatus.RUNNING,
            wait_remaining=1.0,
        ).validate()
