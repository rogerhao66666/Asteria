"""Real-window check of the creature party (Pet Rules, D58).

    python scripts/creature_party_live_check.py OUTPUT_DIR
    python scripts/creature_party_live_check.py OUTPUT_DIR --editor

Opens the Full Verification demo in a real (Cocoa) window with the creature party laid over
it in memory (``trial_creatures``: a party of two with one creature on the stage, storage, the
characters out of the fight) and plays a wild fight of two creatures with real frames and key
presses: the first creature's turn (its menu open), the Switch command, a creature falling and
the prompt for the next one, the capture prompt with its two items and the catch, the
victory, the prompt for a move learned past the limit, and the Pets screen's party / storage
columns. Every step is saved as ``d58_<step>.png``; ``d58_results.json`` lists what each
step found (who stood on the stage and the bench, the party, the catch, the video driver).

``--editor`` (a separate run: SDL and Qt do not share one Cocoa app) opens the editor on the
demo instead and saves the Game Systems > Pet Rules form, the Pet Species form at its new
fields and the Capture Rules form at its rate fields, in English and in Traditional Chinese
(switched for that window only), with ``d58_editor_results.json``.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(DEMO))
for key in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER", "QT_QPA_PLATFORM"):
    os.environ.pop(key, None)

HP = "vitality"


def _helpers():
    spec = importlib.util.spec_from_file_location(
        "real_machine_validation", REPO / "scripts" / "real_machine_validation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _project():
    import trial_creatures

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.rpg.enemies import EncounterDefinition, EncounterMember

    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    trial_creatures.install(project)
    db = project.rpg_database
    db.add_encounter(  # foes that only shoot, so a weak creature of ours is sure to fall
        EncounterDefinition(
            "wild_shooters",
            members=[
                EncounterMember(pet_species_id="cub", level=5, moves=("pet_shot",)),
                EncounterMember(pet_species_id="wolf", level=6, reserve=True, moves=("pet_shot",)),
            ],
        )
    )
    return project


def _game(out):
    import pygame

    from asteria.events import WorldCommand
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    helper = _helpers()
    pump, key = helper._pump, helper._key
    project = _project()
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=1280, height=720
    )
    runtime.open()
    driver = pygame.display.get_driver()
    game = runtime.game
    steps = []

    def shot(name, **facts):
        pump(runtime, 0.2)
        pygame.image.save(runtime.capture(), str(out / f"d58_{name}.png"))
        entry = {"step": name, **facts}
        if game.battle is not None:
            entry["stage"] = {s: game.stage_ids(s) for s in ("heroes", "enemies")}
            entry["bench"] = {s: game.bench_ids(s) for s in ("heroes", "enemies")}
        steps.append(entry)
        return entry

    def press(k, seconds=0.35):
        key(k)
        pump(runtime, 0.05)
        key(k, up=True)  # released: a key left down never counts as pressed again
        pump(runtime, seconds)

    def wait(condition, seconds=12.0):
        """Run real frames until ``condition()`` holds (at most ``seconds``); returns it."""
        import time

        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            if condition():
                return True
            pump(runtime, 0.1)
        return bool(condition())

    def hero_turn():
        return (
            game.battle is not None
            and runtime._battle_actor() is not None
            and not runtime._presentation_busy()
        )

    # the player's creatures and capture items
    first = game.add_pet("cub", level=5, nickname="Fang")
    second = game.add_pet("wolf", level=6)
    game.add_pet("cub", level=5)  # the party is full: this one waits in storage
    game.save.rpg_state.inventory.add("pet_ball", 3)
    game.save.rpg_state.inventory.add("great_ball", 2)
    runtime._ui_mode = "title"
    pump(runtime, 0.3)
    press(pygame.K_n, 0.5)  # New Game: on the field
    game.start_encounter("wild_shooters")
    runtime._battle_presentation.begin()  # as the field update does when a fight starts
    runtime._advance_to_hero_turn()
    wait(hero_turn)  # the battle opens and runs to the first creature's turn
    actor = runtime._battle_actor()
    shot("01_battle_start", turn=actor, party=[p.instance_id for p in game.party_pets()])

    # the Switch command: Fang goes to the bench, the Wolf comes in (an action)
    commands = runtime.battle_commands
    commands.reset()
    rows = commands.root_rows(actor)
    index = next(i for i, r in enumerate(rows) if r.action_id == "root:Switch")
    for _ in range(index):
        press(pygame.K_DOWN, 0.15)
    press(pygame.K_RETURN, 0.4)
    shot("02_switch_rows", rows=[r.label for r in commands.rows(actor)])
    press(pygame.K_RETURN, 0.5)
    wait(hero_turn)  # the foe's turn plays
    turn = runtime._battle_actor()
    shot("03_switched", turn=turn)

    # the Wolf falls to the foe's shots: the prompt for the next creature (a shot deals
    # 9 x magic and these creatures have no magic defence, so it usually fell already; only a
    # Wolf still standing is brought down to 1 - a fallen one set to 1 would stand up again)
    wolf = game.pet_member_id(second)
    if not runtime._switch_menu:
        game.battle.member(wolf).subject.resources.set_current(HP, 1.0)
    for _ in range(6):  # pass turns until a shot lands
        if runtime._switch_menu or game.battle is None:
            break
        actor = runtime._battle_actor()
        if actor is None:
            pump(runtime, 0.5)
            continue
        targets = game.default_targets(actor, "pet_bandage")
        try:
            game.use_ability(actor, "pet_bandage", targets)  # a harmless action
        except Exception as exc:  # noqa: BLE001 - the trace tells what went wrong
            print("action failed:", actor, exc)
        game.battle.member(wolf).subject.resources.set_current(HP, 1.0)  # the bandage healed
        runtime._after_hero_action()
        wait(lambda: hero_turn() or runtime._switch_menu or game.battle is None)
        pool = game.battle.member(wolf).subject.resources if game.battle else None
        print(
            "turn",
            actor,
            "wolf hp",
            pool.current(HP) if pool else None,
            "stage",
            game.stage_ids("heroes") if game.battle else None,
            "switch",
            runtime._switch_menu,
            "defeat",
            runtime._defeat,
        )
    prompt = shot("04_send_out_prompt", switch_menu=runtime._switch_menu)
    assert runtime._switch_menu, "the bench prompt did not open"
    # one shot always knocks out a creature here: Fang gets the health to live through the foe's
    # turn that follows the send-out, so the capture can be shown (an injected value)
    fang = game.pet_member_id(first)
    pool = game.battle.member(fang).subject.resources
    pool.get(HP).set_maximum(500)
    pool.set_current(HP, 500)
    press(pygame.K_1, 0.5)
    wait(hero_turn)
    shot("05_sent_in", turn=runtime._battle_actor())

    # capture: the foe on the stage, nearly down, with the Great Ball
    foe = game.stage_ids("enemies")[0]
    game.battle.member(foe).subject.resources.set_current(HP, 1.0)
    press(pygame.K_x, 0.4)
    shot("06_capture_targets", targets=[list(t) for t in game.capture_targets()])
    press(pygame.K_1, 0.4)
    shot("07_capture_items", items=[list(i) for i in game.capture_items(foe)])
    press(pygame.K_2, 0.5)
    wait(lambda: len(game.pets()) == 4 and (hero_turn() or game.battle is None))
    caught = game.pets()[-1]
    shot(
        "08_captured",
        caught={"species": caught.species_id, "level": caught.level, HP: caught.resources.get(HP)},
        stored=[p.instance_id for p in game.stored_pets()],
        party=[p.instance_id for p in game.party_pets()],
        great_balls=game.save.rpg_state.inventory.count("great_ball"),
    )

    # the reserve foe came in; it falls and the fight is won
    wait(hero_turn)
    for _ in range(4):
        if game.battle is None or runtime._victory:
            break
        foe = game.stage_ids("enemies")[0]
        game.battle.member(foe).subject.resources.set_current(HP, 0.0)
        actor = runtime._battle_actor()
        if actor is not None:
            targets = game.default_targets(actor, "pet_bandage")
            game.use_ability(actor, "pet_bandage", targets)
            runtime._after_hero_action()
        wait(lambda: runtime._victory or hero_turn())
    wait(lambda: not runtime._presentation_busy())
    shot(
        "09_victory",
        victory=runtime._victory,
        levels={p.instance_id: p.level for p in game.pets()},
        pending_moves=[list(x) for x in game.pending_pet_moves()],
    )
    press(pygame.K_RETURN, 0.6)
    press(pygame.K_RETURN, 0.6)
    pump(runtime, 0.8)
    for _ in range(10):  # the learn prompt opens once every victory page is closed
        if runtime._ui_mode == "learn":
            break
        press(pygame.K_RETURN, 0.5)
    shot("10_learn_prompt", ui_mode=runtime._ui_mode)
    if runtime._ui_mode == "learn":
        press(pygame.K_1, 0.6)
    shot("11_after_learning", moves={p.instance_id: list(p.moves) for p in game.pets()})

    # the Pets screen: party and storage; then HEAL_PETS and the PET_STORAGE command
    press(pygame.K_ESCAPE, 0.4)  # pause
    pets_row = [o[0] for o in runtime._pause_menu.options].index("pets")
    for _ in range(8):  # one row a press (presses close together count once)
        if runtime._pause_menu.index == pets_row:
            break
        press(pygame.K_DOWN, 0.45)
    press(pygame.K_RETURN, 0.5)  # Pets
    shot("12_pets_party_storage", ui_mode=runtime._ui_mode)
    press(pygame.K_RIGHT, 0.3)
    press(pygame.K_RETURN, 0.4)  # the stored one cannot join: the party is full
    shot("13_party_full_message", message=runtime._pets_screen.message)
    press(pygame.K_ESCAPE, 0.3)
    press(pygame.K_ESCAPE, 0.3)
    game.world_commands.dispatch(WorldCommand("HEAL_PETS", {}))
    game.world_commands.dispatch(WorldCommand("PET_STORAGE", {}))
    pump(runtime, 0.6)
    shot(
        "14_storage_command",
        ui_mode=runtime._ui_mode,
        healed=all(not p.resources and not p.pp for p in game.pets()),
    )
    press(pygame.K_ESCAPE, 0.3)
    runtime.close()
    report = {
        "check": "D58 creature party in a real window",
        "driver": driver,
        "first_pet": first.instance_id,
        "steps": steps,
        "pass": bool(
            prompt["switch_menu"]
            and caught.species_id == "cub"
            and steps[-1]["healed"]
            and any(s.get("victory") for s in steps)
        ),
    }
    (out / "d58_results.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps({"driver": driver, "pass": report["pass"]}))
    return 0 if report["pass"] else 1


def _editor(out):
    import time

    from PySide6.QtWidgets import QApplication, QLabel, QWidget

    from asteria.editor.i18n import install, set_language
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.theme import apply_asteria_theme
    from asteria.editor.workspace import WorkspaceMode

    app = QApplication.instance() or QApplication(
        ["creature_party_live_check", "-ApplePersistenceIgnoreState", "YES"]
    )
    apply_asteria_theme(app, None)
    install(app, "en")
    window = AsteriaEditorWindow(_project())
    window.document.file_path = DEMO / "project.asteria.json"
    window.document.mark_saved()
    window._resolve_project_resources()
    window.refresh_all()
    window.resize(1600, 1000)
    window.show()

    def settle(seconds=0.6):
        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            app.processEvents()
            time.sleep(0.02)

    def shot(kind_id, record, keys, name):
        window.workspace.set_mode(WorkspaceMode.RPG)
        window.rpg_workspace.setCurrentWidget(window.game_systems_editor)
        editor = window.game_systems_editor
        editor.set_kind(kind_id)
        editor.refresh(select=record)
        settle()
        form, fields = editor.form, {}
        for key in keys:
            tail = re.compile(rf"[\s:：]{re.escape(key)}$")
            tagged = [w for w in form.findChildren(QWidget) if tail.search(w.toolTip().strip())]
            label = next((w for w in tagged if isinstance(w, QLabel)), None)
            widget = next((w for w in tagged if not isinstance(w, QLabel)), None)
            if label is None:
                fields[key] = {"label": "", "widget": "", "shown": False}
                continue
            form.ensureWidgetVisible(label, 40, 160)
            if widget is not None:
                form.ensureWidgetVisible(widget, 40, 40)
            fields[key] = {
                "label": label.text(),
                "widget": type(widget).__name__ if widget is not None else "",
                "shown": True,
            }
        settle()
        path = out / f"d58_editor_{name}.png"
        window.grab().save(str(path))
        return {"shot": path.name, "kind": kind_id, "record": record, "fields": fields}

    shots = []
    for language in ("en", "zh_TW"):
        set_language(language)
        window.refresh_all()
        settle()
        suffix = "" if language == "en" else "_zh"
        keys = ("party_size", "battle_slots", "storage", "exp_share", "stat_formulas")
        shots.append(shot("pet_rules", "creature", keys, f"pet_rules{suffix}"))
        keys = ("exp_curve", "exp_yield", "capture_rate", "back_visual_profile_id")
        shots.append(shot("pet_species", "cub", keys, f"pet_species{suffix}"))
        keys = ("mode", "item_bonuses", "state_bonuses")
        shots.append(shot("capture_rules", "*", keys, f"capture_rules{suffix}"))
    set_language("en")
    window.document.mark_saved()
    window.close()
    report = {"check": "D58 editor forms for the creature party", "shots": shots}
    (out / "d58_editor_results.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(shots, ensure_ascii=False))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    editor = "--editor" in argv
    argv = [a for a in argv if a != "--editor"]
    out = Path(argv[0] if argv else REPO / "docs" / "audits" / "evidence" / "creature_party")
    out.mkdir(parents=True, exist_ok=True)
    return _editor(out) if editor else _game(out)


if __name__ == "__main__":
    raise SystemExit(main())
