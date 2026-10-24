"""Real-window check of Hearthfold's Alchemy Table and Forge (U4, macOS Cocoa, silent).

    ASTERIA_MUTE=1 python scripts/crafting_live_check.py [OUTPUT_DIR]

Walks up to each station on the plaza and presses the interact key the way a player does: the
Alchemy Table opens on its Potions tab, Right picks two, Enter brews two potions; Tab moves to
the next tab. The Forge opens on Ingots; its Throwing tab makes three iron balls at once. The
plaza and every screen are pictured (``field_stations``, ``alchemy_*``, ``forge_*``) and
``results.json`` lists what was checked.
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

    from asteria.core import Transform
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0] if argv else REPO / "docs" / "audits" / "evidence" / "ui_u4")
    out.mkdir(parents=True, exist_ok=True)
    pump = _helpers()._pump
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=1280, height=720
    )
    runtime.open()
    driver = pygame.display.get_driver()
    game = runtime.game
    inventory = game.save.rpg_state.inventory
    for item_id, count in (("healing_herb", 4), ("bat_wing", 2), ("iron_ore", 6), ("coal", 6)):
        inventory.add(item_id, count)
    checks = {}

    def shot(name):
        pump(runtime, 0.4)
        pygame.image.save(runtime.capture(), str(out / f"{name}.png"))

    def key(code, wait=0.15):
        for kind in (pygame.KEYDOWN, pygame.KEYUP):
            pygame.event.post(pygame.event.Event(kind, key=code, mod=0, unicode="", scancode=0))
            runtime._frame(pygame.event.get(), 1 / 60)
        pump(runtime, wait)

    def walk_up_to(name):
        entity = next(e for e in game.scene.entities() if e.name == name)
        point = entity.get(Transform)
        player = game.player.get(Transform)
        player.x, player.y = point.x, point.y + 14
        game.set_player_facing("up")
        pump(runtime, 0.3)
        key(pygame.K_e, 0.4)

    runtime._ui_mode = "field"  # past the title screen
    town = next(s for s in project.scenes() if s.name == "Hearthfold")
    game.transfer_player(town.id, 360.0, 196.0, facing="up")
    pump(runtime, 1.0)
    shot("field_stations")
    for locale, tag in (("en", "en"), ("zh-TW", "zh")):
        game.set_locale(locale)
        walk_up_to("Alchemy Table")
        screen = runtime._crafting_screen
        checks[f"{tag}_alchemy_opens"] = runtime._ui_mode == "crafting" and screen.station == (
            "alchemy"
        )
        ids = [r.recipe_id for r in screen.rows()]
        screen.index = ids.index("brew_potion")
        key(pygame.K_RIGHT)
        before = inventory.count("potion")
        shot(f"{tag}_alchemy_two")
        key(pygame.K_RETURN, 0.2)
        checks[f"{tag}_two_potions"] = inventory.count("potion") == before + 4
        shot(f"{tag}_alchemy_made")
        key(pygame.K_TAB)
        checks[f"{tag}_tab_gems"] = screen.page == "gems"
        key(pygame.K_ESCAPE)
        checks[f"{tag}_closed"] = runtime._ui_mode == "field"
        walk_up_to("Forge")
        screen = runtime._crafting_screen
        checks[f"{tag}_forge_opens"] = screen is not None and screen.station == "forge"
        key(pygame.K_TAB)
        ids = [r.recipe_id for r in screen.rows()]
        screen.index = ids.index("forge_iron_ball")
        key(pygame.K_RIGHT)
        key(pygame.K_RIGHT)
        balls = inventory.count("iron_ball")
        key(pygame.K_RETURN, 0.2)
        checks[f"{tag}_three_at_once"] = inventory.count("iron_ball") == balls + 9
        shot(f"{tag}_forge_made")
        key(pygame.K_ESCAPE)
        inventory.add("bat_wing", 2)
        inventory.add("iron_ore", 3)
        inventory.add("coal", 3)
    runtime.close()
    report = {"driver": driver, "checks": checks}
    (out / "crafting_results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0 if all(checks.values()) and driver == "cocoa" else 1


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
