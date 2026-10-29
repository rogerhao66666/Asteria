"""Dress the party-RPG reference projects (Party RPG demo, complex reference RPG) in Lucifer art.

    python scripts/reskin_reference_projects.py [party_rpg_demo complex_reference_rpg]

Edits the saved projects in place (project, manifest, pictures, icons) and rewrites their credits.
The build scripts of those projects call ``dress`` at their end, so a rebuild keeps the look.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from lucifer_reskin import Reskin  # noqa: E402
from prune_orphan_assets import prune  # noqa: E402

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
    _drop_unused_icon_assets(project, path)
    write_credits(folder)
    prune(folder)  # the pictures the reskin replaced do not stay behind
    from center_cameras import center_file

    center_file(folder, add=True)  # a Camera entity per scene, on the hero


def _drop_unused_icon_assets(project, path):
    """Icon pictures no record points at (the old atlas cells of gear this game never had)."""
    text = path.read_text(encoding="utf-8")
    unused = [
        asset
        for asset in project.assets.query("icon")
        if text.count(f'"{asset.asset_id}"') <= 1  # only its own record names it
    ]
    for asset in unused:
        project.assets.remove(asset.asset_id)
    if unused:
        project.save_json(path)


def write_credits(folder):
    """The credits of a dressed demo: the Lucifer art, the sounds it ships, the effect pictures
    its build draws."""
    credits = folder / "playable_assets" / "CREDITS.md"
    old = credits.read_text(encoding="utf-8") if credits.exists() else ""
    rows = [line for line in old.split("\n") if line.startswith("| `audio/")]
    if (folder / "playable_assets" / "fx_heal.png").exists():
        rows.append(
            "| `fx_heal.png` | Drawn procedurally by the build script | Asteria project | "
            "Same as the repository |"
        )
    credits.write_text(
        "# Playable assets - credits and licenses\n\n"
        "| File(s) | Source | Author | License |\n|---|---|---|---|\n"
        + "\n".join(rows)
        + "\n"
        + CREDITS
        + "\n## Licensing\n\nEvery file here is CC0 1.0 or drawn by this repository's scripts. "
        "No AI-generated art.\n",
        encoding="utf-8",
    )


def main(argv=None):
    names = list(sys.argv[1:] if argv is None else argv) or [
        "party_rpg_demo",
        "complex_reference_rpg",
    ]
    for name in names:
        dress(REPO / "reference_projects" / name)
        print("dressed", name)


if __name__ == "__main__":
    main()
