"""Whether the player can walk through a scene object (D88): the Inspector's Passability.

Every object on a map - a person, a chest, a house, a sign, a bush - is one of:

* ``through`` - passable: no solid collider (none at all, or a trigger: events still see it);
* ``feet`` - blocks at its feet: a solid Collider2D of the size the author gives it (people,
  so the player can stand in front of and behind them);
* ``picture`` - blocks its whole picture: a solid Collider2D the size of every opaque pixel of
  its sprite sheet (``Collider2D.fit = "picture"``): nothing of it can be walked into.

This is RPG Maker's event setting "Through" and its priority "Same as characters" (the
event's whole tile blocks), made for free-standing pictures of any size.
"""

from __future__ import annotations

from asteria.runtime.collision import Collider2DComponent
from asteria.runtime.components2d import SpriteRenderer2D

from .commands import AddComponentCommand, CommandTransaction, SetAttributeCommand

MODES = ("through", "feet", "picture")
MODE_LABELS = {
    "through": "Passable (walk through it)",
    "feet": "Blocks at its feet",
    "picture": "Blocks its whole picture",
}
FEET_HEIGHT = 8.0  # the feet box a new "blocks at its feet" gets, by the picture's width


def passability(entity):
    """The entity's mode (see the module)."""
    collider = entity.try_get(Collider2DComponent)
    if collider is None or not collider.enabled or collider.is_trigger or collider.ladder:
        return "through"
    return "picture" if getattr(collider, "fit", "custom") == "picture" else "feet"


def picture_box(project, root, entity):
    """``(width, height, offset_x, offset_y)`` covering the entity's whole picture (all frames
    of its sprite sheet, flipped like the sprite), or None when it has no picture."""
    from PIL import Image

    from asteria.graphics.character_placement import picture_box as measure
    from asteria.runtime.tilemap_field import AssetResources, TileMapFieldError

    sprite = entity.try_get(SpriteRenderer2D)
    if sprite is None or not sprite.sprite_sheet_asset_id:
        return None
    resources = AssetResources(project, root)
    try:
        sheet = resources.get(sprite.sprite_sheet_asset_id, "sprite_sheet")
        image = Image.open(resources.path(sheet.texture.asset_id, "texture"))
    except (TileMapFieldError, OSError, KeyError, ValueError):
        return None
    frames = [(f.x, f.y, f.width, f.height, f.pivot_x, f.pivot_y) for f in sheet.frames]
    box = measure(image, frames)
    if box is None:
        return None
    width, height, offset_x, offset_y = box
    if sprite.flip_x:
        offset_x = -offset_x
    return (round(width, 2), round(height, 2), round(offset_x, 2), round(offset_y, 2))


def passability_preview(project, root, entity, scale=3):
    """A PIL picture of the entity's current frame with what blocks drawn on it (red: the
    solid box, none when it is passable; a cross marks where it stands), or None."""
    from PIL import Image, ImageDraw

    from asteria.runtime.tilemap_field import AssetResources, TileMapFieldError

    sprite = entity.try_get(SpriteRenderer2D)
    if sprite is None or not sprite.sprite_sheet_asset_id:
        return None
    resources = AssetResources(project, root)
    try:
        sheet = resources.get(sprite.sprite_sheet_asset_id, "sprite_sheet")
        texture = Image.open(resources.path(sheet.texture.asset_id, "texture")).convert("RGBA")
    except (TileMapFieldError, OSError, KeyError, ValueError):
        return None
    frame = sheet.frames[min(max(0, int(sprite.frame_index)), len(sheet.frames) - 1)]
    picture = texture.crop((frame.x, frame.y, frame.x + frame.width, frame.y + frame.height))
    if sprite.flip_x:
        picture = picture.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    margin = 4
    w, h = frame.width + 2 * margin, frame.height + 2 * margin
    canvas = Image.new("RGBA", (w, h), (36, 40, 52, 255))
    canvas.alpha_composite(picture, (margin, margin))
    canvas = canvas.resize((w * scale, h * scale), Image.Resampling.NEAREST)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))  # drawn apart, laid over the picture
    draw = ImageDraw.Draw(layer)
    pivot_x = margin + (1 - frame.pivot_x if sprite.flip_x else frame.pivot_x) * frame.width
    stand_x, stand_y = pivot_x * scale, (margin + frame.pivot_y * frame.height) * scale
    collider = entity.try_get(Collider2DComponent)
    if passability(entity) != "through":
        cx = stand_x + collider.offset_x * scale
        cy = stand_y + collider.offset_y * scale
        half_w, half_h = collider.width * scale / 2, collider.height * scale / 2
        draw.rectangle(
            (cx - half_w, cy - half_h, cx + half_w, cy + half_h),
            fill=(230, 60, 60, 80),
            outline=(255, 90, 90, 255),
            width=2,
        )
    draw.line((stand_x - 5, stand_y, stand_x + 5, stand_y), fill=(120, 230, 255, 255), width=2)
    draw.line((stand_x, stand_y - 5, stand_x, stand_y + 5), fill=(120, 230, 255, 255), width=2)
    canvas.alpha_composite(layer)
    return canvas


def build_passability_command(entity, mode, box=None):
    """One undo step that makes ``entity`` passable, block at its feet or block its whole
    picture (``box``: ``picture_box``; needed for "picture", and sizes a new feet box)."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    transaction = CommandTransaction(f"Passability: {MODE_LABELS[mode]}")
    collider = entity.try_get(Collider2DComponent)
    if collider is None:
        if mode == "through":
            return transaction  # nothing blocks already
        collider = Collider2DComponent()
        if box is not None:  # a new feet box: most of the picture's width, at its foot
            collider.width = max(4.0, round(box[0] * 0.6))
        collider.height = FEET_HEIGHT
        transaction.add(AddComponentCommand(entity, collider))
    wanted = {"is_trigger": mode == "through", "enabled": True, "ladder": False}
    if mode == "picture":
        if box is None:
            raise ValueError("this object has no picture to measure")
        width, height, offset_x, offset_y = box
        wanted.update(
            fit="picture",
            shape="box",
            width=float(width),
            height=float(height),
            offset_x=float(offset_x),
            offset_y=float(offset_y),
        )
    else:
        wanted["fit"] = "custom"
    for name, value in wanted.items():
        old = getattr(collider, name)
        if old != value:
            transaction.add(SetAttributeCommand(collider, name, value, old, f"Set {name}"))
    return transaction


__all__ = [
    "MODES",
    "MODE_LABELS",
    "build_passability_command",
    "passability",
    "passability_preview",
    "picture_box",
]
