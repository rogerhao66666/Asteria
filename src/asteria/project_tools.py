"""Project maintenance commands: upgrade to the current format and export a playable game.

asteria-upgrade path/to/project.asteria.json        # rewrites at the current version (.bak kept)
asteria-export  path/to/project.asteria.json OUT    # portable game folder with run_game.py
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_FILE = "project.asteria.json"
RESOURCE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".ogg", ".wav", ".mp3", ".json", ".ttf", ".otf"}
NOTICE_NAMES = ("CREDITS.md", "CREDITS.txt", "LICENSE", "LICENSE.txt", "LICENSE.md")
RESOURCE_DIRS = ("reference_data",)

LAUNCHER = '''"""Launch this exported Asteria game (requires: pip install "asteria[pygame]")."""
import sys
from pathlib import Path

from asteria.runtime.preview import main

if __name__ == "__main__":
    raise SystemExit(main([str(Path(__file__).with_name("{project}")), *sys.argv[1:]]))
'''


def _registry():
    from asteria.editor.model import EditorDocument

    return EditorDocument().component_registry


def load_project(path):
    from asteria.project import Project

    return Project.load_json(Path(path), _registry())


def upgrade_project(path, *, backup=True):
    """Rewrite a project file at the current format version; returns (old, new) versions."""
    path = Path(path)
    old_version = json.loads(path.read_text(encoding="utf-8")).get("version")
    project = load_project(path)
    if backup:
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    project.save_json(path)
    return old_version, project.to_data()["version"]


@dataclass
class ExportReport:
    output: Path
    files: list[Path] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def _manifest_paths(value):
    if isinstance(value, str):
        if Path(value).suffix.lower() in RESOURCE_SUFFIXES and not Path(value).is_absolute():
            yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _manifest_paths(item)
    elif isinstance(value, list):
        for item in value:
            yield from _manifest_paths(item)


def referenced_files(project, root):
    """Relative paths of every resource the project (and its playable manifest) uses."""
    root = Path(root)
    paths = set()
    for record in project.assets.records():
        paths.add(str(record.source_path))
    for asset in project.assets.snapshot():
        uri = Path(asset.source.uri)
        if not uri.is_absolute():
            paths.add(str(uri))
    manifest = root / "playable_test_manifest.json"
    if manifest.is_file():
        paths.add(manifest.name)
        paths.update(_manifest_paths(json.loads(manifest.read_text(encoding="utf-8"))))
    for directory in RESOURCE_DIRS:
        base = root / directory
        if base.is_dir():
            paths.update(str(p.relative_to(root)) for p in base.rglob("*") if p.is_file())
    return sorted(paths)


def export_game(project_path, output, *, allow_missing=False):
    """Copy a project and everything it references into ``output`` with a launcher."""
    project_path = Path(project_path)
    root = project_path.parent
    output = Path(output)
    project = load_project(project_path)
    report = ExportReport(output)
    files = referenced_files(project, root)
    report.missing = [p for p in files if not (root / p).is_file()]
    if report.missing and not allow_missing:
        raise FileNotFoundError("missing project resources: " + ", ".join(report.missing))
    output.mkdir(parents=True, exist_ok=True)
    project.save_json(output / PROJECT_FILE)
    report.files.append(output / PROJECT_FILE)
    notice_dirs = set()
    for relative in files:
        source = root / relative
        if not source.is_file():
            continue
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        report.files.append(target)
        notice_dirs.update(parent for parent in source.parents if root in parent.parents or parent == root)
    for directory in notice_dirs:  # attribution / license files travel with the assets
        for name in NOTICE_NAMES:
            notice = directory / name
            if notice.is_file():
                target = output / notice.relative_to(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(notice, target)
                report.files.append(target)
    launcher = output / "run_game.py"
    launcher.write_text(LAUNCHER.format(project=PROJECT_FILE), encoding="utf-8")
    report.files.append(launcher)
    return report


def upgrade_main(argv=None):
    parser = argparse.ArgumentParser(description="Upgrade an Asteria project file to the current format")
    parser.add_argument("project")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args(argv)
    old, new = upgrade_project(args.project, backup=not args.no_backup)
    print(f"{args.project}: version {old} -> {new}")
    return 0


def export_main(argv=None):
    parser = argparse.ArgumentParser(description="Export an Asteria project as a playable game folder")
    parser.add_argument("project")
    parser.add_argument("output")
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args(argv)
    report = export_game(args.project, args.output, allow_missing=args.allow_missing)
    print(f"Exported {len(report.files)} files to {report.output}")
    for missing in report.missing:
        print(f"  missing: {missing}")
    print(f"Run: python {report.output / 'run_game.py'}")
    return 0
