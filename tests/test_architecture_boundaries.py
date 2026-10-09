"""Source-level layering rules from CODEX_HANDOFF.md and ASTERIA_SPEC.md §44."""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "asteria"

# Format-specific (RPG Maker MV) knowledge must end at the asset adapter boundary.
CORE_LAYERS = ("core", "gameplay", "rpg", "events", "graphics", "render", "runtime", "presentation", "platform")
MV_PATTERN = re.compile(r"rpg_maker|RPGMaker|mv_weapon|mv-weapon|MVGenerator")

# Runtime layers must stay importable without the Editor or Qt.
EDITOR_IMPORT = re.compile(r"^\s*(from|import)\s+(asteria\.editor|PySide6)\b", re.MULTILINE)
# Known pre-existing exceptions, tracked in docs/audits (RISK-05); do not add more.
EDITOR_IMPORT_ALLOWED = {
    "runtime/preview.py",
    "presentation/workspace_qt.py",
}


def _sources(layer):
    return sorted((SRC / layer).rglob("*.py"))


def test_mv_semantics_stay_inside_the_asset_adapter_boundary():
    offenders = [
        f"{path.relative_to(SRC)}:{number}"
        for layer in CORE_LAYERS
        for path in _sources(layer)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if MV_PATTERN.search(line)
    ]
    assert offenders == []


def test_runtime_layers_do_not_import_the_editor_or_qt():
    offenders = [
        str(path.relative_to(SRC))
        for layer in CORE_LAYERS
        for path in _sources(layer)
        if EDITOR_IMPORT.search(path.read_text(encoding="utf-8"))
        and str(path.relative_to(SRC)) not in EDITOR_IMPORT_ALLOWED
    ]
    assert offenders == []
