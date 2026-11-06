# The package's names are imported when first used (PEP 562): importing one module of it
# no longer imports every other one (and what they import), which made a cycle with
# asteria.assets and slowed every import. Generated from the eager imports it replaces.

from importlib import import_module

_EXPORTS = {  # name -> (module, attribute; None: the module itself)
    "ActorLinkComponent": (".actor_link", "ActorLinkComponent"),
    "AnimationClipSet": (".animation_library", "AnimationClipSet"),
    "AnimationCondition": (".animation_state_machine", "AnimationCondition"),
    "AnimationStateMachine": (".animation_state_machine", "AnimationStateMachine"),
    "AnimationStateMachineDefinition": (
        ".animation_state_machine",
        "AnimationStateMachineDefinition",
    ),
    "AnimationSystem": (".systems", "AnimationSystem"),
    "AnimationTransition": (".animation_state_machine", "AnimationTransition"),
    "Animator2DBinding": (".animation_binding", "Animator2DBinding"),
    "Animator2DComponent": (".components2d", "Animator2DComponent"),
    "AnimatorState": (".animation", "AnimatorState"),
    "Camera2D": (".camera", "Camera2D"),
    "Camera2DComponent": (".components2d", "Camera2DComponent"),
    "CameraFollow2D": (".camera", "CameraFollow2D"),
    "CameraFollowSystem": (".systems", "CameraFollowSystem"),
    "CharacterAnimationController": (".character_animation", "CharacterAnimationController"),
    "CharacterController2D": (".character", "CharacterController2D"),
    "Collider2DComponent": (".collision", "Collider2DComponent"),
    "CollisionSystem": (".collision", "CollisionSystem"),
    "CollisionWorld": (".collision", "CollisionWorld"),
    "CombinedQuery": (".collision", "CombinedQuery"),
    "FieldAIComponent": (".field_ai", "FieldAIComponent"),
    "FieldAISystem": (".field_ai", "FieldAISystem"),
    "GameSessionError": (".game_session", "GameSessionError"),
    "GameSessionRuntime": (".game_session", "GameSessionRuntime"),
    "GameStartDefinition": (".game_start", "GameStartDefinition"),
    "GridMover2DComponent": (".grid_actors", "GridMover2DComponent"),
    "GridMoverSystem": (".grid_actors", "GridMoverSystem"),
    "InputSnapshot": (".input", "InputSnapshot"),
    "Interaction2DComponent": (".components2d", "Interaction2DComponent"),
    "InteractionCandidate": (".interaction", "InteractionCandidate"),
    "InteractionController": (".interaction", "InteractionController"),
    "InteractionQuery": (".interaction", "InteractionQuery"),
    "InteractionTrigger": (".interaction", "InteractionTrigger"),
    "PlayerCameraSlice": (".player_slice", "PlayerCameraSlice"),
    "PlayerRuntime": (".player", "PlayerRuntime"),
    "ReferenceRuntime": (".reference_runtime", "ReferenceRuntime"),
    "SkeletonAnimation2DComponent": (".skeleton_component", "SkeletonAnimation2DComponent"),
    "SkeletonSceneRuntime": (".skeleton_component", "SkeletonSceneRuntime"),
    "SpawnSystem": (".field_ai", "SpawnSystem"),
    "SpawnZoneComponent": (".field_ai", "SpawnZoneComponent"),
    "SpriteRenderer2D": (".components2d", "SpriteRenderer2D"),
    "SpriteRendererState": (".sprite", "SpriteRendererState"),
    "TextureDraw": (".draw", "TextureDraw"),
    "TextureRenderer": (".texture_renderer", "TextureRenderer"),
    "TileMap2DComponent": (".components2d", "TileMap2DComponent"),
    "TileMapQuery": (".tilequery", "TileMapQuery"),
    "VisibleEncounterComponent": (".field_ai", "VisibleEncounterComponent"),
    "actor_link": (".actor_link", None),
    "animation": (".animation", None),
    "animation_binding": (".animation_binding", None),
    "animation_library": (".animation_library", None),
    "animation_state_machine": (".animation_state_machine", None),
    "backlog": (".backlog", None),
    "build_runtime_camera": (".camera_factory", "build_runtime_camera"),
    "build_tile_draws": (".tile_draw", "build_tile_draws"),
    "camera": (".camera", None),
    "camera_factory": (".camera_factory", None),
    "character": (".character", None),
    "character_animation": (".character_animation", None),
    "character_control": (".character_control", None),
    "collision": (".collision", None),
    "components2d": (".components2d", None),
    "draw": (".draw", None),
    "field_ai": (".field_ai", None),
    "game_save": (".game_save", None),
    "game_session": (".game_session", None),
    "game_start": (".game_start", None),
    "grid_actors": (".grid_actors", None),
    "grid_heights": (".grid_heights", None),
    "input": (".input", None),
    "interaction": (".interaction", None),
    "pictures": (".pictures", None),
    "player": (".player", None),
    "player_slice": (".player_slice", None),
    "reference_runtime": (".reference_runtime", None),
    "run_reference_runtime": (".reference_runtime", "run_reference_runtime"),
    "session": (".session", None),
    "skeleton_component": (".skeleton_component", None),
    "skeleton_draw": (".skeleton_draw", None),
    "sprite": (".sprite", None),
    "sprite_draw": (".draw", "sprite_draw"),
    "systems": (".systems", None),
    "texture_renderer": (".texture_renderer", None),
    "tile_draw": (".tile_draw", None),
    "tilequery": (".tilequery", None),
    "touched_encounter": (".field_ai", "touched_encounter"),
    "world_command_handlers": (".world_command_handlers", None),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name):
    try:
        module, attribute = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = import_module(module, __name__)
    if attribute is not None:
        value = getattr(value, attribute)
    globals()[name] = value
    return value


def __dir__():
    return sorted({*globals(), *_EXPORTS})
