"""Texture draw commands: what to draw where (TextureDraw), and the renderer that sends them to a
backend."""

from asteria.graphics.character_placement import CharacterPlacement, frame_rect_at_standing_point
from asteria.graphics.draw import TextureDraw
from asteria.graphics.placement import RenderPlacement2D


def sprite_draw(
    *,
    sheet,
    frame_index,
    world_x,
    world_y,
    camera,
    placement=None,
    opacity=1.0,
    flip_x=False,
):
    placement = placement or RenderPlacement2D()
    placement.validate()
    frame = sheet.frames[frame_index]
    draw_x, draw_y, _, _ = frame_rect_at_standing_point(
        (world_x, world_y),
        CharacterPlacement((frame.width, frame.height), (frame.pivot_x, frame.pivot_y)),
    )
    sx, sy = camera.world_to_screen(
        draw_x, draw_y, placement.parallax_x, placement.parallax_y, placement.elevation
    )
    return TextureDraw(
        sheet.texture.asset_id,
        (frame.x, frame.y, frame.width, frame.height),
        sx,
        sy,
        frame.width * camera.zoom,
        frame.height * camera.zoom,
        placement.layer,
        placement.depth,
        opacity,
        flip_x,
    )


class TextureRenderer:
    def __init__(self, backend, cache, source_paths):
        self.backend = backend
        self.cache = cache
        self.source_paths = dict(source_paths)

    def render(self, draw_commands):
        for draw in draw_commands:
            try:
                source = self.source_paths[draw.texture_asset_id]
            except KeyError as exc:
                raise KeyError(f"missing source path for texture {draw.texture_asset_id}") from exc
            resource = self.cache.get(draw.texture_asset_id, source)
            self.backend.draw_texture(resource, draw)
