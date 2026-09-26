from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from asteria.assets.character_bundle import CharacterBundleGenerator
from asteria.assets.character_generator import CharacterGenerator, CharacterGeneratorCatalog, CharacterRecipe, LAYER_ORDER
from asteria.assets.rpg_maker_mv_generator import RPGMakerMVGeneratorCatalog


@dataclass
class CharacterGeneratorWorkspace:
    """Qt-neutral model shared by custom and MV-backed character creators."""
    catalog: CharacterGeneratorCatalog | RPGMakerMVGeneratorCatalog
    generator: CharacterGenerator | CharacterBundleGenerator
    recipe: CharacterRecipe
    is_mv: bool = False

    @classmethod
    def create(cls, catalog: CharacterGeneratorCatalog, recipe_id: str = "new_character"):
        return cls(catalog, CharacterGenerator(catalog), CharacterRecipe(recipe_id))

    @classmethod
    def create_mv(cls, catalog: RPGMakerMVGeneratorCatalog, recipe_id: str = "new_character"):
        return cls(catalog, CharacterBundleGenerator(catalog), CharacterRecipe(recipe_id), True)

    def categories(self): return LAYER_ORDER

    def _part(self, part_id):
        if self.is_mv:
            return next(part for part in self.catalog.parts if part.id == part_id)
        return self.catalog.get(part_id)

    def choices(self, category, search: str = "", gender: str | None = None):
        choices = (tuple(part for part in self.catalog.parts if part.category == category)
                   if self.is_mv else self.catalog.choices(category))
        needle = search.casefold().strip()
        if needle:
            choices = tuple(part for part in choices if needle in " ".join((
                part.id, getattr(part, "source_category", ""), getattr(part, "display_name", "")
            )).casefold())
        if gender:
            choices = tuple(part for part in choices if getattr(part, "gender", "").casefold() == gender.casefold())
        return choices

    def select(self, category: str, part_id: str | None):
        if part_id is None:
            self.recipe.parts.pop(category, None); return
        part = self._part(part_id)
        if part.category != category: raise ValueError("category mismatch")
        self.recipe.parts[category] = part_id

    def selected_summary(self):
        return tuple((category, self.recipe.parts[category]) for category in LAYER_ORDER if category in self.recipe.parts)

    def _selected_mv_parts(self):
        return tuple(self._part(part_id) for _, part_id in self.selected_summary())

    def representation_available(self, representation: str) -> bool:
        if representation not in {"walking", "face", "side_view"}: raise ValueError(f"unsupported representation: {representation}")
        if not self.is_mv: return representation == "walking"
        parts = self._selected_mv_parts()
        return bool(parts) and all(getattr(part, representation) is not None for part in parts)

    def unavailable_reason(self, representation: str) -> str:
        label = {"walking": "Walking", "face": "Face", "side_view": "Side View"}[representation]
        if not self.is_mv: return "" if representation == "walking" else f"{label} unavailable for custom parts"
        for part in self._selected_mv_parts():
            if getattr(part, representation) is None:
                return f"{label} unavailable for {part.source_category} p{part.part_number}"
        return "" if self._selected_mv_parts() else f"{label} unavailable until a part is selected"

    def preview_representation(self, representation: str):
        if not self.representation_available(representation): return None
        if not self.is_mv: return self.preview_frame()
        return self.generator._compose(representation, self._selected_mv_parts(), self.recipe)

    def preview_frame(self, direction: str = "down", frame_index: int = 1):
        if self.is_mv:
            sheet = self.preview_representation("walking")
            if sheet is None: return Image.new("RGBA", (48, 48), (0, 0, 0, 0))
            directions = ("down", "left", "right", "up")
            if direction not in directions: raise ValueError(f"unsupported direction: {direction}")
            if not 0 <= frame_index < 3: raise IndexError(frame_index)
            row = directions.index(direction)
            return sheet.crop((frame_index * 48, row * 48, (frame_index + 1) * 48, (row + 1) * 48))
        preset = self.generator.preset
        if direction not in preset.directions: raise ValueError(f"unsupported direction: {direction}")
        if not 0 <= frame_index < preset.frames_per_direction: raise IndexError(frame_index)
        fw, fh = preset.frame_size
        cell = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
        for category in LAYER_ORDER:
            part_id = self.recipe.parts.get(category)
            if not part_id: continue
            part = self.catalog.get(part_id)
            with Image.open(part.frames[direction][frame_index]) as source: src = source.convert("RGBA")
            if src.size != (fw, fh): raise ValueError(f"{part_id} frame must be {fw}x{fh}; got {src.size}")
            cell.alpha_composite(src)
        return cell

    def generate(self, output_dir: str | Path): return self.generator.generate(self.recipe, output_dir)

    def create_character_command(self, bundle, project, scene, cell, *, display_name=None):
        from .create_character_command import CreateCharacterCommand
        return CreateCharacterCommand(
            bundle, project, scene, cell,
            display_name=display_name or self.recipe.id,
        )
