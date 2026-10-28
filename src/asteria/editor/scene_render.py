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
        # the map is validated where it is loaded, saved and edited; not on every repaint
        validate_tilemap=False,
    )


def resolve_texture_source(document, texture_asset_id):
    if document.project is None:
        return None
    record = document.project.assets.get(texture_asset_id)
    if record is not None and record.kind == "texture":
        source = Path(record.source_path)
    else:
        try:
            canonical = document.project.assets.resolve(texture_asset_id)
        except KeyError:
            return None
        if canonical.kind not in {"texture", "character.walking"}:
            return None
        source = Path(canonical.source.uri)
    if document.file_path is not None:
        source = document.file_path.parent / source
    return source


def render_source_for_scene(document, scene):
    """Resolve the first visible TileMap2D binding in scene order."""
    if scene is None:
        return None
    from asteria.runtime import TileMap2DComponent

    for entity in scene.entities():
        binding = entity.try_get(TileMap2DComponent)
        if binding is None or not binding.visible or not binding.tilemap_asset_id:
            continue
        tilemap = document.asset_views.tilemap(binding.tilemap_asset_id)
        if tilemap is None:
            continue
        tileset = document.asset_views.tileset(tilemap.tileset.asset_id)
        if tileset is None:
            continue
        sprite_sheet = document.asset_views.sprite_sheet(tileset.sprite_sheet.asset_id)
        if sprite_sheet is None:
            continue
        return TileMapRenderSource(
            tilemap,
            tileset,
            sprite_sheet,
            binding.origin_x,
            binding.origin_y,
        )
    return None
