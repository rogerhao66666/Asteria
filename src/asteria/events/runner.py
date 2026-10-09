from __future__ import annotations

from dataclasses import dataclass

from .call_stack import EventCallFrame
from .context import EventContext
from .dialogue import (
    ChoiceRequest,
    DialogueChoice,
    DialogueLine,
    DialogueRequest,
    DialogueRuntimeState,
)
from .registry import EventProgramRegistry
from .state import EventVMStatus
from .vm import EventVM
from .world_commands import WorldCommand, WorldCommandRouter


class EventRunnerError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ActiveEvent:
    program_id: str
    source_entity_id: str
    local_scope_id: str


class EventRunner:
    """Runtime orchestration layer for a single foreground event.

    Phase 5 Batch 39 intentionally supports one active event at a time.
    Parallel/common/autorun scheduling belongs to a later batch.
    """

    def __init__(
        self,
        registry: EventProgramRegistry,
        *,
        context: EventContext | None = None,
        world_commands: WorldCommandRouter | None = None,
    ):
        if not isinstance(registry, EventProgramRegistry):
            raise TypeError("registry must be EventProgramRegistry")
        self.registry = registry
        self.context = context or EventContext()
        self.world_commands = world_commands
        self.vm: EventVM | None = None
        self.active: ActiveEvent | None = None
        self.dialogue = DialogueRuntimeState()
        self.call_stack: list[EventCallFrame] = []

    @property
    def busy(self) -> bool:
        return self.dialogue.blocked or (
            self.vm is not None
            and self.vm.state.status
            not in {
                EventVMStatus.COMPLETED,
                EventVMStatus.STOPPED,
            }
        )

    @property
    def waiting(self) -> bool:
        return self.vm is not None and self.vm.waiting

    def start(
        self,
        program_id: str,
        *,
        source_entity_id: str = "",
        local_scope_id: str = "",
        replace: bool = False,
    ) -> EventVM:
        if self.busy and not replace:
            raise EventRunnerError("an event is already active")
        if self.vm is not None and replace:
            self.vm.stop()

        program = self.registry.require(program_id)
        scope = str(local_scope_id or source_entity_id)
        self.dialogue.clear()
        self.call_stack.clear()
        self.vm = EventVM(
            program,
            context=self.context,
            local_scope_id=scope or None,
        )
        self.active = ActiveEvent(
            program_id=str(program_id),
            source_entity_id=str(source_entity_id),
            local_scope_id=scope,
        )
        return self.vm

    def start_trigger(self, trigger, *, replace: bool = False) -> EventVM:
        return self.start(
            trigger.event_program_id,
            source_entity_id=trigger.source_entity_id,
            local_scope_id=trigger.local_scope_id,
            replace=replace,
        )

    def update(self, dt: float = 0.0):
        """Advance current event until time/dialogue/choice blocks execution.

        Returns non-dialogue host instructions yielded this update.
        Dialogue and choice are true blocking commands: instructions after them
        are not consumed until the presentation layer responds.
        """
        if self.vm is None or self.dialogue.blocked:
            return ()

        if self.vm.waiting:
            self.vm.update_wait(dt)

        passthrough = []
        intrinsic = {
            "WAIT",
            "END",
            "SET_SWITCH",
            "SET_VARIABLE",
            "SET_LOCAL",
            "LABEL",
            "JUMP",
            "JUMP_IF",
            "IF_FALSE_SKIP",
        }

        while self.vm.state.status == EventVMStatus.RUNNING:
            result = self.vm.step()
            instruction = result.instruction
            if instruction is None:
                break

            if instruction.opcode == "DIALOGUE":
                self._open_dialogue(instruction)
                break

            if instruction.opcode == "CHOICE":
                self._open_choice(instruction)
                break

            if instruction.opcode == "CALL":
                self._call_event(instruction)
                continue

            if instruction.opcode == "RETURN":
                self._return_from_event()
                continue

            if instruction.opcode == "WORLD":
                self._dispatch_world_command(instruction)
                continue

            if instruction.opcode not in intrinsic:
                passthrough.append(instruction)

            if self.vm.state.status == EventVMStatus.COMPLETED:
                if self._complete_or_return():
                    continue
                break

            if self.vm.state.status != EventVMStatus.RUNNING:
                break

        return tuple(passthrough)

    def _call_event(self, instruction):
        if self.vm is None or self.active is None:
            raise EventRunnerError("CALL requires an active event")
        program_id = str(instruction.args.get("program_id", "")).strip()
        if not program_id:
            raise EventRunnerError("CALL requires program_id")
        program = self.registry.require(program_id)

        scope_mode = str(instruction.args.get("scope", "inherit")).strip().lower()
        if scope_mode not in {"inherit", "callee"}:
            raise EventRunnerError("CALL scope must be inherit or callee")
        if scope_mode == "callee":
            local_scope_id = str(instruction.args.get("local_scope_id", "")).strip()
            if not local_scope_id:
                local_scope_id = program_id
        else:
            local_scope_id = self.active.local_scope_id

        self.call_stack.append(
            EventCallFrame(
                program_id=self.active.program_id,
                source_entity_id=self.active.source_entity_id,
                local_scope_id=self.active.local_scope_id,
                vm_state=self.vm.state.to_data(),
            )
        )

        self.vm = EventVM(
            program,
            context=self.context,
            local_scope_id=local_scope_id or None,
        )
        self.active = ActiveEvent(
            program_id=program_id,
            source_entity_id=self.active.source_entity_id,
            local_scope_id=local_scope_id,
        )

    def _return_from_event(self):
        if not self.call_stack:
            if self.vm is not None:
                self.vm.stop()
            return

        frame = self.call_stack.pop()
        program = self.registry.require(frame.program_id)
        self.vm = EventVM.restore(
            program,
            frame.vm_state,
            context=self.context,
            local_scope_id=frame.local_scope_id or None,
        )
        self.active = ActiveEvent(
            program_id=frame.program_id,
            source_entity_id=frame.source_entity_id,
            local_scope_id=frame.local_scope_id,
        )

    def _complete_or_return(self):
        if self.vm is None:
            return False
        if self.vm.state.status != EventVMStatus.COMPLETED:
            return False
        if not self.call_stack:
            return False
        self._return_from_event()
        return True

    def _dispatch_world_command(self, instruction):
        name = instruction.args.get("command")
        raw_args = instruction.args.get("args")
        if raw_args is None:
            # Older programs put command arguments beside "command".
            raw_args = {k: v for k, v in instruction.args.items() if k != "command"}
        if name is None:
            raise EventRunnerError("WORLD requires command")
        if not isinstance(raw_args, dict):
            raise EventRunnerError("WORLD args must be a dict")
        if self.world_commands is None:
            raise EventRunnerError("WORLD command router is not configured")
        source_id = self.active.source_entity_id if self.active is not None else ""
        command = WorldCommand(name, raw_args, source_entity_id=source_id)
        try:
            return self.world_commands.dispatch(command)
        except KeyError as exc:
            raise EventRunnerError(str(exc)) from exc

    def _open_dialogue(self, instruction):
        text = instruction.args.get("text")
        if text is None:
            raise EventRunnerError("DIALOGUE requires text")
        line = DialogueLine(
            text=str(text),
            speaker=str(instruction.args.get("speaker", "")),
            portrait_asset_id=str(instruction.args.get("portrait_asset_id", "")),
        )
        self.dialogue.dialogue = DialogueRequest(line)

    def _open_choice(self, instruction):
        raw_choices = instruction.args.get("choices")
        if not isinstance(raw_choices, list) or not raw_choices:
            raise EventRunnerError("CHOICE requires choices")
        choices = []
        for item in raw_choices:
            if not isinstance(item, dict) or "text" not in item or "value" not in item:
                raise EventRunnerError("invalid CHOICE entry")
            choices.append(DialogueChoice(str(item["text"]), item["value"]))
        self.dialogue.choice = ChoiceRequest(
            str(instruction.args.get("prompt", "")),
            choices,
            variable_name=str(instruction.args.get("variable_name", "")),
            local_name=str(instruction.args.get("local_name", "")),
        )

    def acknowledge_dialogue(self):
        if self.dialogue.dialogue is None:
            raise EventRunnerError("no dialogue is awaiting acknowledgement")
        self.dialogue.dialogue = None

    def choose(self, index: int):
        request = self.dialogue.choice
        if request is None:
            raise EventRunnerError("no choice is awaiting input")
        index = int(index)
        if not 0 <= index < len(request.choices):
            raise IndexError("choice index out of range")
        selected = request.choices[index]
        if request.variable_name:
            self.context.set_variable(request.variable_name, selected.value)
        if request.local_name:
            if self.active is None or not self.active.local_scope_id:
                raise EventRunnerError(
                    "choice local result requires active local scope"
                )
            self.context.set_local(
                self.active.local_scope_id,
                request.local_name,
                selected.value,
            )
        self.dialogue.choice = None
        return selected

    def clear_completed(self) -> bool:
        if self.vm is None:
            return False
        if self.vm.state.status not in {
            EventVMStatus.COMPLETED,
            EventVMStatus.STOPPED,
        }:
            return False
        self.vm = None
        self.active = None
        self.dialogue.clear()
        self.call_stack.clear()
        return True

    def stop(self) -> None:
        if self.vm is not None:
            self.vm.stop()
        self.dialogue.clear()

    def snapshot(self):
        if self.vm is None or self.active is None:
            return None
        return {
            "schema": "asteria.active_event",
            "version": 3,
            "program_id": self.active.program_id,
            "source_entity_id": self.active.source_entity_id,
            "local_scope_id": self.active.local_scope_id,
            "vm_state": self.vm.state.to_data(),
            "call_stack": [frame.to_data() for frame in self.call_stack],
            "dialogue_state": self.dialogue.to_data(),
        }

    def restore(self, data):
        if data is None:
            self.vm = None
            self.active = None
            self.dialogue.clear()
            self.call_stack.clear()
            return
        version = data.get("version")
        if data.get("schema") != "asteria.active_event" or version not in {1, 2, 3}:
            raise ValueError("unsupported active event")

        expected = {
            "schema",
            "version",
            "program_id",
            "source_entity_id",
            "local_scope_id",
            "vm_state",
        }
        if version in {2, 3}:
            expected.add("call_stack")
        if version == 3:
            expected.add("dialogue_state")
        if set(data) != expected:
            raise ValueError("invalid active event")

        program_id = str(data["program_id"])
        program = self.registry.require(program_id)
        self.vm = EventVM.restore(
            program,
            data["vm_state"],
            context=self.context,
            local_scope_id=data["local_scope_id"] or None,
        )
        self.active = ActiveEvent(
            program_id=program_id,
            source_entity_id=str(data["source_entity_id"]),
            local_scope_id=str(data["local_scope_id"]),
        )
        self.call_stack = (
            [EventCallFrame.from_data(item) for item in data["call_stack"]]
            if version in {2, 3}
            else []
        )
        self.dialogue = (
            DialogueRuntimeState.from_data(data["dialogue_state"])
            if version == 3
            else DialogueRuntimeState()
        )
