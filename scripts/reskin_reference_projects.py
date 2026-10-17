"""Dress the party-RPG reference projects (Octopath demo, complex reference RPG) in Lucifer art.

    python scripts/reskin_reference_projects.py [octopath_demo complex_reference_rpg]

Edits the saved projects in place (project, manifest, pictures, icons) and rewrites their credits.
The build scripts of those projects call ``dress`` at their end, so a rebuild keeps the look.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from lucifer_reskin import Reskin  # noqa: E402

from asteria.editor import EditorDocument  # noqa: E402
from asteria.project import Project  # noqa: E402

HEROES = ("warrior", "sorceress", "cultist", "necromancer")
ENEMIES = {
    "astral_tyrant": "skeleton_king",
    "bone_wraith": "skeleton_hunter",
    "ember_hound": "goblin_berserker",
    "gel_slime": "goblin_slinger",
    "iron_guard": "skeleton_grunt",
    "iron_samurai": "skeleton_ancient",
    "mender_wisp": "cultist",
    "mirror_gazer": "necromancer",
    "pit_viper": "goblin_rider",
    "web_spinner": "goblin_beast",
}
CREDITS = """
## Lucifer art (CC0)

Characters, enemies, equipment, pickups, tilesets and the RPG UI (panels, font, icons) are
Foozle's Lucifer packs, CC0 1.0 (the Readme.txt of each pack: free for all uses, attribution not
required). Re-cut and arranged by `scripts/lucifer_reskin.py`; the packs: Lucifer Warrior,
Necromancer, Sorceress, Cultist, Goblin Slinger / Berserker / Beast / Rider, Skeleton Grunt /
Hunter / Ancient / King, Equipment, Pickups, Exterior / Dungeon / Lava tilesets, RPG UI
(<https://foozlecc.itch.io/>).
"""


def dress(folder):
    folder = Path(folder)
    path = folder / "project.asteria.json"
    project = Project.load_json(path, EditorDocument().component_registry)
    heroes = {f"hero_{i:02d}": HEROES[(i - 1) % 4] for i in range(1, 13)}
    Reskin(project, folder).run(
        heroes=heroes,
        enemies=ENEMIES,
        manifest_path=folder / "playable_test_manifest.json",
        legacy=[heroes[f"hero_{i:02d}"] for i in range(1, 7)],
    )
    project.save_json(path)
    credits = folder / "playable_assets" / "CREDITS.md"
    text = credits.read_text(encoding="utf-8") if credits.exists() else "# Credits\n"
    if "## Lucifer art (CC0)" not in text:
        credits.write_text(text.rstrip("\n") + "\n" + CREDITS, encoding="utf-8")


def main(argv=None):
    names = list(sys.argv[1:] if argv is None else argv) or [
        "octopath_demo",
        "complex_reference_rpg",
    ]
    for name in names:
        dress(REPO / "reference_projects" / name)
        print("dressed", name)


if __name__ == "__main__":
    main()
