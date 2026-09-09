from asteria.graphics import EMPTY_TILE

from .draw import TextureDraw


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
):
    tilemap.validate()
    sprite_sheet.validate()
    tileset.validate(len(sprite_sheet.frames))
    draws = []
    for layer in tilemap.ordered_layers():
        if not layer.visible or layer.opacity <= 0:
            continue
        for _, chunk in sorted(layer.chunks.items()):
            for ly in range(chunk.height):
                for lx in range(chunk.width):
                    tile_id = chunk.get(lx, ly)
                    if tile_id == EMPTY_TILE:
                        continue
                    tile_def = tileset.tiles.get(tile_id)
                    if tile_def is None:
                        continue
                    frame = sprite_sheet.frames[tile_def.frame_index]
                    tx = chunk.chunk_x * tilemap.chunk_width + lx
                    ty = chunk.chunk_y * tilemap.chunk_height + ly
                    wx = origin_x + tx * tilemap.tile_width
                    wy = origin_y + ty * tilemap.tile_height
                    sx, sy = camera.world_to_screen(wx, wy)
                    width = tilemap.tile_width * camera.zoom
                    height = tilemap.tile_height * camera.zoom
                    if viewport_width is not None and (
                        sx + width < 0 or sx > viewport_width
                    ):
                        continue
                    if viewport_height is not None and (
                        sy + height < 0 or sy > viewport_height
                    ):
                        continue
                    draws.append(
                        TextureDraw(
                            sprite_sheet.texture.asset_id,
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
    return tuple(
        sorted(draws, key=lambda d: (d.layer, d.depth, d.screen_y, d.screen_x))
    )
