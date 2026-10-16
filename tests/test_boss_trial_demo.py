"""The Boss Trial demo: it loads, and a scripted playthrough reaches every system it enables."""

import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "boss_trial_demo"
sys.path.insert(0, str(DEMO))

import run_trial_smoke  # noqa: E402


def test_project_loads_with_the_expected_content():
    project, game = run_trial_smoke.load()
    db = project.rpg_database
    assert {"knight", "duelist", "mystic"} <= set(db.classes)
    assert sum(len(g.nodes) for g in db.progression_graphs.values()) >= 35
    assert db.refine_rules and db.durability_rules and db.equipment_sets
    assert set(db.enemies) >= {"crimson_warlord", "mender_wisp"}
    assert db.classes["knight"].level_growth["power"] > db.classes["mystic"].level_growth.get(
        "power", 0
    )
    assert game.resolve_actor_build(run_trial_smoke.HERO).abilities


def test_scripted_playthrough_hits_every_system(capsys):
    assert run_trial_smoke.main([]) == 0
    assert "NOT HIT" not in capsys.readouterr().out
