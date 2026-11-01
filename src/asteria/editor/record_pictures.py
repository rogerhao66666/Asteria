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
        pixmap = _texture(path) if path is not None else QPixmap()
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
    pixmap = _texture(path)
    if pixmap.isNull():
        return None
    width, height = (max(1, int(v)) for v in size)
    columns = max(1, pixmap.width() // width)
    clips = meta.get("clips") or {}
    idle = clips.get("idle") or {}
    first = (idle.get("frames") or [0])[0] if isinstance(idle, dict) else 0
    column, row = int(first) % columns, int(first) // columns
    return pixmap.copy(column * width, row * height, width, height)


def _texture(path):
    """The picture file at ``path`` (QPixmapCache keeps it: a list of sheets cut from the
    same few files reads each once)."""
    key = f"asteria.texture/{path}"
    cached = QPixmapCache.find(key)
    if cached is not None and not cached.isNull():
        return cached
    pixmap = QPixmap(str(path))
    if not pixmap.isNull():
        QPixmapCache.insert(key, pixmap)
    return pixmap


def sprite_sheet_frame(document, asset_id, frame_index):
    """One frame of a sprite sheet the editor has loaded, as a QPixmap, or None."""
    from .scene_render import resolve_texture_source

    views = getattr(document, "asset_views", None)
    sheet = views.sprite_sheet(asset_id) if views is not None and asset_id else None
    frames = list(getattr(sheet, "frames", None) or ())
    if not frames:
        return None
    frame = frames[max(0, min(int(frame_index), len(frames) - 1))]
    texture = getattr(getattr(sheet, "texture", None), "asset_id", None)
    path = resolve_texture_source(document, texture) if texture else None
    pixmap = _texture(path) if path is not None else QPixmap()
    if pixmap.isNull():
        return None
    return pixmap.copy(int(frame.x), int(frame.y), int(frame.width), int(frame.height))


def sprite_sheet_pixmap(document, asset_id):
    """The first (idle) frame of a sprite sheet asset as a QPixmap, or None; a sheet whose
    first frame is empty (a tileset starting with a clear tile) shows its first drawn one."""
    if not asset_id or getattr(document, "project", None) is None:
        return None
    pixmap = _first_frame(document, str(asset_id))
    if pixmap is None or not _blank(pixmap):
        return pixmap
    views = getattr(document, "asset_views", None)
    sheet = views.sprite_sheet(str(asset_id)) if views is not None else None
    for index in range(1, min(len(getattr(sheet, "frames", None) or ()), 64)):
        frame = sprite_sheet_frame(document, str(asset_id), index)
        if frame is not None and not _blank(frame):
            return frame
    return pixmap


def _blank(pixmap):
    from PySide6.QtGui import QRegion

    return pixmap.hasAlphaChannel() and QRegion(pixmap.mask()).isEmpty()


def _map_look(document, record_id):
    """An actor's look on the map (the sheet its entities draw), as ``(sheet id, frame)``."""
    from .actor_appearance import get_actor_appearance

    try:
        look = get_actor_appearance(document, record_id)
    except Exception:  # noqa: BLE001 - a broken sidecar is not a reason to hide the form
        return None, 0
    if look is None or not look.sprite_sheet_asset_id:
        return None, 0
    return look.sprite_sheet_asset_id, int(look.frame_index)


def record_picture(document, record_id, size=56):
    """A QPixmap at most ``size`` px square for the record, or None when it has no picture:
    an actor's look on the map first, else its battle portrait, else its battlefield sprite."""
    if not record_id or getattr(document, "project", None) is None:
        return None
    sheet_id, frame = _map_look(document, record_id)
    profile = _profile(document, record_id)
    portrait_id, battlefield_id = _asset_ids(profile) if profile is not None else (None, None)
    if sheet_id is None and profile is None:
        return None
    key = (
        f"asteria.record_picture/{id(document.project)}/{record_id}/{sheet_id}/"
        f"{battlefield_id}/{portrait_id}/{size}"
    )
    cached = QPixmapCache.find(key)
    if cached is not None and not cached.isNull():
        return cached
    pixmap = sprite_sheet_frame(document, sheet_id, frame) if sheet_id else None
    if pixmap is None and portrait_id:
        pixmap = _portrait(document, portrait_id)
    if pixmap is None and battlefield_id:
        pixmap = _first_frame(document, battlefield_id)
    if pixmap is None:
        return None
    pixmap = framed(pixmap, size)
    QPixmapCache.insert(key, pixmap)
    return pixmap


def framed(pixmap, size):
    """``pixmap`` without its empty margin, filling a ``size`` square: a large picture made
    smaller smoothly, a small pixel-art frame made larger with sharp pixels - drawn at the
    screen's own resolution, so a Retina screen gets twice the pixels."""
    from PySide6.QtGui import QGuiApplication, QRegion

    if pixmap.hasAlphaChannel():
        box = QRegion(pixmap.mask()).boundingRect()
        if box.isValid() and not box.isEmpty():
            pixmap = pixmap.copy(box)
    screen = QGuiApplication.primaryScreen()
    ratio = max(1.0, screen.devicePixelRatio()) if screen is not None else 1.0
    side = max(pixmap.width(), pixmap.height(), 1)
    target = round(size * ratio)
    mode = Qt.SmoothTransformation if side > target else Qt.FastTransformation
    scaled = pixmap.scaled(target, target, Qt.KeepAspectRatio, mode)
    scaled.setDevicePixelRatio(ratio)
    return scaled


def forget_pictures():
    """Drop the cached pictures (after the project or its assets changed)."""
    QPixmapCache.clear()
