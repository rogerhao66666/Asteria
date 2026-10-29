import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def doc():
    return (ROOT / "docs" / "history" / "BATCH86_SYSTEM_CLOSURE_AUDIT.md").read_text()


def data():
    return json.loads((ROOT / "docs" / "history" / "BATCH86_CLOSURE_CHECKLIST.json").read_text())


def test_conditional_not_false_production_pass():
    assert "CONDITIONAL PASS" in doc()
    assert "NOT a claim" in doc()


def test_no_architecture_blocker():
    assert data()["architecture_blockers"] == []


def test_real_integration_gates_explicit():
    required = {
        "real_renderer_backend",
        "real_project_scene_save_load",
        "full_repository_regression",
        "starter_asset_real_pipeline_validation",
        "final_vertical_slice",
    }
    assert required.issubset(data()["remaining_gates"])


def test_composition_invariants():
    t = doc()
    for phrase in (
        "Baked, Layered, Attached, Procedural, and Hybrid",
        "Smooth property animation is independent from sprite frame count",
        "Vibration is generic continuous modulation",
        "Source assets may remain baked",
    ):
        assert phrase in t


def test_no_sixth_canonical_doc():
    assert "No new top-level canonical document" in doc()


def test_architecture_reopen_policy():
    assert "concrete_production_integration_failure" in data()["architecture_reopen_policy"]
