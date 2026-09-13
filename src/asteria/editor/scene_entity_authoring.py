from __future__ import annotations

from dataclasses import dataclass

from .clipboard import build_duplicate_entity_command
from .commands import CommandTransaction, SetAttributeCommand
from .hierarchy import (
    build_move_entity_to_scene_command,
    build_reorder_entity_command,
)
from .scenes import (
    build_add_scene_command,
    build_remove_scene_command,
    build_reorder_scene_command,
)
from .structure import (
    build_add_component_command,
    build_add_entity_command,
    build_remove_component_command,
    build_remove_entity_command,
    build_rename_command,
)


class SceneEntityAuthoringError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SceneEntityCoverage:
    scene_create: bool = True
    scene_rename: bool = True
    scene_delete: bool = True
    scene_reorder: bool = True
    startup_scene: bool = True
    entity_create: bool = True
    entity_rename: bool = True
    entity_delete: bool = True
    entity_duplicate: bool = True
    entity_reorder: bool = True
    entity_move_between_scenes: bool = True
    entity_enabled: bool = True
    component_add: bool = True
    component_remove: bool = True
    component_field_edit: bool = True
    multi_entity_delete: bool = True
    multi_entity_duplicate: bool = True


class SceneEntityAuthoringController:
    """Complete authoring surface over canonical Scene/Entity/Component structures.

    The controller owns no duplicate data. Every operation executes an undoable
    command against the EditorDocument's canonical Project.
    """

    coverage=SceneEntityCoverage()

    def __init__(self, document):
        self.document=document

    def _execute(self, command):
        self.document.execute(command)
        return command

    def set_startup_scene(self, scene):
        project=self.document.project
        if project is None or scene is None or project.scene(scene.id) is not scene:
            raise SceneEntityAuthoringError("scene must belong to current project")
        if project.startup_scene_id == scene.id:
            return None
        return self._execute(SetAttributeCommand(
            project,"startup_scene_id",scene.id,project.startup_scene_id,
            f"Set Startup Scene {scene.name}",
        ))

    def add_scene(self,name="Scene"):
        project=self.document.project
        if project is None:
            raise SceneEntityAuthoringError("project required")
        return self._execute(build_add_scene_command(project,name)).scene

    def rename(self,target,name):
        return self._execute(build_rename_command(target,name))

    def remove_scene(self,scene):
        project=self.document.project
        if project is None:
            raise SceneEntityAuthoringError("project required")
        return self._execute(build_remove_scene_command(project,scene))

    def reorder_scene(self,scene,new_index):
        project=self.document.project
        if project is None:
            raise SceneEntityAuthoringError("project required")
        return self._execute(build_reorder_scene_command(project,scene,new_index))

    def add_entity(self,scene,name="Entity"):
        return self._execute(build_add_entity_command(scene,name)).entity

    def set_entity_enabled(self,entity,enabled):
        value=bool(enabled)
        if entity.enabled == value:
            return None
        return self._execute(SetAttributeCommand(
            entity,"enabled",value,entity.enabled,
            f"{'Enable' if value else 'Disable'} Entity {entity.name}",
        ))

    def remove_entity(self,entity):
        return self._execute(build_remove_entity_command(entity))

    def duplicate_entity(self,entity):
        cmd=build_duplicate_entity_command(entity,self.document.component_registry)
        self._execute(cmd)
        return cmd.duplicate_entity

    def reorder_entity(self,entity,new_index):
        return self._execute(build_reorder_entity_command(entity,new_index))

    def move_entity_to_scene(self,entity,target_scene,target_index=None):
        return self._execute(
            build_move_entity_to_scene_command(entity,target_scene,target_index)
        )

    def add_component(self,entity,component_type):
        cmd=build_add_component_command(entity,component_type)
        self._execute(cmd)
        return cmd.component

    def remove_component(self,component):
        return self._execute(build_remove_component_command(component))

    def delete_entities(self,entities):
        entities=tuple(entities)
        if not entities:
            return None
        if len({id(e) for e in entities}) != len(entities):
            raise SceneEntityAuthoringError("duplicate entity selection")
        tx=CommandTransaction(
            f"Delete {len(entities)} Entities",
            [build_remove_entity_command(e) for e in entities],
        )
        self._execute(tx)
        return tx

    def duplicate_entities(self,entities):
        entities=tuple(entities)
        if not entities:
            return ()
        commands=[
            build_duplicate_entity_command(e,self.document.component_registry)
            for e in entities
        ]
        tx=CommandTransaction(f"Duplicate {len(commands)} Entities",commands)
        self._execute(tx)
        return tuple(c.duplicate_entity for c in commands)
