"""Local-only RPG Maker MV visual and audio reference catalog."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from PIL import Image

from .canonical import AssetSource, CanonicalAsset
from .local_reference import RPGMakerMVProjectLayout
from .rpg_maker_mv_database import MVReferenceIssue, RPGMakerMVDatabase


def _image_asset_id(relative: str) -> str:
    digest = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:12]
    readable = re.sub(r"[^A-Za-z0-9_.-]+", "_", relative.replace("/", "."))
    return f"mv.image.{digest}.{readable.strip('_')}"


@dataclass(frozen=True, slots=True)
class MVIconReference:
    index: int
    source: Path
    box: tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class MVAudioReference:
    kind: str
    name: str
    candidates: tuple[Path, ...]


@dataclass(slots=True)
class RPGMakerMVCatalog:
    layout: RPGMakerMVProjectLayout
    database: RPGMakerMVDatabase
    assets: tuple[CanonicalAsset, ...]
    issues: list[MVReferenceIssue]

    @classmethod
    def build(cls, layout: RPGMakerMVProjectLayout, database: RPGMakerMVDatabase) -> "RPGMakerMVCatalog":
        assets = []
        if layout.img is not None:
            for path in sorted(layout.img.glob("**/*.png")):
                relative = path.relative_to(layout.img).with_suffix("").as_posix()
                category = relative.split("/", 1)[0]
                kind = (
                    "tileset"
                    if category == "tilesets"
                    else (
                        "sprite_sheet" if category in {"characters", "faces", "sv_actors", "animations"} else "texture"
                    )
                )
                assets.append(
                    CanonicalAsset(
                        asset_id=_image_asset_id(relative),
                        kind=kind,
                        source=AssetSource(
                            str(path.resolve()),
                            provider="rpg_maker_mv",
                            provenance=(("development_fixture", True),),
                        ),
                        tags=frozenset({"source:rpg-maker-mv", f"mv:{category}"}),
                        metadata=(("mv_relative_path", path.relative_to(layout.root).as_posix()),),
                    )
                )
        return cls(layout, database, tuple(assets), list(database.issues))

    def category_root(self, category: str) -> Path:
        base = self.layout.root / "img"
        return base / str(category)

    def images_for(self, category: str) -> tuple[Path, ...]:
        root = self.category_root(category)
        return tuple(sorted(root.glob("*.png"))) if root.is_dir() else ()

    def resolve_image(self, category: str, name: str) -> Path | None:
        if not str(name):
            self.issues.append(MVReferenceIssue("image.empty", category, "empty image name"))
            return None
        path = self.category_root(category) / f"{name}.png"
        if path.is_file():
            return path.resolve()
        self.issues.append(MVReferenceIssue("image.missing", category, str(name)))
        return None

    def icon(self, index: int) -> MVIconReference | None:
        source = self.resolve_image("system", "IconSet")
        if source is None:
            return None
        index = int(index)
        with Image.open(source) as image:
            columns = image.width // 32
            rows = image.height // 32
        if index < 0 or index >= columns * rows:
            self.issues.append(MVReferenceIssue("icon.out_of_range", "IconSet.png", str(index)))
            return None
        column, row = index % columns, index // columns
        return MVIconReference(
            index,
            source,
            (column * 32, row * 32, (column + 1) * 32, (row + 1) * 32),
        )

    def audio(self, kind: str, name: str) -> MVAudioReference:
        root = self.layout.root / "audio" / str(kind)
        candidates = tuple(
            path.resolve() for suffix in (".ogg", ".m4a") if (path := root / f"{name}{suffix}").is_file()
        )
        if not candidates:
            self.issues.append(MVReferenceIssue("audio.missing", str(kind), str(name)))
        return MVAudioReference(str(kind), str(name), candidates)
