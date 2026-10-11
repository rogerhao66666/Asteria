"""Generic character visuals for placing a playable character on a map.

A ``CharacterVisualSet`` is what ``CreateCharacterCommand`` needs: a walking
sprite sheet as a canonical asset (first in ``canonical_assets``), its frame
size and standing anchor, and optionally files the command owns. It can come
from any source — a plain walking sheet from a free asset pack or a
Character Generator bundle — so character placement does not depend on the
Generator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .canonical import AssetSource, CanonicalAsset

WALK_COLUMNS = 3
WALK_ROWS = 4  # down, left, right, up


def _key(value):
    key = re.sub(r"[^a-z0-9_]+", "_", str(value).strip().lower()).strip("_")
    if not key:
        raise ValueError("character key is required")
    return key


@dataclass(frozen=True, slots=True)
class CharacterVisualSet:
    key: str
    canonical_assets: tuple[CanonicalAsset, ...]
    frame_size: tuple[int, int]
    anchor: tuple[int, int]
    owned_paths: tuple[Path, ...] = ()

    def __post_init__(self):
        if not self.canonical_assets or self.canonical_assets[0].kind != "character.walking":
            raise ValueError("first canonical asset must be a character.walking sheet")
        width, height = (int(self.frame_size[0]), int(self.frame_size[1]))
        if width <= 0 or height <= 0:
            raise ValueError("frame size must be positive")

    @property
    def walking_asset(self):
        return self.canonical_assets[0]

    @classmethod
    def from_walking_sheet(cls, path, *, key, uri=None, frame_size=None):
        """Wrap a 3x4 walking sheet (rows down/left/right/up) that the project does not own.

        ``uri`` is the path stored in the project (relative to the project
        file when possible); it defaults to ``path``. ``frame_size`` defaults
        to the image size divided into the 3x4 grid.
        """
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(path)
        if frame_size is None:
            from PIL import Image

            with Image.open(path) as image:
                width, height = image.size
            if width % WALK_COLUMNS or height % WALK_ROWS:
                raise ValueError(f"{path.name} is not a 3x4 walking sheet ({width}x{height})")
            frame_size = (width // WALK_COLUMNS, height // WALK_ROWS)
        key = _key(key)
        frame_size = (int(frame_size[0]), int(frame_size[1]))
        asset = CanonicalAsset(
            f"character/{key}/walking",
            "character.walking",
            AssetSource(str(uri if uri is not None else path), "walking_sheet"),
            tags=frozenset({"character"}),
            metadata=(("representation", "walking"),),
        )
        return cls(key, (asset,), frame_size, (frame_size[0] // 2, frame_size[1]))
