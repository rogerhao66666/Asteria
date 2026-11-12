from __future__ import annotations

from dataclasses import dataclass

from asteria.editor.ui.i18n import translate
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
class RemoveEventProgramCommand:
    registry: object
    program_id: str
    program: EventProgram

    @property
    def label(self):
        return "Delete Event Program"

    def redo(self):
        self.registry.unregister(self.program_id)

    def undo(self):
        self.registry.register(self.program_id, self.program)


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


def describe_instruction(instruction, names=None):
    """A command in the author's words; ``names(key, value)`` gives a record's name (see
    ``world_command_form.record_names``)."""
    from asteria.editor.records.vocabulary import words

    op = instruction.opcode
    a = instruction.args
    if op == "DIALOGUE":
        speaker = str(a.get("speaker", "")).strip()
        text = str(a.get("text", ""))
        portrait = str(a.get("portrait_asset_id", "")).strip()
        if portrait:  # the picture's name, and its side when it is not the usual left
            name = portrait.rsplit("/", 1)[-1]
            side = ", right" if str(a.get("portrait_side", "")).lower() == "right" else ""
            portrait = f"  [portrait: {name}{side}]"
        said = f'{speaker + ": " if speaker else ""}"{text}"{portrait}'
        return f"{translate('Dialogue')}  {said}"
    if op == "CHOICE":
        return f"{translate('Choice')}  {a.get('prompt', '')}"
    if op in {"JUMP_IF", "IF_FALSE_SKIP"}:
        return translate("If / Branch")
    if op == "SET_SWITCH":
        state = translate("Turned on" if a.get("value", True) else "Turned off")
        return f"{translate('Set Switch')}  {words(a.get('name', ''))} = {state}"
    if op == "SET_VARIABLE":
        head = f"{translate('Set Variable')}  {words(a.get('name', ''))} = "
        if a.get("from_variable"):
            return head + words(a.get("from_variable"))
        if a.get("random") is not None:
            return head + f"{translate('A random number')} (0-{int(a['random']) - 1})"
        return head + str(a.get("value"))
    if op == "WORLD":
        from asteria.editor.events.world_command_form import (
            KEPT_KEYS,
            argument_label,
            command_words,
            value_words,
        )

        details = ", ".join(
            f"{translate(argument_label(k))}: {value_words(v, k, names)}"
            for k, v in (a.get("args") or {}).items()
            if k not in KEPT_KEYS  # a popup's translation key: not the author's words
        )
        said = translate(command_words(a.get("command", "")))
        return f"{translate('World')}  {said}" + (f"  ({details})" if details else "")
    if op == "CALL":
        program = a.get("program_id", "")
        return f"{translate('Call')}  {words(program)}"
    if op == "WAIT":
        until = a.get("until")
        if isinstance(until, dict):
            condition = f"{words(until.get('name', ''))} {until.get('operator', '==')} "
            return f"{translate('Wait Until')}  {condition}" + str(until.get("value"))
        return f"{translate('Wait')}  {a.get('seconds', 0)}s"
    if op == "END":
        return translate("End")
    if op == "SEQUENCE":
        flags = [translate(words(f)) for f in ("cutscene", "skippable") if a.get(f)]
        names_said = ", ".join(str(x.get("name", "")) for x in a.get("tracks", []))
        tracks = translate(f"{len(a.get('tracks', []))} parallel tracks")
        return f"{translate('Sequence')}  {tracks} ({names_said})" + (
            f"  [{', '.join(flags)}]" if flags else ""
        )
    if op == "MOVE":
        where = f"{a.get('entity', '')} → ({a.get('x', 0)}, {a.get('y', 0)})"
        return f"{translate('Move')}  {where}" + (
            f" {translate('relative')}" if a.get("relative") else ""
        )
    if op == "FACE":
        facing = translate(words(a.get("facing", "")))
        return f"{translate('Turn To')}  {a.get('entity', '')} {facing}"
    if op == "ANIMATE":
        return f"{translate('Animate')}  {a.get('entity', '')} {a.get('clip', '')}"
    return translate(op.replace("_", " ").title())


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
