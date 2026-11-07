# The package's names are imported when first used (PEP 562): importing one module of it
# no longer imports every other one (and what they import), which made a cycle with
# asteria.assets and slowed every import. Generated from the eager imports it replaces.

from importlib import import_module

_EXPORTS = {  # name -> (module, attribute; None: the module itself)
    "ActorLinkComponent": ("asteria.runtime.field.actor_link", "ActorLinkComponent"),
    "AnimationClipSet": ("asteria.runtime.scene.animation", "AnimationClipSet"),
    "AnimationCondition": ("asteria.runtime.scene.animation_state_machine", "AnimationCondition"),
    "AnimationStateMachine": (
        "asteria.runtime.scene.animation_state_machine",
        "AnimationStateMachine",
    ),
    "AnimationStateMachineDefinition": (
        "asteria.runtime.scene.animation_state_machine",
        "AnimationStateMachineDefinition",
    ),
    "AnimationSystem": ("asteria.runtime.systems", "AnimationSystem"),
    "AnimationTransition": (
        "asteria.runtime.scene.animation_state_machine",
        "AnimationTransition",
    ),
    "Animator2DBinding": ("asteria.runtime.scene.animation", "Animator2DBinding"),
    "Animator2DComponent": ("asteria.runtime.scene.components", "Animator2DComponent"),
    "AnimatorState": ("asteria.runtime.scene.animation", "AnimatorState"),
    "Camera2D": ("asteria.runtime.scene.camera", "Camera2D"),
    "Camera2DComponent": ("asteria.runtime.scene.components", "Camera2DComponent"),
    "CameraFollow2D": ("asteria.runtime.scene.camera", "CameraFollow2D"),
    "CameraFollowSystem": ("asteria.runtime.systems", "CameraFollowSystem"),
    "CharacterAnimationController": (
        "asteria.runtime.scene.animation",
        "CharacterAnimationController",
    ),
    "CharacterController2D": ("asteria.runtime.field.character", "CharacterController2D"),
    "Collider2DComponent": ("asteria.runtime.field.collision", "Collider2DComponent"),
    "CollisionSystem": ("asteria.runtime.field.collision", "CollisionSystem"),
    "CollisionWorld": ("asteria.runtime.field.collision", "CollisionWorld"),
    "CombinedQuery": ("asteria.runtime.field.collision", "CombinedQuery"),
    "FieldAIComponent": ("asteria.runtime.field.ai", "FieldAIComponent"),
    "FieldAISystem": ("asteria.runtime.field.ai", "FieldAISystem"),
    "GameSessionError": ("asteria.runtime.game_session", "GameSessionError"),
    "GameSessionRuntime": ("asteria.runtime.game_session", "GameSessionRuntime"),
    "GameStartDefinition": ("asteria.runtime.game_start", "GameStartDefinition"),
    "GridMover2DComponent": ("asteria.runtime.field.grid_actors", "GridMover2DComponent"),
    "GridMoverSystem": ("asteria.runtime.field.grid_actors", "GridMoverSystem"),
    "InputSnapshot": ("asteria.runtime.input_map", "InputSnapshot"),
    "Interaction2DComponent": ("asteria.runtime.scene.components", "Interaction2DComponent"),
    "InteractionCandidate": ("asteria.runtime.field.interaction", "InteractionCandidate"),
    "InteractionController": ("asteria.runtime.field.interaction", "InteractionController"),
    "InteractionQuery": ("asteria.runtime.field.interaction", "InteractionQuery"),
    "InteractionTrigger": ("asteria.runtime.field.interaction", "InteractionTrigger"),
    "PlayerCameraSlice": ("asteria.runtime.field.character", "PlayerCameraSlice"),
    "ReferenceRuntime": ("asteria.runtime.tools.reference_runtime", "ReferenceRuntime"),
    "SkeletonAnimation2DComponent": (
        "asteria.runtime.scene.skeleton_component",
        "SkeletonAnimation2DComponent",
    ),
    "SkeletonSceneRuntime": ("asteria.runtime.scene.skeleton_component", "SkeletonSceneRuntime"),
    "SpawnSystem": ("asteria.runtime.field.ai", "SpawnSystem"),
    "SpawnZoneComponent": ("asteria.runtime.field.ai", "SpawnZoneComponent"),
    "SpriteRenderer2D": ("asteria.runtime.scene.components", "SpriteRenderer2D"),
    "TextureDraw": ("asteria.runtime.scene.draw", "TextureDraw"),
    "TextureRenderer": ("asteria.runtime.scene.draw", "TextureRenderer"),
    "TileMap2DComponent": ("asteria.runtime.scene.components", "TileMap2DComponent"),
    "TileMapQuery": ("asteria.runtime.field.tile_query", "TileMapQuery"),
    "VisibleEncounterComponent": ("asteria.runtime.field.ai", "VisibleEncounterComponent"),
    "build_runtime_camera": ("asteria.runtime.scene.camera", "build_runtime_camera"),
    "build_tile_draws": ("asteria.runtime.scene.tile_draw", "build_tile_draws"),
    "game_save": ("asteria.runtime.game_save", None),
    "game_session": ("asteria.runtime.game_session", None),
    "game_start": ("asteria.runtime.game_start", None),
    "run_reference_runtime": ("asteria.runtime.tools.reference_runtime", "run_reference_runtime"),
    "session": ("asteria.runtime.session", None),
    "sprite_draw": ("asteria.runtime.scene.draw", "sprite_draw"),
    "systems": ("asteria.runtime.systems", None),
    "touched_encounter": ("asteria.runtime.field.ai", "touched_encounter"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name):
    try:
        module, attribute = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = import_module(module)
    if attribute is not None:
        value = getattr(value, attribute)
    globals()[name] = value
    return value


def __dir__():
    return sorted({*globals(), *_EXPORTS})
