from __future__ import annotations

from dataclasses import dataclass

from .field_game_flow_authoring import FieldGameFlowInformationArchitecture


@dataclass(frozen=True, slots=True)
class FieldGameFlowWorkspaceSnapshot:
    section_id: str
    scene_id: str | None
    entity_id: str | None
    binding_id: str | None
    program_id: str | None
    focused_command_index: int | None
    detail_groups: tuple[str, ...]


class FieldGameFlowWorkspaceModel:
    def __init__(self, controller):
        self.controller = controller
        self.architecture = FieldGameFlowInformationArchitecture()
        self.section_id = "scene"
        self.scene_id = None
        self.entity_id = None
        self.binding_id = None
        self.program_id = None
        self.focused_command_index = None

    def set_section(self, key):
        if self.architecture.section(key) is None:
            raise KeyError(key)
        self.section_id = str(key)
        self.focused_command_index = None

    def select_scene(self, key):
        self.controller.scene(key)
        self.scene_id = str(key)
        self.entity_id = self.binding_id = self.program_id = None
        self.focused_command_index = None

    def select_entity(self, key):
        if self.scene_id is None:
            raise RuntimeError("select a scene first")
        e = self.controller.entity(self.scene_id, key)
        self.entity_id = e.id
        flow = self.controller.action_flow(self.scene_id, e.id)
        self.binding_id = flow["binding"].binding_id if flow and flow["binding"] else None
        self.program_id = flow["program"].name if False else (flow["interaction"].event_program_id if flow else None)
        self.focused_command_index = None

    def focus_command(self, index):
        if self.program_id is None:
            raise RuntimeError("select an event program first")
        program = self.controller.project.event_programs.require(self.program_id)
        index = int(index)
        if not 0 <= index < len(program.instructions):
            raise IndexError(index)
        self.focused_command_index = index

    def snapshot(self):
        s = self.architecture.section(self.section_id)
        return FieldGameFlowWorkspaceSnapshot(
            self.section_id,
            self.scene_id,
            self.entity_id,
            self.binding_id,
            self.program_id,
            self.focused_command_index,
            s.detail_groups,
        )
