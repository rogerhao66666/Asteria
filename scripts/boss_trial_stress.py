"""Real-window load test of the Boss Trial: the boss and eight wisps at once, the hero tanky enough
to keep going, battle played by key presses for a fixed time; frame times are measured.

    python scripts/boss_trial_stress.py OUTPUT_DIR [--seconds 25]

Writes ``stress_results.json`` (frames, average and 95th percentile frame time, fps, the worst
frame) and a screenshot in the middle of the fight.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import boss_trial_live_check as live  # noqa: E402


def main(argv=None):
    import pygame
    import run_trial_smoke as smoke

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0] if argv else REPO / "docs" / "audits" / "evidence" / "boss_trial")
    seconds = float(argv[argv.index("--seconds") + 1]) if "--seconds" in argv else 25.0
    out.mkdir(parents=True, exist_ok=True)
    helper = live._helpers()
    key = helper._key
    project = Project.load_json(
        live.DEMO / "project.asteria.json", EditorDocument().component_registry
    )
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), live.DEMO, width=1280, height=720
    )
    runtime.open()
    game = runtime.game
    smoke.prepare(game, Counter(), "sage")
    runtime._ui_mode = "field"
    runtime.clock.tick(60)
    game.start_encounter("swarm")
    for hero_id in game.active_hero_ids():
        pool = game.battle.member(hero_id).subject.resources
        pool.define("vitality", 900_000, current=900_000, replace=True)
    runtime._battle_presentation.begin()
    runtime._advance_to_hero_turn()
    times, shot_taken, start = [], False, time.perf_counter()
    last = start
    enemies = len(game.active_enemy_ids())
    while time.perf_counter() - start < seconds and runtime.running:
        dt = min(runtime.clock.tick(60) / 1000.0, 0.05)
        if not runtime._battle_presentation.busy() and runtime._battle_actor():
            key(pygame.K_RETURN)
            key(pygame.K_RETURN, up=True)
        runtime._frame(pygame.event.get(), dt)
        runtime.present()
        now = time.perf_counter()
        times.append((now - last) * 1000.0)
        last = now
        if not shot_taken and now - start > seconds / 2:
            pygame.image.save(runtime.capture(), str(out / "stress_swarm.png"))
            shot_taken = True
        if runtime._victory or runtime._defeat:
            break
    driver = pygame.display.get_driver()
    runtime.close()
    ordered = sorted(times)
    report = {
        "driver": driver,
        "enemies_at_start": enemies,
        "seconds": round(time.perf_counter() - start, 1),
        "frames": len(times),
        "avg_ms": round(sum(times) / len(times), 2),
        "p95_ms": round(ordered[int(len(ordered) * 0.95)], 2),
        "worst_ms": round(ordered[-1], 2),
        "fps": round(len(times) / max(sum(times) / 1000.0, 1e-9), 1),
        "battle_over": bool(runtime._victory or runtime._defeat),
    }
    (out / "stress_results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
