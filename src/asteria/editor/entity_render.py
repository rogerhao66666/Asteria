from dataclasses import dataclass

from asteria.core import Transform
from asteria.graphics import RenderPlacement2D
from asteria.runtime import Camera2DComponent, SpriteRenderer2D, sprite_draw


@dataclass(frozen=True, slots=True)
class CameraFrame:
    entity: object
    screen_x: float
    screen_y: float
    width: float
    height: float
    active: bool
    deadzone: tuple[float, float, float, float] | None


def build_entity_sprite_draws(scene, camera, resolve_sprite_sheet):
    if scene is None:
        return ()
    draws = []
    for entity in scene.entities():
        transform = entity.try_get(Transform)
        renderer = entity.try_get(SpriteRenderer2D)
        if transform is None or renderer is None or not renderer.visible:
            continue
        sheet = resolve_sprite_sheet(renderer.sprite_sheet_asset_id)
        if sheet is None or not (0 <= renderer.frame_index < len(sheet.frames)):
            continue
        placement = RenderPlacement2D(
            layer=renderer.layer, depth=renderer.depth, elevation=renderer.elevation
        )
        draw = sprite_draw(
            sheet=sheet,
            frame_index=renderer.frame_index,
            world_x=transform.x,
            world_y=transform.y,
            camera=camera,
            placement=placement,
            opacity=renderer.opacity,
            flip_x=renderer.flip_x,
        )
        draw = type(draw)(
            draw.texture_asset_id,
            draw.source,
            draw.screen_x,
            draw.screen_y,
            draw.width * transform.scale_x,
            draw.height * transform.scale_y,
            draw.layer,
            draw.depth,
            draw.opacity,
            draw.flip_x,
        )
        draws.append(draw)
    return tuple(
        sorted(draws, key=lambda d: (d.layer, d.depth, d.screen_y, d.screen_x))
    )


def build_camera_frames(scene, editor_camera):
    if scene is None:
        return ()
    result = []
    for entity in scene.entities():
        transform = entity.try_get(Transform)
        spec = entity.try_get(Camera2DComponent)
        if transform is None or spec is None:
            continue
        sx, sy = editor_camera.world_to_screen(transform.x, transform.y)
        width = (spec.width / spec.zoom) * editor_camera.zoom
        height = (spec.height / spec.zoom) * editor_camera.zoom
        deadzone = None
        if spec.deadzone_x > 0 or spec.deadzone_y > 0:
            dw = spec.deadzone_x * 2 * editor_camera.zoom
            dh = spec.deadzone_y * 2 * editor_camera.zoom
            deadzone = (sx + width / 2 - dw / 2, sy + height / 2 - dh / 2, dw, dh)
        result.append(CameraFrame(entity, sx, sy, width, height, spec.active, deadzone))
    return tuple(result)
