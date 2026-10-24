"""The party's KayKit art: smooth 2D sheets photographed from CC0 3D chibi characters.

``scripts/build_kaykit_art.py`` writes them to ``asset_library/kaykit/KayKit_Rendered_Sheets``
(``<key>_battle.png`` + ``.json``: every battle clip on one grid; ``<key>_field.png`` +
``.json``: the 3 x 4 walking sheet). This module only copies and registers them; a demo build
never needs Blender.

Opt-in: the demo's party is the Lucifer pixel cast (the user's choice after trying KayKit,
2026-10-23: smooth 3D renders beside pixel art did not match). ``ASTERIA_FV_PARTY=kaykit`` at
build time puts the KayKit party in instead, when its sheets are built.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RENDERED = REPO / "asset_library" / "kaykit" / "KayKit_Rendered_Sheets"
SOURCE = (("license", "CC0 1.0"), ("source", "KayKit (Kay Lousberg), rendered sheets"))
CAST = {  # party member -> rendered character (the user's choice, 2026-10-23)
    "hero_01": "knight",  # Roger: sword and shield
    "hero_02": "mage",  # Mira: staff and open spellbook
    "hero_03": "rogue_hooded",  # Vesper: wand and closed spellbook
    "hero_04": "rogue",  # Cael: two daggers
}


FIELD_LOOKS = {  # the party's Lucifer field look -> the rendered character that replaces it
    "warrior": "knight",
    "sorceress": "mage",
    "necromancer": "rogue_hooded",
    "cultist": "rogue",
}


def built():
    return all((RENDERED / f"{key}_battle.png").is_file() for key in CAST.values())


def available():
    """True when the build asks for the KayKit party (``ASTERIA_FV_PARTY=kaykit``) and its
    sheets exist."""
    return os.environ.get("ASTERIA_FV_PARTY", "").lower() == "kaykit" and built()


def field_character(assets, key, look, name):
    """A party member's field look from its rendered 3 x 4 walking sheet (rows down, left,
    right, up): ``idle_<facing>`` is the middle step, ``walk_<facing>`` the three steps and
    back; the sheet is marked ``smooth``. Returns ``(sheet asset id, clips asset id)`` like
    ``trial_maps.character``."""
    from PIL import Image

    rendered = FIELD_LOOKS[look]
    meta = json.loads((RENDERED / f"{rendered}_field.json").read_text(encoding="utf-8"))
    image = Image.open(RENDERED / f"{rendered}_field.png").convert("RGBA")
    cell = int(meta["frame_size"][0])
    frames = [(c * cell, r * cell, cell, cell) for r in range(4) for c in range(3)]
    clips = {}
    for row, facing in enumerate(meta["rows"]):
        base = row * 3
        clips[f"idle_{facing}"] = ([base + 1], 0.2, True)
        clips[f"walk_{facing}"] = ([base, base + 1, base + 2, base + 1], 0.12, True)
    sheet = assets.sheet(key, image, frames, name, scaling=meta["scaling"])
    return sheet, assets.clips(key, clips, name)


def battle_sheet(key):
    """``(image, (frame w, frame h), clips, scale, body_height)`` of a rendered character."""
    from PIL import Image

    meta = json.loads((RENDERED / f"{key}_battle.json").read_text(encoding="utf-8"))
    image = Image.open(RENDERED / f"{key}_battle.png").convert("RGBA")
    frame = (int(meta["frame_size"][0]), int(meta["frame_size"][1]))
    return image, frame, dict(meta["clips"]), float(meta["scale"]), int(meta["body_height"])


def field_sheet(out_dir):
    """The hero's walking sheet; returns the manifest's field settings for it."""
    out_dir = Path(out_dir)
    key = CAST["hero_01"]
    shutil.copyfile(RENDERED / f"{key}_field.png", out_dir / "player_field_sheet.png")
    meta = json.loads((RENDERED / f"{key}_field.json").read_text(encoding="utf-8"))
    return {"player_frame_size": list(meta["frame_size"]), "player_scaling": meta["scaling"]}


def patch_manifest(root):
    """After ``write_manifest``: the walker is a smooth sheet (drawn with blended pixels)."""
    path = Path(root) / "playable_test_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["field"].update(field_sheet(Path(root) / "playable_assets"))
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def credits_rows():
    cc0 = "[CC0 1.0](http://creativecommons.org/publicdomain/zero/1.0/)"
    names = ", ".join(f"{member}: {key}" for member, key in CAST.items())
    return [
        f"| `battle/hero_01.png` .. `hero_04.png`, `player_field_sheet.png` ({names}) | KayKit "
        "Adventurers 2.0 and KayKit Character Animations 1.1 (3D characters, props and "
        "animations), photographed into 2D sheets by `scripts/build_kaykit_art.py` with Blender "
        f"| Kay Lousberg (www.kaylousberg.com) | {cc0} |"
    ]
