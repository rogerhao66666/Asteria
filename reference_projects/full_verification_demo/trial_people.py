"""Who the townsfolk look like: every person on the maps wears a picture of their own.

The hero and the three companions keep their Lucifer looks; everyone else gets a different
Ninja Adventure character (CC0, Pixel-boy), drawn half as big again so it stands about as tall
as the Lucifer cast; the two shrines, the plaque and the banner are statues or spirits, the cache
a bag and the vault a chest. Foes keep their monsters (a kind of foe looks alike on purpose).
"""

from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NINJA = Path(
    os.environ.get(
        "ASTERIA_NINJA_ASSETS",
        REPO
        / "local_reference"
        / "free_assets"
        / "ninja_adventure"
        / "extracted"
        / "Ninja Adventure - Asset Pack",
    )
)
CELL, SCALE, FEET = 48, 1.5, 40  # the Lucifer frame, the zoom, where Lucifer feet stand in it
DIRECTIONS = ("down", "up", "left", "right")  # the columns of a Ninja Adventure sheet
CAST = {  # map name: Ninja Adventure character (Actor/Character/<name>) or ("item", file)
    # the workshop
    "Smith": "Caveman",
    "Merchant": "Sultan",
    "Jeweler": "Sultan2",
    "Card Dealer": "Inspector",
    "Armory": "Knight",
    "Breaker": "Caveman2",
    "Outfitter": "Villager2",
    "Alchemist": "Shaman",
    # the job teachers
    "Mystic Teacher": "Monk",
    "Duelist Teacher": "FighterRed",
    "Weapon Master Dojo": "Samurai",
    "Sage's Tower": "SorcererBlack",
    "Forgemaster's Smithy": "GladiatorBlue",
    "Rogue Guild": "NinjaDark",
    "Guardian Post": "KnightGold",
    "Job Master": "Master",
    # the story
    "Warden Thessaly": "Hunter",
    "Guildmaster Orla": "Noble",
    "Innkeeper Marla": "Woman",
    "Bounty Clerk": "Villager3",
    "Old Master": "OldMan",
    "Scholar Lin": "Monk2",
    "Showman Pip": "MaskRacoon",
    "Camp Scout": "CamouflageGreen",
    # shrines and monuments
    "Shrine": "Spirit",
    "Hero's Shrine": "Tengu",
    "Hall of Heroes": "Statue",
    "Victory Banner": "GoldStatue",
    # things, not people
    "Old Cache": ("item", "Items/Object/Bag.png"),
    "Sealed Vault": ("item", "Items/Treasure/BigTreasureChest.png"),
}
LANTERN = "Flam"  # Showman Pip's spirit lantern (a prefab)


def _place(image):
    """A picture drawn at twice its size in a Lucifer-sized cell, its feet where theirs are."""
    from PIL import Image

    big = image.resize((round(image.width * SCALE), round(image.height * SCALE)), Image.NEAREST)
    box = big.getbbox() or (0, 0, big.width, big.height)
    big = big.crop(box)
    cell = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    cell.alpha_composite(big, ((CELL - big.width) // 2, max(0, FEET - big.height)))
    return cell


def look(assets, key, who, name):
    """``(sheet asset id, clip set id)`` of one Ninja Adventure character (or item) with the
    idle / walk clips for the four facings the field expects."""
    from PIL import Image

    images, clips = [], {}
    if isinstance(who, tuple):  # an item: one picture for every facing
        picture = _place(Image.open(NINJA / who[1]).convert("RGBA"))
        images.append(picture)
        for facing in DIRECTIONS:
            clips[f"idle_{facing}"] = ([0], 0.5, True)
            clips[f"walk_{facing}"] = ([0], 0.5, True)
    else:
        sheet = Image.open(NINJA / "Actor" / "Character" / who / "SpriteSheet.png").convert("RGBA")
        for column, facing in enumerate(DIRECTIONS):
            start = len(images)
            for row in range(4):  # rows 0-3: the walk; the first one is the standing pose
                tile = sheet.crop((column * 16, row * 16, column * 16 + 16, row * 16 + 16))
                images.append(_place(tile))
            clips[f"idle_{facing}"] = ([start], 0.4, True)
            clips[f"walk_{facing}"] = (list(range(start, start + 4)), 0.12, True)
    strip = Image.new("RGBA", (CELL * len(images), CELL), (0, 0, 0, 0))
    frames = []
    for index, image in enumerate(images):
        strip.alpha_composite(image, (index * CELL, 0))
        frames.append((index * CELL, 0, CELL, CELL))
    return assets.sheet(key, strip, frames, name), assets.clips(key, clips, name)


def dress(assets, builders):
    """Give every person in ``CAST`` their own look (they all had to share four)."""
    from asteria.runtime.components2d import Animator2DComponent, SpriteRenderer2D

    made, worn = {}, set()
    for builder in builders.values():
        for entity in builder.scene.entities():
            who = CAST.get(entity.name)
            if who is None:
                continue
            if entity.name not in made:
                key = "look_npc_" + entity.name.lower().replace(" ", "_").replace("'", "")
                made[entity.name] = look(assets, key, who, entity.name)
            sheet, clips = made[entity.name]
            entity.get(SpriteRenderer2D).sprite_sheet_asset_id = sheet
            entity.get(Animator2DComponent).clip_set_id = clips
            worn.add(who)
    assert len(worn) == len(made), "two people share a look"
    return made
