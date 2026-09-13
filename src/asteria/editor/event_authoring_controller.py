from .commands import CommandTransaction
from .event_editing import (
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

try:
    from PySide6.QtWidgets import QInputDialog
except ImportError:
    QInputDialog = None

from asteria.core.ids import new_id
from asteria.events import (
    EventBinding,
    EventCondition,
    EventInstruction,
    EventProgram,
    EventTriggerCondition,
    EventTriggerKind,
)


class EventAuthoringController:
    """Owns event binding / program editing behind the Qt shell.

    `window` is the AsteriaEditorWindow: it is the Qt parent for modal
    dialogs and the owner of the refresh orchestration triggered after edits.
    """

    def __init__(self, window, document, event_editor):
        self.window = window
        self.document = document
        self.event_editor = event_editor

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

    def _sync_event_context(self):
        project = self.document.project
        entity = self._selected_event_entity()
        scene = self._selected_event_scene()
        if project is None or entity is None or scene is None:
            self.event_editor.show_empty("Select an Entity to edit events")
            return
        bindings = bindings_for_scene(project, scene)
        self.event_editor.set_entity_context(entity, bindings, project.event_programs)

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
        name, ok = QInputDialog.getText(
            self.window, "New Event", "Event name:", text="Interaction"
        )
        if not ok:
            return
        program_id = new_id()
        binding_id = new_id()
        program = EventProgram([], name=name.strip() or "Interaction")
        binding = EventBinding(
            binding_id, entity.id, program_id, trigger=EventTriggerKind.ACTION
        )
        bindings = bindings_for_scene(project, scene)

        tx = CommandTransaction("Add Event")
        tx.add(AddEventProgramCommand(project.event_programs, program_id, program))
        tx.add(AddEventBindingCommand(bindings, binding))
        self.document.execute(tx)
        self.window.refresh_all()

    def _event_binding_changed(self, field, value):
        if field == "select":
            bindings, binding = self._current_event_binding()
            if binding is not None:
                self.event_editor._refreshing = True
                try:
                    self.event_editor._show_binding(
                        binding, self.document.project.event_programs
                    )
                finally:
                    self.event_editor._refreshing = False
            return
        bindings, binding = self._current_event_binding()
        if binding is None:
            return
        if field == "trigger":
            replacement = replace_binding_fields(
                binding, trigger=EventTriggerKind(value)
            )
        elif field == "program_id":
            replacement = replace_binding_fields(binding, program_id=value)
        else:
            return
        self.document.execute(
            ReplaceEventBindingCommand(bindings, replacement, binding)
        )
        self.window.refresh_all()

    def _event_add_condition(self):
        bindings, binding = self._current_event_binding()
        if binding is None:
            return
        name, ok = QInputDialog.getText(
            self.window, "Event Condition", "Switch name:", text="quest_started"
        )
        if not ok or not name.strip():
            return
        cond = EventTriggerCondition(EventCondition("switch", name.strip(), "==", True))
        replacement = replace_binding_fields(
            binding, conditions=tuple(binding.conditions) + (cond,)
        )
        self.document.execute(
            ReplaceEventBindingCommand(bindings, replacement, binding)
        )
        self.window.refresh_all()

    def _event_make_instruction(self, kind):
        if kind == "dialogue":
            text, ok = QInputDialog.getText(self.window, "Dialogue", "Text:")
            if not ok:
                return None
            speaker, ok = QInputDialog.getText(self.window, "Dialogue", "Speaker:")
            if not ok:
                return None
            return EventInstruction("DIALOGUE", {"speaker": speaker, "text": text})
        if kind == "choice":
            prompt, ok = QInputDialog.getText(self.window, "Choice", "Prompt:")
            if not ok:
                return None
            return EventInstruction(
                "CHOICE",
                {
                    "prompt": prompt,
                    "choices": [
                        {"text": "Option 1", "value": 1},
                        {"text": "Option 2", "value": 2},
                    ],
                    "variable_name": "choice",
                },
            )
        if kind == "if":
            name, ok = QInputDialog.getText(self.window, "If", "Switch name:")
            if not ok or not name.strip():
                return None
            condition = EventCondition("switch", name.strip(), "==", True).to_data()
            return EventInstruction(
                "JUMP_IF", {"condition": condition, "label": "target"}
            )
        if kind == "switch":
            name, ok = QInputDialog.getText(self.window, "Set Switch", "Switch name:")
            if not ok or not name.strip():
                return None
            return EventInstruction("SET_SWITCH", {"name": name.strip(), "value": True})
        if kind == "variable":
            name, ok = QInputDialog.getText(self.window, "Set Variable", "Variable name:")
            if not ok or not name.strip():
                return None
            value, ok = QInputDialog.getText(self.window, "Set Variable", "Value:")
            if not ok:
                return None
            return EventInstruction(
                "SET_VARIABLE", {"name": name.strip(), "value": value}
            )
        if kind == "world":
            command, ok = QInputDialog.getText(
                self.window, "World Command", "Command:", text="TRANSFER"
            )
            if not ok or not command.strip():
                return None
            return EventInstruction(
                "WORLD", {"command": command.strip().upper(), "args": {}}
            )
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
        new_program = program_with_insert(program, index, instruction)
        self.document.execute(
            ReplaceEventProgramCommand(
                project.event_programs, binding.program_id, new_program, program
            )
        )
        self.window.refresh_all()

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
        self.window.refresh_all()

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
        self.window.refresh_all()
