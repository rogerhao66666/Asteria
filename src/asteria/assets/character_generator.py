from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Mapping, Sequence
import json
from PIL import Image

DIRECTIONS = ("down", "left", "right", "up")
LAYER_ORDER = ("body", "eyes", "hair_back", "outfit", "armor", "hair_front", "accessory")

@dataclass(frozen=True)
class CharacterGeneratorPreset:
    id: str = "rpg_like_48"
    frame_size: tuple[int, int] = (48, 48)
    directions: tuple[str, ...] = DIRECTIONS
    frames_per_direction: int = 3
    anchor: tuple[int, int] = (24, 46)

@dataclass(frozen=True)
class CharacterPart:
    id: str
    category: str
    frames: Mapping[str, Sequence[str]]
    display_name: str = ""
    tags: tuple[str, ...] = ()

@dataclass
class CharacterRecipe:
    id: str
    preset: str = "rpg_like_48"
    parts: dict[str, str] = field(default_factory=dict)
    palette: dict[str, str] = field(default_factory=dict)

@dataclass(frozen=True)
class GeneratedCharacter:
    recipe_id: str
    sheet_path: str
    metadata_path: str
    width: int
    height: int

class CharacterGeneratorCatalog:
    def __init__(self, parts: Sequence[CharacterPart] = ()):
        self._parts = {p.id: p for p in parts}
    def add(self, part: CharacterPart) -> None:
        if part.category not in LAYER_ORDER:
            raise ValueError(f"unsupported character part category: {part.category}")
        self._parts[part.id] = part
    def get(self, part_id: str) -> CharacterPart:
        return self._parts[part_id]
    def choices(self, category: str) -> tuple[CharacterPart, ...]:
        return tuple(p for p in self._parts.values() if p.category == category)

class CharacterGenerator:
    """Editor-side layered authoring tool. Output is ordinary canonical image + metadata."""
    def __init__(self, catalog: CharacterGeneratorCatalog, preset: CharacterGeneratorPreset | None = None):
        self.catalog = catalog
        self.preset = preset or CharacterGeneratorPreset()

    def _validate(self, recipe: CharacterRecipe) -> None:
        for category, part_id in recipe.parts.items():
            if category not in LAYER_ORDER:
                raise ValueError(f"unsupported category: {category}")
            part = self.catalog.get(part_id)
            if part.category != category:
                raise ValueError(f"part {part_id} belongs to {part.category}, not {category}")
            for direction in self.preset.directions:
                frames = part.frames.get(direction, ())
                if len(frames) != self.preset.frames_per_direction:
                    raise ValueError(f"{part_id}/{direction}: expected {self.preset.frames_per_direction} frames")

    def generate(self, recipe: CharacterRecipe, output_dir: str | Path) -> GeneratedCharacter:
        self._validate(recipe)
        out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
        fw, fh = self.preset.frame_size
        cols, rows = self.preset.frames_per_direction, len(self.preset.directions)
        sheet = Image.new("RGBA", (fw * cols, fh * rows), (0,0,0,0))
        for row, direction in enumerate(self.preset.directions):
            for frame_idx in range(cols):
                cell = Image.new("RGBA", (fw, fh), (0,0,0,0))
                for category in LAYER_ORDER:
                    part_id = recipe.parts.get(category)
                    if not part_id: continue
                    src = Image.open(self.catalog.get(part_id).frames[direction][frame_idx]).convert("RGBA")
                    if src.size != (fw, fh):
                        raise ValueError(f"{part_id} frame must be {fw}x{fh}; got {src.size}")
                    cell.alpha_composite(src)
                sheet.alpha_composite(cell, (frame_idx * fw, row * fh))
        sheet_path = out / f"{recipe.id}.png"
        meta_path = out / f"{recipe.id}.character.json"
        sheet.save(sheet_path)
        metadata = {
            "schema": "asteria.character.generated.v1", "recipe": asdict(recipe),
            "preset": asdict(self.preset), "sheet": sheet_path.name,
            "layout": {"columns": cols, "rows": rows, "row_directions": list(self.preset.directions)},
            "runtime_special_type": False,
        }
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return GeneratedCharacter(recipe.id, str(sheet_path), str(meta_path), sheet.width, sheet.height)
