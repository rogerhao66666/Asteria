"""CB13: regression baseline, presentation timing and runtime benchmark coverage."""

import json
import random
from pathlib import Path

import pytest

pytest.importorskip("pygame")

from asteria.runtime.profiler import SPEC_METRICS  # noqa: E402
from asteria.validation.benchmark import run_benchmark  # noqa: E402
from asteria.validation.presentation_timing import measure_action_timing  # noqa: E402
from asteria.validation.regression import regression_snapshot  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).resolve().parent / "baselines" / "regression.json"


def test_behaviour_matches_the_regression_baseline():
    snapshot = json.loads(json.dumps(regression_snapshot(REPO), sort_keys=True))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    for key in ("boss_battle", "reference_saves", "rpg_database", "golden_summary"):
        assert snapshot[key] == baseline[key], (
            f"{key} drifted (see tests/golden/README.md before updating)"
        )
    assert snapshot["boss_battle"]["winner"] == "heroes"


@pytest.mark.parametrize(
    "frames",
    [
        [1 / 30] * 60,
        [1 / 60] * 120,
        [1 / 144] * 290,
        [random.Random(3).uniform(0.008, 0.04) for _ in range(120)],
    ],
    ids=["30fps", "60fps", "144fps", "jitter"],
)
def test_presented_beats_land_on_the_first_frame_after_their_authored_time(frames):
    samples = measure_action_timing(REPO, frames)
    assert {s.cue for s in samples} == {
        "attack_pose",
        "effect",
        "hit_pose",
        "damage_number",
        "hit_sound",
    }
    for sample in samples:
        assert sample.ok, (sample.cue, sample.authored, sample.observed, sample.frame)


def test_benchmark_measures_every_spec_metric_or_marks_it_unsupported():
    reports = run_benchmark(REPO, field_frames=40, battle_frames=120, enemies=12)
    measured = set()
    unsupported = set()
    for report in reports.values():
        measured |= set(report["sections"]) | set(report["counters"]) | {"frame", "memory"}
        unsupported |= set(report["unsupported"])
    missing = set(SPEC_METRICS) - measured - unsupported
    assert not missing, missing
    assert reports["field"]["counters"]["entity_count"]["max"] >= 12  # enemies were really spawned
    assert "vfx" in reports["battle"]["sections"] and "ai" in reports["field"]["sections"]
