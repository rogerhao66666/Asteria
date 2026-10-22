"""Real-window check of the party portraits on the battle HUD cards (D53).

    python scripts/battle_portraits_live_check.py OUTPUT_DIR
    python scripts/battle_portraits_live_check.py OUTPUT_DIR --editor

Opens real (Cocoa) windows on the Full Verification and Octopath demos with each of the first
four heroes' Combatant Sprites records given a portrait - CC0 Ninja Adventure facesets from
``local_reference/`` stand in for anime faces - and plays each battle with real frames to the
first hero's turn, its command menu open: the Acolyte's Vigil (Portrait Party Layout: bodies
hidden, the side list), the Octopath side list (bodies shown), the engine's default column HUD
and a bottom row with the portraits over its cells. The projects are changed in memory only.
Every battle is saved as ``d53_<name>.png``; ``d53_battle_portraits_results.json`` lists the
portraits drawn and the checks: each portrait is on screen pixel for pixel as fitted, nothing
of its card and no menu is over it, and the video driver.

``--editor`` (a separate run: SDL and Qt do not share one Cocoa app) opens the editor in a real
window on the same project instead and saves the Battle Screen tab's Battle UI Layout form at
its two portrait fields and the Combatant Sprites form at its portrait pickers, in English and
in Traditional Chinese (switched for that window only: no editor setting is saved), with
``d53_editor_results.json``.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
for key in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER", "QT_QPA_PLATFORM"):
    os.environ.pop(key, None)

FACES = (
    REPO
    / "local_reference/free_assets/ninja_adventure/extracted/Ninja Adventure - Asset Pack"
    / "Actor/Character"
)
STAND_INS = ("Hunter", "SorcererBlack", "Vampire", "SamuraiBlue")  # hero_01 .. hero_04
DEMOS = {
    "full_verification": REPO / "reference_projects" / "full_verification_demo",
    "octopath": REPO / "reference_projects" / "octopath_demo",
}
# (name, demo, encounter, layout changes)
BATTLES = (
    ("vigil_side_list", "full_verification", "acolyte_vigil", {}),
    ("vigil_side_list_right", "full_verification", "acolyte_vigil", {"hud_portraits": "right"}),
    ("octopath_side_list", "octopath", "boss_room", {}),
    (
        "octopath_column",
        "octopath",
        "boss_room",
        {"party_hud": "column", "action_menu_placement": "bottom", "overhead_zones": ()},
    ),
    (
        "octopath_bottom_row_above",
        "octopath",
        "boss_room",
        {
            "party_hud": "bottom_row",
            "hud_portraits": "above",
            "hud_portrait_size": 30.0,
            "action_menu_placement": "actor",
            "overhead_zones": (),
        },
    ),
)


def _helpers():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "real_machine_validation", REPO / "scripts" / "real_machine_validation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _project(demo, layout):
    """The demo's project with portraits on hero_01..hero_04 and ``layout`` set on its battle
    UI layout records (in memory only)."""
    from asteria.editor import EditorDocument
    from asteria.project import Project

    project = Project.load_json(
        DEMOS[demo] / "project.asteria.json", EditorDocument().component_registry
    )
    library = project.battle_presentation_library
    for number, name in enumerate(STAND_INS, start=1):
        key = f"hero_{number:02d}"
        profile = library.require("combatant_visuals", key)
        face = str(FACES / name / "Faceset.png")
        assets = replace(profile.assets, portrait_asset_id=face)
        library.set("combatant_visuals", key, replace(profile, assets=assets))
    for key in library.ids("ui_layout"):
        library.set("ui_layout", key, replace(library.require("ui_layout", key), **layout))
    return project


def _box(item):
    return (item.x, item.y, item.width, item.height)


def _hit(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _battle(name, demo, encounter, layout, out, pump):
    import pygame

    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = _project(demo, layout)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMOS[demo], width=1280, height=720
    )
    runtime.open()
    driver = pygame.display.get_driver()
    try:
        if demo == "full_verification":
            sys.path.insert(0, str(DEMOS[demo]))
            import run_trial_smoke as smoke

            smoke.prepare(runtime.game, Counter(), "hero")
        runtime._ui_mode = "field"
        runtime._frame([], 1 / 60)
        runtime.game.start_encounter(encounter)
        adapter = runtime._battle_presentation
        adapter.begin()
        runtime._advance_to_hero_turn()
        drawn = {}
        draw = adapter.draw

        def noted():  # the frame each real frame drew
            result = draw()
            drawn["frame"] = getattr(result, "frame", None)
            return result

        adapter.draw = noted
        frames = pump(runtime, 4.0)  # the intro and the hero's turn, its command menu open
        frame = drawn["frame"]
        shot = out / f"d53_{name}.png"
        pygame.image.save(runtime.capture(), str(shot))
        backend, theme = adapter._ui_backend, adapter.renderer.theme
        portraits, problems = [], []
        menus = [
            _box(p)
            for p in frame.panels
            if p.panel_id in ("action_menu", "action_help", "action_workflow")
        ]
        for portrait in frame.portraits:
            box = _box(portrait)
            rect = backend._rect(*box)
            picture = runtime.dialogue_portrait(portrait.asset_id, rect.width, rect.height)
            at = picture.get_rect(center=rect.center)
            wrong = sum(
                runtime.screen.get_at((at.x + x, at.y + y))[:3] != picture.get_at((x, y))[:3]
                for x in range(at.width)
                for y in range(at.height)
            )
            for text in frame.texts:  # the card's own words, as wide as the backend draws them
                if text.member_id != portrait.member_id:
                    continue
                image = backend._text_image(text.text, (255, 255, 255), theme.text_size(text.role))
                width = image[0].get_width() / backend.scale
                left = text.x - {"right": width, "center": width / 2}.get(text.align, 0.0)
                if _hit((left, text.y, width, 8.0), box):
                    problems.append(f"{portrait.member_id}: text {text.text!r} over it")
            for gauge in frame.gauges:
                if gauge.member_id == portrait.member_id and _hit(_box(gauge), box):
                    problems.append(f"{portrait.member_id}: bar {gauge.resource_id} over it")
            for menu in menus:
                if _hit(menu, box):
                    problems.append(f"{portrait.member_id}: a menu over it {menu}")
            if wrong:
                problems.append(f"{portrait.member_id}: {wrong} pixels differ from the portrait")
            portraits.append(
                {
                    "member": portrait.member_id,
                    "asset": Path(portrait.asset_id).parent.name,
                    "box": [round(v, 1) for v in box],
                    "pixels": [at.width, at.height],
                    "pixels_differing": wrong,
                }
            )
        expected = sorted(adapter.screen.member_portraits)
        return {
            "battle": name,
            "demo": demo,
            "encounter": encounter,
            "layout": {
                key: getattr(adapter.screen.composer.layout, key)
                for key in ("party_hud", "hud_portraits", "hud_portrait_size")
            },
            "video_driver": driver,
            "frames": frames,
            "screenshot": shot.name,
            "members_with_portraits": expected,
            "portraits": portraits,
            "menus": [[round(v, 1) for v in m] for m in menus],
            "problems": problems,
            "pass": bool(portraits) and not problems,
        }
    finally:
        runtime.close()
        sys.modules.pop("run_trial_smoke", None)


def _editor(out):
    import time

    from PySide6.QtWidgets import QApplication, QLabel, QWidget

    from asteria.editor.i18n import install, set_language
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.theme import apply_asteria_theme
    from asteria.editor.workspace import WorkspaceMode

    app = QApplication.instance() or QApplication(
        ["battle_portraits_live_check", "-ApplePersistenceIgnoreState", "YES"]
    )
    apply_asteria_theme(app, None)
    install(app, "en")  # as the editor's launcher does: the language can be switched live
    window = AsteriaEditorWindow(_project("full_verification", {}))  # no saved layout is used
    window.document.file_path = DEMOS["full_verification"] / "project.asteria.json"
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

    def shot(category, record, keys, name):
        window.workspace.set_mode(WorkspaceMode.UI)
        window.ui_workspace.setCurrentWidget(window.presentation_authoring)
        family = window.presentation_authoring.child
        family.category.setCurrentIndex(family.category.findData(category))
        settle()
        family.select_ids([record])
        settle()
        form, fields = family.editor, {}
        for key in keys:  # a row's label and field end their tooltips "data: <key>" (any language)
            tail = re.compile(rf"[\s:：]{re.escape(key)}$")
            tagged = [w for w in form.findChildren(QWidget) if tail.search(w.toolTip().strip())]
            label = next((w for w in tagged if isinstance(w, QLabel)), None)
            editor = next((w for w in tagged if not isinstance(w, QLabel)), None)
            if label is None:  # an empty field waits under "More…" until it is opened
                fields[key] = {"label": "", "widget": "", "shown": False}
                continue
            form.ensureWidgetVisible(label, 40, 160)
            if editor is not None:  # the whole field in view (a picker is taller than its label)
                form.ensureWidgetVisible(editor, 40, 40)
            fields[key] = {
                "label": label.text(),
                "widget": type(editor).__name__ if editor is not None else "",
                "shown": True,
            }
        settle()
        path = out / f"d53_editor_{name}.png"
        window.grab().save(str(path))
        return {"shot": path.name, "category": category, "record": record, "fields": fields}

    shots = []
    for language in ("en", "zh_TW"):
        set_language(language)  # this window only (the View menu would save the choice)
        window.refresh_all()
        settle()
        suffix = "" if language == "en" else "_zh"
        keys = ("hud_portraits", "hud_portrait_size")
        shots.append(shot("ui_layout", "adaptive", keys, f"battle_ui_layout{suffix}"))
        keys = ("portrait_asset_id", "small_portrait_asset_id")
        shots.append(shot("combatant_visuals", "hero_01", keys, f"combatant_portraits{suffix}"))
    set_language("en")
    window.document.mark_saved()
    window.close()
    report = {"check": "D53 editor fields for battle HUD portraits", "shots": shots}
    (out / "d53_editor_results.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(shots, ensure_ascii=False))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0] if argv else REPO / "docs" / "audits" / "evidence" / "real_machine")
    out.mkdir(parents=True, exist_ok=True)
    if not FACES.is_dir():
        raise SystemExit(f"the stand-in faces are missing: {FACES}")
    if "--editor" in argv:
        return _editor(out)
    pump = _helpers()._pump
    results = [_battle(*battle, out, pump) for battle in BATTLES]
    report = {
        "check": "D53 party portraits on the battle HUD cards",
        "stand_in_faces": "Ninja Adventure facesets (CC0): " + ", ".join(STAND_INS),
        "battles": results,
        "pass": all(r["pass"] for r in results),
    }
    (out / "d53_battle_portraits_results.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps({r["battle"]: r["pass"] for r in results}), "PASS" if report["pass"] else "FAIL"
    )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
