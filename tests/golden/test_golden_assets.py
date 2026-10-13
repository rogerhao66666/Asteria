"""CB13 / AS§34: golden asset suite with committed baselines (see tests/golden/README.md)."""

import json
import shutil
from pathlib import Path

import pytest

from asteria.validation.golden import CHECKS, GOLDEN_CATEGORIES, run_golden_suite

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
BASELINE = HERE / "baselines" / "golden_summary.json"

# Checks every category must run (animation/event/package checks only apply where relevant).
REQUIRED = {
    name: {"import", "metadata", "dimensions", "reload", "references"}
    for name in GOLDEN_CATEGORIES
}
for name in (
    "golden_character",
    "golden_monster",
    "golden_tileset",
    "golden_vfx",
    "golden_projectile",
):
    REQUIRED[name] |= {"animations", "events"}
REQUIRED["golden_skill"] |= {"events"}
REQUIRED["golden_scene"] |= {"package"}


@pytest.fixture(scope="module")
def report():
    return run_golden_suite(ASSETS)


def test_all_eleven_golden_categories_pass_every_required_check(report):
    assert report.ok, report.failures
    assert set(report.summaries) == set(GOLDEN_CATEGORIES)
    for name, required in REQUIRED.items():
        assert required <= set(report.checks_run[name]), (
            name,
            required - set(report.checks_run[name]),
        )
    assert set(CHECKS) == {
        c for checks in report.checks_run.values() for c in checks
    }  # all eight ran


def test_results_match_the_committed_baseline(report):
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    current = json.loads(json.dumps(report.summaries, sort_keys=True))
    for name in GOLDEN_CATEGORIES:
        assert current[name] == baseline[name], (
            f"{name} differs from baseline (see tests/golden/README.md)"
        )


# --- the checks must fail when an asset is broken ---------------------------------


@pytest.fixture
def broken(tmp_path):
    root = tmp_path / "assets"
    shutil.copytree(ASSETS, root)
    return root


def _doc(root, asset_id):
    path = root / asset_id / f"{asset_id}.asset.json"
    return path, json.loads(path.read_text())


def _failed(root):
    return {(a, c) for a, c, _ in run_golden_suite(root).failures}


def test_corrupt_document_fails_import(broken):
    (broken / "golden_ui" / "golden_ui.asset.json").write_text("{not json")
    assert any(check == "import" for _, check in _failed(broken))


def test_resized_image_fails_dimensions(broken):
    from PIL import Image

    Image.new("RGBA", (190, 250)).save(broken / "golden_character" / "walk.png")
    assert ("golden_character", "dimensions") in _failed(broken) or any(
        c == "import" for _, c in _failed(broken)
    )


def test_missing_image_fails(broken):
    (broken / "golden_prop" / "house.png").unlink()
    assert ("golden_prop", "dimensions") in _failed(broken)


def test_undeclared_reference_fails_references(broken):
    path, data = _doc(broken, "golden_skill")
    data["dependencies"] = ["golden_icon"]  # drops projectile + vfx
    path.write_text(json.dumps(data))
    assert ("golden_skill", "references") in _failed(broken)


def test_clip_frame_outside_the_sheet_fails(broken):
    path, data = _doc(broken, "golden_projectile")
    data["payload"]["sprite"]["clips"]["fly"]["frames"] = [0, 1, 2, 9]
    path.write_text(json.dumps(data))
    failures = run_golden_suite(broken).failures
    assert any(c in {"import", "references"} and "frame" in m for _, c, m in failures)


def test_missing_dependency_file_breaks_the_scene_package(broken):
    shutil.rmtree(broken / "golden_npc")
    failed = _failed(broken)
    assert any(
        check == "import" for _, check in failed
    )  # dependency.missing blocks the whole load


def test_timing_change_is_caught_by_the_baseline(broken):
    path, data = _doc(broken, "golden_character")
    data["payload"]["sprite"]["clips"]["walk_down"]["frame_duration"] = 0.2
    path.write_text(json.dumps(data))
    report = run_golden_suite(broken)
    assert report.ok  # still a valid asset...
    baseline = json.loads(BASELINE.read_text())
    assert (
        report.summaries["golden_character"] != baseline["golden_character"]
    )  # ...but not the golden one
