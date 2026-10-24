"""Real-window run of the Full Verification demo's three new Hearthfold shops and the workshop
(D61 G3; macOS, Cocoa).

    ASTERIA_MUTE=1 python scripts/shops_live_check.py OUTPUT_DIR

In English and then in Traditional Chinese, by real key presses: E at each keeper (Brann,
Hilde, Sela) shows their line and opens their shop; Enter buys the Knight's Blade, the Padded
Jerkin and a Fire Orb; the blade is worn, and in the workshop (build menu, 8) S sockets the orb
and R refines. ``results_g3.json`` lists the words each picture drew and the checks.
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
# keeper, shop id, what Enter buys there, words the shop picture must draw (en, zh)
VISITS = (
    ("Weaponsmith Brann", "arms_shop", "w_knights_blade", ("Knight's Blade", "騎士之刃")),
    ("Armorer Hilde", "armour_shop", "a_padded_jerkin", ("Padded Jerkin", "襯墊短衣")),
    ("Apothecary Sela", "remedy_shop", "fire_orb_item", ("Fire Orb", "火之寶珠")),
)


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
    state = game.save.rpg_state
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

    def find(name):
        return next(e for e in game.scene.entities() if e.name == name)

    def owned(item_id):
        bag = sum(1 for g in state.equipment_bag if g.equipment.equipment_id == item_id)
        return bag + state.inventory.count(item_id)

    def decline_offers():
        for _ in range(8):  # new gear asks to be worn: keep it in the bag
            if not game.equip_offers:
                return
            press(pygame.K_2, 0.2)

    state.currencies["gold"] = 60000.0
    state.inventory.add("iron_ore", 4)
    runtime._ui_mode = "field"
    pump(runtime, 0.4)
    player = game.player.get(Transform)
    for locale, tag in (("en", "en"), ("zh-TW", "zh")):
        zh = tag == "zh"
        game.set_locale(locale)
        for keeper, shop_id, item_id, names in VISITS:
            short = shop_id.split("_")[0]
            spot = find(keeper).get(Transform)
            player.x, player.y = spot.x, spot.y + 14
            game.set_player_facing("up")
            pump(runtime, 0.2)
            press(pygame.K_e, 0.4)
            shot(f"g3_{tag}_{short}_line")
            for _ in range(20):
                if runtime._ui_mode == "shop":
                    break
                press(pygame.K_RETURN, 0.25)
            checks[f"{tag}_{short}_opened"] = game.open_shop_id == shop_id
            screen = runtime._shop_screen
            ids = [r.item_id for r in screen.rows()] if screen else []
            before = owned(item_id)
            if item_id in ids:
                while screen.index != ids.index(item_id):
                    press(pygame.K_DOWN, 0.03)
                press(pygame.K_RETURN, 0.3)
            checks[f"{tag}_{short}_bought"] = owned(item_id) == before + 1
            shot(f"g3_{tag}_{short}_shop", names[1] if zh else names[0])
            press(pygame.K_ESCAPE, 0.3)
            decline_offers()
            runtime._ui_mode = "field"
        # the bought blade on Roger, then the workshop: S sockets the orb, R refines
        wear = {"actor_id": "hero_01", "equipment_id": "w_knights_blade", "slot_id": "weapon"}
        game.world_commands.dispatch(WorldCommand("EQUIP_ITEM", wear))
        blade = state.loadouts["hero_01"].equipped("weapon")[0]
        checks[f"{tag}_blade_worn"] = blade.equipment.equipment_id == "w_knights_blade"
        runtime._ui_mode = "build"
        pump(runtime, 0.3)
        press(pygame.K_8, 0.3)  # the build menu's 8: the enhance screen (U3)
        checks[f"{tag}_workshop_opened"] = runtime._ui_mode == "enhance"
        screen = runtime._gear_screen
        gear = [p.instance_id for _s, p in screen.gear()]
        fire = game.resolve_actor_build("hero_01").stats.get("fire_attack")
        press(pygame.K_TAB, 0.2)  # the Sockets page: the blade's gem socket, then the orb
        screen.rows["gear"] = gear.index(blade.instance_id)
        press(pygame.K_RETURN, 0.2)
        press(pygame.K_RETURN, 0.2)
        names = [item.item_id for item, _a, _n in screen.choices()]
        if "fire_orb_item" in names:
            screen.rows["choices"] = names.index("fire_orb_item")
            press(pygame.K_RETURN, 0.3)
        socketed = blade.attachments.get("g1")
        checks[f"{tag}_orb_socketed"] = bool(socketed) and socketed.attachment_id == "fire_orb"
        checks[f"{tag}_fire_attack"] = [
            fire,
            game.resolve_actor_build("hero_01").stats.get("fire_attack"),
        ]
        for _ in range(3):  # back round to the Refine page
            press(pygame.K_TAB, 0.1)
        screen.rows["gear"] = gear.index(blade.instance_id)
        ore = state.inventory.count("iron_ore")
        press(pygame.K_RETURN, 0.3)
        checks[f"{tag}_refined"] = state.inventory.count("iron_ore") == ore - 1
        checks[f"{tag}_workshop_message"] = screen.message
        shot(f"g3_{tag}_workshop", "騎士之刃" if zh else "Knight's Blade")
        press(pygame.K_ESCAPE, 0.2)
        runtime._ui_mode = "field"
        pump(runtime, 0.3)
        deadline = time.perf_counter() + 1.0
        while time.perf_counter() < deadline:
            pump(runtime, 0.1)
    runtime.close()
    failed = sorted(k for k, v in checks.items() if v in (False, None, [], ""))
    report = {
        "driver": driver,
        "status": "PASS" if not failed and driver == "cocoa" else "FAIL",
        "checks": checks,
        "failed": failed,
        "words": words,
    }
    (out / "results_g3.json").write_text(
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
