"""Play the ARPG playground in a real window (D22 A8): the reference field as an action scene.

    python scripts/arpg_playground.py [--side] [--frames N] [--screenshot PATH]

Controls: WASD move, J attack (three-hit combo), K dodge, 1 fire bolt, L lock on, F pick up, B bag, C build,
Space jump (side view), Esc pause.
"""

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--side", action="store_true")
    parser.add_argument("--frames", type=int, default=None)
    parser.add_argument("--screenshot", default=None)
    args = parser.parse_args(argv)
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime
    from asteria.validation.arpg_playground import build_playground

    root = REPO / "reference_projects" / "complex_reference_rpg"
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(project, project.game_start.instantiate(project), root, width=1280, height=720)
    runtime.open()
    build_playground(runtime, "side" if args.side else "topdown")
    frames = 0
    try:
        while runtime.running and (args.frames is None or frames < args.frames):
            dt = min(runtime.clock.tick(60) / 1000.0, 0.05)
            runtime._frame(runtime.pg.event.get(), dt)
            runtime.present()
            frames += 1
        if args.screenshot:
            runtime.pg.image.save(runtime.screen, args.screenshot)
    finally:
        runtime.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
