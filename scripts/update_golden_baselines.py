"""Rewrite tests/golden/baselines/{golden_summary,regression}.json from the current code and assets.

    python scripts/update_golden_baselines.py

Only run this after reading tests/golden/README.md ("Updating baselines"): the
suite must pass all eight checks first, and the diff of the baseline must be
reviewed and explained in the commit message.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from asteria.validation.golden import run_golden_suite, summary_json  # noqa: E402
from asteria.validation.regression import regression_snapshot  # noqa: E402

BASELINE = REPO / "tests" / "golden" / "baselines" / "golden_summary.json"


def main():
    report = run_golden_suite(REPO / "tests" / "golden" / "assets")
    if not report.ok:
        for asset_id, check, message in report.failures:
            print(f"FAIL {asset_id} [{check}] {message}")
        print("Baseline NOT updated: fix the failures first.")
        return 1
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(summary_json(report) + "\n", encoding="utf-8")
    regression = BASELINE.with_name("regression.json")
    regression.write_text(json.dumps(regression_snapshot(REPO), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"updated {BASELINE.relative_to(REPO)} and {regression.relative_to(REPO)}; review `git diff` before committing"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
