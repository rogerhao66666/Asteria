"""Real-window pictures of the Full Verification demo's armour, accessories and supplies
(D61 G2; macOS, Cocoa).

    ASTERIA_MUTE=1 python scripts/supplies_live_check.py OUTPUT_DIR

The bag gets potions, cures, bombs, materials, orbs and cards; Aldric wears new armour and an
accessory. The status menu's items and equipment pages, the battle's item list and a thrown
Thunder Bomb (real key presses) are pictured in English and in Traditional Chinese.
``results.json`` lists the words each picture drew and the checks.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(DEMO))
for key in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER", "QT_QPA_PLATFORM"):
    os.environ.pop(key, None)
ITEMS = (
    "potion", "hi_potion", "ether", "elixir", "antidote", "remedy", "thunder_bomb",
    "holy_bomb", "iron_ball", "wolf_fur", "mithril_ingot", "fire_orb_item", "card_sage_item",
)  # fmt: skip
WEAR = (("a_mithril_mail", "armor"), ("a_hunters_charm", "accessory"))


def _helpers():
    spec = importlib.util.spec_from_file_location(
        "real_machine_validation", REPO / "scripts" / "real_machine_validation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv=None):
    import pygame

    from asteria.editor import EditorDocument
    from asteria.events.world_commands import WorldCommand
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0] if argv else REPO / "docs" / "audits" / "evidence" / "arsenal")
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
    host_text = runtime.text

    def text(value, *args, **kwargs):
        drawn.append(str(value))
        return host_text(value, *args, **kwargs)

    runtime.text = text

    def press(k, wait=0.15):
        key(k)
        pump(runtime, 0.05)
        key(k, up=True)
        pump(runtime, wait)

    def shot(name, *expected):
        drawn.clear()
        pump(runtime, 0.3)
        pygame.image.save(runtime.capture(), str(out / f"{name}.png"))
        words[name] = sorted(set(drawn))
        missing = [w for w in expected if not any(w in d for d in drawn)]
        checks[name] = not missing
        if missing:
            print(name, "missing", missing)

    def idle(limit=8.0):
        deadline = time.perf_counter() + limit
        while runtime._battle_presentation.busy() and time.perf_counter() < deadline:
            pump(runtime, 0.1)

    used = []
    use_item = game.use_battle_item

    def noting(actor_id, item_id, *args, **kwargs):
        used.append(item_id)
        return use_item(actor_id, item_id, *args, **kwargs)

    game.use_battle_item = noting
    inventory = game.save.rpg_state.inventory
    for item_id in ITEMS:
        inventory.add(item_id, 3)
    for equipment_id, slot in WEAR:
        game.world_commands.dispatch(
            WorldCommand("GIVE_EQUIPMENT", {"equipment_id": equipment_id})
        )
        game.world_commands.dispatch(
            WorldCommand(
                "EQUIP_ITEM",
                {"actor_id": "hero_01", "equipment_id": equipment_id, "slot_id": slot},
            )
        )
    worn = {w.equipment.equipment_id for w in game.save.rpg_state.loadouts["hero_01"].equipped()}
    checks["worn"] = sorted(worn & {e for e, _s in WEAR})
    runtime._ui_mode = "field"
    pump(runtime, 0.4)
    for locale, tag in (("en", "en"), ("zh-TW", "zh")):
        zh = tag == "zh"
        game.set_locale(locale)
        for _ in range(6):  # new gear asks to be worn first: keep it in the bag
            if not game.equip_offers:
                break
            press(pygame.K_2, 0.2)
        runtime.open_status_menu()
        menu = runtime.status_menu
        menu.tab = "items"
        keys = [row[1] for row in menu.rows()]
        menu.row = keys.index("thunder_bomb")  # the list scrolls to the new supplies
        shot(f"g2_{tag}_items", "雷電炸彈" if zh else "Thunder Bomb", "藥水" if zh else "Potion")
        menu.tab, menu.row = "equipment", 0
        shot(f"g2_{tag}_equipment", "秘銀鎧甲" if zh else "Mithril Mail")
        runtime._ui_mode = "field"
        pump(runtime, 0.2)
        game.start_encounter("woods_patrol")
        runtime._turn_actor = None
        runtime._battle_presentation.begin()
        runtime._advance_to_hero_turn()
        idle()
        commands = runtime.battle_commands
        actor = runtime._battle_actor()
        checks[f"{tag}_hero_turn"] = actor is not None
        # the top level: Fight, Skills, ..., Items - walk to Items and open it
        tops = commands.entries(actor) if actor else []
        items_at = next(i for i, r in enumerate(tops) if r.action_id == "root:Items")
        while commands.cursor != items_at:
            press(pygame.K_DOWN, 0.05)
        press(pygame.K_RETURN, 0.4)
        rows = commands.entries(actor) if actor else []
        checks[f"{tag}_items_listed"] = [r.label for r in rows][:8]
        shot(f"g2_{tag}_battle_items")
        bomb = next((i for i, r in enumerate(rows) if r.action_id == "thunder_bomb"), None)
        if bomb is not None:
            while commands.cursor != bomb:
                press(pygame.K_DOWN, 0.05)
            for _ in range(6):
                if "thunder_bomb" in used:
                    break
                idle()
                press(pygame.K_RETURN, 0.4)
        idle()
        checks[f"{tag}_bomb_thrown"] = "thunder_bomb" in used
        shot(f"g2_{tag}_after_bomb")
        game.battle = None
        game.mode = "field"
        runtime._ui_mode = "field"
        used.clear()
        pump(runtime, 0.4)
    runtime.close()
    failed = sorted(k for k, v in checks.items() if v in (False, None, []))
    report = {
        "driver": driver,
        "status": "PASS" if not failed and driver == "cocoa" else "FAIL",
        "checks": checks,
        "failed": failed,
        "words": words,
    }
    (out / "results_g2.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: report[k] for k in ("driver", "status", "failed", "checks")},
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
