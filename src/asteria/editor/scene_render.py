from dataclasses import dataclass
from pathlib import Path

from asteria.runtime import build_tile_draws


@dataclass(slots=True)
class TileMapRenderSource:
    tilemap: object
    tileset: object
    sprite_sheet: object
    origin_x: float = 0.0
    origin_y: float = 0.0


def build_scene_texture_draws(source, camera, viewport_width, viewport_height):
    if source is None:
        return ()
    return build_tile_draws(
        source.tilemap,
        source.tileset,
        source.sprite_sheet,
        camera,
        origin_x=source.origin_x,
        origin_y=source.origin_y,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )


def resolve_texture_source(document, texture_asset_id):
    if document.project is None:
        return None
    record = document.project.assets.get(texture_asset_id)
    if record is None or record.kind != "texture":
        return None
    source = Path(record.source_path)
    if document.file_path is not None:
        source = document.file_path.parent / source
    return source
