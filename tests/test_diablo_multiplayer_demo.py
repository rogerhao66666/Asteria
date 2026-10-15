"""The multiplayer experiment remains a distinct copy of the offline reference project."""

import json
from pathlib import Path

from asteria.multiplayer.rules import load_rules

ROOT = Path(__file__).resolve().parents[1] / "reference_projects"
OFFLINE = ROOT / "diablo_demo"
MULTIPLAYER = ROOT / "diablo_multiplayer_demo"


def test_multiplayer_demo_copies_the_offline_project_and_assets_without_changing_them():
    for source in OFFLINE.rglob("*"):
        if (
            not source.is_file()
            or "__pycache__" in source.parts
            or source.name
            in {
                "README.md",
                "project.asteria.json",
                "playable_test_manifest.json",
                "build_project.py",
            }
        ):
            continue
        relative = source.relative_to(OFFLINE)
        copied = MULTIPLAYER / relative
        assert copied.is_file(), relative
        assert copied.read_bytes() == source.read_bytes(), relative


def test_multiplayer_demo_has_a_valid_full_per_player_xp_profile():
    project = json.loads((MULTIPLAYER / "project.asteria.json").read_text(encoding="utf-8"))
    profile = json.loads(
        (MULTIPLAYER / ".asteria" / "multiplayer.json").read_text(encoding="utf-8")
    )
    rules = load_rules(MULTIPLAYER / ".asteria" / "multiplayer-rules.json")

    assert project["name"] == "Asteria Diablo Multiplayer Demo"
    assert (
        project["id"]
        == json.loads((OFFLINE / "project.asteria.json").read_text(encoding="utf-8"))["id"]
    )
    assert profile["adapter_factory"] == "asteria.multiplayer.project_demo:build_project_adapter"
    assert profile["connect_on_run"] is True
    assert rules["rewards"]["boss"]["experience"] == {
        "policy": "full_amount_per_eligible_player",
        "amount": 100,
    }
    assert rules["rewards"]["boss"]["eligibility"] == "positive_damage"
    assert rules["rewards"]["boss"]["drops"]["assignment"] == "random_eligible_player"
