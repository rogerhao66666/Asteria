"""Build the multiplayer ARPG demo: the offline ARPG demo (``reference_projects/arpg_demo``)
written into this folder under its own name.

The game, its art and its build code live in the offline demo; this folder adds only the
multiplayer profile and rules in ``.asteria/``. A project folder carries its own art, so the
pictures are written here too.

Run: ``python reference_projects/arpg_multiplayer_demo/build_project.py`` (writes this folder;
idempotent).
Play: ``python -m asteria.runtime.preview
reference_projects/arpg_multiplayer_demo/project.asteria.json``.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "arpg_demo"))

import build_project as offline  # noqa: E402

if __name__ == "__main__":
    offline.main(HERE, "Asteria ARPG Multiplayer Demo")
