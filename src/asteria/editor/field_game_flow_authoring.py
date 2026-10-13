from __future__ import annotations

from dataclasses import dataclass

from asteria.events import EventBinding, EventProgram, EventTriggerKind
from asteria.runtime.components2d import Interaction2DComponent

from .editing import build_set_component_field_command
from .event_editing import (
    AddEventBindingCommand,
    AddEventProgramCommand,
    ReplaceEventBindingCommand,
    ReplaceEventProgramCommand,
    bindings_for_scene,
)


class FieldGameFlowAuthoringError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FieldGameFlowSection:
    section_id: str
    label: str
    detail_groups: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FieldGameFlowInformationArchitecture:
    sections: tuple[FieldGameFlowSection, ...] = (
        FieldGameFlowSection(
            "scene", "Scene Flow", ("Scene", "Startup / Entry", "Lifecycle", "Transitions")
        ),
        FieldGameFlowSection(
            "interaction",
            "Interactions",
            ("Entity", "Interaction Range", "Facing", "Binding", "Conditions"),
        ),
        FieldGameFlowSection(
            "events",
            "Event Programs",
            ("Program", "Commands", "Selected Command", "Branches / Conditions"),
        ),
        FieldGameFlowSection(
            "encounter",
            "Encounter Flow",
            ("Trigger", "Encounter Command", "Battle Transition", "Return Flow"),
        ),
    )
    primary_navigation: str = "game_flow_section_sidebar"
    inspector_pattern: str = "viewport_plus_contextual_detail"
    progressive_disclosure: bool = True
    show_all_flow_details_simultaneously: bool = False

    def section(self, key):
        return next((x for x in self.sections if x.section_id == str(key)), None)


class FieldGameFlowAuthoringController:
    information_architecture = FieldGameFlowInformationArchitecture()

    def __init__(self, document):
        self.document = document

    @property
    def project(self):
        if self.document.project is None:
            raise FieldGameFlowAuthoringError("project required")
        return self.document.project

    def scene(self, scene_id):
        s = self.project.scene(str(scene_id))
        if s is None:
            raise FieldGameFlowAuthoringError(f"unknown scene: {scene_id}")
        return s

    def entity(self, scene_id, entity_id):
        s = self.scene(scene_id)
        e = s.get_entity(str(entity_id))
        if e is None:
            raise FieldGameFlowAuthoringError(f"unknown entity: {entity_id}")
        return e

    def create_program(self, program_id, program):
        if not isinstance(program, EventProgram):
            raise TypeError("program must be EventProgram")
        if self.project.event_programs.get(program_id) is not None:
            raise FieldGameFlowAuthoringError(f"duplicate event program: {program_id}")
        self.document.execute(
            AddEventProgramCommand(self.project.event_programs, str(program_id), program)
        )
        return program

    def edit_program(self, program_id, program):
        old = self.project.event_programs.get(str(program_id))
        if old is None:
            raise FieldGameFlowAuthoringError(f"unknown event program: {program_id}")
        self.document.execute(
            ReplaceEventProgramCommand(self.project.event_programs, str(program_id), program, old)
        )
        return program

    def create_binding(self, scene_id, binding):
        if not isinstance(binding, EventBinding):
            raise TypeError("binding must be EventBinding")
        scene = self.scene(scene_id)
        if scene.get_entity(binding.entity_id) is None:
            raise FieldGameFlowAuthoringError(f"binding entity not in scene: {binding.entity_id}")
        if self.project.event_programs.get(binding.program_id) is None:
            raise FieldGameFlowAuthoringError(f"unknown event program: {binding.program_id}")
        bindings = bindings_for_scene(self.project, scene)
        if binding.binding_id in bindings.bindings:
            raise FieldGameFlowAuthoringError(f"duplicate event binding: {binding.binding_id}")
        self.document.execute(AddEventBindingCommand(bindings, binding))
        return binding

    def edit_binding(self, scene_id, binding):
        scene = self.scene(scene_id)
        bindings = bindings_for_scene(self.project, scene)
        old = bindings.bindings.get(binding.binding_id)
        if old is None:
            raise FieldGameFlowAuthoringError(f"unknown event binding: {binding.binding_id}")
        if scene.get_entity(binding.entity_id) is None:
            raise FieldGameFlowAuthoringError(f"binding entity not in scene: {binding.entity_id}")
        if self.project.event_programs.get(binding.program_id) is None:
            raise FieldGameFlowAuthoringError(f"unknown event program: {binding.program_id}")
        self.document.execute(ReplaceEventBindingCommand(bindings, binding, old))
        return binding

    def configure_interaction(
        self,
        scene_id,
        entity_id,
        *,
        binding_id,
        range=24.0,
        require_facing=True,
        local_scope_id="",
    ):
        scene = self.scene(scene_id)
        entity = self.entity(scene_id, entity_id)
        bindings = bindings_for_scene(self.project, scene)
        binding = bindings.bindings.get(str(binding_id))
        if binding is None:
            raise FieldGameFlowAuthoringError(f"unknown event binding: {binding_id}")
        if binding.entity_id != entity.id:
            raise FieldGameFlowAuthoringError("binding belongs to another entity")
        if binding.trigger != EventTriggerKind.ACTION:
            raise FieldGameFlowAuthoringError("Interaction2D requires an action binding")
        component = entity.try_get(Interaction2DComponent)
        if component is None:
            component = Interaction2DComponent()
            entity.add_component(component)
        values = {
            "event_binding_id": binding.binding_id,
            "event_program_id": binding.program_id,
            "range": range,
            "require_facing": require_facing,
            "local_scope_id": local_scope_id or binding.local_scope_id or entity.id,
        }
        for field, value in values.items():
            self.document.execute(build_set_component_field_command(component, field, value))
        return component

    def action_flow(self, scene_id, entity_id):
        scene = self.scene(scene_id)
        entity = self.entity(scene_id, entity_id)
        component = entity.try_get(Interaction2DComponent)
        if component is None:
            return None
        binding = bindings_for_scene(self.project, scene).bindings.get(component.event_binding_id)
        program = self.project.event_programs.get(component.event_program_id)
        return {
            "scene": scene,
            "entity": entity,
            "interaction": component,
            "binding": binding,
            "program": program,
        }

    def validate(self):
        issues = []
        try:
            self.project.validate()
        except Exception as exc:
            issues.append(str(exc))
        for scene in self.project.scenes():
            bindings = bindings_for_scene(self.project, scene)
            for binding in bindings.bindings.values():
                if scene.get_entity(binding.entity_id) is None:
                    issues.append(f"{scene.name}: binding {binding.binding_id} entity missing")
                if self.project.event_programs.get(binding.program_id) is None:
                    issues.append(f"{scene.name}: binding {binding.binding_id} program missing")
            for entity in scene.entities():
                comp = entity.try_get(Interaction2DComponent)
                if comp is None or not comp.enabled:
                    continue
                if comp.event_binding_id and comp.event_binding_id not in bindings.bindings:
                    issues.append(f"{scene.name}/{entity.name}: interaction binding missing")
                if (
                    comp.event_program_id
                    and self.project.event_programs.get(comp.event_program_id) is None
                ):
                    issues.append(f"{scene.name}/{entity.name}: interaction program missing")
        return tuple(issues)
