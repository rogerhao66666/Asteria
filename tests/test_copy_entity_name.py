"""COPY_ENTITY takes the new entity's ``name`` (it was documented but dropped)."""

import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "boss_trial_demo"
sys.path.insert(0, str(DEMO))

import run_trial_smoke as smoke  # noqa: E402

from asteria.events.world_commands import WorldCommand  # noqa: E402


def test_a_copied_entity_gets_the_given_name():
    _project, game = smoke.load()
    source = next(
        e.name for e in game.scene.entities() if e.name not in ("Map", "Camera", "Player")
    )
    game.world_commands.dispatch(
        WorldCommand("COPY_ENTITY", {"entity": source, "x": 100, "y": 100, "name": "Echo"})
    )
    names = [e.name for e in game.scene.entities()]
    assert "Echo" in names and names.count(source) == 1
