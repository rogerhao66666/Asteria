from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image

from .character_generator import DIRECTIONS, LAYER_ORDER, CharacterPart


@dataclass(frozen=True)
class CharacterAnimationTopology:
    id: str = "rpg_like_48_walk_v1"
    frame_size: tuple[int, int] = (48, 48)
    directions: tuple[str, ...] = DIRECTIONS
    frames_per_direction: int = 3
    anchor: tuple[int, int] = (24, 46)
    # Every modular part must be authored against the same topology id.


@dataclass(frozen=True)
class CharacterPartManifest:
    id: str
    category: str
    topology_id: str
    frames: Mapping[str, Sequence[str]]
    palette_masks: Mapping[str, Mapping[str, Sequence[str]]] | None = None

    def to_part(self) -> CharacterPart:
        return CharacterPart(self.id, self.category, self.frames, self.id, (f"topology:{self.topology_id}",))


def validate_part_manifest(
    manifest: CharacterPartManifest, topology: CharacterAnimationTopology, root: str | Path = "."
) -> None:
    if manifest.category not in LAYER_ORDER:
        raise ValueError(f"unsupported category: {manifest.category}")
    if manifest.topology_id != topology.id:
        raise ValueError(f"{manifest.id}: topology mismatch {manifest.topology_id} != {topology.id}")
    root = Path(root)
    for direction in topology.directions:
        seq = manifest.frames.get(direction, ())
        if len(seq) != topology.frames_per_direction:
            raise ValueError(f"{manifest.id}/{direction}: expected {topology.frames_per_direction} frames")
        for rel in seq:
            im = Image.open(root / rel).convert("RGBA")
            if im.size != topology.frame_size:
                raise ValueError(f"{manifest.id}: expected {topology.frame_size}, got {im.size}")
            # Parts may be sparse, but authored pixels may never leave the canonical canvas.
            if im.getbbox() is None and manifest.category == "body":
                raise ValueError(f"{manifest.id}: body frame may not be empty")
    if manifest.palette_masks:
        for mask_name, by_dir in manifest.palette_masks.items():
            for direction in topology.directions:
                seq = by_dir.get(direction, ())
                if len(seq) != topology.frames_per_direction:
                    raise ValueError(f"{manifest.id}/{mask_name}/{direction}: invalid mask frame count")
                for rel in seq:
                    im = Image.open(root / rel).convert("L")
                    if im.size != topology.frame_size:
                        raise ValueError(f"{manifest.id}/{mask_name}: invalid mask size")


def write_authoring_template(output_dir: str | Path, topology: CharacterAnimationTopology | None = None) -> Path:
    topology = topology or CharacterAnimationTopology()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "asteria.character.topology.v1",
        **asdict(topology),
        "layer_order": list(LAYER_ORDER),
        "contract": {
            "transparent_background": True,
            "shared_canvas": True,
            "shared_anchor": True,
            "no_runtime_generator_type": True,
            "parts_are_interchangeable": True,
        },
    }
    p = out / "topology.json"
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p
