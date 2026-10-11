from dataclasses import dataclass

from asteria.graphics.character_placement import CharacterPlacement, frame_rect_at_standing_point
from asteria.graphics.placement import RenderPlacement2D


@dataclass(frozen=True, slots=True)
class TextureDraw:
    texture_asset_id: str
    source: tuple[int, int, int, int]
    screen_x: float
    screen_y: float
    width: float
    height: float
    layer: int = 0
    depth: float = 0.0
    opacity: float = 1.0
    flip_x: bool = False
    rotation_deg: float = 0.0  # clockwise on screen, about the quad centre


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
    sx, sy = camera.world_to_screen(draw_x, draw_y, placement.parallax_x, placement.parallax_y, placement.elevation)
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
