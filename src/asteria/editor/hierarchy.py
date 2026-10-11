from .commands import MoveEntityToSceneCommand, ReorderEntityCommand


class HierarchyEditError(ValueError):
    pass


def build_reorder_entity_command(entity, new_index):
    if entity is None or entity.scene is None:
        raise HierarchyEditError("Entity must belong to a scene")
    scene = entity.scene
    old_index = scene.entity_index(entity)
    new_index = max(0, min(int(new_index), len(scene.entities()) - 1))
    return ReorderEntityCommand(scene, entity, new_index, old_index)


def build_move_entity_to_scene_command(entity, target_scene, target_index=None):
    if entity is None or entity.scene is None:
        raise HierarchyEditError("Entity must belong to a scene")
    if target_scene is None:
        raise HierarchyEditError("Target scene required")
    if entity.scene is target_scene:
        if target_index is None:
            raise HierarchyEditError("Target index required for same-scene move")
        return build_reorder_entity_command(entity, target_index)
    return MoveEntityToSceneCommand(
        source_scene=entity.scene,
        target_scene=target_scene,
        entity=entity,
        target_index=target_index,
    )


def drop_entities(document, entities, target_kind, target, position="on"):
    """Apply a hierarchy drag-and-drop (EDT-14) as one undo step.

    ``target_kind`` "entity": ``position`` "on" parents the entities to ``target``;
    "above" / "below" puts them next to it (same parent, scene order).
    ``target_kind`` "scene": moves them to that scene's top level (unparented).
    """
    from asteria.core.transform import Transform, can_parent

    from .editing import ReparentTransformCommand

    entities = [e for e in entities if e is not None and e is not target]
    if not entities:
        raise HierarchyEditError("nothing to drop")
    with document.group(f"Drag {len(entities)} entit{'y' if len(entities) == 1 else 'ies'}"):
        for entity in entities:
            if target_kind == "scene":
                if entity.scene is not target:
                    document.execute(build_move_entity_to_scene_command(entity, target))
                if entity.has(Transform) and entity.get(Transform).parent_id:
                    document.execute(ReparentTransformCommand(entity.get(Transform), ""))
                continue
            if target_kind != "entity" or target is None:
                raise HierarchyEditError("drop target must be a scene or an entity")
            if entity.scene is not target.scene:
                document.execute(build_move_entity_to_scene_command(entity, target.scene))
            if position == "on":
                if not entity.has(Transform) or not can_parent(entity, target):
                    raise HierarchyEditError(f"{entity.name} cannot be a child of {target.name}")
                document.execute(ReparentTransformCommand(entity.get(Transform), target.id))
                continue
            sibling_parent = target.get(Transform).parent_id if target.has(Transform) else ""
            if entity.has(Transform) and entity.get(Transform).parent_id != sibling_parent:
                parent = target.scene.get_entity(sibling_parent) if sibling_parent else None
                if parent is not None and not can_parent(entity, parent):
                    raise HierarchyEditError(f"{entity.name} cannot be a child of {parent.name}")
                document.execute(ReparentTransformCommand(entity.get(Transform), sibling_parent))
            scene = target.scene
            index = scene.entity_index(target) + (1 if position == "below" else 0)
            if scene.entity_index(entity) < index:
                index -= 1
            document.execute(build_reorder_entity_command(entity, index))
    return entities
