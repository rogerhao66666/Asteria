"""The engine's built-in component types: one list shared by the game, the editor and project
tools."""

from __future__ import annotations

from asteria.core import ComponentRegistry, PersistentComponent, Transform
from asteria.core.prefab import PrefabInstanceComponent
from asteria.gameplay import GameplayAttributesComponent
from asteria.runtime.action.abilities import register_action_combat_components
from asteria.runtime.action.combat import register_combat_components
from asteria.runtime.action.ground_loot import register_loot_components
from asteria.runtime.action.play import register_action_play_components
from asteria.runtime.field.actor_link import ActorLinkComponent, ClassAppearanceComponent
from asteria.runtime.field.ai import (
    FieldAIComponent,
    SpawnZoneComponent,
    VisibleEncounterComponent,
)
from asteria.runtime.field.character_control import register_character_components
from asteria.runtime.field.collision import Collider2DComponent
from asteria.runtime.field.grid_actors import (
    GridMover2DComponent,
    LookByVariable2DComponent,
    SightTrigger2DComponent,
    SwitchVisibility2DComponent,
)
from asteria.runtime.field.npc_state import NpcIdentity2DComponent
from asteria.runtime.scene.components import (
    Animator2DComponent,
    Camera2DComponent,
    Interaction2DComponent,
    ParallaxBackground2DComponent,
    SpriteRenderer2D,
    TileMap2DComponent,
)
from asteria.runtime.scene.environment import register_environment_components
from asteria.runtime.scene.skeleton_component import SkeletonAnimation2DComponent


def default_component_registry():
    registry = ComponentRegistry()
    for component in (
        Transform,
        SpriteRenderer2D,
        Camera2DComponent,
        Interaction2DComponent,
        Animator2DComponent,
        TileMap2DComponent,
        ParallaxBackground2DComponent,
        GameplayAttributesComponent,
        ActorLinkComponent,
        ClassAppearanceComponent,
        PersistentComponent,
        PrefabInstanceComponent,
        Collider2DComponent,
    ):
        registry.register(component)
    register_character_components(registry)

    register_combat_components(registry)  # ASTERIA_SPEC §20 combatants

    register_action_combat_components(registry)  # ASTERIA_SPEC §20 real-time ability use

    register_loot_components(registry)  # ASTERIA_SPEC §35 loot on the ground

    register_action_play_components(registry)  # ASTERIA_SPEC §20 action scenes
    for component in (
        NpcIdentity2DComponent,
        FieldAIComponent,
        SpawnZoneComponent,
        VisibleEncounterComponent,
        GridMover2DComponent,
        SightTrigger2DComponent,
        SwitchVisibility2DComponent,
        LookByVariable2DComponent,
        SkeletonAnimation2DComponent,
    ):
        registry.register(component)

    register_environment_components(
        registry
    )  # VFX-02 / VFX-03 scene environment, lights, shadow casters
    return registry
