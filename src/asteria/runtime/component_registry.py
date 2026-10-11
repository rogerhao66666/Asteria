"""The engine's built-in component types: one list shared by the game, the editor and project tools."""

from __future__ import annotations


def default_component_registry():
    from asteria.core import ComponentRegistry, PersistentComponent, Transform
    from asteria.core.prefab import PrefabInstanceComponent
    from asteria.gameplay import GameplayAttributesComponent

    from .actor_link import ActorLinkComponent
    from .character_control import register_character_components
    from .collision import Collider2DComponent
    from .components2d import (
        Animator2DComponent,
        Camera2DComponent,
        Interaction2DComponent,
        SpriteRenderer2D,
        TileMap2DComponent,
    )
    from .field_ai import FieldAIComponent, SpawnZoneComponent, VisibleEncounterComponent
    from .npc_state import NpcIdentity2DComponent

    registry = ComponentRegistry()
    for component in (
        Transform,
        SpriteRenderer2D,
        Camera2DComponent,
        Interaction2DComponent,
        Animator2DComponent,
        TileMap2DComponent,
        GameplayAttributesComponent,
        ActorLinkComponent,
        PersistentComponent,
        PrefabInstanceComponent,
        Collider2DComponent,
    ):
        registry.register(component)
    register_character_components(registry)
    for component in (NpcIdentity2DComponent, FieldAIComponent, SpawnZoneComponent, VisibleEncounterComponent):
        registry.register(component)
    from .environment2d import register_environment_components

    register_environment_components(registry)  # VFX-02 / VFX-03 scene environment, lights, shadow casters
    return registry
