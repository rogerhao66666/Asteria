"""Turn skeleton ``SpriteDraw`` rows into ``TextureDraw`` commands the renderers understand."""

from __future__ import annotations

from math import cos, radians, sin

from asteria.runtime.draw import TextureDraw


def to_texture_draws(rows, sheet_for, *, camera=None, layer=0, depth=0.0, opacity=1.0):
    """One ``TextureDraw`` per row. ``sheet_for(asset id)`` gives the sprite sheet (with
    ``frames`` carrying ``x, y, width, height, pivot_x, pivot_y`` and a ``texture``).

    A frame is placed so its pivot lies on the row's position and is rotated about that pivot;
    ``camera`` (anything with ``world_to_screen(x, y)`` and ``zoom``) maps world to screen.
    """
    draws = []
    zoom = 1.0 if camera is None else camera.zoom
    for row in rows:
        sheet = sheet_for(row.sheet_asset_id)
        if sheet is None or not 0 <= row.frame < len(sheet.frames):
            continue
        frame = sheet.frames[row.frame]
        width, height = (
            frame.width * abs(row.scale_x) * zoom,
            frame.height * abs(row.scale_y) * zoom,
        )
        x, y = (row.x, row.y) if camera is None else camera.world_to_screen(row.x, row.y)
        # centre of the quad, relative to the pivot, then rotated with the sprite
        rx = width / 2 - frame.pivot_x * abs(row.scale_x) * zoom
        ry = height / 2 - frame.pivot_y * abs(row.scale_y) * zoom
        c, s = cos(radians(row.rotation)), sin(radians(row.rotation))
        cx, cy = x + rx * c - ry * s, y + rx * s + ry * c
        draws.append(
            TextureDraw(
                sheet.texture.asset_id,
                (frame.x, frame.y, frame.width, frame.height),
                cx - width / 2,
                cy - height / 2,
                width,
                height,
                layer + row.z,
                depth,
                opacity,
                row.scale_x < 0,
                row.rotation,
            )
        )
    return draws
