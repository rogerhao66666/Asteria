from .commands import ReorderEntityCommand,MoveEntityToSceneCommand

class HierarchyEditError(ValueError): pass

def build_reorder_entity_command(entity,new_index):
    if entity is None or entity.scene is None:
        raise HierarchyEditError("Entity must belong to a scene")
    scene=entity.scene
    old_index=scene.entity_index(entity)
    new_index=max(0,min(int(new_index),len(scene.entities())-1))
    return ReorderEntityCommand(scene,entity,new_index,old_index)

def build_move_entity_to_scene_command(entity,target_scene,target_index=None):
    if entity is None or entity.scene is None:
        raise HierarchyEditError("Entity must belong to a scene")
    if target_scene is None:
        raise HierarchyEditError("Target scene required")
    if entity.scene is target_scene:
        if target_index is None:
            raise HierarchyEditError("Target index required for same-scene move")
        return build_reorder_entity_command(entity,target_index)
    return MoveEntityToSceneCommand(
        source_scene=entity.scene,
        target_scene=target_scene,
        entity=entity,
        target_index=target_index,
    )
