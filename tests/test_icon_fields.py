"""Icon fields everywhere: records carry an icon_id, editors offer a picker, menus draw it."""

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "octopath_demo"


def _records():
    from asteria.rpg import (
        AchievementDefinition,
        EquipmentSetDefinition,
        FactionDefinition,
        QuestDefinition,
        QuestObjective,
        ShopDefinition,
    )
    from asteria.rpg.ability_build import PassiveDefinition
    from asteria.rpg.actors import ClassDefinition
    from asteria.rpg.extras import MenuEntry, MusicTrack
    from asteria.rpg.items import AttachmentDefinition

    return [
        QuestDefinition("q", "Q", objectives=[QuestObjective("o")], icon_id="forged:star"),
        FactionDefinition("f", "F", icon_id="forged:shield"),
        AchievementDefinition("a", "A", target="x", icon_id="forged:star"),
        EquipmentSetDefinition("s", "S", icon_id="forged:armor"),
        ClassDefinition("c", "C", icon_id="forged:sword"),
        AttachmentDefinition("g", "Gem", icon_id="forged:mono:Gm"),
        PassiveDefinition("p", "P", icon_id="forged:holy"),
        ShopDefinition("sh", "Shop", icon_id="icons/shop.png"),
        MusicTrack("t", "Track", "audio", icon_id="forged:bolt"),
        MenuEntry("m", "Menu", "prog", icon_id="forged:flag"),
    ]


@pytest.mark.parametrize("index", range(10))
def test_records_round_trip_their_icon_and_write_nothing_by_default(index):
    record = _records()[index]
    assert record.icon_id
    again = type(record).from_data(record.to_data())
    assert again.icon_id == record.icon_id
    plain_data = record.to_data()
    plain_data.pop("icon_id", None)
    assert type(record).from_data(plain_data).icon_id == ""  # old data still loads
    assert "icon_id" not in plain_data


def test_built_in_icons_resolve_for_the_runtime():
    from asteria.runtime.menu_icons import forged_spec, forged_surface

    assert forged_spec("forged:fire") == ("kind", "fire")
    assert forged_spec("forged:mono:Ab") == ("mono", "Ab")
    assert forged_spec("playable_assets/icons/x.png") is None
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    assert forged_surface("forged:fire", 24).get_size() == (24, 24)
    assert forged_surface("forged:mono:Ab", 20).get_size() == (20, 20)
    assert forged_surface("forged:no_such_kind", 24) is None
    assert forged_surface("whatever.png", 24) is None


@pytest.fixture
def document():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.project import Project

    QApplication.instance() or QApplication([])
    doc = EditorDocument()
    doc.project = Project.load_json(ROOT / "project.asteria.json", doc.component_registry)
    doc.file_path = ROOT / "project.asteria.json"
    return doc


def test_the_choices_list_project_pictures_and_the_built_in_library(document):
    from asteria.editor.image_tools import icon_choices

    ids = [i for i, _ in icon_choices(document)]
    assert any(i.startswith("playable_assets/lucifer/icons/skill_") for i in ids)
    assert "forged:fire" in ids and "forged:pet_lynx" in ids
    assert all(icon is not None for i, icon in icon_choices(document) if i.startswith("forged:"))


def test_importing_a_picture_copies_it_into_the_project_once(document, tmp_path):
    from asteria.editor.image_tools import IconLibrary

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    document.file_path = project_dir / "project.asteria.json"
    source = tmp_path / "outside" / "gem.png"
    source.parent.mkdir()
    import pygame

    surface = pygame.Surface((8, 8))
    surface.fill((200, 40, 40))
    pygame.image.save(surface, str(source))
    library = IconLibrary(document)
    first = library.import_file(source)
    assert first == "icons/gem.png" and (project_dir / first).is_file()
    assert library.import_file(source) == first  # the same picture is not copied again
    inside = project_dir / "pics" / "a.png"
    inside.parent.mkdir()
    pygame.image.save(surface, str(inside))
    assert library.import_file(inside) == "pics/a.png"  # a file already in the project stays


def test_the_form_icon_field_picks_shows_and_saves_an_icon(document):
    from asteria.editor.game_systems_authoring import FORMS, GameSystemsAuthoringController
    from asteria.editor.game_systems_widget import RecordForm

    controller = GameSystemsAuthoringController(document)
    for kind in (
        "shops",
        "quests",
        "factions",
        "achievements",
        "equipment_sets",
        "music_tracks",
        "menu_entries",
        "pet_species",
    ):
        assert any(f.kind == "icon" for f in FORMS[kind]), kind
    form = RecordForm(FORMS["pet_species"], controller.references, icons=controller.icon_library)
    form.set_data({"species_id": "x", "display_name": "X", "icon_id": "forged:pet_lynx"})
    picker = form.widgets["icon_id"]
    assert picker.text() == "forged:pet_lynx" and picker.preview.pixmap() is not None
    picker.setText("forged:fire")
    assert form.data()["icon_id"] == "forged:fire"
    picker.setText("")
    assert form.data()["icon_id"] == ""


def test_every_game_systems_kind_has_an_icon():
    from asteria.editor.decor import label_icon
    from asteria.editor.game_systems_authoring import KINDS
    from asteria.editor.icons import DRAWINGS

    missing = [k.label for k in KINDS if label_icon(k.label) not in DRAWINGS]
    assert missing == []


def test_the_pause_menu_and_quest_log_draw_icons(monkeypatch):
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.rpg import QuestDefinition, QuestObjective
    from asteria.rpg.extras import MenuEntry
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    db = project.rpg_database
    db.add_menu_entry(MenuEntry("tips", "Tips", "p", icon_id="forged:star"))
    db.add_quest(
        QuestDefinition(
            "herbs", "Herbs", objectives=[QuestObjective("pick")], icon_id="forged:heal"
        )
    )
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), ROOT, width=960, height=540
    )
    runtime.open()
    try:
        assert runtime._pause_menu.icons == {"entry:tips": "forged:star"}
        drawn = []
        original = runtime._draw_icon
        runtime._draw_icon = lambda icon_id, *a, **k: (
            drawn.append(icon_id),
            original(icon_id, *a, **k),
        )[1]
        menu = runtime._pause_menu  # on Tips: a short window scrolls the list to it
        menu.index = [key for key, _label in menu.options].index("entry:tips")
        runtime._draw_overlay_menu("Paused", menu)
        runtime.game.start_quest("herbs")
        runtime._draw_quests()
        assert drawn == ["forged:star", "forged:heal"]
    finally:
        runtime.close()
