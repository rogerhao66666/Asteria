"""Real-window run of the whole Full Verification campaign (macOS, real Cocoa window).

    python scripts/full_verification_campaign_live_check.py OUTPUT_DIR

First a few minutes of real key presses (walk, talk with E, answer with Enter, open the quest log
and the workshop); then the scripted campaign plays on in the same window, a picture at every
milestone. ``results.json`` lists the facts the run counted and the pictures taken.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(DEMO))


def main(argv=None):
    import run_campaign  # sets dummy video / audio drivers for scripted runs: undo that here

    for name in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER", "QT_QPA_PLATFORM"):
        os.environ.pop(name, None)
    import pygame

    from asteria.core import Transform
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    argv = list(sys.argv[1:] if argv is None else argv)
    evidence = REPO / "docs" / "audits" / "evidence" / "full_verification_campaign"
    out = Path(argv[0] if argv else evidence)
    out.mkdir(parents=True, exist_ok=True)
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=1280, height=720
    )
    runtime.open()
    driver = pygame.display.get_driver()
    shots, checks = [], {}
    original = runtime._frame

    def shown(events, dt):  # every frame of the script reaches the window
        original(list(events) + pygame.event.get(), dt)
        runtime.present()

    runtime._frame = shown

    def key(k, hold=0.08):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0))
        for _ in range(max(1, round(hold / 0.016))):
            shown([], 0.016)
        pygame.event.post(pygame.event.Event(pygame.KEYUP, key=k, mod=0))
        shown([], 0.016)

    def shot(name):
        pygame.image.save(runtime.capture(), str(out / f"{name}.png"))
        shots.append(name)

    runtime._ui_mode = "field"
    for _ in range(20):
        shown([], 0.03)
    shot("00_start")
    # -- real key presses --------------------------------------------------------------
    player = runtime.game.player.get(Transform)
    x0 = player.x
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT, mod=0))
    for _ in range(60):
        shown([], 0.016)
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_RIGHT, mod=0))
    checks["walked_by_keys"] = player.x > x0 + 10
    shot("01_walked")
    campaign = run_campaign.Campaign(rt=runtime, log=print)
    campaign.on_shot = shot
    warden = campaign.find("Warden Thessaly").get(Transform)
    player.x, player.y = warden.x, warden.y + 14
    runtime.game.set_player_facing("up")
    key(pygame.K_e)
    shot("02_dialogue")
    for _ in range(40):
        if not runtime.game.event_busy:
            break
        key(pygame.K_RETURN)
    checks["talked_by_keys"] = runtime.game.quest_log.status("q_patrol") == "active"
    key(pygame.K_q)  # the quest log
    for _ in range(10):
        shown([], 0.03)
    shot("03_quests")
    key(pygame.K_ESCAPE)
    runtime._ui_mode = "field"
    # -- the campaign, picture by picture ----------------------------------------------------
    facts = campaign.run()
    runtime._ui_mode = "quests"
    for _ in range(10):
        shown([], 0.03)
    shot("99_quest_log_at_the_end")
    failed = [k for k in run_campaign.REQUIRED if not facts.get(k)] + [
        k for k, v in checks.items() if not v
    ]
    runtime.close()
    report = {
        "driver": driver,
        "status": "PASS" if not failed and driver == "cocoa" else "FAIL",
        "checks": checks,
        "failed": failed,
        "facts": dict(facts),
        "screenshots": shots,
    }
    (out / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("driver", "status", "checks", "failed")}, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
