"""Real-window check of the engine's own words in Traditional Chinese (Full Verification demo).

    python scripts/built_in_text_live_check.py OUTPUT_DIR

Opens the demo in a real (Cocoa) window and switches it to zh-TW the way Settings ▸ Language
does, then walks the screens with real key presses where the game takes them: the title, the
field, the pause and settings menus, the save slots, the status menu, the battle commands (the
top level, a skill list, a skill's help, a disabled skill's reason, a target), the victory
pages and game over. Every screen is saved as ``zh_<name>.png`` (the pause menu and the battle
commands also in English, ``en_<name>.png``); ``built_in_text_results.json`` lists the words
each screen drew, the checks and the video driver.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import unicodedata
from collections import Counter
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


def _chinese(text):
    return any(unicodedata.east_asian_width(c) == "W" for c in str(text))


def main(argv=None):
    import pygame
    import run_trial_smoke as smoke

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0] if argv else REPO / "docs" / "audits" / "evidence" / "real_machine")
    out.mkdir(parents=True, exist_ok=True)
    helper = _helpers()
    pump, key = helper._pump, helper._key

    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=1280, height=720
    )
    runtime.open()
    driver = pygame.display.get_driver()
    game = runtime.game
    drawn, words, checks = [], {}, {}
    host_text = runtime.text  # every word the host draws is noted as it is drawn

    def text(value, *args, **kwargs):
        drawn.append(str(value))
        return host_text(value, *args, **kwargs)

    runtime.text = text

    def battle_words():  # the battle screen's own words go through its pygame backend
        backend = getattr(runtime._battle_presentation, "_ui_backend", None)
        if backend is None or getattr(backend, "_noted", False):
            return
        draw = backend.draw_text

        def draw_text(item, **kwargs):
            drawn.append(item.text)
            return draw(item, **kwargs)

        backend.draw_text, backend._noted = draw_text, True

    def press(k, wait=0.15):
        key(k)
        pump(runtime, 0.05)
        key(k, up=True)
        pump(runtime, wait)

    def shot(name, *expected):
        """Save the screen; the words drawn on it must include each of ``expected``."""
        battle_words()
        drawn.clear()
        pump(runtime, 0.3)
        pygame.image.save(runtime.capture(), str(out / f"{name}.png"))
        words[name] = sorted(set(drawn))
        missing = [w for w in expected if not any(w in d for d in drawn)]
        checks[name] = not missing
        if missing:
            print(name, "missing", missing)

    def hero_turn(limit=20.0):
        deadline = time.perf_counter() + limit
        while time.perf_counter() < deadline:
            if game.battle is None or runtime._victory or runtime._defeat:
                return None
            battle_words()
            if not runtime._battle_presentation.busy() and runtime._battle_actor():
                return runtime._battle_actor()
            pump(runtime, 0.1)
        return None

    def menu_shown(limit=15.0):
        """Wait for the command menu (a status tick or a blow may still be playing)."""
        deadline = time.perf_counter() + limit
        while time.perf_counter() < deadline:
            battle_words()
            screen = getattr(runtime._battle_presentation, "screen", None)
            menu = getattr(screen, "action_menu", None)
            busy = runtime._battle_presentation.busy()
            if menu is not None and menu.view.total_count and not busy:
                return True
            pump(runtime, 0.1)
        return False

    def start(encounter):
        game.start_encounter(encounter)
        runtime._turn_actor = None  # what the field frame does when a fight starts
        runtime._battle_presentation.begin()
        runtime._advance_to_hero_turn()
        return hero_turn()

    smoke.prepare(game, Counter())  # a hero with trees, gear and skills to show
    runtime._ui_mode = "pause"
    shot("en_pause", "Resume", "Settings")

    game.set_locale("zh-TW")  # as Settings ▸ Language does
    checks["locale"] = game.localizer.locale == "zh-TW"
    runtime._ui_mode = "title"
    shot("zh_title", "新遊戲", "讀取進度")
    press(pygame.K_n, 0.6)  # N: a new game (the hero prepared above plays on)
    shot("zh_field", "野外測試")
    runtime._ui_mode = "pause"
    shot("zh_pause", "暫停", "繼續遊戲", "設定", "結束遊戲")
    runtime._ui_mode = "settings"
    shot("zh_settings", "設定", "語言", "繁體中文", "音樂音量", "戰鬥訊息")
    runtime.open_slots("save")
    shot("zh_slots", "儲存進度", "自動存檔")
    runtime.open_status_menu()
    shot("zh_status", "狀態", "道具", "裝備", "技能")
    runtime._ui_mode = "field"

    # the battle commands, in English first and then in Chinese
    game.set_locale("en")
    actor = start("woods_patrol")
    checks["hero_turn"] = actor is not None and menu_shown()
    actor = runtime._battle_actor()
    shot("en_battle_menu", "Fight", "Choose a weapon")
    game.set_locale("zh-TW")
    shot("zh_battle_menu", "攻擊", "技能", "選擇武器")
    commands = runtime.battle_commands
    press(pygame.K_DOWN, 0.1)
    press(pygame.K_RETURN, 0.4)  # Skills
    shot("zh_battle_skills", "技能")
    rows = commands.entries(actor)
    long_help = next(
        (i for i, r in enumerate(rows) if r.enabled and len(r.detail) > 40), None
    )  # a skill whose description needs the help box
    if long_help is not None:
        while commands.cursor != long_help:
            press(pygame.K_DOWN, 0.05)
        shot("zh_battle_skill_help")
    disabled = next((i for i, r in enumerate(rows) if not r.enabled), None)
    if disabled is not None:  # a skill that cannot be used now: its reason, in Chinese
        while commands.cursor != disabled:
            press(pygame.K_DOWN, 0.05)
        reason = rows[disabled].disabled_reason
        shot("zh_battle_disabled", reason[:4])  # the footer may shorten a long reason
        checks["reason_in_chinese"] = _chinese(reason)
    press(pygame.K_ESCAPE, 0.3)  # back to the top level (the cursor stays on Skills)
    for _ in range(8):
        if commands.cursor == 0:
            break
        press(pygame.K_UP, 0.05)
    press(pygame.K_RETURN, 0.3)  # Fight: the weapon list
    press(pygame.K_RETURN, 0.3)  # the first weapon: pick a foe
    if commands.mode == "target":
        shot("zh_battle_target", "目標")
    press(pygame.K_ESCAPE, 0.2)
    press(pygame.K_ESCAPE, 0.2)

    # the victory pages: the patrol's foes one blow from falling
    for _ in range(60):
        if runtime._victory or game.battle is None:
            break
        for enemy in game.active_enemy_ids():
            game.battle.member(enemy).subject.resources.set_current("vitality", 1.0)
        if not runtime._battle_presentation.busy() and runtime._battle_actor():
            press(pygame.K_RETURN, 0.1)
        else:
            pump(runtime, 0.1)
    for _ in range(80):  # the last blows play out before the results
        if not runtime._presentation_busy():
            break
        pump(runtime, 0.1)
    checks["victory"] = bool(runtime._victory)
    shot("zh_victory", "勝利")
    press(pygame.K_RETURN, 0.3)
    shot("zh_victory_hero", "經驗值")
    for _ in range(6):
        if not runtime._victory:
            break
        press(pygame.K_RETURN, 0.3)

    # game over: every hero falls in the next fight
    runtime._ui_mode = "field"
    pump(runtime, 0.3)
    if game.battle is None:
        start("woods_patrol")
        for hero in game.active_hero_ids():
            game.battle.member(hero).subject.resources.set_current("vitality", 0.0)
            game.battle.incapacitate(hero)
        runtime._advance_to_hero_turn()
        for _ in range(40):
            if runtime._ui_mode == "game_over":
                break
            pump(runtime, 0.1)
    checks["game_over"] = runtime._ui_mode == "game_over"
    shot("zh_game_over", "遊戲結束", "讀取上次的存檔", "回到標題畫面")
    runtime.close()

    failed = sorted(k for k, v in checks.items() if not v)
    report = {
        "driver": driver,
        "status": "PASS" if not failed and driver == "cocoa" else "FAIL",
        "checks": checks,
        "failed": failed,
        "words": words,
        "note": "The words are the ones the screens drew; how they read is for a person.",
    }
    (out / "built_in_text_results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: report[k] for k in ("driver", "status", "failed")}, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
