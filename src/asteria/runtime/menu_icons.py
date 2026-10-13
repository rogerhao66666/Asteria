"""Icons for items and equipment in the game's menus (AST-07).

An item's or equipment's ``icon_id`` names any of these, whichever the author finds easiest:

* a canonical asset of the project (kind ``icon``, ``texture`` or any image asset); a ``region``
  in its
  metadata (``[x, y, width, height]``) picks one cell of a sheet (an RPG Maker IconSet, an atlas);
* a legacy asset record id (its ``source_path``);
* a path to a PNG, relative to the project folder.

Nothing is required: a record without an icon shows its name only.
"""

from __future__ import annotations


def icon_source(project, icon_id):
    """``(image path or uri, region or None)`` for ``icon_id``, or None when it names nothing."""
    icon_id = str(icon_id or "").strip()
    if not icon_id or project is None:
        return None
    assets = project.assets
    try:
        asset = assets.resolve(icon_id)
    except (KeyError, ValueError):
        asset = None
    if asset is not None:
        meta = dict(asset.metadata)
        region = meta.get("region") or meta.get("atlas")
        if isinstance(region, dict):
            region = (
                region.get("x", 0),
                region.get("y", 0),
                region.get("width", 0),
                region.get("height", 0),
            )
        region = tuple(int(v) for v in region) if region else None
        return asset.source.uri, region
    record = assets.get(icon_id)
    if record is not None:
        return str(record.source_path), None
    if icon_id.lower().endswith(".png"):
        return icon_id, None
    return None


def record_icon_id(project, kind, key):
    """The icon id of a menu row: ``item``, ``equipment`` / ``candidate``, or ``""``."""
    db = project.rpg_database
    if kind == "item":  # the bag can hold equipment too
        record = db.items.get(key) or db.equipment.get(key)
    elif kind in ("equipment", "candidate"):
        record = db.equipment.get(key)
    else:
        record = None
    return getattr(record, "icon_id", "") if record is not None else ""
