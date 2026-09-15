"""Best-effort icon thumbnails for the Assets panel.

Mirrors the real-art-over-placeholder-text pattern already used by
TilePaletteWidget: a texture/sprite-sheet/tileset gets its actual pixels,
everything else (tilemap, animation, audio, font, shader, data) falls back
to no icon so the panel still lists it as plain text.
"""

try:
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QIcon, QPixmap
except ImportError:
    QIcon = None

from .resource_resolver import asset_source_path
from .tile_palette import build_tile_palette

THUMBNAIL_SIZE = 24


def _frame_icon(image, frame, size=THUMBNAIL_SIZE):
    cropped = image.copy(
        QRect(int(frame.x), int(frame.y), int(frame.width), int(frame.height))
    )
    if cropped.isNull():
        return None
    pixmap = QPixmap.fromImage(cropped).scaled(
        size, size, Qt.KeepAspectRatio, Qt.FastTransformation
    )
    return QIcon(pixmap)


def _texture_frame(document, texture_asset_id, cache):
    texture_record = document.project.assets.get(texture_asset_id)
    if texture_record is None:
        return None
    path = asset_source_path(document, texture_record)
    if path is None:
        return None
    return cache.get(path)


def asset_thumbnail(document, record, cache):
    """Return a QIcon for `record`, or None to fall back to plain text."""
    if QIcon is None or document.project is None:
        return None
    try:
        if record.kind == "texture":
            path = asset_source_path(document, record)
            image = cache.get(path) if path is not None else None
            if image is None or image.isNull():
                return None
            pixmap = QPixmap.fromImage(image).scaled(
                THUMBNAIL_SIZE, THUMBNAIL_SIZE, Qt.KeepAspectRatio, Qt.FastTransformation
            )
            return QIcon(pixmap)

        if record.kind == "sprite_sheet":
            sprite_sheet = document.asset_views.sprite_sheet(record.id)
            if sprite_sheet is None or not sprite_sheet.frames:
                return None
            image = _texture_frame(document, sprite_sheet.texture.asset_id, cache)
            if image is None:
                return None
            return _frame_icon(image, sprite_sheet.frames[0])

        if record.kind == "tileset":
            tileset = document.asset_views.tileset(record.id)
            if tileset is None or not tileset.tiles:
                return None
            sprite_sheet = document.asset_views.sprite_sheet(
                tileset.sprite_sheet.asset_id
            )
            if sprite_sheet is None or not sprite_sheet.frames:
                return None
            image = _texture_frame(document, sprite_sheet.texture.asset_id, cache)
            if image is None:
                return None
            first_tile = build_tile_palette(tileset)[0]
            if not 0 <= first_tile.frame_index < len(sprite_sheet.frames):
                return None
            return _frame_icon(image, sprite_sheet.frames[first_tile.frame_index])
    except Exception:
        return None
    return None
