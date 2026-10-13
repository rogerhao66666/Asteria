"""Item and equipment icons for the Complex Reference RPG (AST-07).

Packs one CC0 icon per item / equipment record from the Ninja Adventure Asset Pack (kept
un-tracked in
``local_reference/free_assets/``) into ``playable_assets/item_icons.png`` (18x18 cells, icons
centred), then
adds to ``project.asteria.json``, in its stored format:

* one canonical ``icon`` asset per record, ``icon.<record id>``, whose ``region`` metadata is its
  cell;
* ``icon_id`` on each item and equipment record.

Running it again rebuilds the atlas and rewrites the same entries (idempotent). Nothing else
changes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO / "reference_projects" / "complex_reference_rpg"
PACK = (
    REPO
    / "local_reference"
    / "free_assets"
    / "ninja_adventure"
    / "extracted"
    / "Ninja Adventure - Asset Pack"
)
ATLAS = "playable_assets/item_icons.png"
CELL = 18
COLUMNS = 8

ICONS = {
    # items
    "alchemy_salt": "Items/Resource/Rock.png",
    "ancient_thread": "Items/Other/Letter2.png",
    "boss_emblem": "Items/Treasure/GoldCup.png",
    "ether_leaf": "Items/Food/TeaLeaf.png",
    "fire_dust": "Items/Resource/GemRed.png",
    "focus_stone": "Items/Resource/GemPurple.png",
    "guardian_scale": "Items/Resource/BarMithril.png",
    "healing_herb": "Items/Potion/LifePot.png",
    "ice_crystal": "Items/Resource/Water.png",
    "iron_ore": "Items/Resource/BarIron.png",
    "moon_shard": "Items/Resource/GemYellow.png",
    "phoenix_seed": "Items/Food/SeedBig3.png",
    "silver_ore": "Items/Resource/BarSilver.png",
    "storm_core": "Items/Scroll/ScrollThunder.png",
    "venom_sac": "Items/Potion/WaterPot.png",
    "wisp_essence": "Items/Resource/feather.png",
    # weapons
    "weapon_01": "Items/Weapons/Sword/Sprite.png",
    "weapon_02": "Items/Weapons/Katana/Sprite.png",
    "weapon_03": "Items/Weapons/Axe/Sprite.png",
    "weapon_04": "Items/Weapons/Bow/Sprite.png",
    "weapon_05": "Items/Weapons/MagicWand/Sprite.png",
    "weapon_06": "Items/Weapons/Lance/Sprite.png",
    "weapon_07": "Items/Weapons/Hammer/Sprite.png",
    "weapon_08": "Items/Weapons/Rapier/Sprite.png",
    "weapon_09": "Items/Weapons/Club/Sprite.png",
    "weapon_10": "Items/Weapons/Sai/Sprite.png",
    "weapon_11": "Items/Weapons/BigSword/Sprite.png",
    "weapon_12": "Items/Weapons/Book/Sprite.png",
    # accessories
    "accessory_01": "Items/Treasure/SilverCup.png",
    "accessory_02": "Items/Treasure/GoldKey.png",
    "accessory_03": "Items/Object/Gourd.png",
    "accessory_04": "Items/Object/Hourglass.png",
    "accessory_05": "Items/Object/PanFlute.png",
    "accessory_06": "Items/Potion/Heart.png",
    "accessory_07": "Items/Object/Bag.png",
    "accessory_08": "Items/Treasure/SilverCoin.png",
}


def build_atlas(output):
    rows = (len(ICONS) + COLUMNS - 1) // COLUMNS
    atlas = Image.new("RGBA", (COLUMNS * CELL, rows * CELL), (0, 0, 0, 0))
    regions = {}
    for index, (record_id, source) in enumerate(ICONS.items()):
        with Image.open(PACK / source) as image:
            icon = image.convert("RGBA")
        if icon.width > CELL or icon.height > CELL:
            icon.thumbnail((CELL, CELL), Image.NEAREST)
        x, y = (index % COLUMNS) * CELL, (index // COLUMNS) * CELL
        atlas.alpha_composite(icon, (x + (CELL - icon.width) // 2, y + (CELL - icon.height) // 2))
        regions[record_id] = [x, y, CELL, CELL]
    output.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(output)
    return regions


def _records(table, key):
    return table.values() if isinstance(table, dict) else (r for r in table if key in r)


def update_project(path, regions):
    data = json.loads(path.read_text(encoding="utf-8"))
    assets = data["assets"]["canonical_assets"]
    assets[:] = [a for a in assets if not a["asset_id"].startswith("icon.")]
    for record_id, region in sorted(regions.items()):
        assets.append(
            {
                "asset_id": f"icon.{record_id}",
                "kind": "icon",
                "metadata": [["region", region]],
                "source": {
                    "provenance": [
                        ["license", "CC0 1.0"],
                        ["source", "Ninja Adventure Asset Pack"],
                    ],
                    "provider": "project",
                    "uri": ATLAS,
                },
                "tags": ["icon", "menu"],
                "version": 1,
            }
        )
    db = data["rpg_database"]
    for table, key in (("items", "item_id"), ("equipment", "equipment_id")):
        for record in _records(db[table], key):
            if record[key] in regions:
                record["icon_id"] = f"icon.{record[key]}"
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main():
    missing = [s for s in ICONS.values() if not (PACK / s).is_file()]
    if missing:
        print(
            "Missing source icons (download the Ninja Adventure Asset Pack into local_reference):",
            missing,
        )
        return 1
    regions = build_atlas(PROJECT / ATLAS)
    update_project(PROJECT / "project.asteria.json", regions)
    print(f"{len(regions)} icons -> {ATLAS}; icon_id set on items and equipment")
    return 0


if __name__ == "__main__":
    sys.exit(main())
