"""Copy the two reference projects into the package as project templates.

    python scripts/sync_templates.py            # write src/asteria/templates/
    python scripts/sync_templates.py --check    # exit 1 when the package copies are stale

The editor's File > New from Template reads ``src/asteria/templates`` (shipped with the
package). The reference projects stay the source: edit them, rebuild them, then sync.
"""

from __future__ import annotations

import filecmp
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "src" / "asteria" / "templates"
SKIP = {"__pycache__", ".DS_Store", "build_project.py", "art.py", "maps.py"}
TEMPLATES = {  # template id -> (reference project folder, guide)
    "party_rpg": ("octopath_demo", "START_HERE_party_rpg.md"),
    "action_rpg": ("diablo_demo", "START_HERE_action_rpg.md"),
}


def _files(root):
    return sorted(
        p.relative_to(root)
        for p in root.rglob("*")
        if p.is_file() and not (set(p.relative_to(root).parts) & SKIP)
    )


def sync():
    for template_id, (folder, guide) in TEMPLATES.items():
        source, target = REPO / "reference_projects" / folder, OUT / template_id
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, ignore=shutil.ignore_patterns(*SKIP))
        shutil.copyfile(REPO / "docs" / "templates" / guide, target / "START_HERE.md")


def stale():
    """Template ids whose package copy differs from the reference project (or is missing)."""
    out = []
    for template_id, (folder, guide) in TEMPLATES.items():
        source, target = REPO / "reference_projects" / folder, OUT / template_id
        if not target.is_dir():
            out.append(template_id)
            continue
        expected = _files(source)
        have = [p for p in _files(target) if p.name != "START_HERE.md"]
        if expected != have or any(
            not filecmp.cmp(source / p, target / p, shallow=False) for p in expected
        ):
            out.append(template_id)
            continue
        if not filecmp.cmp(REPO / "docs" / "templates" / guide, target / "START_HERE.md", False):
            out.append(template_id)
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--check" in argv:
        bad = stale()
        print("stale templates:", bad or "none")
        return 1 if bad else 0
    sync()
    print("synced", ", ".join(TEMPLATES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
