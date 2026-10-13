from PIL import Image

from asteria.assets.canonical import AssetRef
from asteria.graphics import SpriteFrame, SpriteSheet
from asteria.reference_data import (
    load_animation_set,
    load_sprite_sheet,
    load_tilemap,
    load_tileset,
)


class EditorResourceError(RuntimeError):
    pass


_LOADERS = {
    "sprite_sheet": load_sprite_sheet,
    "tileset": load_tileset,
    "tilemap": load_tilemap,
    "animation": load_animation_set,
}


def asset_source_path(document, record):
    if document.file_path is None:
        return None
    return document.file_path.parent / record.source_path


def resolve_project_resources(document):
    """Resolve canonical project asset sidecars into editor/runtime resource views."""
    document.asset_views.clear()
    project = document.project
    if project is None or document.file_path is None:
        return document.asset_views

    for record in project.assets.records():
        loader = _LOADERS.get(record.kind)
        if loader is None:
            continue
        path = asset_source_path(document, record)
        if path is None or not path.is_file():
            raise EditorResourceError(f"Missing {record.kind} asset: {record.source_path}")
        try:
            value = loader(path)
        except Exception as exc:
            raise EditorResourceError(f"Failed to load {record.source_path}: {exc}") from exc

        if record.kind == "sprite_sheet":
            document.asset_views.set_sprite_sheet(record.id, value)
        elif record.kind == "tileset":
            document.asset_views.set_tileset(record.id, value)
        elif record.kind == "tilemap":
            document.asset_views.set_tilemap(record.id, value)
        elif record.kind == "animation":
            document.asset_views.set_clip_set(record.id, value)

    # Generated characters are canonical image assets rather than
    # legacy JSON sidecars. Rebuild their 3x4 walking sheet view from the
    # persisted frame metadata so save/reopen retains viewport rendering.
    for asset in project.assets.snapshot():
        if asset.kind != "character.walking":
            continue
        path = document.file_path.parent / asset.source.uri
        if not path.is_file():
            raise EditorResourceError(f"Missing character.walking asset: {asset.source.uri}")
        metadata = asset.meta()
        frame_width, frame_height = metadata.get("frame_size", (48, 48))
        try:
            with Image.open(path) as image:
                width, height = image.size
        except Exception as exc:
            raise EditorResourceError(f"Failed to load {asset.source.uri}: {exc}") from exc
        if width % frame_width or height % frame_height:
            raise EditorResourceError(f"Invalid walking sheet grid: {asset.source.uri}")
        frames = [
            SpriteFrame(column * frame_width, row * frame_height, frame_width, frame_height)
            for row in range(height // frame_height)
            for column in range(width // frame_width)
        ]
        document.asset_views.set_sprite_sheet(
            asset.asset_id, SpriteSheet(AssetRef(asset.asset_id), frames)
        )

    # Validate cross-resource references only after every record is resolved.
    for tilemap_id, tilemap in document.asset_views.tilemaps():
        tileset = document.asset_views.tileset(tilemap.tileset.asset_id)
        if tileset is None:
            raise EditorResourceError(
                f"TileMap {tilemap_id} references unresolved Tileset {tilemap.tileset.asset_id}"
            )
        sprite_sheet = document.asset_views.sprite_sheet(tileset.sprite_sheet.asset_id)
        if sprite_sheet is None:
            raise EditorResourceError(
                f"Tileset {tilemap.tileset.asset_id} references unresolved SpriteSheet "
                f"{tileset.sprite_sheet.asset_id}"
            )
        tilemap.validate()
        tileset.validate(len(sprite_sheet.frames))

    return document.asset_views
