from asteria.core import Entity

from .commands import (
    AddComponentCommand,
    AddEntityCommand,
    RemoveComponentCommand,
    RemoveEntityCommand,
    RenameCommand,
)


class StructureEditError(ValueError):
    pass


def build_rename_command(target, new_name):
    name = str(new_name).strip()
    if not name:
        raise StructureEditError("Name cannot be empty")
    if not hasattr(target, "name"):
        raise StructureEditError("Selected object cannot be renamed")
    return RenameCommand(target, name, target.name)


def build_add_entity_command(scene, name="Entity"):
    if scene is None:
        raise StructureEditError("Scene required")
    name = str(name).strip() or "Entity"
    return AddEntityCommand(scene, Entity(name))


def build_remove_entity_command(entity):
    if entity is None or entity.scene is None:
        raise StructureEditError("Entity must belong to a scene")
    return RemoveEntityCommand(entity.scene, entity)


def build_add_component_command(entity, component_type):
    if entity is None:
        raise StructureEditError("Entity required")
    if entity.has(component_type):
        raise StructureEditError(f"{component_type.__name__} already exists")
    try:
        component = component_type()
    except TypeError as exc:
        raise StructureEditError(f"{component_type.__name__} cannot be default-constructed") from exc
    return AddComponentCommand(entity, component)


def build_remove_component_command(component):
    if component is None or not getattr(component, "attached", False):
        raise StructureEditError("Component must be attached")
    return RemoveComponentCommand(component.entity, component)
