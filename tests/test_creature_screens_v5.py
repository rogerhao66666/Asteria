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
    assert engine_defaults("field.name_input") == {}
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
