"""ARPG stress scene (D22 A2): enemies + projectiles in a real GameSession field update, profiled
per kernel set.

    python scripts/arpg_stress.py OUTPUT.json [--enemies 300] [--projectiles 500] [--frames 300]
                                  [--kernels python numpy]

Headless (engine work only). Compare results only between runs on the same machine.
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from asteria.validation.arpg_stress import run_arpg_stress  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--enemies", type=int, default=300)
    parser.add_argument("--projectiles", type=int, default=500)
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--kernels", nargs="+", default=["python", "numpy"])
    args = parser.parse_args(argv)
    reports = {}
    for kernel in args.kernels:
        report = run_arpg_stress(
            REPO,
            enemies=args.enemies,
            projectiles=args.projectiles,
            frames=args.frames,
            kernel=kernel,
        )
        reports[kernel] = report
        sections = ", ".join(f"{k}={v['mean_ms']}" for k, v in report["sections"].items())
        print(
            f"{kernel:6} frame mean={report['frame']['mean_ms']}ms "
            f"p95={report['frame']['p95_ms']}ms "
            f"hits={report['arpg']['hits']} | {sections}"
        )
    Path(args.output).write_text(json.dumps(reports, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
