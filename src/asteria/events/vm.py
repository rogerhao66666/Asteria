from __future__ import annotations

from dataclasses import dataclass

from .conditions import EventCondition
from .context import EventContext
from .program import EventInstruction, EventProgram
from .state import EventVMState, EventVMStatus


class EventVMError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EventStepResult:
    status: EventVMStatus
    instruction: EventInstruction | None = None
    pc_before: int = 0
    pc_after: int = 0


class EventVM:
    """Deterministic single-program event interpreter core.

    Batch 36 intrinsic opcodes:
    - WAIT {"seconds": number}
    - END {}

    Any other opcode is yielded to the host as one deterministic step. Later
    batches can layer context, conditions, dialogue, world commands, etc. on
    top without changing the VM state contract.
    """

    def __init__(
        self,
        program: EventProgram,
        state: EventVMState | None = None,
        *,
        context: EventContext | None = None,
        local_scope_id: str | None = None,
    ):
        if not isinstance(program, EventProgram):
            raise TypeError("program must be EventProgram")
        self.program = program
        self.context = context or EventContext()
        self.local_scope_id = local_scope_id
        self.state = state or EventVMState()
        self.state.validate()
        if self.state.pc > len(self.program):
            raise ValueError("VM state pc exceeds program length")
        if self.state.pc == len(self.program) and self.state.status == EventVMStatus.RUNNING:
            self.state.status = EventVMStatus.COMPLETED

    @property
    def completed(self):
        return self.state.status == EventVMStatus.COMPLETED

    @property
    def waiting(self):
        return self.state.status == EventVMStatus.WAITING

    def stop(self):
        self.state.status = EventVMStatus.STOPPED
        self.state.wait_remaining = 0.0

    def resume(self):
        if self.state.status == EventVMStatus.STOPPED:
            self.state.status = (
                EventVMStatus.COMPLETED
                if self.state.pc >= len(self.program)
                else EventVMStatus.RUNNING
            )
        return self.state.status

    def update_wait(self, dt: float):
        """Advance time without consuming a new program instruction."""
        dt = float(dt)
        if dt < 0.0:
            raise ValueError("dt must be >= 0")
        if self.state.status != EventVMStatus.WAITING:
            return self.state.status
        until = getattr(self, "_until", None)
        if until is not None:  # WAIT until: still waiting while the condition is false
            if not until.evaluate(self.context):
                return self.state.status
            self._until = None
        remaining = max(0.0, self.state.wait_remaining - dt)
        self.state.wait_remaining = remaining
        if remaining == 0.0:
            self.state.status = (
                EventVMStatus.COMPLETED
                if self.state.pc >= len(self.program)
                else EventVMStatus.RUNNING
            )
        return self.state.status

    def step(self):
        status = self.state.status
        pc_before = self.state.pc

        if status in {
            EventVMStatus.WAITING,
            EventVMStatus.COMPLETED,
            EventVMStatus.STOPPED,
        }:
            return EventStepResult(status, None, pc_before, self.state.pc)

        if self.state.pc >= len(self.program):
            self.state.status = EventVMStatus.COMPLETED
            return EventStepResult(self.state.status, None, pc_before, self.state.pc)

        instruction = self.program.instruction(self.state.pc)
        self.state.pc += 1

        if instruction.opcode == "SET_SWITCH":
            name = instruction.args.get("name")
            if name is None:
                raise EventVMError("SET_SWITCH requires name")
            self.context.set_switch(name, instruction.args.get("value", True))

        elif instruction.opcode == "SET_VARIABLE":
            name = instruction.args.get("name")
            if name is None:
                raise EventVMError("SET_VARIABLE requires name")
            source = instruction.args.get("from_variable")
            if source:  # a copy of another variable's value (0 when it has none)
                self.context.set_variable(name, self.context.get_variable(str(source), 0))
            elif instruction.args.get("add") is not None:  # added to (a number; 0 when unset)
                current = self.context.get_variable(name, 0)
                current = current if isinstance(current, (int, float)) else 0
                self.context.set_variable(name, current + instruction.args["add"])
            else:
                self.context.set_variable(name, instruction.args.get("value"))

        elif instruction.opcode == "SET_LOCAL":
            scope_id = instruction.args.get("scope_id", self.local_scope_id)
            name = instruction.args.get("name")
            if not scope_id or name is None:
                raise EventVMError("SET_LOCAL requires scope_id/local_scope_id and name")
            self.context.set_local(scope_id, name, instruction.args.get("value"))

        elif instruction.opcode == "LABEL":
            pass

        elif instruction.opcode == "JUMP":
            label = instruction.args.get("label")
            if label is None:
                raise EventVMError("JUMP requires label")
            try:
                self.state.pc = self.program.label_pc(label)
            except KeyError as exc:
                raise EventVMError(str(exc)) from exc

        elif instruction.opcode == "JUMP_IF":
            raw_condition = instruction.args.get("condition")
            label = instruction.args.get("label")
            if not isinstance(raw_condition, dict) or label is None:
                raise EventVMError("JUMP_IF requires condition and label")
            condition = EventCondition.from_data(raw_condition)
            if condition.evaluate(self.context):
                try:
                    self.state.pc = self.program.label_pc(label)
                except KeyError as exc:
                    raise EventVMError(str(exc)) from exc

        elif instruction.opcode == "IF_FALSE_SKIP":
            raw_condition = instruction.args.get("condition")
            if not isinstance(raw_condition, dict):
                raise EventVMError("IF_FALSE_SKIP requires condition")
            count = int(instruction.args.get("count", 1))
            if count < 0:
                raise EventVMError("IF_FALSE_SKIP count must be >= 0")
            condition = EventCondition.from_data(raw_condition)
            if not condition.evaluate(self.context):
                self.state.pc = min(len(self.program), self.state.pc + count)
                if self.state.pc >= len(self.program):
                    self.state.status = EventVMStatus.COMPLETED

        elif instruction.opcode == "WAIT" and instruction.args.get("until") is not None:
            # wait until a condition holds (a route walked, a switch turned on...)
            raw_condition = instruction.args.get("until")
            if not isinstance(raw_condition, dict):
                raise EventVMError("WAIT until requires a condition")
            condition = EventCondition.from_data(raw_condition)
            if not condition.evaluate(self.context):
                self._until = condition
                self.state.status = EventVMStatus.WAITING
                self.state.wait_remaining = 0.0
            elif self.state.pc >= len(self.program):
                self.state.status = EventVMStatus.COMPLETED

        elif instruction.opcode == "WAIT":
            raw = instruction.args.get("seconds")
            if raw is None:
                raise EventVMError("WAIT requires seconds")
            seconds = float(raw)
            if seconds < 0.0:
                raise EventVMError("WAIT seconds must be >= 0")
            if seconds > 0.0:
                self.state.status = EventVMStatus.WAITING
                self.state.wait_remaining = seconds
            elif self.state.pc >= len(self.program):
                self.state.status = EventVMStatus.COMPLETED

        elif instruction.opcode == "END":
            self.state.pc = len(self.program)
            self.state.status = EventVMStatus.COMPLETED
            self.state.wait_remaining = 0.0

        elif self.state.pc >= len(self.program):
            # Host still receives the final yielded instruction. Completion is
            # observable on the returned state immediately afterward.
            self.state.status = EventVMStatus.COMPLETED

        return EventStepResult(
            self.state.status,
            instruction,
            pc_before,
            self.state.pc,
        )

    def run_until_blocked(self, *, max_steps: int = 10000):
        """Run deterministic instructions until WAIT/END/completion.

        Host opcodes are returned in execution order so a caller can execute
        their effects. This guard prevents accidental infinite orchestration if
        future control-flow instructions are introduced.
        """
        if max_steps <= 0:
            raise ValueError("max_steps must be > 0")
        yielded = []
        for _ in range(max_steps):
            if self.state.status != EventVMStatus.RUNNING:
                break
            result = self.step()
            if result.instruction is not None and result.instruction.opcode not in {
                "WAIT",
                "END",
                "SET_SWITCH",
                "SET_VARIABLE",
                "SET_LOCAL",
                "LABEL",
                "JUMP",
                "JUMP_IF",
                "IF_FALSE_SKIP",
            }:
                yielded.append(result.instruction)
        else:
            raise EventVMError("event execution exceeded max_steps")
        return tuple(yielded)

    def snapshot(self):
        return EventVMState.from_data(self.state.to_data())

    @classmethod
    def restore(
        cls,
        program: EventProgram,
        data,
        *,
        context: EventContext | None = None,
        local_scope_id: str | None = None,
    ):
        state = data if isinstance(data, EventVMState) else EventVMState.from_data(data)
        return cls(program, state, context=context, local_scope_id=local_scope_id)
