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

from asteria.assets.canonical import AssetSource, CanonicalAsset
from asteria.assets.types import AssetRecord
from asteria.editor.assets.picture_categories import category, folder_category, paired_clip_set_id

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


# a map clip each battle clip is taken from (heroes stand on the right facing left)
_BATTLE_FROM_MAP = {"idle": ("idle_left", "idle_down"), "move": ("walk_left", "walk_down")}


def battle_sheet_for(document, sheet_id):
    """A battle sprite for the map sheet ``sheet_id`` (any character the map can show): the
    sheet itself when it is a battle sprite already, else one made of the same picture, frame
    size and frames - its idle and move clips from the sheet's own (made once, then reused).
    Returns the battle asset id."""

    project = document.project
    known = {asset.asset_id: asset for asset in project.assets.snapshot()}
    if sheet_id in known and "combatant" in getattr(known[sheet_id], "tags", ()):
        return sheet_id
    views = document.asset_views
    sheet = views.sprite_sheet(sheet_id)
    texture = project.assets.get(str(sheet.texture.asset_id))
    if texture is None or not sheet.frames:
        raise PictureImportError(f"{sheet_id}: no picture to draw in battle")
    first = sheet.frames[0]
    size = (int(first.width), int(first.height))
    source = str(texture.source_path)
    for asset in known.values():  # made before: the same picture, the same frames
        meta = dict(getattr(asset, "metadata", ()) or ())
        same_frame = tuple(meta.get("frame_size", ())) == size
        if asset.source.uri == source and same_frame and "combatant" in asset.tags:
            return asset.asset_id
    width, height = _image_size(_project_dir(document) / source)
    columns = max(1, width // size[0])
    grid = all(  # the battle sheet cuts the picture in a grid: the map frames must be it
        (f.x, f.y) == ((i % columns) * size[0], (i // columns) * size[1])
        for i, f in enumerate(sheet.frames)
    )
    clips = {}
    record = project.assets.get(sheet_id)

    clip_set_id = paired_clip_set_id(project, record) if record is not None else None
    clip_set = views.clip_set(clip_set_id) if clip_set_id else None
    for battle_clip, names in _BATTLE_FROM_MAP.items():
        clip = next((clip_set.clips[n] for n in names if clip_set and n in clip_set.clips), None)
        if clip is None or not grid:
            continue
        clips[battle_clip] = {
            "frames": [k.frame_index for k in clip.keyframes],
            "frame_duration": float(clip.keyframes[0].duration) if clip.keyframes else 0.2,
            "loop": True,
        }
    clips.setdefault("idle", {"frames": [0], "frame_duration": 0.2, "loop": True})
    from asteria.editor.records.sprite_sheet_picker import sheet_label

    base = f"battle.combatant.{_key(sheet_label(document, sheet_id))}"
    asset_id, counter = base, 2
    while asset_id in known:
        asset_id, counter = f"{base}_{counter}", counter + 1
    project.assets.register(
        CanonicalAsset(
            asset_id,
            "sprite_sheet",
            AssetSource(source, "project", (("license", "as the map picture's"),)),
            tags=frozenset({"battle", "combatant"}),
            metadata=(
                ("clips", clips),
                ("frame_size", size),
                ("pivot", (float(first.pivot_x), float(first.pivot_y))),
                ("category", "characters"),
            ),
        )
    )
    return asset_id
