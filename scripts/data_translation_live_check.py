"""Real-window run of the Full Verification demo's own data in Chinese (D60 T3; macOS, Cocoa).

    ASTERIA_MUTE=1 python scripts/data_translation_live_check.py OUTPUT_DIR

The same screens in English and then in Traditional Chinese, switched the way Settings ▸
Language does: a talk with an NPC (dialogue line with its ``text_key`` and its speaker), the
status menu's items, equipment and skills, the shop, the quest log, the battle (names over the
foes, the skill list and a skill's help) and the victory page. Each picture's words are noted as
the screen draws them; ``results.json`` lists them and the checks (the project's names drawn in
Chinese, nothing of the project left in English on a Chinese screen that the table words).
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

    from asteria.core import Transform
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0] if argv else REPO / "docs" / "audits" / "evidence" / "data_translation")
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
    db = project.rpg_database
    drawn, words, checks = [], {}, {}
    host_text = runtime.text

    def text(value, *args, **kwargs):
        drawn.append(str(value))
        return host_text(value, *args, **kwargs)

    runtime.text = text

    def battle_words():
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

    def start(encounter):
        game.start_encounter(encounter)
        runtime._turn_actor = None
        runtime._battle_presentation.begin()
        runtime._advance_to_hero_turn()
        return hero_turn()

    def talk(name):
        """Stand below ``name`` facing it and press E (a real key), as a player would."""
        runtime._ui_mode = "field"
        for _ in range(8):  # new gear from the last fight asks first: put it in the bag
            if not game.equip_offers:
                break
            press(pygame.K_2, 0.2)
        for entity in game.scene.entities():
            if getattr(entity, "name", "") == name:
                spot = entity.get(Transform)
                player = game.player.get(Transform)
                player.x, player.y = spot.x, spot.y + 14
                game.set_player_facing("up")
                runtime._ui_mode = "field"
                pump(runtime, 0.2)
                press(pygame.K_e, 0.5)
                return True
        return False

    def finish_talk():
        for _ in range(40):
            if not game.event_busy:
                return
            press(pygame.K_RETURN, 0.15)

    smoke.prepare(game, Counter())  # a hero with gear, skills and items to show
    game.quest_log.start("q_patrol")
    runtime._ui_mode = "field"
    pump(runtime, 0.5)

    for locale, tag in (("en", "en"), ("zh-TW", "zh")):
        game.set_locale(locale)  # as Settings ▸ Language does
        zh = locale == "zh-TW"
        checks[f"{tag}_talked"] = talk("Warden Thessaly")
        shot(f"t3_{tag}_dialogue", "守衛瑟莎莉" if zh else "Warden Thessaly")
        finish_talk()
        runtime.open_status_menu()
        runtime.status_menu.tab = "items"
        shot(f"t3_{tag}_items", "以太葉" if zh else "Ether Leaf")
        runtime.status_menu.tab = "equipment"
        shot(f"t3_{tag}_equipment")
        runtime.status_menu.tab = "skills"
        shot(f"t3_{tag}_skills")
        runtime._ui_mode = "field"
        game.open_shop("trial_shop")
        pump(runtime, 0.4)
        shot(f"t3_{tag}_shop", "裝備與雜貨" if zh else "Gear & Goods")
        press(pygame.K_ESCAPE, 0.3)
        game.close_shop() if game.open_shop_id else None
        runtime._ui_mode = "quests"
        shot(f"t3_{tag}_quests", "清理道路" if zh else "Clear the Road")
        runtime._ui_mode = "field"
        pump(runtime, 0.3)

        actor = start("woods_patrol")
        checks[f"{tag}_hero_turn"] = actor is not None
        commands = runtime.battle_commands
        shot(f"t3_{tag}_battle", "羅傑" if zh else "Roger")
        foes = [commands.display_name(m) for m in game.active_enemy_ids()]
        checks[f"{tag}_foe_names"] = bool(foes) and all(
            ("哥布林" in n) == zh for n in foes
        )  # over the foes the names are short ("GS1"): the full names are the menu's
        press(pygame.K_DOWN, 0.1)
        press(pygame.K_RETURN, 0.4)  # Skills
        rows = commands.entries(actor)
        helped = next((i for i, r in enumerate(rows) if r.enabled and r.detail), None)
        if helped is not None:
            while commands.cursor != helped:
                press(pygame.K_DOWN, 0.05)
            checks[f"{tag}_skill_help_language"] = _chinese(rows[helped].detail) == zh
            checks[f"{tag}_skill_name_language"] = _chinese(rows[helped].label) == zh
        shot(f"t3_{tag}_battle_skills")
        press(pygame.K_ESCAPE, 0.3)
        for _ in range(60):  # the foes one blow from falling: the victory page
            if runtime._victory or game.battle is None:
                break
            for enemy in game.active_enemy_ids():
                game.battle.member(enemy).subject.resources.set_current("vitality", 1.0)
            if not runtime._battle_presentation.busy() and runtime._battle_actor():
                press(pygame.K_RETURN, 0.1)
            else:
                pump(runtime, 0.1)
        for _ in range(80):
            if not runtime._presentation_busy():
                break
            pump(runtime, 0.1)
        checks[f"{tag}_victory"] = bool(runtime._victory)
        shot(f"t3_{tag}_victory")
        for _ in range(8):
            if not runtime._victory:
                break
            press(pygame.K_RETURN, 0.3)
        runtime._ui_mode = "field"
        pump(runtime, 0.4)

    # on the Chinese screens, no project name the table words is drawn in English
    table = dict(db.locale_tables["zh-TW"].entries)
    english_names = {
        english
        for key, english in (
            (k, getattr(r, "display_name", ""))
            for kind in ("items", "equipment", "enemies", "quests", "actors")
            for k, r in getattr(db, kind).items()
        )
        if english and len(english) > 3
    }
    left = sorted(
        {
            d
            for name, seen in words.items()
            if name.startswith("t3_zh")
            for d in seen
            if d in english_names
        }
    )
    checks["zh_no_project_names_left_in_english"] = not left
    runtime.close()
    failed = sorted(k for k, v in checks.items() if not v)
    report = {
        "driver": driver,
        "status": "PASS" if not failed and driver == "cocoa" else "FAIL",
        "checks": checks,
        "failed": failed,
        "english_names_on_chinese_screens": left,
        "table_entries": len(table),
        "words": words,
        "note": "The words are the ones the screens drew; how they read is for a person.",
    }
    (out / "results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: report[k] for k in ("driver", "status", "failed")}, indent=2))
    print("english left:", left)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
