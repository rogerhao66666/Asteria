"""The asset library: art packs kept beside the engine that any project can take pictures from.

The library is a folder of packs (``asset_library/<collection>/<pack>/...``, CC0 art with each
pack's readme). It is never loaded by a game: importing a picture copies it into the project
(``playable_assets/library/<pack>/...``) and registers it as a project asset, so the project
stays self-contained. ``ASTERIA_ASSET_LIBRARY`` points at another library folder.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .types import AssetRecord

IMAGE_SUFFIXES = (".png",)
PROJECT_FOLDER = "playable_assets/library"


def default_library_root():
    """``$ASTERIA_ASSET_LIBRARY``, else ``asset_library`` beside the engine's source tree."""
    override = os.environ.get("ASTERIA_ASSET_LIBRARY")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[3] / "asset_library"


@dataclass(frozen=True, slots=True)
class LibraryPack:
    pack_id: str  # "<collection>/<pack>"
    path: Path
    license_text: str

    @property
    def name(self):
        """``Foozle_2DS0005_Lucifer_Equipment_Pixel_Art`` -> ``Lucifer Equipment Pixel Art``."""
        parts = self.path.name.split("_")
        if len(parts) > 2 and parts[0].isalpha() and any(ch.isdigit() for ch in parts[1]):
            parts = parts[2:]
        return " ".join(parts)


def library_packs(root=None):
    """Every pack in the library, by id."""
    root = Path(root or default_library_root())
    packs = []
    if not root.is_dir():
        return ()
    for collection in sorted(p for p in root.iterdir() if p.is_dir()):
        for pack in sorted(p for p in collection.iterdir() if p.is_dir()):
            readme = next((f for f in sorted(pack.iterdir()) if f.suffix.lower() == ".txt"), None)
            text = readme.read_text(encoding="utf-8", errors="replace") if readme else ""
            packs.append(LibraryPack(f"{collection.name}/{pack.name}", pack, text))
    return tuple(packs)


def pack_images(pack):
    """The pictures of a pack, as paths relative to it (POSIX), sorted."""
    return tuple(
        sorted(
            PurePosixPath(*p.relative_to(pack.path).parts).as_posix()
            for p in pack.path.rglob("*")
            if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
        )
    )


def project_path_for(pack, relative):
    """Where an imported picture lives in a project (relative to the project folder)."""
    return f"{PROJECT_FOLDER}/{pack.path.name}/{relative}"


def import_into_project(project, project_dir, pack, relative, *, kind="texture"):
    """Copy ``relative`` of ``pack`` into the project and register it as an asset; a picture
    already imported returns its record unchanged. Returns the AssetRecord."""
    source = pack.path / relative
    if not source.is_file():
        raise FileNotFoundError(f"not in the library: {pack.pack_id}/{relative}")
    target_path = project_path_for(pack, relative)
    for record in project.assets.records():
        if record.source_path == target_path:
            return record
    target = Path(project_dir) / target_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    record = AssetRecord.create(
        kind=kind,
        source_path=target_path,
        importer="asset_library",
        metadata={"library": f"{pack.pack_id}/{relative}", "license": pack_license(pack)},
    )
    project.assets.add(record)
    return record


def pack_license(pack):
    """``CC0 1.0`` when the pack's readme grants it, else a pointer to the readme."""
    text = pack.license_text.lower()
    if "cc0" in text or "creative commons zero" in text or "public domain" in text:
        return "CC0 1.0"
    return "see the pack's readme"
