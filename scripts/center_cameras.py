"""Point every scene camera of a saved project at the main character, and let the Player's place
in the scene be where the game starts.

    python scripts/center_cameras.py PROJECT_DIR [PROJECT_DIR ...]

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

from asteria.editor.scene_cameras import center  # noqa: E402


def center_file(folder):
    import json

    path = Path(folder) / "project.asteria.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = center(data)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return changed


def main(argv=None):
    for folder in list(sys.argv[1:] if argv is None else argv):
        print(f"{folder}: {center_file(folder)} camera(s) on the player")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
