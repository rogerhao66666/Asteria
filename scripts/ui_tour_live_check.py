"""Real-window tour of every menu screen of the Full Verification demo (macOS, Cocoa).

    ASTERIA_MUTE=1 python scripts/ui_tour_live_check.py OUTPUT_DIR [NAME,NAME...]

Each screen is opened the way the game opens it and pictured in English and Traditional
Chinese: title, pause, settings, controls, save slots, the status menu's four pages, the bag,
the skill tree, the build menu, the equipment doll and the enhance pages, the crafting
stations' tabs, the bounty board, the guild office, the Starfall Chest (banner, ten prizes,
rates, history), a shop and its sell tab, the quest log, pets, achievements, bestiary, the
backlog, music room, credits, ability slots, an equip offer, a battle and its item list,
victory and game over.
``results.json`` lists the screens. Names after the folder (``crafting,shop``) picture only the
screens whose names start with one of them.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(DEMO))
for key in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER", "QT_QPA_PLATFORM"):
    os.environ.pop(key, None)


def _helpers():
    spec = importlib.util.spec_from_file_location(
        "real_machine_validation", REPO / "scripts" / "real_machine_validation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv=None):
    import pygame
    import trial_ui_tour

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0] if argv else REPO / "docs" / "audits" / "evidence" / "ui_tour")
    out.mkdir(parents=True, exist_ok=True)
    only = tuple(argv[1].split(",")) if len(argv) > 1 else ()
    pump = _helpers()._pump
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=1280, height=720
    )
    runtime.open()
    driver = pygame.display.get_driver()
    game = runtime.game
    trial_ui_tour.prepare(game)
    shots, errors = [], {}

    def shot(name):
        pump(runtime, 0.5)
        pygame.image.save(runtime.capture(), str(out / f"{name}.png"))
        shots.append(name)

    def visit(name, setup):
        try:
            setup()
            shot(name)
        except Exception as exc:  # noqa: BLE001 - noted, the tour goes on
            errors[name] = f"{type(exc).__name__}: {exc}"
        trial_ui_tour.reset(runtime)
        pump(runtime, 0.2)

    def battle():
        game.start_encounter("woods_patrol")
        runtime._turn_actor = None
        runtime._battle_presentation.begin()
        runtime._advance_to_hero_turn()
        pump(runtime, 2.0)

    screens = (
        *trial_ui_tour.screens(runtime),
        ("battle", battle),
        ("game_over", lambda: setattr(runtime, "_ui_mode", "game_over")),
    )
    for locale, tag in (("en", "en"), ("zh-TW", "zh")):
        game.set_locale(locale)
        for name, setup in screens:
            if not only or name.startswith(only):
                visit(f"{tag}_{name}", setup)
        for _ in range(8):
            if not game.equip_offers:
                break
            game.equip_offers.pop(0)
    runtime.close()
    report = {"driver": driver, "shots": shots, "errors": errors}
    (out / "results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"driver": driver, "count": len(shots), "errors": errors}, indent=2))
    return 0 if not errors and driver == "cocoa" else 1


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
