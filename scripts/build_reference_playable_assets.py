"""Build the reference project's playable test images from downloaded free packs.

The field player sheet (``player_field_sheet.png``) is built by
``build_reference_battle_presentation.py`` so it matches the battle party leader.

Usage:
    python scripts/build_reference_playable_assets.py [FREE_ASSETS_DIR]

FREE_ASSETS_DIR defaults to local_reference/free_assets and must contain the
extracted packs (see reference_projects/complex_reference_rpg/playable_assets/
CREDITS.md for sources and licenses):

- kenney_tiny-town/extracted, kenney_tiny-dungeon/extracted   (CC0)

Skill effect sheets are drawn procedurally here (no third-party art).
Output is deterministic.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
OUTPUT = REPO / "reference_projects" / "complex_reference_rpg" / "playable_assets"
TILE = 16

# Tiny Dungeon tilemap_packed.png indices (12 tiles per row).
HERO_TILES = (96, 84, 99, 87, 100, 112)  # knight, wizard, girl, viking, healer, ranger
BOSS_TILE = 110  # red demon
WISP_TILE = 108  # green ghost

# Tiny Town tilemap_packed.png indices.
GRASS, FLOWERS, FLOWERS_2 = 0, 1, 2
PATH_H = 40
TREE_TOP, TREE_BOTTOM = 4, 16
ORANGE_TOP, ORANGE_BOTTOM = 3, 15
BUSH = 5
HOUSE = ((48, 49, 50), (60, 61, 62), (72, 73, 74), (84, 85, 86))


def tile(sheet, index, columns=12):
    x, y = (index % columns) * TILE, (index // columns) * TILE
    return sheet.crop((x, y, x + TILE, y + TILE))


def scaled(image, size):
    return image.resize(size, Image.NEAREST)


def compose_field(town):
    canvas = Image.new("RGBA", (320, 180))
    for y in range(0, 180, TILE):
        for x in range(0, 320, TILE):
            canvas.alpha_composite(tile(town, GRASS), (x, y))
    for i, x in enumerate(range(0, 320, TILE)):
        canvas.alpha_composite(tile(town, PATH_H), (x, 96))
        if i % 5 == 2:
            canvas.alpha_composite(tile(town, FLOWERS if i % 2 else FLOWERS_2), (x, 128))
    for x in range(0, 320, 48):
        top, bottom = (TREE_TOP, TREE_BOTTOM) if x % 96 else (ORANGE_TOP, ORANGE_BOTTOM)
        canvas.alpha_composite(tile(town, top), (x + 8, 0))
        canvas.alpha_composite(tile(town, bottom), (x + 8, TILE))
        canvas.alpha_composite(tile(town, BUSH), (x + 24, 160))
    for row, indices in enumerate(HOUSE):
        for col, index in enumerate(indices):
            canvas.alpha_composite(tile(town, index), (32 + col * TILE, 32 + row * TILE))
    return canvas


def compose_battle_background(town):
    canvas = Image.new("RGBA", (320, 180), (52, 74, 61, 255))
    for y in range(64, 180, TILE):
        for x in range(0, 320, TILE):
            canvas.alpha_composite(tile(town, GRASS), (x, y))
    for x in range(-8, 320, 24):
        canvas.alpha_composite(tile(town, TREE_TOP), (x, 32))
        canvas.alpha_composite(tile(town, TREE_BOTTOM), (x, 48))
    return canvas


def effect_sheet(kind, color, frames=16, size=64):
    """Procedural 4x4 effect sheet: expanding ring, slash arcs, rising sparkles or falling star."""
    cols = 4
    sheet = Image.new("RGBA", (cols * size, (frames // cols) * size))
    for i in range(frames):
        t = (i + 1) / frames
        frame = Image.new("RGBA", (size, size))
        d = ImageDraw.Draw(frame)
        alpha = int(255 * (1 - t) ** 0.6)
        c = (*color, alpha)
        mid = size // 2
        if kind == "ring":
            r = 4 + t * (mid - 6)
            d.ellipse((mid - r, mid - r, mid + r, mid + r), outline=c, width=max(1, int(6 * (1 - t)) + 1))
        elif kind == "slash":
            span = 40 + 140 * t
            d.arc((6, 6, size - 6, size - 6), 210, 210 + span, fill=c, width=5)
            d.arc((14, 14, size - 14, size - 14), 220, 220 + span * 0.8, fill=c, width=2)
        elif kind == "sparkle":
            for k in range(6):
                angle = k * math.pi / 3 + t
                x = mid + math.cos(angle) * 18 * t
                y = mid - 26 * t + math.sin(angle) * 8
                d.rectangle((x - 2, y - 2, x + 2, y + 2), fill=c)
        elif kind == "meteor":
            x, y = 8 + 40 * t, 4 + 44 * t
            d.line((x - 18, y - 18, x, y), fill=c, width=4)
            d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=c)
        sheet.alpha_composite(frame, ((i % cols) * size, (i // cols) * size))
    return sheet


def build(free_assets: Path, output: Path = OUTPUT):
    dungeon = Image.open(free_assets / "kenney_tiny-dungeon/extracted/Tilemap/tilemap_packed.png").convert("RGBA")
    town = Image.open(free_assets / "kenney_tiny-town/extracted/Tilemap/tilemap_packed.png").convert("RGBA")
    output.mkdir(parents=True, exist_ok=True)

    files = {
        "field_map.png": scaled(compose_field(town), (960, 540)),
        "battle_background.png": scaled(compose_battle_background(town), (960, 540)),
        "boss_field.png": scaled(tile(dungeon, BOSS_TILE), (96, 96)),
        "astral_tyrant_battle.png": scaled(tile(dungeon, BOSS_TILE), (220, 220)),
        "mender_wisp_battle.png": scaled(tile(dungeon, WISP_TILE), (96, 96)),
        "fx_strike.png": effect_sheet("slash", (255, 244, 214)),
        "fx_fire.png": effect_sheet("ring", (255, 120, 40)),
        "fx_heal.png": effect_sheet("sparkle", (120, 255, 160)),
        "fx_meteor.png": effect_sheet("meteor", (255, 200, 90)),
    }
    for number, index in enumerate(HERO_TILES, 1):
        files[f"hero_{number:02d}_battle.png"] = scaled(tile(dungeon, index), (96, 96))
    for name, image in files.items():
        image.save(output / name, optimize=True)
    return tuple(sorted(files))


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "local_reference" / "free_assets"
    for name in build(source):
        print(name)
