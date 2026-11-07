"""The Events panel: the entity picked, its bindings and conditions, and every command dialog."""

from __future__ import annotations

from collections import Counter

from asteria.editor.events.editing import (
    AddEventBindingCommand,
    AddEventProgramCommand,
    ReplaceEventBindingCommand,
    ReplaceEventProgramCommand,
    bindings_for_scene,
    program_with_insert,
    program_with_move,
    program_with_remove,
    replace_binding_fields,
)
from asteria.editor.events.world_command_form import record_names
from asteria.editor.project.commands import CommandTransaction

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QInputDialog, QMainWindow
except ImportError:
    QApplication = None
    QMainWindow = object
    Qt = None
from asteria.core.ids import new_id
from asteria.editor.window.support import (
    _sequence_kwargs,
)
from asteria.events import (
    EventBinding,
    EventCondition,
    EventInstruction,
    EventProgram,
    EventTriggerCondition,
    EventTriggerKind,
)


class EventEditingMixin:
    """The Events panel and its command dialogs."""

    def _selected_event_entity(self):
        sel = self.document.selection
        if sel.kind == "entity" and sel.value is not None and not sel.multiple:
            return sel.value
        if sel.kind == "component" and sel.value is not None and not sel.multiple:
            try:
                return sel.value.entity
            except RuntimeError:
                return None
        return None

    def _selected_event_scene(self):
        entity = self._selected_event_entity()
        return entity.scene if entity is not None else None

    def _event_candidates(self, project):
        """``(entity, event count)`` for every entity of the scene shown."""
        scene = self.viewport.current_scene() if project is not None else None
        if scene is None:
            return ()
        bindings = bindings_for_scene(project, scene)
        # one pass over the bindings (asking each entity for its own scanned them all per entity)
        counts = Counter(str(b.entity_id) for b in bindings.bindings.values())
        return tuple((entity, counts[str(entity.id)]) for entity in scene.entities())

    def _event_entity_picked(self, entity):
        self.document.select_entity(entity)
        self.refresh_selection_context()
        self.project_tree.refresh()

    def _sync_event_context(self):
        project = self.document.project
        entity = self._selected_event_entity()
        scene = self._selected_event_scene()
        if project is None or entity is None or scene is None:
            self.event_editor.show_empty(
                "Select an Entity to edit events", self._event_candidates(project)
            )
            return
        bindings = bindings_for_scene(project, scene)
        self.event_editor.names = record_names(self.document)
        self.event_editor.set_entity_context(
            entity, bindings, project.event_programs, self._event_candidates(project)
        )

    def _current_event_binding(self):
        project = self.document.project
        scene = self._selected_event_scene()
        if project is None or scene is None:
            return None, None
        bindings = bindings_for_scene(project, scene)
        binding_id = self.event_editor.selected_binding_id()
        return bindings, bindings.bindings.get(binding_id) if binding_id else None

    def _event_add_binding(self):
        project = self.document.project
        entity = self._selected_event_entity()
        scene = self._selected_event_scene()
        if project is None or entity is None or scene is None:
            return
        name, ok = QInputDialog.getText(self, "New Event", "Event name:", text="Interaction")
        if not ok:
            return
        program_id = new_id()
        binding_id = new_id()
        program = EventProgram([], name=name.strip() or "Interaction")
        binding = EventBinding(binding_id, entity.id, program_id, trigger=EventTriggerKind.ACTION)
        bindings = bindings_for_scene(project, scene)

        tx = CommandTransaction("Add Event")
        tx.add(AddEventProgramCommand(project.event_programs, program_id, program))
        tx.add(AddEventBindingCommand(bindings, binding))
        self.document.execute(tx)
        self.refresh_all()

    def _event_binding_changed(self, field, value):
        if field == "select":
            bindings, binding = self._current_event_binding()
            if binding is not None:
                self.event_editor._refreshing = True
                try:
                    self.event_editor._show_binding(binding, self.document.project.event_programs)
                finally:
                    self.event_editor._refreshing = False
            return
        bindings, binding = self._current_event_binding()
        if binding is None:
            return
        if field == "trigger":
            replacement = replace_binding_fields(binding, trigger=EventTriggerKind(value))
        elif field == "program_id":
            replacement = replace_binding_fields(binding, program_id=value)
        else:
            return
        self.document.execute(ReplaceEventBindingCommand(bindings, replacement, binding))
        self.refresh_all()

    def _event_add_condition(self):
        bindings, binding = self._current_event_binding()
        if binding is None:
            return
        picked = self._switch_dialog("Event Condition")
        if picked is None:
            return
        cond = EventTriggerCondition(EventCondition("switch", picked[0], "==", picked[1]))
        replacement = replace_binding_fields(
            binding, conditions=tuple(binding.conditions) + (cond,)
        )
        self.document.execute(ReplaceEventBindingCommand(bindings, replacement, binding))
        self.refresh_all()

    def _sequence_dialog(self, args=None):
        """Modal sequence editor; returns SEQUENCE args or None (tests replace this)."""
        from asteria.editor.events.flow_widget import SequenceEditorDialog

        dialog = SequenceEditorDialog(args, self, document=self.document)
        return dialog.result_args() if dialog.exec() == SequenceEditorDialog.Accepted else None

    def _dialogue_dialog(self, args=None):
        """Modal Dialogue editor (speaker, text, portrait); returns DIALOGUE args or None
        (tests replace this)."""
        from asteria.editor.events.dialogue_dialog import DialogueCommandDialog

        dialog = DialogueCommandDialog(args, document=self.document, parent=self)
        return dialog.result_args() if dialog.exec() == DialogueCommandDialog.Accepted else None

    def _choice_dialog(self, args=None):
        """Modal Choice editor (prompt, options, variable, start, cancel, box); returns CHOICE
        args or None (tests replace this)."""
        from asteria.editor.events.choice_dialog import ChoiceCommandDialog

        dialog = ChoiceCommandDialog(args, parent=self, document=self.document)
        return dialog.result_args() if dialog.exec() == ChoiceCommandDialog.Accepted else None

    def _wait_dialog(self, args=None):
        """Modal Wait editor (seconds, or until a condition); returns WAIT args or None (tests
        replace this)."""
        from asteria.editor.events.wait_dialog import WaitCommandDialog

        dialog = WaitCommandDialog(args, parent=self)
        return dialog.result_args() if dialog.exec() == WaitCommandDialog.Accepted else None

    def _switch_dialog(self, title, name="", value=True):
        """A switch picked or made, and on or off; ``(name, value)`` or None (tests replace
        this)."""
        from asteria.editor.events.name_dialog import SwitchDialog

        dialog = SwitchDialog(self.document, title, self, name=name, value=value)
        return (dialog.name(), dialog.value()) if dialog.exec() else None

    def _variable_dialog(self, args=None):
        """A variable picked or made and what it becomes; SET_VARIABLE args or None (tests
        replace this)."""
        from asteria.editor.events.name_dialog import VariableDialog

        dialog = VariableDialog(self.document, self, args=args)
        return dialog.result_args() if dialog.exec() else None

    def _world_dialog(self, command="TRANSFER", args=None):
        """A world command picked and filled in; WORLD args or None (tests replace this)."""
        from asteria.editor.events.picture_dialog import PICTURE_COMMANDS, PictureCommandDialog
        from asteria.editor.events.world_command_form import WorldCommandDialog

        dialog = WorldCommandDialog(
            self.document, self, command=command, args=args, pictures_later=True
        )
        if not dialog.exec():
            return None
        command = dialog.command_name()
        if command not in PICTURE_COMMANDS:
            return {"command": command, "args": dialog.result_args()}
        picture = PictureCommandDialog(command, args or {}, document=self.document, parent=self)
        if not picture.exec():
            return None
        return {"command": picture.command.currentText(), "args": picture.result_args()}

    def _replace_event_command(self, binding, program, index, instruction):
        rows = list(program.instructions)
        rows[index] = instruction
        self.document.execute(
            ReplaceEventProgramCommand(
                self.document.project.event_programs,
                binding.program_id,
                EventProgram(rows, name=program.name),
                program,
            )
        )

    def _edited_event_command(self, instruction):
        """The new form of a switch, variable or world command, or None when it isn't one of
        those (or the dialog was cancelled)."""
        args = instruction.args
        if instruction.opcode == "SET_SWITCH":
            picked = self._switch_dialog("Set Switch", args.get("name", ""), args.get("value"))
            return picked and EventInstruction(
                "SET_SWITCH", dict(args, name=picked[0], value=picked[1])
            )
        if instruction.opcode == "SET_VARIABLE":
            changed = self._variable_dialog(args)
            return changed and EventInstruction("SET_VARIABLE", changed)
        if instruction.opcode == "WORLD":
            changed = self._world_dialog(args.get("command", ""), args.get("args"))
            return changed and EventInstruction("WORLD", dict(args, **changed))
        condition = args.get("condition") if instruction.opcode == "JUMP_IF" else None
        if condition and condition.get("source") == "switch" and condition.get("operator") == "==":
            picked = self._switch_dialog("If", condition.get("name", ""), condition.get("value"))
            return picked and EventInstruction(
                "JUMP_IF", dict(args, condition=dict(condition, name=picked[0], value=picked[1]))
            )
        return None

    def _event_edit_command(self, index):
        """Open the specialized editor for dialogue, choice, wait, sequence, switch, variable,
        picture and world instructions."""
        from asteria.editor.events.flow_authoring import EventFlowAuthoring
        from asteria.editor.events.picture_dialog import PICTURE_COMMANDS, PictureCommandDialog

        project = self.document.project
        _, binding = self._current_event_binding()
        if project is None or binding is None:
            return False
        program = project.event_programs.require(binding.program_id)
        if not 0 <= index < len(program.instructions):
            return False
        instruction = program.instructions[index]
        if instruction.opcode == "SEQUENCE":
            args = self._sequence_dialog(instruction.args)
            if args is None:
                return False
            EventFlowAuthoring(self.document).replace_sequence(
                binding.program_id, index, **_sequence_kwargs(args)
            )
        elif instruction.opcode in ("DIALOGUE", "CHOICE", "WAIT"):
            edit = {
                "DIALOGUE": self._dialogue_dialog,
                "CHOICE": self._choice_dialog,
                "WAIT": self._wait_dialog,
            }[instruction.opcode]
            args = edit(instruction.args)
            if args is None:
                return False
            rows = list(program.instructions)
            rows[index] = EventInstruction(instruction.opcode, args)
            self.document.execute(
                ReplaceEventProgramCommand(
                    project.event_programs,
                    binding.program_id,
                    EventProgram(rows, name=program.name),
                    program,
                )
            )
        elif (
            instruction.opcode == "WORLD"
            and str(instruction.args.get("command", "")).upper() in PICTURE_COMMANDS
        ):
            dialog = PictureCommandDialog(
                instruction.args["command"],
                instruction.args.get("args", {}),
                document=self.document,
                parent=self,
            )
            if not dialog.exec():
                return False
            changed = EventInstruction(
                "WORLD",
                {
                    "command": dialog.command.currentText(),
                    "args": dialog.result_args(),
                },
            )
            self._replace_event_command(binding, program, index, changed)
        elif instruction.opcode in ("SET_SWITCH", "SET_VARIABLE", "WORLD"):
            changed = self._edited_event_command(instruction)
            if changed is None:
                return False
            self._replace_event_command(binding, program, index, changed)
        else:
            return False
        self.refresh_all()
        return True

    def _event_make_instruction(self, kind):
        if kind == "sequence":
            args = self._sequence_dialog()
            return None if args is None else EventInstruction("SEQUENCE", args)
        if kind == "dialogue":
            args = self._dialogue_dialog()
            return None if args is None else EventInstruction("DIALOGUE", args)
        if kind == "choice":
            args = self._choice_dialog()
            return None if args is None else EventInstruction("CHOICE", args)
        if kind == "wait":
            args = self._wait_dialog()
            return None if args is None else EventInstruction("WAIT", args)
        if kind == "if":
            picked = self._switch_dialog("If")
            if picked is None:
                return None
            condition = EventCondition("switch", picked[0], "==", picked[1]).to_data()
            return EventInstruction("JUMP_IF", {"condition": condition, "label": "target"})
        if kind == "switch":
            picked = self._switch_dialog("Set Switch")
            if picked is None:
                return None
            return EventInstruction("SET_SWITCH", {"name": picked[0], "value": picked[1]})
        if kind == "variable":
            args = self._variable_dialog()
            return None if args is None else EventInstruction("SET_VARIABLE", args)
        if kind == "world":
            args = self._world_dialog()
            return None if args is None else EventInstruction("WORLD", args)
        return None

    def _event_add_command(self, kind):
        project = self.document.project
        _, binding = self._current_event_binding()
        if project is None or binding is None:
            return
        program = project.event_programs.get(binding.program_id)
        if program is None:
            return
        instruction = self._event_make_instruction(kind)
        if instruction is None:
            return
        row = self.event_editor.selected_command_index()
        index = len(program.instructions) if row < 0 else row + 1
        rows = program.instructions
        if index == len(rows) and rows and rows[-1].opcode == "END":
            index -= 1  # after the End it would never run
        new_program = program_with_insert(program, index, instruction)
        self.document.execute(
            ReplaceEventProgramCommand(
                project.event_programs, binding.program_id, new_program, program
            )
        )
        self.refresh_all()

    def _event_remove_command(self, index):
        project = self.document.project
        _, binding = self._current_event_binding()
        if project is None or binding is None:
            return
        program = project.event_programs.require(binding.program_id)
        if not 0 <= index < len(program.instructions):
            return
        new_program = program_with_remove(program, index)
        self.document.execute(
            ReplaceEventProgramCommand(
                project.event_programs, binding.program_id, new_program, program
            )
        )
        self.refresh_all()

    def _event_move_command(self, old_index, new_index):
        project = self.document.project
        _, binding = self._current_event_binding()
        if project is None or binding is None:
            return
        program = project.event_programs.require(binding.program_id)
        new_program = program_with_move(program, old_index, new_index)
        self.document.execute(
            ReplaceEventProgramCommand(
                project.event_programs, binding.program_id, new_program, program
            )
        )
        self.refresh_all()
