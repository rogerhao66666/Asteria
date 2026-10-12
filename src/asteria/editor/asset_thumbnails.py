"""Best-effort icon thumbnails for the Assets panel.

Textures, sprite sheets, tilesets and canonical character sheets get their
actual pixels (first frame/tile); every other asset kind returns ``None`` so
the panel still lists it as plain text. Restored from 16a6ebd and extended to
canonical assets.
"""

from pathlib import Path

try:
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QIcon, QImage, QPixmap
except ImportError:  # pragma: no cover - editor without Qt
    QIcon = None

from .resource_resolver import asset_source_path
from .tile_palette import build_tile_palette

THUMBNAIL_SIZE = 24


class ImageCache:
    """Loads each image file once per panel refresh."""

    def __init__(self):
        self._images = {}

    def get(self, path):
        path = Path(path)
        if path not in self._images:
            image = QImage(str(path)) if path.is_file() else None
            self._images[path] = None if image is None or image.isNull() else image
        return self._images[path]


def _icon(image, rect=None, size=THUMBNAIL_SIZE):
    if rect is not None:
        image = image.copy(QRect(*(int(v) for v in rect)))
        if image.isNull():
            return None
    pixmap = QPixmap.fromImage(image).scaled(size, size, Qt.KeepAspectRatio, Qt.FastTransformation)
    return QIcon(pixmap)


def _frame_rect(frame):
    return (frame.x, frame.y, frame.width, frame.height)


def _texture_image(document, texture_asset_id, cache):
    record = document.project.assets.get(texture_asset_id)
    if record is None:
        return None
    path = asset_source_path(document, record)
    return None if path is None else cache.get(path)


def asset_thumbnail(document, record, cache):
    """Return a QIcon for an AssetRecord, or None to fall back to plain text."""
    if QIcon is None or document.project is None:
        return None
    try:
        if record.kind == "texture":
            path = asset_source_path(document, record)
            image = cache.get(path) if path is not None else None
            return None if image is None else _icon(image)
        if record.kind == "sprite_sheet":
            sheet = document.asset_views.sprite_sheet(record.id)
            if sheet is None or not sheet.frames:
                return None
            image = _texture_image(document, sheet.texture.asset_id, cache)
            return None if image is None else _icon(image, _frame_rect(sheet.frames[0]))
        if record.kind == "tileset":
            tileset = document.asset_views.tileset(record.id)
            if tileset is None or not tileset.tiles:
                return None
            sheet = document.asset_views.sprite_sheet(tileset.sprite_sheet.asset_id)
            if sheet is None or not sheet.frames:
                return None
            image = _texture_image(document, sheet.texture.asset_id, cache)
            first = build_tile_palette(tileset)[0]
            if image is None or not 0 <= first.frame_index < len(sheet.frames):
                return None
            return _icon(image, _frame_rect(sheet.frames[first.frame_index]))
    except Exception:
        return None
    return None


def canonical_asset_thumbnail(document, asset, cache):
    """QIcon for a canonical image asset (first frame for character sheets), or None."""
    if QIcon is None or document.project is None:
        return None
    try:
        path = Path(asset.source.uri)
        if not path.is_absolute():
            if document.file_path is None:
                return None
            path = document.file_path.parent / path
        image = cache.get(path)
        if image is None:
            return None
        meta = dict(asset.metadata)
        frame_size = meta.get("frame_size")
        if meta.get("region"):  # one cell of a sheet (menu icons, AST-07)
            return _icon(image, meta["region"])
        if asset.kind == "character.walking" and frame_size:
            width, height = (int(frame_size[0]), int(frame_size[1]))
            return _icon(image, (width, 0, width, height))  # down-facing standing frame
        return _icon(image)
    except Exception:
        return None
