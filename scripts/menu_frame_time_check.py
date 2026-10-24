"""How long a frame of every menu screen takes, in a real window (U6, silent).

    ASTERIA_MUTE=1 python scripts/menu_frame_time_check.py [OUTPUT_DIR]

Each screen of ``trial_ui_tour`` is opened, drawn 10 frames to settle, then 60 frames are timed
(the runtime's own ``_frame``: input, update, drawing and the flip). ``frame_times.json`` lists
every screen's mean, 95th percentile and slowest frame in milliseconds; the run fails when a
screen's 95th percentile is over 16.7 ms (one frame at 60 fps).
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(DEMO))
for key in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER", "QT_QPA_PLATFORM"):
    os.environ.pop(key, None)
BUDGET_MS = 1000 / 60


def main(argv=None):
    import pygame
    import trial_ui_tour

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0] if argv else REPO / "docs" / "audits" / "evidence" / "ui_u6")
    out.mkdir(parents=True, exist_ok=True)
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=1280, height=720
    )
    runtime.open()
    driver = pygame.display.get_driver()
    game = runtime.game
    trial_ui_tour.prepare(game)
    times = {}
    for locale, tag in (("en", "en"), ("zh-TW", "zh")):
        game.set_locale(locale)
        for name, setup in trial_ui_tour.screens(runtime):
            setup()
            for _ in range(10):
                runtime._frame(pygame.event.get(), 1 / 60)
            spent = []
            for _ in range(60):
                start = time.perf_counter()
                runtime._frame(pygame.event.get(), 1 / 60)
                spent.append((time.perf_counter() - start) * 1000)
            spent.sort()
            times[f"{tag}_{name}"] = {
                "mean": round(statistics.fmean(spent), 2),
                "p95": round(spent[int(len(spent) * 0.95) - 1], 2),
                "max": round(spent[-1], 2),
            }
            trial_ui_tour.reset(runtime)
    runtime.close()
    slow = {k: v for k, v in times.items() if v["p95"] > BUDGET_MS}
    report = {"driver": driver, "budget_ms": round(BUDGET_MS, 2), "slow": slow, "times": times}
    (out / "frame_times.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    worst = sorted(times.items(), key=lambda kv: -kv[1]["p95"])[:8]
    print(json.dumps({"driver": driver, "screens": len(times), "slow": slow}, indent=2))
    for name, value in worst:
        mean, p95, top = value["mean"], value["p95"], value["max"]
        print(f"{name:<28} mean {mean:6.2f}  p95 {p95:6.2f}  max {top:6.2f}")
    return 0 if not slow and driver == "cocoa" else 1


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
