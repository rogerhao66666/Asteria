"""Delete the files of a project's ``playable_assets`` that nothing refers to.

    python scripts/prune_orphan_assets.py reference_projects/party_rpg_demo [--dry-run]

A file counts as used when its path appears in ``project.asteria.json`` or in
``playable_test_manifest.json`` (``CREDITS.md`` always stays). Run after a reskin so the old
pictures it replaced do not stay in the repository.
"""

from __future__ import annotations

import sys
from pathlib import Path


def orphans(folder):
    folder = Path(folder)
    text = " ".join(
        (folder / name).read_text(encoding="utf-8")
        for name in ("project.asteria.json", "playable_test_manifest.json")
        if (folder / name).exists()
    )
    found = []
    for path in sorted((folder / "playable_assets").rglob("*")):
        if not path.is_file() or path.name == "CREDITS.md":
            continue
        if str(path.relative_to(folder)) not in text:
            found.append(path)
    return found


def prune(folder, *, dry_run=False):
    removed = orphans(folder)
    if not dry_run:
        for path in removed:
            path.unlink()
        for directory in sorted(
            (Path(folder) / "playable_assets").rglob("*"), key=lambda p: -len(p.parts)
        ):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
    return removed


def main(argv):
    dry = "--dry-run" in argv
    for name in [a for a in argv[1:] if not a.startswith("--")]:
        removed = prune(name, dry_run=dry)
        print(f"{name}: {len(removed)} unused files{' (kept)' if dry else ' removed'}")
        for path in removed:
            print("   ", path)


if __name__ == "__main__":
    main(sys.argv)
