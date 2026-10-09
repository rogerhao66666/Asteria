from __future__ import annotations

from dataclasses import dataclass

from asteria.events import (
    EventBinding,
    EventProgram,
    SceneEventBindings,
)


def bindings_for_scene(project, scene):
    return project.scene_event_bindings.setdefault(scene.id, SceneEventBindings())


@dataclass(slots=True)
class ReplaceEventProgramCommand:
    registry: object
    program_id: str
    new_program: EventProgram
    old_program: EventProgram

    @property
    def label(self):
        return "Edit Event Program"

    def redo(self):
        self.registry.replace(self.program_id, self.new_program)

    def undo(self):
        self.registry.replace(self.program_id, self.old_program)


@dataclass(slots=True)
class AddEventProgramCommand:
    registry: object
    program_id: str
    program: EventProgram

    @property
    def label(self):
        return "Add Event Program"

    def redo(self):
        if self.registry.get(self.program_id) is None:
            self.registry.register(self.program_id, self.program)
        else:
            self.registry.replace(self.program_id, self.program)

    def undo(self):
        self.registry.unregister(self.program_id)


@dataclass(slots=True)
class AddEventBindingCommand:
    bindings: SceneEventBindings
    binding: EventBinding

    @property
    def label(self):
        return "Add Event Binding"

    def redo(self):
        if self.binding.binding_id in self.bindings.bindings:
            self.bindings.replace(self.binding)
        else:
            self.bindings.add(self.binding)

    def undo(self):
        self.bindings.remove(self.binding.binding_id)


@dataclass(slots=True)
class ReplaceEventBindingCommand:
    bindings: SceneEventBindings
    new_binding: EventBinding
    old_binding: EventBinding

    @property
    def label(self):
        return "Edit Event Binding"

    def redo(self):
        self.bindings.replace(self.new_binding)

    def undo(self):
        self.bindings.replace(self.old_binding)


def program_with_insert(program, index, instruction):
    items = list(program.instructions)
    index = max(0, min(int(index), len(items)))
    items.insert(index, instruction)
    return EventProgram(items, name=program.name)


def program_with_remove(program, index):
    items = list(program.instructions)
    del items[int(index)]
    return EventProgram(items, name=program.name)


def program_with_move(program, old_index, new_index):
    items = list(program.instructions)
    item = items.pop(int(old_index))
    new_index = max(0, min(int(new_index), len(items)))
    items.insert(new_index, item)
    return EventProgram(items, name=program.name)


def _coerce_world_value(text):
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    for kind in (int, float):
        try:
            return kind(text)
        except ValueError:
            pass
    return text


def parse_world_args(text):
    """Parse "key=value, key2=value2" into WORLD command arguments.

    Numbers and true/false are converted; everything else stays a string.
    """
    args = {}
    for part in str(text or "").split(","):
        part = part.strip()
        if not part:
            continue
        key, sep, value = part.partition("=")
        key = key.strip()
        if not sep or not key:
            raise ValueError(f"expected key=value, got {part!r}")
        args[key] = _coerce_world_value(value.strip())
    return args


def format_world_args(args):
    return ", ".join(f"{k}={v}" for k, v in dict(args or {}).items())


def describe_instruction(instruction):
    op = instruction.opcode
    a = instruction.args
    if op == "DIALOGUE":
        speaker = str(a.get("speaker", "")).strip()
        text = str(a.get("text", ""))
        return f'Dialogue  {speaker + ": " if speaker else ""}"{text}"'
    if op == "CHOICE":
        return f"Choice  {a.get('prompt', '')}"
    if op in {"JUMP_IF", "IF_FALSE_SKIP"}:
        return "If / Branch"
    if op == "SET_SWITCH":
        return f"Set Switch  {a.get('name', '')} = {a.get('value', True)}"
    if op == "SET_VARIABLE":
        return f"Set Variable  {a.get('name', '')} = {a.get('value')}"
    if op == "WORLD":
        details = format_world_args(a.get("args") or {})
        return f"World  {a.get('command', '')}" + (f"  ({details})" if details else "")
    if op == "CALL":
        return f"Call  {a.get('program_id', '')}"
    if op == "WAIT":
        return f"Wait  {a.get('seconds', 0)}s"
    if op == "END":
        return "End"
    return op.replace("_", " ").title()


def replace_binding_fields(binding, **changes):
    return EventBinding(
        changes.get("binding_id", binding.binding_id),
        changes.get("entity_id", binding.entity_id),
        changes.get("program_id", binding.program_id),
        trigger=changes.get("trigger", binding.trigger),
        enabled=changes.get("enabled", binding.enabled),
        conditions=changes.get("conditions", binding.conditions),
        local_scope_id=changes.get("local_scope_id", binding.local_scope_id),
    )
