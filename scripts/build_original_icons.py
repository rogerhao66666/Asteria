"""Draw the original skill / state / pet icons for the two reference projects.

``python scripts/build_original_icons.py`` writes ``skill_<kind>.png`` files under each project's
``playable_assets/icons`` and sets ``icon_id`` on the abilities, states and pet species that match
a keyword (see ``asteria.graphics.forged_icons``). Run it after a project is rebuilt; the build
scripts call the same function. Nothing is downloaded and no AI art is used.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from asteria.graphics.forged_icons import apply_to_project_file  # noqa: E402


def main():
    projects = {
        # ARPG keeps its drawn state glyphs and the potion's item icon; skills get new ones
        "arpg_demo": {"replace": True, "keep": ("potion",), "states": False},
        "party_rpg_demo": {"replace": False, "keep": (), "states": True},
    }
    for name, options in projects.items():
        path = ROOT / "reference_projects" / name / "project.asteria.json"
        print(name, apply_to_project_file(path, **options))


if __name__ == "__main__":
    main()
