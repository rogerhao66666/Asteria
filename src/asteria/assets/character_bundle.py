"""Atomic coordinated character visual generation."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageColor, ImageOps

from .canonical import AssetSource, CanonicalAsset
from .character_generator import CharacterRecipe, LAYER_ORDER
from .rpg_maker_mv_generator import MVGeneratorPart, MVGeneratorRepresentation, RPGMakerMVGeneratorCatalog


_REPRESENTATIONS = ("walking", "face", "damaged", "side_view")
_CANVASES = {"walking": (144, 192), "face": (144, 144), "damaged": (144, 48), "side_view": (576, 384)}
_KINDS = {
    "walking": "character.walking",
    "face": "character.face",
    "damaged": "character.damaged",
    "side_view": "character.side_view",
}
_FACE_COMPOSITION_ORDER = (
    "body",
    "hair_back",
    "outfit",
    "armor",
    "cloak",
    "face_shape",
    "eyes",
    "eyebrows",
    "nose",
    "mouth",
    "ears",
    "beard",
    "facial_mark",
    "hair_front",
    "beast_ears",
    "accessory",
    "accessory_b",
    "glasses",
    "tail",
    "wing",
)


@dataclass(frozen=True, slots=True)
class GeneratedCharacterBundle:
    recipe_id: str
    output_dir: Path
    walking_path: Path
    face_path: Path
    side_view_path: Path
    metadata_path: Path
    anchor: tuple[int, int]
    source_part_ids: tuple[str, ...]
    canonical_assets: tuple[CanonicalAsset, ...]
    files_owned: bool = True
    damaged_path: Path | None = None

    @property
    def visual_paths(self) -> tuple[Path, Path, Path]:
        return self.walking_path, self.face_path, self.side_view_path

    @property
    def all_visual_paths(self) -> tuple[Path, ...]:
        return self.visual_paths + (() if self.damaged_path is None else (self.damaged_path,))


class CharacterBundleGenerator:
    """Compose MV representations and publish them only after all writes succeed."""

    def __init__(self, catalog: RPGMakerMVGeneratorCatalog):
        self.catalog = catalog
        self._parts = {part.id: part for part in catalog.parts}

    def _selected(self, recipe: CharacterRecipe) -> tuple[MVGeneratorPart, ...]:
        selected = []
        ordered = iter(recipe.ordered_part_ids())
        for category in (item for item in LAYER_ORDER if item in recipe.parts):
            part_id = next(ordered)
            try:
                part = self._parts[part_id]
            except KeyError as exc:
                raise ValueError(f"unknown character part: {part_id}") from exc
            if part.category != category:
                raise ValueError(f"part {part_id} belongs to {part.category}, not {category}")
            selected.append(part)
        if not selected:
            raise ValueError("character recipe must select at least one part")
        return tuple(selected)

    @staticmethod
    def _validate_representation(
        part: MVGeneratorPart,
        name: str,
        representation: MVGeneratorRepresentation | None,
        palette_requested: bool,
    ) -> None:
        if representation is None or not representation.images:
            return
        expected = _CANVASES[name]
        for path in representation.images:
            with Image.open(path) as image:
                if image.size != expected:
                    raise ValueError(f"{part.id}: {name} canvas must be {expected[0]}x{expected[1]}; got {image.size}")
        if palette_requested and name != "face" and not representation.masks:
            raise ValueError(f"{part.id}: {name} mask unavailable for palette")
        for path in representation.masks:
            with Image.open(path) as image:
                if image.size != expected:
                    raise ValueError(
                        f"{part.id}: {name} mask canvas must be {expected[0]}x{expected[1]}; got {image.size}"
                    )

    def _validate(self, recipe: CharacterRecipe, parts: tuple[MVGeneratorPart, ...]) -> None:
        if "body" not in recipe.parts:
            raise ValueError("body part required for generated character")
        if recipe.body_family and any(part.gender != recipe.body_family for part in parts):
            raise ValueError("selected parts use incompatible body family")
        genders = {part.gender.lower() for part in parts if part.gender.lower() != "unspecified"}
        if len(genders) > 1:
            raise ValueError("selected parts use incompatible body/gender variants")
        for name in _REPRESENTATIONS:
            contributors = tuple(part for part in parts if (rep := getattr(part, name)) is not None and rep.images)
            if not contributors:
                raise ValueError(f"{name} unavailable for selected character parts")
            for part in contributors:
                palette_requested = part.id in recipe.palette or part.category in recipe.palette
                self._validate_representation(part, name, getattr(part, name), palette_requested)

    @staticmethod
    def _colorize_mask(canvas: Image.Image, mask_path: Path, color: str) -> None:
        with Image.open(mask_path) as source:
            mask_rgba = source.convert("RGBA")
        alpha = mask_rgba.getchannel("A")
        if not alpha.getbbox():
            alpha = mask_rgba.convert("L")
        CharacterBundleGenerator._colorize_region(canvas, alpha, color)

    @staticmethod
    def _colorize_region(canvas: Image.Image, alpha: Image.Image, color: str) -> None:
        try:
            rgb = ImageColor.getrgb(color)
        except ValueError as exc:
            raise ValueError(f"invalid palette color: {color}") from exc
        dark = tuple(round(channel * 0.18) for channel in rgb[:3])
        light = tuple(round(channel + (255 - channel) * 0.75) for channel in rgb[:3])
        tint = ImageOps.colorize(canvas.convert("RGB").convert("L"), dark, light, mid=rgb[:3]).convert("RGBA")
        tint.putalpha(ImageChops.multiply(alpha, canvas.getchannel("A")))
        canvas.alpha_composite(tint)

    def _compose(self, name: str, parts: tuple[MVGeneratorPart, ...], recipe: CharacterRecipe) -> Image.Image:
        if name == "face":
            by_category = {part.category: part for part in parts}
            parts = tuple(by_category[category] for category in _FACE_COMPOSITION_ORDER if category in by_category)
        canvas = Image.new("RGBA", _CANVASES[name], (0, 0, 0, 0))
        for part in parts:
            representation = getattr(part, name)
            if representation is None:
                continue
            layer = Image.new("RGBA", _CANVASES[name], (0, 0, 0, 0))
            # FG color sublayers are named c1, c2, ... with c1 in front.
            # Source-file sorting alone puts the opaque eye white over the iris.
            images = reversed(representation.images) if name == "face" else representation.images
            for path in images:
                with Image.open(path) as source:
                    layer.alpha_composite(source.convert("RGBA"))
            color = recipe.palette.get(part.id) or recipe.palette.get(part.category)
            if color:
                if name == "face":
                    self._colorize_region(layer, layer.getchannel("A"), color)
                else:
                    for mask in representation.masks:
                        self._colorize_mask(layer, mask, color)
            canvas.alpha_composite(layer)
        return canvas

    def compose(self, name: str, recipe: CharacterRecipe) -> Image.Image:
        if name not in _REPRESENTATIONS:
            raise ValueError(f"unknown character representation: {name}")
        parts = self._selected(recipe)
        self._validate(recipe, parts)
        return self._compose(name, parts, recipe)

    def generate(self, recipe: CharacterRecipe, output_root: str | Path) -> GeneratedCharacterBundle:
        parts = self._selected(recipe)
        self._validate(recipe, parts)
        root = Path(output_root)
        target = root / recipe.id
        if target.exists():
            raise FileExistsError(f"generated character already exists: {target}")

        images = {name: self._compose(name, parts, recipe) for name in _REPRESENTATIONS}
        root.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{recipe.id}-", dir=root))
        try:
            for name, image in images.items():
                image.save(temporary / f"{name}.png")
            metadata = {
                "schema": "asteria.character.bundle.v1",
                "recipe": asdict(recipe),
                "source_part_ids": [part.id for part in parts],
                "anchor": [24, 48],
                "walking": {
                    "file": "walking.png",
                    "canvas": [144, 192],
                    "frame_size": [48, 48],
                    "columns": 3,
                    "rows": 4,
                    "row_directions": ["down", "left", "right", "up"],
                },
                "face": {"file": "face.png", "canvas": [144, 144]},
                "damaged": {"file": "damaged.png", "canvas": [144, 48], "columns": 3, "rows": 1},
                "side_view": {"file": "side_view.png", "canvas": [576, 384]},
            }
            (temporary / "character.bundle.json").write_text(
                json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
            )
            os.replace(temporary, target)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

        paths = {name: target / f"{name}.png" for name in _REPRESENTATIONS}
        assets = tuple(
            CanonicalAsset(
                f"generated/{recipe.id}/{name}",
                _KINDS[name],
                AssetSource(str(paths[name]), "generated"),
                tags=frozenset({"generated", "character", "mv-derived"}),
                metadata=(("recipe_id", recipe.id), ("representation", name)),
            )
            for name in _REPRESENTATIONS
        )
        return GeneratedCharacterBundle(
            recipe.id,
            target,
            paths["walking"],
            paths["face"],
            paths["side_view"],
            target / "character.bundle.json",
            (24, 48),
            tuple(part.id for part in parts),
            assets,
            damaged_path=paths["damaged"],
        )
