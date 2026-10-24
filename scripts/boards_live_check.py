"""Real-window check of Hearthfold's Bounty Board, Guild Office and Starfall Chest (U5, silent).

    ASTERIA_MUTE=1 python scripts/boards_live_check.py [OUTPUT_DIR]

Walks up to each object on the plaza and presses the interact key the way a player does, in
English and in Traditional Chinese: the board opens on its cards, Enter takes the first bounty
and Space turns its card over; the clerk's office lists the companions, Enter twice hires one;
the chest pulls ten for star stones and is pictured as its chest shakes, as it opens and with
the prizes, then on the rates page. Every screen is pictured (``board_*``, ``recruit_*``,
``gacha_*``) and ``boards_results.json`` lists what was checked.
"""

from __future__ import annotations

import importlib.util
import json
import os
import random
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
    out = Path(argv[0] if argv else REPO / "docs" / "audits" / "evidence" / "ui_u5")
    out.mkdir(parents=True, exist_ok=True)
    pump = _helpers()._pump
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=1280, height=720
    )
    runtime.open()
    driver = pygame.display.get_driver()
    game = runtime.game
    wallet = game.save.rpg_state.currencies
    checks = {}

    def shot(name, wait=0.4):
        pump(runtime, wait)
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
    game.transfer_player(town.id, 376.0, 228.0, facing="up")
    pump(runtime, 1.0)
    shot("field_boards")
    for locale, tag in (("en", "en"), ("zh-TW", "zh")):
        game.set_locale(locale)
        # -- the Bounty Board
        walk_up_to("Bounty Board")
        screen = runtime._service_screen
        checks[f"{tag}_board_opens"] = runtime._ui_mode == "service" and (
            screen is not None and screen.SCREEN == "quest_board"
        )
        shot(f"{tag}_board")
        key(pygame.K_RETURN)
        quest = screen.selected()[0].quest_id
        checks[f"{tag}_board_took"] = game.quest_log.status(quest) == "active"
        key(pygame.K_SPACE)
        checks[f"{tag}_board_flipped"] = screen.flipped
        shot(f"{tag}_board_flipped")
        key(pygame.K_ESCAPE)
        key(pygame.K_ESCAPE)
        checks[f"{tag}_board_closed"] = runtime._ui_mode == "field"
        game.save.rpg_state.quests.pop(quest, None)  # the other language takes it again
        # -- the Guild Office
        walk_up_to("Guild Clerk")
        screen = runtime._service_screen
        checks[f"{tag}_recruit_opens"] = screen is not None and screen.SCREEN == "recruit"
        shot(f"{tag}_recruit")
        key(pygame.K_RETURN)
        checks[f"{tag}_recruit_asks"] = screen.asking
        shot(f"{tag}_recruit_ask")
        key(pygame.K_RETURN)
        checks[f"{tag}_recruit_hired"] = "hero_02" in game.save.rpg_state.party_actor_ids
        shot(f"{tag}_recruit_hired", 0.2)
        key(pygame.K_x)  # send her away again (half the price back)
        checks[f"{tag}_recruit_dismissed"] = "hero_02" not in game.save.rpg_state.party_actor_ids
        key(pygame.K_ESCAPE)
        # -- the Starfall Chest
        wallet["star_stones"] = 300.0
        walk_up_to("Starfall Chest")
        screen = runtime._service_screen
        checks[f"{tag}_gacha_opens"] = screen is not None and screen.SCREEN == "gacha"
        shot(f"{tag}_gacha")
        key(pygame.K_RIGHT)
        results = screen.confirm(random.Random(5))
        checks[f"{tag}_gacha_ten"] = len(results or ()) == 10 and wallet["star_stones"] == 30
        b = screen.banner
        pump(runtime, b.appear_seconds + b.shake_seconds / 2)
        shot(f"{tag}_gacha_shake", 0.0)
        pump(runtime, b.shake_seconds / 2 + b.open_seconds * 0.8)
        shot(f"{tag}_gacha_open", 0.0)
        pump(runtime, 1.0)
        checks[f"{tag}_gacha_results"] = screen.page == "results"
        shot(f"{tag}_gacha_results")
        key(pygame.K_RETURN)
        key(pygame.K_r)
        checks[f"{tag}_gacha_rates"] = screen.page == "rates"
        shot(f"{tag}_gacha_rates")
        key(pygame.K_ESCAPE)
        key(pygame.K_h)
        shot(f"{tag}_gacha_history")
        key(pygame.K_ESCAPE)
        key(pygame.K_ESCAPE)
        checks[f"{tag}_gacha_closed"] = runtime._ui_mode == "field"
    runtime.close()
    report = {"driver": driver, "checks": checks}
    (out / "boards_results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0 if all(checks.values()) and driver == "cocoa" else 1


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
