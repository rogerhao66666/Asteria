"""Placing doodads (free-standing decorations) as scene entities, with undo."""

from __future__ import annotations

from asteria.core import Entity, Transform
from asteria.rpg.doodads import DoodadDefinition, snap_position
from asteria.runtime.collision import Collider2DComponent
from asteria.runtime.components2d import SpriteRenderer2D

from .commands import AddEntityCommand, CommandTransaction

TAG_PREFIX = "doodad:"


def make_doodad_entity(definition, x, y, *, name=None, flip=False):
    """A scene entity for ``definition`` standing at ``(x, y)`` (snapped when the definition
    asks). Its name starts with the doodad id; ``doodad_of`` reads it back."""
    if not isinstance(definition, DoodadDefinition):
        raise TypeError("definition must be DoodadDefinition")
    x, y = snap_position(x, y, definition.snap)
    entity = Entity(name or f"{TAG_PREFIX}{definition.doodad_id}")
    transform = entity.add_component(Transform(x, y))
    transform.scale_x = -1.0 if flip else 1.0
    sprite = entity.add_component(SpriteRenderer2D())
    sprite.sprite_sheet_asset_id = definition.sprite_sheet_asset_id
    sprite.frame_index = definition.frame
    sprite.layer = definition.layer
    sprite.depth = definition.depth
    sprite.flip_x = bool(flip)
    if definition.solid:
        collider = entity.add_component(Collider2DComponent())
        collider.width, collider.height = definition.solid_width, definition.solid_height
        collider.offset_y = definition.solid_offset_y
    return entity


def doodad_of(entity):
    """The doodad id an entity was made from, or ``None``."""
    if not entity.name.startswith(TAG_PREFIX):
        return None
    return entity.name[len(TAG_PREFIX) :].split(".", 1)[0]


def build_place_doodads_command(scene, definition, positions, *, flip=False):
    """One undo step that adds a doodad at each of ``positions`` (``(x, y)`` pairs)."""
    positions = list(positions)
    if not positions:
        raise ValueError("no positions to place doodads at")
    plural = "Doodads" if len(positions) > 1 else "Doodad"
    transaction = CommandTransaction(f"Place {plural}")
    for index, (x, y) in enumerate(positions):
        entity = make_doodad_entity(
            definition, x, y, name=f"{TAG_PREFIX}{definition.doodad_id}.{index + 1}", flip=flip
        )
        transaction.add(AddEntityCommand(scene, entity))
    return transaction
