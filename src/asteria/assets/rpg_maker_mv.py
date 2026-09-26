"""RPG Maker MV image adapter.

MV layout knowledge ends in this module. Its output is generic metadata and a
canonical Asteria asset; runtime, scene, battle, and presentation code do not
depend on MV constants.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from .canonical import AssetSource, CanonicalAsset


_LAYOUTS = {
    "faces": "faces_4x2",
    "sv_actors": "sv_actor_9x6",
    "enemies": "single_image",
    "sv_enemies": "single_image",
    "tilesets": "tileset_source",
    "animations": "animation_sheet_5x5",
    "pictures": "single_image",
    "parallaxes": "single_image",
}

_KINDS = {
    "characters": "sprite_sheet",
    "faces": "sprite_sheet",
    "sv_actors": "sprite_sheet",
    "enemies": "texture",
    "sv_enemies": "texture",
    "tilesets": "tileset",
    "animations": "sprite_sheet",
    "pictures": "texture",
    "parallaxes": "texture",
}


@dataclass(frozen=True, slots=True)
class RPGMakerMVImage:
    source_path: Path
    category: str
    source_size: tuple[int, int]
    alpha: bool
    layout: str
    frame_size: tuple[int, int] | None = None
    character_count: int | None = None
    frames_per_direction: int | None = None
    directions: tuple[str, ...] = ()
    idle_frame: int | None = None
    anchor: tuple[float, float] = (0.5, 0.5)
    object_character: bool = False


class RPGMakerMVImporter:
    """Inspect real MV PNGs and translate their source layout to Asteria data."""

    categories = frozenset({"characters", *_LAYOUTS})

    @staticmethod
    def _category(path: Path) -> str:
        parts = path.parts
        for index in range(len(parts) - 2):
            if parts[index] == "img" and parts[index + 1] in RPGMakerMVImporter.categories:
                return parts[index + 1]
        raise ValueError(f"unsupported RPG Maker MV category: {path}")

    def inspect(self, source_path: str | Path) -> RPGMakerMVImage:
        path = Path(source_path).expanduser().resolve()
        category = self._category(path)
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                width, height = image.size
                alpha = "A" in image.getbands() or "transparency" in image.info
        except (OSError, UnidentifiedImageError, ValueError) as exc:
            raise ValueError(f"invalid RPG Maker MV image: {path}") from exc

        if width <= 0 or height <= 0:
            raise ValueError(f"invalid RPG Maker MV image dimensions: {path}")

        if category == "characters":
            object_character = path.stem.startswith("!")
            single_character = path.stem.startswith("$") or path.stem.startswith("!$")
            columns, rows = (3, 4) if single_character else (12, 8)
            if width % columns or height % rows:
                raise ValueError(f"invalid RPG Maker MV character sheet layout: {path}")
            return RPGMakerMVImage(
                source_path=path,
                category=category,
                source_size=(width, height),
                alpha=alpha,
                layout="character_single_3x4" if single_character else "characters_12x8",
                frame_size=(width // columns, height // rows),
                character_count=1 if single_character else 8,
                frames_per_direction=3,
                directions=("down", "left", "right", "up"),
                idle_frame=1,
                anchor=(0.5, 1.0),
                object_character=object_character,
            )

        frame_size = None
        if category == "faces":
            frame_size = (width // 4, height // 2)
        elif category == "sv_actors":
            frame_size = (width // 9, height // 6)
        elif category == "animations":
            frame_size = (width // 5, height // 5)

        return RPGMakerMVImage(
            source_path=path,
            category=category,
            source_size=(width, height),
            alpha=alpha,
            layout=_LAYOUTS[category],
            frame_size=frame_size,
            anchor=(0.5, 1.0)
            if category in {"sv_actors", "enemies", "sv_enemies"}
            else (0.5, 0.5),
        )

    def to_canonical(self, imported: RPGMakerMVImage, *, asset_id: str) -> CanonicalAsset:
        metadata = self.to_dict(imported)
        metadata.pop("source_path")
        return CanonicalAsset(
            asset_id=asset_id,
            kind=_KINDS[imported.category],
            source=AssetSource(
                str(imported.source_path),
                provider="rpg_maker_mv",
                provenance=(("development_fixture", True),),
            ),
            tags=frozenset({"source:rpg-maker-mv", f"mv:{imported.category}"}),
            metadata=tuple(sorted(metadata.items())),
        )

    @staticmethod
    def walk_clip_boxes(
        imported: RPGMakerMVImage, *, character_index: int, direction: str
    ) -> tuple[tuple[int, int, int, int], ...]:
        if imported.category != "characters" or imported.frame_size is None:
            raise ValueError("walk clips require an MV character sheet")
        if character_index < 0 or character_index >= (imported.character_count or 0):
            raise ValueError("character_index out of range")
        try:
            direction_row = imported.directions.index(direction)
        except ValueError as exc:
            raise ValueError(f"unsupported direction: {direction}") from exc
        frame_width, frame_height = imported.frame_size
        characters_across = 1 if imported.character_count == 1 else 4
        block_column = character_index % characters_across
        block_row = character_index // characters_across
        first_column = block_column * 3
        source_row = block_row * 4 + direction_row
        return tuple(
            (
                (first_column + frame) * frame_width,
                source_row * frame_height,
                (first_column + frame + 1) * frame_width,
                (source_row + 1) * frame_height,
            )
            for frame in range(3)
        )

    @staticmethod
    def side_view_motion_boxes(
        imported: RPGMakerMVImage, *, motion_index: int
    ) -> tuple[tuple[int, int, int, int], ...]:
        if imported.category != "sv_actors" or imported.frame_size is None:
            raise ValueError("side-view motions require an MV sv_actor sheet")
        if motion_index < 0 or motion_index >= 18:
            raise ValueError("motion_index out of range")
        frame_width, frame_height = imported.frame_size
        motion_column = motion_index % 3
        motion_row = motion_index // 3
        first_column = motion_column * 3
        return tuple(
            (
                (first_column + frame) * frame_width,
                motion_row * frame_height,
                (first_column + frame + 1) * frame_width,
                (motion_row + 1) * frame_height,
            )
            for frame in range(3)
        )

    @staticmethod
    def to_dict(imported: RPGMakerMVImage) -> dict[str, Any]:
        data = asdict(imported)
        data["source_path"] = str(imported.source_path)
        return data

    @staticmethod
    def from_dict(data: dict[str, Any]) -> RPGMakerMVImage:
        values = dict(data)
        values["source_path"] = Path(values["source_path"])
        for key in ("source_size", "frame_size", "directions", "anchor"):
            if values.get(key) is not None:
                values[key] = tuple(values[key])
        return RPGMakerMVImage(**values)
