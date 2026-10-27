"""D93: job icons are figures and emblems, not equipment.

D91 drew each job from the demo's gear (a sword for the Brave, a helmet for the Knight), so a
job looked like an item. Now every job shows a figure or an emblem from the 7Soul icons (CC0,
``asset_library/opengameart/7Soul_496_RPG_Icons``), copied unchanged into
``playable_assets/icons_7soul/`` like the demo's other 7Soul icons: fighters are figures in their
colour, the holy jobs crosses and angels, the dark jobs shadows. No two jobs share a picture and
no other record uses these ones. The D91 pictures (``lucifer/icons/job_*.png``) are removed.

Run it once over ``project.asteria.json``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1] / "asset_library" / "opengameart" / "7Soul_496_RPG_Icons"
FOLDER = "playable_assets/icons_7soul"
# job: the 7Soul picture
JOB_ICONS = {
    "brave": "S_Buff08",  # a hero, arms raised
    "duelist": "S_Buff02",  # a fighter, pointing ahead
    "weapon_master": "S_Buff14",  # red, flexing
    "knight": "S_Buff03",  # blue, a crest on the chest
    "guardian": "S_Buff10",  # blue, standing firm
    "forgemaster": "S_Physic01",  # a fiery swirl
    "rogue": "S_Buff04",  # green, running
    "archmage": "S_Magic02",  # a blue magic sun
    "sage": "S_Light01",  # a spark of light
    "mystic": "S_Light03",  # the moon
    "cleric": "S_Holy03",  # a red cross
    "priest": "S_Holy02",  # a cross on an altar
    "bishop": "S_Holy08",  # a crowned angel
    "necromancer": "S_Shadow16",  # a hooded shade
    "lich": "S_Shadow07",  # a winged skull
    "death_lord": "S_Shadow14",  # a dark eye
    "cultist": "S_Fire08",  # a burning pentagram
    "heretic": "S_Buff13",  # a purple figure
    "zealot": "S_Fire03",  # a fanatic's flame
    "spirit": "S_Ice08",  # a pale ghost
}


def main():
    path = HERE / "project.asteria.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(set(JOB_ICONS.values())) == len(JOB_ICONS)
    for job in data["rpg_database"]["classes"]:
        name = JOB_ICONS.get(job["class_id"])
        if name is None:
            continue
        shutil.copyfile(SOURCE / f"{name}.png", HERE / FOLDER / f"{name}.png")
        old = job.get("icon_id") or ""
        job["icon_id"] = f"{FOLDER}/{name}.png"
        if old.startswith("playable_assets/lucifer/icons/job_"):
            (HERE / old).unlink(missing_ok=True)
    text = json.dumps(data, indent=2) + "\n"
    assert "lucifer/icons/job_" not in text
    path.write_text(text, encoding="utf-8")
    print(f"{len(JOB_ICONS)} jobs show a figure or an emblem")


if __name__ == "__main__":
    main()
