"""A creature game's own screens as project data (UI_PLAN_2 V5): records in the presentation
library, the project's record before the manifest's, the editor's conversion and undo, the
settings tree and its places, and screens drawn the same from a record as from the manifest."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from asteria.presentation.creature_screens import (
    CreatureScreenSettings,
    creature_battle_on,
    creature_settings,
    from_manifest,
    manifest_part,
)
from asteria.presentation.library import BattlePresentationLibrary

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"

MANIFEST = {
    "battle": {
        "style": "creature",
        "creature_screen": {"background": "ui/battle_bg.png", "layout": {"foe_box": [13, 16]}},
    },
    "field": {
        "background": "maps/town.png",
        "creature_menu": {"entries": [{"id": "bag", "label": "BAG", "screen": "bag"}]},
        "name_input": {"columns": 8},
    },
}


def _runtime(manifest=MANIFEST, records=()):
    library = BattlePresentationLibrary()
    for record in records:
        library.set("creature_screen", record.screen_id, record)
    project = SimpleNamespace(battle_presentation_library=library)
    return SimpleNamespace(project=project, manifest=manifest)


def test_a_record_round_trips_and_is_only_written_when_there_is_one():
    record = CreatureScreenSettings("field.name_input", {"columns": 9, "rows": [["A", "B"]]})
    assert CreatureScreenSettings.from_data(record.to_data()) == record
    off = CreatureScreenSettings("field.name_input", {}, enabled=False)
    assert off.to_data()["enabled"] is False
    assert hash(CreatureScreenSettings.from_data(off.to_data())) == hash(off)
    with pytest.raises(ValueError):
        CreatureScreenSettings("field.unknown", {})
    with pytest.raises(ValueError):
        CreatureScreenSettings.from_data({"screen_id": "field.name_input", "extra": 1})
    with pytest.raises(TypeError):
        CreatureScreenSettings("field.name_input", {"bad": object()})
    source = {"columns": [1, 2]}
    kept = CreatureScreenSettings("field.name_input", source)
    source["columns"].append(3)  # the record keeps its own copy
    assert kept.data == {"columns": [1, 2]}

    library = BattlePresentationLibrary()
    assert "creature_screen" not in library.to_data()["categories"]
    library.set("creature_screen", record.screen_id, record)
    data = json.loads(json.dumps(library.to_data()))
    assert data["categories"]["creature_screen"]["field.name_input"]["data"]["columns"] == 9
    again = BattlePresentationLibrary.from_data(data)
    assert again.get("creature_screen", "field.name_input") == record


def test_the_project_record_comes_before_the_manifest_and_off_falls_back():
    runtime = _runtime()
    assert creature_settings(runtime, "field.name_input") == {"columns": 8}
    assert creature_settings(runtime, "field.creature_shop") == {}
    record = CreatureScreenSettings("field.name_input", {"columns": 10})
    assert creature_settings(_runtime(records=[record]), "field.name_input") == {"columns": 10}
    off = CreatureScreenSettings("field.name_input", {"columns": 10}, enabled=False)
    assert creature_settings(_runtime(records=[off]), "field.name_input") == {"columns": 8}
    mine = creature_settings(runtime, "battle.creature_screen")
    mine["layout"]["foe_box"][0] = 99  # a screen changes its copy, not the manifest
    assert MANIFEST["battle"]["creature_screen"]["layout"]["foe_box"] == [13, 16]
    # a runtime without a project (older callers): the manifest
    plain = SimpleNamespace(manifest=MANIFEST)
    assert creature_settings(plain, "field.name_input") == {"columns": 8}


def test_the_creature_battle_is_on_by_its_record_or_the_manifest_style():
    assert creature_battle_on(_runtime())
    assert not creature_battle_on(_runtime(manifest={}))
    battle = CreatureScreenSettings("battle.creature_screen", {})
    assert creature_battle_on(_runtime(manifest={}, records=[battle]))
    off = CreatureScreenSettings("battle.creature_screen", {}, enabled=False)
    assert not creature_battle_on(_runtime(manifest={}, records=[off]))
    assert creature_battle_on(_runtime(records=[off]))  # off: the manifest's style decides


def test_the_manifest_turns_into_one_record_a_screen():
    found = {s.screen_id: s for s in from_manifest(MANIFEST)}
    assert set(found) == {"battle.creature_screen", "field.creature_menu", "field.name_input"}
    assert found["field.name_input"].data == manifest_part(MANIFEST, "field.name_input")
    styled = from_manifest({"battle": {"style": "creature"}})  # no settings, still its screen
    assert [s.screen_id for s in styled] == ["battle.creature_screen"]
    assert from_manifest({"battle": {"style": "turn"}}) == []


def test_the_editor_converts_the_manifest_and_undoes_a_screen(tmp_path):
    from asteria.editor import EditorDocument
    from asteria.editor.menu_layout_authoring import MenuLayoutAuthoringController
    from asteria.editor.storage import load_document

    document = EditorDocument()
    load_document(document, str(DEMO / "project.asteria.json"))
    controller = MenuLayoutAuthoringController(document)
    assert controller.read_creature_manifest(tmp_path) == {}
    (tmp_path / "playable_test_manifest.json").write_text(json.dumps(MANIFEST), "utf-8")
    read = controller.read_creature_manifest(tmp_path)
    assert controller.creature_screen("field.name_input") is None  # reading changes nothing
    assert set(read) == {"battle.creature_screen", "field.creature_menu", "field.name_input"}
    assert sorted(controller.import_creature_manifest(tmp_path)) == sorted(read)
    assert controller.creature_screen("field.name_input").data == {"columns": 8}
    controller.set_creature_screen(
        "field.name_input", CreatureScreenSettings("field.name_input", {"columns": 6})
    )
    assert controller.creature_screen("field.name_input").data == {"columns": 6}
    document.undo()
    assert controller.creature_screen("field.name_input").data == {"columns": 8}
    controller.set_creature_screen("field.name_input", None)
    assert controller.creature_screen("field.name_input") is None
    document.undo()
    assert controller.creature_screen("field.name_input") is not None


def test_the_settings_tree_lists_places_and_keeps_only_what_differs(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor.creature_screens_dialog import (
        CreatureScreensDialog,
        engine_defaults,
        is_colour,
        is_point,
        merged,
        stripped,
    )

    QApplication.instance() or QApplication([])
    defaults = engine_defaults("battle.creature_screen")
    assert "foe_box" in defaults["layout"] and defaults["colours"]
    assert engine_defaults("field.picture_choices") == {}
    data = {"layout": {"foe_box": [1, 2]}, "background": "bg.png"}
    full = merged(data, defaults)
    assert full["layout"]["foe_box"] == [1, 2] and len(full["layout"]) == len(defaults["layout"])
    assert stripped(full, defaults) == data
    assert is_point("cursor_at", [3, 4]) and is_point("x", [3, 4], "layout")
    assert not is_point("size", [3, 4]) and is_colour("text_colour", [1, 2, 3])

    battle = CreatureScreenSettings("battle.creature_screen", data)
    dialog = CreatureScreensDialog(EditorDocument(), {"battle.creature_screen": battle})
    assert dialog.screen_id == "battle.creature_screen" and dialog.enabled.isChecked()
    paths = {p for p, _label, _xy in dialog.tree.points()}
    assert ("layout", "foe_box") in paths and ("layout", "mine_box") in paths
    dialog.tree.set_point(("layout", "foe_box"), [20, 30])  # a dot dragged on the picture
    dialog.screens.setCurrentRow(4)  # another screen: the battle's settings are kept
    dialog._start()
    dialog.tree.data["columns"] = [{"label": "A"}]
    dialog.tree.rebuild()
    dialog.tree._add_row(("columns",))
    assert dialog.tree.get(("columns",)) == [{"label": "A"}, {"label": "A"}]
    dialog.tree._remove(("columns", 0))
    dialog._accept()
    changes = dialog.changes()
    assert changes["battle.creature_screen"].data == {
        "layout": {"foe_box": [20, 30]},
        "background": "bg.png",
    }
    assert changes["field.picture_choices"].data == {"columns": [{"label": "A"}]}
    dialog.screens.setCurrentRow(0)
    dialog._remove()
    assert dialog.changes()["battle.creature_screen"] is None


def test_the_start_menu_draws_the_same_from_a_record_as_from_the_manifest(monkeypatch, tmp_path):
    sys.path.insert(0, str(DEMO))
    import pygame
    import run_trial_smoke as smoke
    import trial_creatures

    from asteria.runtime.creature_menu import CreatureMenuScreen

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project, game = smoke.load()
    trial_creatures.install(project, party_size=3)
    pygame.display.init()
    pygame.font.init()
    screen = pygame.display.set_mode((480, 320))
    menu = {"entries": [{"id": "bag", "label": "BAG", "screen": "bag"}], "cursor_at": [150, 9]}

    def drawn(manifest, records=()):
        library = BattlePresentationLibrary()
        for record in records:
            library.set("creature_screen", record.screen_id, record)
        runtime = SimpleNamespace(
            game=game,
            pg=pygame,
            project=SimpleNamespace(battle_presentation_library=library),
            manifest=manifest,
            resource_root=tmp_path,
            input=SimpleNamespace(just_pressed=lambda name: False),
            screen=screen,
        )
        screen.fill((0, 0, 0))
        CreatureMenuScreen(runtime).draw()
        return pygame.image.tobytes(screen, "RGB")

    from_manifest_ = drawn({"field": {"creature_menu": menu}, "battle": {"creature_screen": {}}})
    record = CreatureScreenSettings("field.creature_menu", menu)
    from_record = drawn({"field": {}, "battle": {}}, [record])
    assert from_record == from_manifest_
    off = CreatureScreenSettings("field.creature_menu", {"entries": []}, enabled=False)
    with_off = drawn({"field": {"creature_menu": menu}, "battle": {}}, [off])
    assert with_off == from_manifest_


def test_a_shop_set_up_only_in_the_project_opens_from_an_event(monkeypatch):
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    sys.path.insert(0, str(DEMO))
    import run_trial_smoke as smoke
    import trial_creatures

    from asteria.rpg.economy import ShopDefinition, ShopEntry
    from asteria.rpg.items import ItemDefinition
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project, game = smoke.load()
    trial_creatures.install(project)
    shop = CreatureScreenSettings("field.creature_shop", {"map_front_at": [72, 72]})
    project.battle_presentation_library.set("creature_screen", shop.screen_id, shop)
    rt = PlayableTestRuntime(project, game.save, DEMO, width=960, height=640)
    rt.manifest.get("field", {}).pop("creature_shop", None)  # only the project says so
    rt.open()
    rt._ui_mode = "field"
    try:
        db = rt.project.rpg_database
        db.add_item(ItemDefinition("test_potion", "POTION"))
        db.add_shop(ShopDefinition("test_mart", "MART", [
            ShopEntry("test_potion", buy_prices={"gold": 300.0})
        ]))  # fmt: skip
        rt.game.open_shop("test_mart")
        for _ in range(2):
            rt._frame([], 1 / 60)
        assert rt._ui_mode == "creature_shop"
        assert rt._creature_shop.shop_settings == {"map_front_at": [72, 72]}
    finally:
        rt.close()


def test_every_screen_lists_its_engine_places_and_explains_its_settings():
    from asteria.editor.creature_screens_dialog import engine_defaults, help_for, is_point

    assert engine_defaults("field.creature_shop")["places"]["list"] == [112, 16, 120, 128]
    assert "places" in engine_defaults("field.creature_menu")["summary"]
    assert engine_defaults("field.name_input")["pages"][0]["label"] == "UPPER"
    assert engine_defaults("field.picture_choices") == {}
    assert is_point("list", [112, 16, 120, 128], "places")  # a window's inside: x, y, w, h
    assert not is_point("size", [1, 2, 3, 4], "layout")
    assert "start menu's rows" in help_for("field.creature_menu", ("entries",))
    # a row's field: the sentence about its own table, not another table's same name
    assert "badges" in help_for("field.creature_menu", ("card", "badges", 0, "switch"))
    assert help_for("field.creature_menu", ("no_such_setting",)) == ""


def test_the_preview_draws_a_creature_screen_with_lent_settings(monkeypatch):
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    sys.path.insert(0, str(DEMO))
    import run_trial_smoke as smoke
    import trial_creatures

    from asteria.runtime.menu_preview import MenuPreview

    project, _game = smoke.load()
    trial_creatures.install(project, party_size=3)
    preview = MenuPreview(project, DEMO)
    library = project.battle_presentation_library
    try:
        menu = CreatureScreenSettings(
            "field.creature_menu", {"entries": [{"id": "bag", "label": "BAG", "screen": "bag"}]}
        )
        surface = preview.render_creature("field.creature_menu", menu)
        assert surface.get_size() == (240, 160)
        beside = [surface.get_at((x, y)) for x in range(0, 100, 7) for y in range(0, 160, 7)]
        assert min(c.a for c in beside) == 255  # the field under the window, as in the game
        assert sum(c[:3] != (0, 0, 0) for c in beside) > len(beside) // 2  # not a black field
        assert library.get("creature_screen", "field.creature_menu") is None  # only lent
        moved = CreatureScreenSettings(
            "field.creature_menu", {**menu.data, "start_at": [20, 40], "start_width": 80}
        )
        other = preview.render_creature("field.creature_menu", moved)
        assert other.get_view("2").raw != surface.get_view("2").raw  # the window moved
        library.set("creature_screen", "field.creature_menu", moved)
        preview.render_creature("field.creature_menu", None)  # the manifest's for a moment
        assert library.get("creature_screen", "field.creature_menu") == moved  # given back
        # a screen that cannot be shown here: no picture, nothing breaks
        assert preview.render_creature("field.picture_choices", None) is None
    finally:
        preview.close()


def test_every_setting_help_sentence_has_chinese():
    import importlib
    import re

    from asteria.editor import i18n
    from asteria.editor.creature_screens_dialog import MODULES, help_for

    missing = []
    for module in MODULES.values():
        words = " ".join((importlib.import_module(module).__doc__ or "").split())
        for part in re.split(r"(?<=\.)\s+|;\s+|\s\*\s", words):  # as help_for splits
            if "``" in part or '"' in part:
                sentence = part.strip(" -;*").replace("``", "")
                if i18n.translate(sentence, "zh_TW") == sentence:
                    missing.append(sentence)
    assert missing == []
    shown = i18n.CURRENT["language"]
    try:
        i18n.CURRENT["language"] = "zh_TW"
        assert "開始選單" in help_for("field.creature_menu", ("entries",))
    finally:
        i18n.CURRENT["language"] = shown
