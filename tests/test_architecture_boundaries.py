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


# Everything but the asset adapters and the editor (which hosts the MV import tools) is MV-free text.
NON_ADAPTER_LAYERS = ("authoring", "validation")
TOP_LEVEL = ("project.py", "project_tools.py", "reference_data.py", "reference_ids.py", "reference_world.py")


def test_authoring_validation_and_top_level_modules_are_mv_free():
    paths = [p for layer in NON_ADAPTER_LAYERS for p in _sources(layer)] + [SRC / name for name in TOP_LEVEL]
    offenders = [
        f"{path.relative_to(SRC)}:{number}"
        for path in paths
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if MV_PATTERN.search(line)
    ]
    assert offenders == []


def test_playing_the_game_never_loads_mv_adapter_code(tmp_path):
    """AST-13 at import level: field, battle (canonical presentation) and save run with no MV module loaded."""
    import os
    import subprocess
    import sys

    import pytest

    pytest.importorskip("pygame")
    script = f"""
import sys
from pathlib import Path
from asteria.project_tools import load_project
from asteria.runtime.battle_presentation_adapters import CanonicalBattleAdapter
from asteria.runtime.game_save import GameRuntimeSave
from asteria.runtime.playable_test_runtime import PlayableTestRuntime
root = Path({str(SRC.parents[1] / "reference_projects" / "complex_reference_rpg")!r})
project = load_project(root / "project.asteria.json")
save = GameRuntimeSave.load_json(root / "saves" / "boss_stress.asteria-save.json", project)
runtime = PlayableTestRuntime(project, save, root, width=960, height=540)
runtime.open()
runtime._battle_presentation = adapter = CanonicalBattleAdapter(runtime)
runtime.game.start_encounter("boss_room")
adapter.begin()
runtime._advance_to_hero_turn()
for _ in range(30):
    runtime._present_battle(0.02)
    adapter.draw()
runtime._use_skill(0)
for _ in range(60):
    runtime._present_battle(0.02)
runtime.game.sync_world_state()
runtime.game.save.save_json(Path({str(tmp_path)!r}) / "s.json")
runtime.close()
loaded = sorted(m for m in sys.modules if "rpg_maker" in m or "character_bundle" in m or "mv_" in m)
print("LOADED", loaded)
"""
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=180
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert "LOADED []" in result.stdout, result.stdout[-500:]
