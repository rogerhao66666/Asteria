"""Point every scene camera of a saved project at the main character, and let the Player's place
in the scene be where the game starts.

    python scripts/center_cameras.py [--add] PROJECT_DIR [PROJECT_DIR ...]

For each Camera2D: it follows the game start's player entity, and it stands where the player is
in that scene (the Player entity), else where the player arrives (the first TRANSFER into the
scene), else unchanged. A game start position that only repeats where the
Player entity already stands is cleared, so dragging the Player in the editor moves the start.
The build scripts call ``center_file`` after saving; running it twice changes nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from asteria.editor.scene_cameras import add_missing_cameras, center  # noqa: E402


def center_file(folder, *, add=False):
    """``add``: a scene without a Camera entity gets one first."""
    import json

    path = Path(folder) / "project.asteria.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    added = add_missing_cameras(data) if add else 0
    changed = center(data)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return added + changed


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    add = "--add" in args  # a scene without a Camera entity gets one
    for folder in (a for a in args if a != "--add"):
        print(f"{folder}: {center_file(folder, add=add)} camera(s) added or aimed at the player")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
