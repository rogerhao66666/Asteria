"""RPG Maker MV generator-part topology adapter."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .character_generator import CharacterPart, DIRECTIONS


_NAME = re.compile(
    r"^(?P<prefix>TV|TVD|SV|FG|icon)_(?P<category>[^_]+)_p(?P<number>[A-Za-z]*\d+)(?P<suffix>.*)$",
    re.IGNORECASE,
)
_REPRESENTATIONS = {
    "TV": "walking", "TVD": "damaged", "SV": "side_view",
    "FG": "face", "ICON": "thumbnail",
}
_CATEGORIES = {
    "body": "body", "clothing": "outfit", "clothing1": "outfit",
    "clothing2": "armor", "acca": "accessory", "accb": "accessory",
    "glasses": "accessory", "fronthair": "hair_front",
    "rearhair": "hair_back", "eyes": "eyes", "eyebrows": "eyes",
    "beard": "accessory", "ears": "accessory", "tail": "accessory",
    "wing": "accessory", "face": "body",
}


@dataclass(frozen=True, slots=True)
class MVGeneratorIssue:
    code: str
    path: str
    message: str
    part_id: str = ""


@dataclass(frozen=True, slots=True)
class MVGeneratorRepresentation:
    kind: str
    images: tuple[Path, ...]
    masks: tuple[Path, ...] = ()


@dataclass(frozen=True, slots=True)
class MVGeneratorLayerOrder:
    walking: int = 10
    face: int = 20
    side_view: int = 30
    damaged: int = 40

    def __getitem__(self, representation: str) -> int:
        if representation not in {"walking", "face", "side_view", "damaged"}:
            raise KeyError(representation)
        return getattr(self, representation)


@dataclass(frozen=True, slots=True)
class MVGeneratorPart:
    id: str
    source_root: Path
    gender: str
    source_category: str
    category: str
    part_number: int | str
    walking: MVGeneratorRepresentation | None = None
    face: MVGeneratorRepresentation | None = None
    side_view: MVGeneratorRepresentation | None = None
    damaged: MVGeneratorRepresentation | None = None
    thumbnail: MVGeneratorRepresentation | None = None
    layer_order: MVGeneratorLayerOrder = MVGeneratorLayerOrder()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RPGMakerMVGeneratorCatalog:
    roots: tuple[Path, ...]
    parts: tuple[MVGeneratorPart, ...]
    issues: tuple[MVGeneratorIssue, ...]
    source_file_count: int

    @classmethod
    def discover(cls, reference_root: Path) -> "RPGMakerMVGeneratorCatalog":
        root = Path(reference_root).expanduser().resolve()
        roots = tuple(sorted(path.resolve() for path in root.glob("**/Generator") if path.is_dir()))
        issues = []
        groups = {}
        source_count = 0
        for generator_root in roots:
            for path in sorted(item for item in generator_root.rglob("*") if item.is_file()):
                source_count += 1
                if path.suffix.lower() != ".png":
                    issues.append(MVGeneratorIssue("generator.unsupported_file", str(path), path.name))
                    continue
                match = _NAME.match(path.stem)
                if match is None:
                    issues.append(MVGeneratorIssue("generator.unrecognized_name", str(path), path.name))
                    continue
                relative_parts = path.relative_to(generator_root).parts
                gender = next((value for value in relative_parts if value.lower() in {"male", "female"}), "Unspecified")
                source_category = match.group("category")
                token = match.group("number")
                number = int(token) if token.isdigit() else token
                key = (generator_root, gender, source_category, number)
                representation = _REPRESENTATIONS[match.group("prefix").upper()]
                suffix = match.group("suffix").lower()
                is_mask = suffix == "_c"
                bucket = groups.setdefault(key, {}).setdefault(representation, {"images": [], "masks": []})
                bucket["masks" if is_mask else "images"].append(path.resolve())

        parts = []
        for (generator_root, gender, source_category, number), representations in groups.items():
            relative = generator_root.relative_to(root).as_posix()
            identity = f"{relative}|{gender}|{source_category}|{number}"
            digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
            part_id = f"mvgen.{digest}.{source_category.lower()}.{str(number).lower()}"

            def rep(name):
                value = representations.get(name)
                if value is None:
                    return None
                return MVGeneratorRepresentation(
                    name, tuple(sorted(value["images"])), tuple(sorted(value["masks"]))
                )

            category = _CATEGORIES.get(source_category.lower(), "accessory")
            part = MVGeneratorPart(
                part_id, generator_root, gender, source_category, category, number,
                rep("walking"), rep("face"), rep("side_view"),
                rep("damaged"), rep("thumbnail"),
                tags=(f"gender:{gender.lower()}", f"mv-category:{source_category.lower()}"),
            )
            parts.append(part)
            for required in ("walking", "face", "side_view"):
                if getattr(part, required) is None:
                    issues.append(MVGeneratorIssue(
                        "generator.representation_missing", str(generator_root),
                        f"{required} unavailable", part_id,
                    ))
        return cls(roots, tuple(sorted(parts, key=lambda item: item.id)), tuple(issues), source_count)

    def to_character_parts(self) -> tuple[CharacterPart, ...]:
        result = []
        for part in self.parts:
            sheet = None if part.walking is None or not part.walking.images else str(part.walking.images[0])
            frames = {} if sheet is None else {direction: (sheet, sheet, sheet) for direction in DIRECTIONS}
            result.append(CharacterPart(part.id, part.category, frames, part.source_category, part.tags))
        return tuple(result)
