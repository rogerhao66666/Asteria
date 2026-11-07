"""Common events, battle events and sequences (EVT-03, EVT-04) — the editor and the Authoring API
share this.

All edits are undoable document commands on the canonical Project:
``project.common_events`` (``CommonEvent``), ``project.lifecycle_event_bindings``
(battle events are bindings on ``rpg.battle.*`` hooks) and ``SEQUENCE``
instructions inside ordinary event programs.
"""

from __future__ import annotations

from dataclasses import dataclass

from asteria.editor.events.editing import (
    AddEventProgramCommand,
    RemoveEventProgramCommand,
    ReplaceEventProgramCommand,
)
from asteria.events import EventInstruction, EventProgram, LifecycleEventBinding
from asteria.events.common import COMMON_TRIGGERS, CommonEvent
from asteria.events.conditions import EventCondition
from asteria.events.sequencer import SequenceError, validate_sequence_args

# Battle hooks an author can attach events to (the battle runtime emits these).
BATTLE_HOOKS = (
    "rpg.battle.started",
    "rpg.battle.round_started",
    "rpg.battle.turn_ready",
    "rpg.battle.after_action",
    "rpg.battle.ai.phase_changed",
    "rpg.battle.round_ended",
    "rpg.battle.finished",
)
TRACK_OPCODES = (
    "MOVE",
    "FACE",
    "ANIMATE",
    "DIALOGUE",
    "WORLD",
    "WAIT",
    "SET_SWITCH",
    "SET_VARIABLE",
)


class EventFlowError(ValueError):
    pass


def _names_in(data, source, opcode, found):
    """The names ``data`` sets (``opcode``) or asks about (a condition of ``source``)."""
    if isinstance(data, dict):
        name = None
        if data.get("opcode") == opcode:
            name = (data.get("args") or {}).get("name")
        elif data.get("source") == source:
            name = data.get("name")
        if isinstance(name, str) and name:
            found.add(name)
        data = list(data.values())
    if isinstance(data, (list, tuple)):
        for value in data:
            _names_in(value, source, opcode, found)


@dataclass(slots=True)
class _ProjectListCommand:
    project: object
    attr: str
    new: list
    old: list
    description: str

    @property
    def label(self):
        return self.description

    def redo(self):
        setattr(self.project, self.attr, list(self.new))

    def undo(self):
        setattr(self.project, self.attr, list(self.old))


def battle_condition(name, operator="<=", value=0.5):
    """Condition on battle values: ``round``, ``hp_ratio:<member or enemy id>``, ``alive:<id>``."""
    return EventCondition("battle", str(name), str(operator), value)


def track(name, *instructions):
    """A sequence track from ``EventInstruction``s or ``(opcode, args)`` pairs."""
    items = []
    for item in instructions:
        if not isinstance(item, EventInstruction):
            opcode, args = item
            item = EventInstruction(opcode, dict(args))
        items.append(item.to_data())
    return {"name": str(name), "instructions": items}


class EventFlowAuthoring:
    def __init__(self, document):
        self.document = document

    @property
    def project(self):
        if self.document.project is None:
            raise EventFlowError("project required")
        return self.document.project

    def names_used(self, source):
        """The switches (``source`` "switch") or variables ("variable") the events use."""
        project, found = self.project, set()
        opcode = {"switch": "SET_SWITCH", "variable": "SET_VARIABLE"}[source]
        for program_id in project.event_programs.ids():
            _names_in(project.event_programs.get(program_id).to_data(), source, opcode, found)
        for binding in project.lifecycle_event_bindings:
            _names_in([c.to_data() for c in binding.conditions], source, opcode, found)
        if source == "switch":
            found.update(c.switch for c in project.common_events if c.switch)
        return tuple(sorted(found))

    def _set(self, attr, values, label):
        old = list(getattr(self.project, attr))
        self.document.execute(_ProjectListCommand(self.project, attr, list(values), old, label))
        self.project.validate()

    def _check_program(self, program_id):
        if self.project.event_programs.get(str(program_id)) is None:
            raise EventFlowError(f"unknown event program {program_id}")

    def new_program(self, program_id, name="", instructions=()):
        program_id = str(program_id).strip()
        if not program_id or self.project.event_programs.get(program_id) is not None:
            raise EventFlowError(f"program id {program_id!r} is empty or taken")
        program = EventProgram(tuple(instructions), name=str(name or program_id))
        self.document.execute(
            AddEventProgramCommand(self.project.event_programs, program_id, program)
        )
        return program

    def delete_program(self, program_id):
        """Delete an event program nothing runs any more (one undo step); a program still in
        use (a common event, a menu entry, a map event...) is refused with what uses it."""

        program_id = str(program_id)
        self._check_program(program_id)
        program = self.project.event_programs.get(program_id)
        command = RemoveEventProgramCommand(self.project.event_programs, program_id, program)
        command.redo()
        try:
            self.project.validate()
        except ValueError as exc:
            command.undo()
            raise EventFlowError(f"still in use: {exc}") from exc
        command.undo()
        self.document.execute(command)

    # -- common events --------------------------------------------------------------------------
    def common_events(self):
        return tuple(self.project.common_events)

    def add_common_event(self, program_id, trigger="call", switch=""):
        self._check_program(program_id)
        if any(c.program_id == program_id for c in self.project.common_events):
            raise EventFlowError(f"{program_id} is already a common event")
        try:
            value = CommonEvent(str(program_id), str(trigger), str(switch))
        except ValueError as exc:
            raise EventFlowError(str(exc)) from exc
        self._set(
            "common_events", [*self.project.common_events, value], f"Add Common Event {program_id}"
        )
        return value

    def set_common_event(self, index, *, trigger=None, switch=None):
        values = list(self.project.common_events)
        old = values[int(index)]
        if trigger is not None and trigger not in COMMON_TRIGGERS:
            raise EventFlowError(f"trigger must be one of {COMMON_TRIGGERS}")
        values[int(index)] = CommonEvent(
            old.program_id,
            old.trigger if trigger is None else trigger,
            old.switch if switch is None else switch,
        )
        self._set("common_events", values, f"Edit Common Event {old.program_id}")
        return values[int(index)]

    def remove_common_event(self, index):
        values = list(self.project.common_events)
        removed = values.pop(int(index))
        self._set("common_events", values, f"Remove Common Event {removed.program_id}")
        return removed

    # -- battle events ----------------------------------------------------------------------------
    def battle_events(self):
        """``[(index in lifecycle_event_bindings, binding)]`` for ``rpg.battle.*`` hooks."""
        return [
            (i, b)
            for i, b in enumerate(self.project.lifecycle_event_bindings)
            if b.hook_name.startswith("rpg.battle.")
        ]

    def add_battle_event(self, hook, program_id, *, conditions=(), once=False):
        if not str(hook).startswith("rpg.battle."):
            raise EventFlowError("battle events attach to rpg.battle.* hooks")
        self._check_program(program_id)
        binding = LifecycleEventBinding(hook, program_id, conditions=conditions, once=once)
        values = [*self.project.lifecycle_event_bindings, binding]
        self._set("lifecycle_event_bindings", values, f"Add Battle Event {program_id}")
        return binding

    def set_battle_event(self, index, *, hook=None, program_id=None, conditions=None, once=None):
        values = list(self.project.lifecycle_event_bindings)
        old = values[int(index)]
        if program_id is not None:
            self._check_program(program_id)
        values[int(index)] = LifecycleEventBinding(
            old.hook_name if hook is None else hook,
            old.event_program_id if program_id is None else program_id,
            source_entity_id=old.source_entity_id,
            conditions=old.conditions if conditions is None else conditions,
            once=old.once if once is None else once,
        )
        self._set(
            "lifecycle_event_bindings",
            values,
            f"Edit Battle Event {values[int(index)].event_program_id}",
        )
        return values[int(index)]

    def remove_battle_event(self, index):
        values = list(self.project.lifecycle_event_bindings)
        removed = values.pop(int(index))
        self._set(
            "lifecycle_event_bindings", values, f"Remove Battle Event {removed.event_program_id}"
        )
        return removed

    # -- sequences --------------------------------------------------------------------------------
    @staticmethod
    def sequence_args(tracks, *, cutscene=False, skippable=False, wait="all"):
        args = {
            "tracks": list(tracks),
            "cutscene": bool(cutscene),
            "skippable": bool(skippable),
            "wait": wait,
        }
        try:
            validate_sequence_args(args)
        except (SequenceError, ValueError, KeyError) as exc:
            raise EventFlowError(str(exc)) from exc
        return args

    def _replace_program(self, program_id, instructions, label):
        old = self.project.event_programs.require(program_id)
        new = EventProgram(tuple(instructions), name=old.name)
        self.document.execute(
            ReplaceEventProgramCommand(self.project.event_programs, program_id, new, old)
        )
        return new

    def insert_sequence(self, program_id, index, tracks, **options):
        program = self.project.event_programs.require(str(program_id))
        items = list(program.instructions)
        items.insert(
            int(index), EventInstruction("SEQUENCE", self.sequence_args(tracks, **options))
        )
        return self._replace_program(str(program_id), items, f"Add Sequence to {program_id}")

    def replace_sequence(self, program_id, index, tracks, **options):
        program = self.project.event_programs.require(str(program_id))
        items = list(program.instructions)
        if items[int(index)].opcode != "SEQUENCE":
            raise EventFlowError(f"instruction {index} of {program_id} is not a SEQUENCE")
        items[int(index)] = EventInstruction("SEQUENCE", self.sequence_args(tracks, **options))
        return self._replace_program(str(program_id), items, f"Edit Sequence in {program_id}")
