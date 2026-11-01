"""Bringing a picture file into a project as a character, from anywhere on disk or from the
project's own picture folders.

A project sorts its pictures by folder: whatever PNG sits in a ``characters`` folder of the
project (``playable_assets/characters/hero.png``) is offered as a character picture before it
is used, and choosing it makes it a sprite sheet. A file from elsewhere is first copied into
``playable_assets/characters/`` so the project stays self-contained.

A map character is a 3x4 walking sheet (columns are the steps, rows face down, left, right,
up - the RPG Maker layout): it becomes a sprite sheet and its walking animations, beside the
picture (``hero_sheet.json``, ``hero_clips.json``). A battle picture is any image: it becomes
a one-frame battle sprite (``battle.combatant.<name>``).
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path, PurePosixPath

from .picture_categories import category, folder_category

CHARACTER_FOLDER = "playable_assets/characters"
WALK_COLUMNS, WALK_ROWS = 3, 4
_DIRECTIONS = ("down", "left", "right", "up")


class PictureImportError(ValueError):
    pass


def _project_dir(document):
    if getattr(document, "project", None) is None or document.file_path is None:
        raise PictureImportError("Save the project first: pictures are copied into its folder")
    return Path(document.file_path).parent


def _key(text):
    key = re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")
    return key or "picture"


def _known_paths(project):
    paths = {str(record.source_path) for record in project.assets.records()}
    for asset in project.assets.snapshot():
        uri = getattr(getattr(asset, "source", None), "uri", "")
        if uri:
            paths.add(str(PurePosixPath(uri)))
    return paths


def folder_pictures(document, category_id="characters"):
    """PNG files in the project's folders for ``category_id`` that are not project assets
    yet, as paths relative to the project folder (POSIX), sorted."""
    try:
        root = _project_dir(document)
    except PictureImportError:
        return ()
    known = _known_paths(document.project)
    found = []
    for folder in category(category_id).folders:
        for directory in (root / "playable_assets" / folder, root / folder):
            if not directory.is_dir():
                continue
            for path in directory.rglob("*.png"):
                relative = path.relative_to(root).as_posix()
                if relative not in known and folder_category(relative) == category_id:
                    found.append(relative)
    return tuple(sorted(set(found)))


def _into_project(document, path, subfolder=""):
    """``path`` inside the project: as it is when it already is, else copied (under a free
    name) into the characters folder. Returns ``(absolute, relative POSIX)``."""
    root = _project_dir(document)
    source = Path(path)
    if not source.is_absolute():
        source = root / source
    if not source.is_file():
        raise PictureImportError(f"No such picture: {path}")
    try:
        return source, source.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        pass
    folder = root / CHARACTER_FOLDER / subfolder
    folder.mkdir(parents=True, exist_ok=True)
    stem, target, counter = _key(source.stem), None, 1
    while target is None or target.exists():
        target = folder / (f"{stem}.png" if counter == 1 else f"{stem}_{counter}.png")
        counter += 1
    shutil.copyfile(source, target)
    return target, target.relative_to(root).as_posix()


def _image_size(path):
    from PIL import Image

    with Image.open(path) as image:
        return image.size


def _write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def import_walking_picture(document, path, name=None):
    """Make the 3x4 walking sheet at ``path`` a sprite sheet of the project (with its walking
    animations); returns the sprite sheet's asset id. The caller resolves the project's
    resources again so the editor draws it."""
    from asteria.assets.types import AssetRecord

    project = document.project
    source = Path(path) if Path(path).is_absolute() else _project_dir(document) / path
    if not source.is_file():
        raise PictureImportError(f"No such picture: {path}")
    width, height = _image_size(source)
    if width % WALK_COLUMNS or height % WALK_ROWS:
        raise PictureImportError(
            f"{source.name} is {width}x{height}: a walking sheet is 3 columns by 4 rows "
            "of equal frames (down, left, right, up)"
        )
    absolute, relative = _into_project(document, source)
    frame_w, frame_h = width // WALK_COLUMNS, height // WALK_ROWS
    label = str(name or absolute.stem.replace("_", " ").title())
    meta = {"category": "characters", "license": "the author's own"}
    texture = AssetRecord.create(
        kind="texture", source_path=relative, name=label, importer="editor_picture", metadata=meta
    )
    stem = relative.rsplit(".", 1)[0]
    sheet = AssetRecord.create(
        kind="sprite_sheet",
        source_path=f"{stem}_sheet.json",
        name=f"{label} Sheet",
        importer="editor_picture",
        metadata=meta,
    )
    clips = AssetRecord.create(
        kind="animation",
        source_path=f"{stem}_clips.json",
        name=f"{label} Animations",
        importer="editor_picture",
        metadata=meta,
    )
    frames = [
        {
            "x": column * frame_w,
            "y": row * frame_h,
            "width": frame_w,
            "height": frame_h,
            "pivot_x": 0.5,
            "pivot_y": 1.0,
        }
        for row in range(WALK_ROWS)
        for column in range(WALK_COLUMNS)
    ]
    animations = {}
    for row, direction in enumerate(_DIRECTIONS):
        base = row * WALK_COLUMNS
        animations[f"idle_{direction}"] = {
            "keyframes": [{"frame_index": base + 1, "duration": 0.4}],
            "loop": True,
        }
        animations[f"walk_{direction}"] = {  # the middle cell stands between the two steps
            "keyframes": [{"frame_index": base + i, "duration": 0.12} for i in (1, 2, 1, 0)],
            "loop": True,
        }
    root = _project_dir(document)
    _write_json(root / sheet.source_path, {"frames": frames, "texture_asset_id": texture.id})
    _write_json(root / clips.source_path, {"clips": animations})
    for record in (texture, sheet, clips):
        project.assets.add(record)
    return sheet.id


def import_battle_picture(document, path, name=None):
    """Make the image at ``path`` a one-frame battle sprite (``battle.combatant.<name>``);
    returns its asset id."""
    from asteria.assets.canonical import AssetSource, CanonicalAsset

    project = document.project
    absolute, relative = _into_project(document, path, "battle")
    width, height = _image_size(absolute)
    base = f"battle.combatant.{_key(name or absolute.stem)}"
    asset_id, counter = base, 2
    known = {asset.asset_id for asset in project.assets.snapshot()}
    while asset_id in known:
        asset_id, counter = f"{base}_{counter}", counter + 1
    clip = {"frames": [0], "frame_duration": 0.2, "loop": True}
    project.assets.register(
        CanonicalAsset(
            asset_id,
            "sprite_sheet",
            AssetSource(relative, "project", (("license", "the author's own"),)),
            tags=frozenset({"battle", "combatant"}),
            metadata=(
                ("clips", {"idle": clip}),
                ("frame_size", (int(width), int(height))),
                ("pivot", (0.5, 1.0)),
                ("category", "characters"),
            ),
        )
    )
    return asset_id
