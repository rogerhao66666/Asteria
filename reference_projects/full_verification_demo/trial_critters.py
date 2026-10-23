"""Cute companions from Foozle's CC0 Critters packs (same artist as the Lucifer cast): the
party's pet (a tamed creature fights as "pet") is the Little Bird and the summoned Spirit
Knight is the Elite, a fox in armour with a sword (the user's pick). Each pack draws one
facing in fixed-size frames: the player critters face right and are mirrored, the enemy
packs already face left (the party fights facing left)."""

from __future__ import annotations

from trial_lucifer import FREE_ASSETS, sheet_from_strips

SOURCE = (("license", "CC0 1.0"), ("source", "Foozle Critters packs"))
CRITTERS = {  # key: (pack folder, strip folder, frame (w, h), role -> strip file)
    "fox_elite": (
        "Foozle_2DC0023_Critters_EnemyPack1_Pixel_Art",
        "Elite/Spritesheet",
        (96, 48),
        {
            "idle": "Elite Idle",
            "attack": "Elite Attack",  # the pack draws one attack: every swing uses it
            "attack2": "Elite Attack",
            "attack3": "Elite Attack",
            "cast": "Elite Attack",
            "hit": "Elite Hurt",
            "ko": "Elite Death",
            "transform": "Elite Jump",
        },
    ),
    "mouse": (
        "Foozle_2DC0022_RealmOfCritters_Mouse_Pixel_Art",
        "Mouse/Spritesheet",
        (64, 48),
        {
            "idle": "Player Idle",
            "attack": "Player Light Attack 1",
            "attack2": "Player Light Attack 2",
            "attack3": "Player Light Attack 3",
            "cast": "Player Heavy Attack",
            "hit": "Player Hurt",
            "ko": "Player Death",
            "transform": "Player Double Jump",
        },
    ),
    "little_bird": (
        "Foozle_2DC0024_Little_Bird_Pixel_Art",
        "Spritesheet",
        (64, 64),
        {
            "idle": "Little Bird Idle",
            "attack": "Little Birt Light Attack",  # (sic: the pack's file name)
            "attack2": "Little Bird Heavy Attack",
            "attack3": "Little Birt Light Attack",
            "cast": "Little Bird Heavy Attack",
            "hit": "Little Bird Hurt",
            "ko": "Little Bird Death",
            "transform": "Little Bird Jump Up",
        },
    ),
}
PACKS = {key: pack for key, (pack, *_rest) in CRITTERS.items()}
FACING_LEFT = {"fox_elite"}  # drawn as foes of the player: already facing left


def strips(key, *, mirror=True):
    """Role -> frames of a critter, facing left when ``mirror`` (the packs face right)."""
    from PIL import Image, ImageOps

    pack, folder, (width, height), files = CRITTERS[key]
    out = {}
    for role, name in files.items():
        image = Image.open(FREE_ASSETS / pack / folder / f"{name}.png").convert("RGBA")
        frames = [
            image.crop((i * width, 0, (i + 1) * width, height))
            for i in range(image.width // width)
        ]
        frames = [f for f in frames if f.getbbox()]  # some strips end on empty cells
        out[role] = [ImageOps.mirror(f) for f in frames] if mirror else frames
    return out


def character_sheet(key):
    return sheet_from_strips(strips(key, mirror=key not in FACING_LEFT))


def credits_rows():
    cc0 = "[CC0 1.0](http://creativecommons.org/publicdomain/zero/1.0/)"
    return [
        "| `battle/pet.png`, `battle/spirit_knight.png` (Little Bird, Elite) | Foozle Critters "
        "packs (`Foozle_2DC0024_Little_Bird_Pixel_Art`, "
        "`Foozle_2DC0023_Critters_EnemyPack1_Pixel_Art`), strips mirrored to face left and "
        "arranged on one sheet (built by `trial_critters.py`) | Foozle (Baldur) | "
        f"{cc0} |"
    ]
