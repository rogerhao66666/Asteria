"""Runtime benchmark: field with many AI enemies + choreographed battle, profiled.

    python scripts/runtime_benchmark.py OUTPUT.json [--real-window] [--enemies 50] [--frames 600]

Headless by default (engine work only); --real-window opens a real window and
also measures presentation and frame pacing. Compare results only between
runs on the same machine.
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from asteria.validation.benchmark import run_benchmark  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--real-window", action="store_true")
    parser.add_argument("--enemies", type=int, default=50)
    parser.add_argument("--frames", type=int, default=600)
    args = parser.parse_args(argv)
    reports = run_benchmark(
        REPO,
        field_frames=args.frames,
        battle_frames=args.frames,
        enemies=args.enemies,
        real_window=args.real_window,
    )
    Path(args.output).write_text(json.dumps(reports, indent=2), encoding="utf-8")
    for name, report in reports.items():
        frame = report["frame"]
        pacing = report["pacing"] or {}
        print(
            f"{name:7} frames={report['frames']} mean={frame['mean_ms']}ms "
            f"p95={frame['p95_ms']}ms "
            f"fps={pacing.get('measured_fps')} "
            f"entities={report['counters'].get('entity_count', {}).get('max')} "
            f"unsupported={sorted(report['unsupported'])} not_recorded={report['not_recorded']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
