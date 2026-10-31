"""The picture of a database record, where the project has one: an actor or enemy shows its
battle portrait, or failing that the first frame of its battlefield sprite, in the records
list and at the top of its form (the way RPG Maker shows a face beside each actor).

The pictures come from the battle presentation library's ``combatant_visuals`` profile whose
id is the record's id; nothing is a field the author must fill in twice.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPixmapCache


def _profile(document, record_id):
    project = getattr(document, "project", None)
    library = getattr(project, "battle_presentation_library", None)
    if library is None or not record_id:
        return None
    try:
        return library.get("combatant_visuals", record_id)
    except (KeyError, ValueError):
        return None


def _asset_ids(profile):
    """``(portrait id, battlefield sprite id)`` of a combatant visual profile (or its dict)."""
    assets = getattr(profile, "assets", None)
    if assets is None and isinstance(profile, dict):
        assets = profile.get("assets") or {}
    if isinstance(assets, dict):
        return assets.get("portrait_asset_id"), assets.get("battlefield_asset_id")
    portrait = getattr(assets, "portrait_asset_id", None)
    return portrait, getattr(assets, "battlefield_asset_id", None)


def _portrait(document, asset_id):
    from asteria.runtime.menu_icons import icon_source

    from .image_tools import project_root

    source = icon_source(document.project, asset_id)
    if source is None:
        return None
    uri, region = source
    path = Path(uri)
    if not path.is_absolute():
        path = project_root(document) / path
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    return pixmap.copy(*region) if region else pixmap


def _first_frame(document, asset_id):
    """The first frame of a sprite sheet asset: a sheet the editor has loaded, or a battle
    sheet described by its canonical asset's ``frame_size`` and clips (the idle pose)."""
    from .scene_render import resolve_texture_source

    views = getattr(document, "asset_views", None)
    sheet = views.sprite_sheet(asset_id) if views is not None else None
    frames = list(getattr(sheet, "frames", None) or ())
    if frames:
        texture = getattr(getattr(sheet, "texture", None), "asset_id", None)
        path = resolve_texture_source(document, texture) if texture else None
        pixmap = QPixmap(str(path)) if path is not None else QPixmap()
        if pixmap.isNull():
            return None
        frame = frames[0]
        return pixmap.copy(int(frame.x), int(frame.y), int(frame.width), int(frame.height))
    return _canonical_frame(document, asset_id)


def _canonical_frame(document, asset_id):
    from .image_tools import project_root

    try:
        asset = document.project.assets.resolve(asset_id)
    except (KeyError, AttributeError):
        return None
    meta = asset.meta() if hasattr(asset, "meta") else {}
    size = meta.get("frame_size")
    uri = getattr(getattr(asset, "source", None), "uri", None)
    if not uri or not size:
        return None
    path = Path(uri)
    if not path.is_absolute():
        path = project_root(document) / path
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    width, height = (max(1, int(v)) for v in size)
    columns = max(1, pixmap.width() // width)
    clips = meta.get("clips") or {}
    idle = clips.get("idle") or {}
    first = (idle.get("frames") or [0])[0] if isinstance(idle, dict) else 0
    column, row = int(first) % columns, int(first) // columns
    return pixmap.copy(column * width, row * height, width, height)


def record_picture(document, record_id, size=56):
    """A QPixmap at most ``size`` px square for the record, or None when it has no picture."""
    profile = _profile(document, record_id)
    if profile is None:
        return None
    portrait_id, battlefield_id = _asset_ids(profile)
    key = f"asteria.record_picture/{id(document.project)}/{record_id}/{size}"
    cached = QPixmapCache.find(key)
    if cached is not None and not cached.isNull():
        return cached
    pixmap = _portrait(document, portrait_id) if portrait_id else None
    if pixmap is None and battlefield_id:
        pixmap = _first_frame(document, battlefield_id)
    if pixmap is None:
        return None
    if pixmap.width() > size or pixmap.height() > size:
        pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    QPixmapCache.insert(key, pixmap)
    return pixmap


def forget_pictures():
    """Drop the cached pictures (after the project or its assets changed)."""
    QPixmapCache.clear()
