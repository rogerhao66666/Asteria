"""What kind of picture a sprite sheet is - a character (a hero, a monster: anything that walks
or fights), a map tileset, a thing on the map, an item, an icon, an effect, a piece of UI - so a
list of pictures shows the kind a field wants and not every sheet in the project.

The kind is, in order: the asset's own ``category`` (metadata on the record, or a tag on a
canonical asset), the folder the picture sits in (``.../characters/hero.png``: a project
sorts its own pictures by putting them in folders), else what the sheet is used as - a sheet
a tileset cuts is a tileset, a sheet with walking or idle clips is a character, a battle
combatant is a character and a battle effect an effect, a single-frame sheet a map object.
Monsters are characters: anything can walk the map or fight.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True, slots=True)
class PictureCategory:
    category_id: str
    label: str
    folders: tuple[str, ...]  # folder names that put a picture in this category


CATEGORIES = (
    PictureCategory(
        "characters", "Characters", ("characters", "character", "monsters", "enemies")
    ),
    PictureCategory("tilesets", "Map Tiles", ("tilesets", "tileset", "tiles")),
    PictureCategory("objects", "Map Objects", ("objects", "props", "doodads")),
    PictureCategory("items", "Items & Gear", ("items", "equipment", "gear", "pickups")),
    PictureCategory("icons", "Icons", ("icons",)),
    PictureCategory("effects", "Effects", ("effects", "vfx", "fx")),
    PictureCategory("ui", "UI & Numbers", ("ui", "hud", "numbers", "fonts")),
    PictureCategory("backgrounds", "Backgrounds", ("backgrounds", "battlebacks", "parallax")),
)
OTHER = PictureCategory("other", "Other", ())
_BY_ID = {c.category_id: c for c in (*CATEGORIES, OTHER)}
_BY_FOLDER = {folder: c.category_id for c in CATEGORIES for folder in c.folders}
_TAGS = {
    "character": "characters",
    "combatant": "characters",
    "vfx": "effects",
    "icon": "icons",
    "ui": "ui",
}


def category(category_id):
    return _BY_ID.get(str(category_id), OTHER)


def folder_category(path):
    """The category a path's folders put it in (the innermost that names one), or None."""
    for part in reversed(PurePosixPath(str(path).replace("\\", "/")).parts[:-1]):
        found = _BY_FOLDER.get(part.lower())
        if found is not None:
            return found
    return None


def _tileset_sheets(views):
    sheets = set()
    for tileset_id in views.tileset_ids() if views is not None else ():
        tileset = views.tileset(tileset_id)
        ref = getattr(getattr(tileset, "sprite_sheet", None), "asset_id", None)
        if ref:
            sheets.add(str(ref))
    return sheets


def _clip_names(project, views, sheet_id, record):
    """The clips of the animation set beside a sheet (``x_sheet.json`` / ``x_clips.json``)."""
    clip_set_id = paired_clip_set_id(project, record)
    clip_set = views.clip_set(clip_set_id) if clip_set_id else None
    return set(getattr(clip_set, "clips", {}) or ())


def paired_clip_set_id(project, record):
    """The animation record that goes with a sprite sheet record: the one whose file has the
    same stem (``look_warrior_sheet.json`` -> ``look_warrior_clips.json``), or None."""
    if record is None or project is None:
        return None
    stem = str(record.source_path).rsplit(".", 1)[0].removesuffix("_sheet")
    for other in project.assets.records():
        if other.kind == "animation":
            if str(other.source_path).rsplit(".", 1)[0].removesuffix("_clips") == stem:
                return other.id
    return None


def _walks(clips):
    return any(name.split("_", 1)[0] in ("walk", "idle", "run") for name in clips)


def sheet_category(document, sheet_id, *, _tiles=None):
    """The category id of a sprite sheet (a record, or a canonical battle asset)."""
    project = getattr(document, "project", None)
    views = getattr(document, "asset_views", None)
    if project is None:
        return OTHER.category_id
    record = project.assets.get(sheet_id)
    if record is not None:
        stated = (record.metadata or {}).get("category")
        if stated in _BY_ID:
            return stated
        texture = _texture_record(project, views, sheet_id)
        for path in (record.source_path, getattr(texture, "source_path", "")):
            found = folder_category(path) if path else None
            if found is not None:
                return found
        tiles = _tiles if _tiles is not None else _tileset_sheets(views)
        if sheet_id in tiles:
            return "tilesets"
        sheet = views.sprite_sheet(sheet_id) if views is not None else None
        if len(getattr(sheet, "frames", ()) or ()) <= 1:
            return "objects"  # a still picture, even with walking clips: a house, a chest
        if views is not None and _walks(_clip_names(project, views, sheet_id, record)):
            return "characters"
        return OTHER.category_id
    try:
        asset = project.assets.resolve(sheet_id)
    except (KeyError, AttributeError):
        return OTHER.category_id
    meta = asset.meta() if hasattr(asset, "meta") else {}
    if meta.get("category") in _BY_ID:
        return meta["category"]
    for tag in sorted(getattr(asset, "tags", ()) or ()):
        if tag in _BY_ID:
            return tag
        if tag in _TAGS:
            return _TAGS[tag]
    uri = getattr(getattr(asset, "source", None), "uri", "") or ""
    return folder_category(uri) or OTHER.category_id


def _texture_record(project, views, sheet_id):
    sheet = views.sprite_sheet(sheet_id) if views is not None else None
    texture_id = getattr(getattr(sheet, "texture", None), "asset_id", None)
    return project.assets.get(texture_id) if texture_id else None


def sheets_by_category(document, sheet_ids):
    """``{category id: [sheet ids]}`` for ``sheet_ids``, in their order."""
    tiles = _tileset_sheets(getattr(document, "asset_views", None))
    grouped = {}
    for sheet_id in sheet_ids:
        grouped.setdefault(sheet_category(document, sheet_id, _tiles=tiles), []).append(sheet_id)
    return grouped
