"""Field-map character art for the Astral Gate scene.

Separate from field_tiles.py on purpose: characters render through the
Entity/SpriteRenderer2D path (build_entity_sprite_draws), not the TileMap2D
path that field_tiles.py feeds. A character is not a tile.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from asteria.assets.types import AssetRecord
from asteria.graphics.sprites import SpriteFrame

CHARACTER_ATLAS = Path(__file__).resolve().parent / "field_tiles" / "characters_atlas.png"
FRAME_SIZE = (16, 24)

# Left-to-right frames in the atlas.
PLAYER_FRAME, ASTRAL_TYRANT_FRAME = range(2)


def install_character_sprites(project, output_dir, asset_dir="field_tiles"):
    """Register the character atlas as a texture + sprite_sheet asset pair.

    Returns the sprite_sheet AssetRecord id; callers add a SpriteRenderer2D
    per entity pointing at it with the frame index they want.
    """
    output_dir = Path(output_dir)
    target_dir = output_dir / asset_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / "characters_atlas.png"
    if destination.resolve() != CHARACTER_ATLAS.resolve():
        shutil.copyfile(CHARACTER_ATLAS, destination)

    texture = AssetRecord.create(
        kind="texture", source_path=f"{asset_dir}/characters_atlas.png"
    )
    sheet = AssetRecord.create(
        kind="sprite_sheet", source_path=f"{asset_dir}/characters.sprite_sheet.json"
    )
    project.assets.add(texture)
    project.assets.add(sheet)

    width, height = FRAME_SIZE
    frames = [
        asdict(SpriteFrame(x=i * width, y=0, width=width, height=height))
        for i in range(2)
    ]
    (target_dir / "characters.sprite_sheet.json").write_text(
        json.dumps(
            {"texture_asset_id": texture.id, "frames": frames},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return sheet.id
