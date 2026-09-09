from dataclasses import dataclass
from .hierarchy import build_reorder_entity_command,build_move_entity_to_scene_command
from .scenes import build_reorder_scene_command

@dataclass(frozen=True,slots=True)
class DropIntent:
    kind:str
    command:object

def build_hierarchy_drop_intent(project,drag_kind,drag_value,target_kind,target_value,target_index=None):
    if drag_kind=="scene" and target_kind=="scene":
        if target_index is None:
            target_index=project.scene_index(target_value)
        return DropIntent("scene_reorder",build_reorder_scene_command(project,drag_value,target_index))

    if drag_kind=="entity":
        if target_kind=="scene":
            return DropIntent("entity_move",build_move_entity_to_scene_command(drag_value,target_value,target_index))
        if target_kind=="entity":
            target_scene=target_value.scene
            if target_index is None:
                target_index=target_scene.entity_index(target_value)
            return DropIntent("entity_move",build_move_entity_to_scene_command(drag_value,target_scene,target_index))

    raise ValueError(f"Unsupported hierarchy drop: {drag_kind} -> {target_kind}")
