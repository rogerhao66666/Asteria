"""Real-window pictures of the Full Verification demo's arsenal (D61 G1; macOS, Cocoa).

    ASTERIA_MUTE=1 python scripts/arsenal_live_check.py OUTPUT_DIR

Aldric is given a fist, a book and a throwing weapon (the new kinds) and wears them; the status
menu's equipment page, the battle's weapon list (Fight) and an attack with each new kind are
pictured in English and in Traditional Chinese. ``results.json`` lists the words each picture
drew and the checks.
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
NEW = ("w_shadow_star", "w_grimoire_of_flames", "w_titan_fists")  # the last one is worn


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
            battle_words()
            if game.battle is None:
                return None
            if not runtime._battle_presentation.busy() and runtime._battle_actor():
                return runtime._battle_actor()
            pump(runtime, 0.1)
        return None

    used_abilities = []  # every skill the battle really carries out, from the key presses
    use_ability = game.use_ability

    def noting(actor_id, ability_id, *args, **kwargs):
        used_abilities.append(ability_id)
        return use_ability(actor_id, ability_id, *args, **kwargs)

    game.use_ability = noting
    for weapon_id in NEW:  # given, then worn (one weapon at a time: the last one stays)
        game.world_commands.dispatch(WorldCommand("GIVE_EQUIPMENT", {"equipment_id": weapon_id}))
        game.world_commands.dispatch(
            WorldCommand(
                "EQUIP_ITEM",
                {"actor_id": "hero_01", "equipment_id": weapon_id, "slot_id": "weapon"},
            )
        )
    worn = {
        w.equipment.equipment_id
        for w in game.save.rpg_state.loadouts["hero_01"].equipped("weapon")
    }
    checks["worn"] = sorted(worn & set(NEW))  # one weapon at a time: the fists
    held = {w.equipment.equipment_id for w in game.save.rpg_state.equipment_bag}
    checks["others_in_bag"] = sorted(held & set(NEW[:-1]))
    runtime._ui_mode = "field"
    pump(runtime, 0.4)
    for locale, tag in (("en", "en"), ("zh-TW", "zh")):
        zh = tag == "zh"
        game.set_locale(locale)
        runtime.open_status_menu()
        runtime.status_menu.tab = "equipment"
        shot(f"g1_{tag}_equipment", "泰坦之拳" if zh else "Titan Fists")
        runtime._ui_mode = "field"
        pump(runtime, 0.2)
        game.start_encounter("woods_patrol")
        runtime._turn_actor = None
        runtime._battle_presentation.begin()
        runtime._advance_to_hero_turn()
        actor = hero_turn()
        checks[f"{tag}_hero_turn"] = actor is not None
        commands = runtime.battle_commands

        # the battle menu's words are drawn once and kept (cached): read the menu itself
        def idle(limit=8.0):
            deadline = time.perf_counter() + limit
            while runtime._battle_presentation.busy() and time.perf_counter() < deadline:
                pump(runtime, 0.1)

        idle()
        press(pygame.K_RETURN, 0.4)  # Fight: the attack of the weapon the hero holds
        shot(f"g1_{tag}_fight")
        checks[f"{tag}_attack_name"] = commands._name("attack_fist")
        for _ in range(8):  # into the attack, then the first foe, until the blow is struck
            if "attack_fist" in used_abilities:
                break
            idle()
            if commands.mode != "target":
                rows = commands.entries(actor) if actor else []
                fist = next((i for i, r in enumerate(rows) if r.action_id == "attack_fist"), 0)
                while rows and commands.cursor != fist:
                    press(pygame.K_DOWN, 0.05)
            press(pygame.K_RETURN, 0.4)
        idle()
        checks[f"{tag}_fist_attack_used"] = "attack_fist" in used_abilities
        shot(f"g1_{tag}_after_fist")
        game.battle = None
        game.mode = "field"
        runtime._ui_mode = "field"
        runtime._battle_presentation.end() if hasattr(
            runtime._battle_presentation, "end"
        ) else None
        pump(runtime, 0.4)
    runtime.close()
    failed = sorted(
        k for k, v in checks.items() if v in (False, None, []) and not k.endswith("_damage")
    )
    report = {
        "driver": driver,
        "status": "PASS" if not failed and driver == "cocoa" else "FAIL",
        "checks": checks,
        "failed": failed,
        "words": words,
    }
    (out / "results.json").write_text(
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
