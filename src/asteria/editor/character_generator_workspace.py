from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from PIL import Image
from asteria.assets.character_generator import CharacterGenerator, CharacterGeneratorCatalog, CharacterRecipe, LAYER_ORDER

@dataclass
class CharacterGeneratorWorkspace:
    """Qt-neutral workspace model; a GUI can bind selectors/preview/Generate to this API."""
    catalog: CharacterGeneratorCatalog
    generator: CharacterGenerator
    recipe: CharacterRecipe

    @classmethod
    def create(cls, catalog: CharacterGeneratorCatalog, recipe_id: str = "new_character"):
        return cls(catalog, CharacterGenerator(catalog), CharacterRecipe(recipe_id))

    def categories(self): return LAYER_ORDER
    def choices(self, category): return self.catalog.choices(category)
    def select(self, category: str, part_id: str | None):
        if part_id is None: self.recipe.parts.pop(category, None)
        else:
            part = self.catalog.get(part_id)
            if part.category != category: raise ValueError("category mismatch")
            self.recipe.parts[category] = part_id

    def preview_frame(self, direction: str = "down", frame_index: int = 1):
        """Compose one frame in memory for live editor preview."""
        preset = self.generator.preset
        if direction not in preset.directions:
            raise ValueError(f"unsupported direction: {direction}")
        if not 0 <= frame_index < preset.frames_per_direction:
            raise IndexError(frame_index)
        fw, fh = preset.frame_size
        cell = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
        for category in LAYER_ORDER:
            part_id = self.recipe.parts.get(category)
            if not part_id:
                continue
            part = self.catalog.get(part_id)
            src = Image.open(part.frames[direction][frame_index]).convert("RGBA")
            if src.size != (fw, fh):
                raise ValueError(f"{part_id} frame must be {fw}x{fh}; got {src.size}")
            cell.alpha_composite(src)
        return cell

    def generate(self, output_dir: str | Path): return self.generator.generate(self.recipe, output_dir)
