from asteria.graphics import EMPTY_TILE

from .draw import TextureDraw


def _visible_span(first, last, extent, limit):
    """Whether any of the cells whose screen starts run ``first`` .. ``last`` (each ``extent``
    long) reaches into ``0 .. limit`` (no ``limit`` means everything is visible)."""
    if limit is None:
        return True
    return not (max(first, last) + extent < 0 or min(first, last) > limit)


def build_tile_draws(
    tilemap,
    tileset,
    sprite_sheet,
    camera,
    *,
    origin_x=0.0,
    origin_y=0.0,
    viewport_width=None,
    viewport_height=None,
    validate_tilemap=True,
):
    """Texture draws of every visible tile. Chunks (and rows) wholly outside the viewport are
    skipped before their tiles are visited; ``validate_tilemap=False`` leaves the whole-map
    check to whoever loads and edits the map (the editor repaints far more often)."""
    if validate_tilemap:
        tilemap.validate()
    sprite_sheet.validate()
    tileset.validate(len(sprite_sheet.frames))
    tile_w, tile_h = tilemap.tile_width, tilemap.tile_height
    chunk_w, chunk_h = tilemap.chunk_width, tilemap.chunk_height
    width = tile_w * camera.zoom
    height = tile_h * camera.zoom
    texture_id = sprite_sheet.texture.asset_id
    frames = sprite_sheet.frames
    tile_defs = tileset.tiles
    draws = []
    for layer in tilemap.ordered_layers():
        if not layer.visible or layer.opacity <= 0:
            continue
        for _, chunk in sorted(layer.chunks.items()):
            base_x = chunk.chunk_x * chunk_w
            base_y = chunk.chunk_y * chunk_h
            first = camera.world_to_screen(origin_x + base_x * tile_w, origin_y + base_y * tile_h)
            last = camera.world_to_screen(
                origin_x + (base_x + chunk.width - 1) * tile_w,
                origin_y + (base_y + chunk.height - 1) * tile_h,
            )
            if not _visible_span(first[0], last[0], width, viewport_width):
                continue
            if not _visible_span(first[1], last[1], height, viewport_height):
                continue
            tiles = chunk.tiles
            for ly in range(chunk.height):
                row = ly * chunk.width
                for lx in range(chunk.width):
                    tile_id = tiles[row + lx]
                    if tile_id == EMPTY_TILE:
                        continue
                    tile_def = tile_defs.get(tile_id)
                    if tile_def is None:
                        continue
                    frame = frames[tile_def.frame_index]
                    tx = base_x + lx
                    ty = base_y + ly
                    wx = origin_x + tx * tile_w
                    wy = origin_y + ty * tile_h
                    sx, sy = camera.world_to_screen(wx, wy)
                    if viewport_width is not None and (sx + width < 0 or sx > viewport_width):
                        continue
                    if viewport_height is not None and (sy + height < 0 or sy > viewport_height):
                        continue
                    draws.append(
                        TextureDraw(
                            texture_id,
                            (frame.x, frame.y, frame.width, frame.height),
                            sx,
                            sy,
                            width,
                            height,
                            layer.order,
                            float(ty),
                            layer.opacity,
                            False,
                        )
                    )
    return tuple(sorted(draws, key=lambda d: (d.layer, d.depth, d.screen_y, d.screen_x)))
