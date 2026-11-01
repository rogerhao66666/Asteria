"""Pictures by kind: a character's picture is chosen among characters (monsters too), the
project's picture folders and any file; the party leader looks like the player on the map."""

import shutil
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

DEMO = Path(__file__).resolve().parents[1] / "reference_projects/full_verification_demo"


def _window(project_file):
    from asteria.editor import EditorDocument
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project

    project = Project.load_json(project_file, EditorDocument().component_registry)
    window = AsteriaEditorWindow(project)
    window.document.file_path = project_file
    window._resolve_project_resources()
    window.refresh_all()
    return window


def _close(window):
    window.document.mark_saved()  # closing never asks about unsaved changes here
    window.runtime_monitor.stop()
    window.close()
    window.deleteLater()


def _walking_sheet(path, size=(96, 128)):
    from PIL import Image

    Image.new("RGBA", size, (200, 80, 40, 255)).save(path)
    return path


def test_folders_name_the_kind_of_a_picture():
    from asteria.editor.picture_categories import folder_category

    assert folder_category("playable_assets/characters/hero.png") == "characters"
    assert folder_category("art/Monsters/slime.png") == "characters"  # monsters are characters
    assert folder_category("playable_assets/tilesets/town.png") == "tilesets"
    assert folder_category("playable_assets/items/sword.png") == "items"
    assert folder_category("characters/fx/slash.png") == "effects"  # the innermost folder
    assert folder_category("playable_assets/hero.png") is None


def test_the_picture_dialog_starts_at_characters(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.picture_categories import sheet_category
    from asteria.editor.sprite_sheet_picker import PicturePickerDialog

    app = QApplication.instance() or QApplication([])
    window = _window(DEMO / "project.asteria.json")
    try:
        document = window.document
        dialog = PicturePickerDialog(document, window)
        tabs = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        assert len(tabs) == 1 and tabs[0].startswith("Characters")  # no map tiles to wade
        assert dialog.tabs.isHidden()
        shown = [dialog.listing.item(i).data(0x0100)[1] for i in range(dialog.listing.count())]
        assert shown and all(sheet_category(document, s) == "characters" for s in shown)
        kinds = {sheet_category(document, s) for s in document.asset_views.sprite_sheet_ids()}
        assert {"characters", "tilesets", "objects"} <= kinds  # the map's tiles are apart
        # nothing is picked when it opens: OK waits for a click on a picture
        assert dialog.picked() is None and not dialog.ok_button.isEnabled()
        dialog.accept()
        assert dialog.result() == 0 and dialog.chosen is None
        dialog.listing.item(1).setSelected(True)
        assert dialog.ok_button.isEnabled()
        every = PicturePickerDialog(document, window, category_id=None)  # every kind, tabbed
        names = [every.tabs.tabText(i) for i in range(every.tabs.count())]
        assert names[0].startswith("Characters") and names[-1].startswith("All")
        every.listing.item(0).setSelected(True)
        every.tabs.setCurrentIndex(0)  # another tab (it opens on All): picked afresh
        assert not every.ok_button.isEnabled()
        battle = PicturePickerDialog(document, window, battle=True)
        assert battle.tabs.count() == 1 and battle.tabs.tabText(0).startswith("Characters")
        shown = [battle.listing.item(i).data(0x0100)[1] for i in range(battle.listing.count())]
        assert shown and not any(s.startswith("battle.fx.") for s in shown)  # no effects
        app.processEvents()
    finally:
        _close(window)


def test_the_leader_wears_the_players_look_and_a_new_picture_walks(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.actor_appearance import get_actor_appearance
    from asteria.editor.picture_import import (
        PictureImportError,
        folder_pictures,
        import_walking_picture,
    )
    from asteria.editor.record_form import RecordForm
    from asteria.editor.sprite_sheet_picker import PictureBox, resolve_pictures
    from asteria.runtime import Animator2DComponent, SpriteRenderer2D

    app = QApplication.instance() or QApplication([])
    project_dir = tmp_path / "demo"
    shutil.copytree(DEMO, project_dir, ignore=shutil.ignore_patterns("__pycache__"))
    window = _window(project_dir / "project.asteria.json")
    try:
        document = window.document
        project = document.project
        start = project.game_start
        player = next(
            s.get_entity(start.player_entity_id)
            for s in project.scenes()
            if s.get_entity(start.player_entity_id) is not None
        )
        sprite, animator = player.get(SpriteRenderer2D), player.get(Animator2DComponent)
        before = (sprite.sprite_sheet_asset_id, animator.clip_set_id, player.name)
        look = get_actor_appearance(document, "hero_01")  # Roger leads the party
        assert look.sprite_sheet_asset_id == before[0]
        # a picture dropped in the project's characters folder is offered before it is used
        folder = project_dir / "playable_assets" / "characters"
        folder.mkdir(parents=True)
        _walking_sheet(folder / "dropped.png")
        assert folder_pictures(document) == ("playable_assets/characters/dropped.png",)
        sheet_id = import_walking_picture(document, _walking_sheet(tmp_path / "My Hero.png"))
        resolve_pictures(document, window)
        assert (folder / "my_hero.png").is_file()  # copied in: the project stays whole
        assert document.asset_views.sprite_sheet(sheet_id) is not None
        assert len(document.asset_views.sprite_sheet(sheet_id).frames) == 12
        with pytest.raises(PictureImportError, match="3 columns by 4 rows"):
            import_walking_picture(document, _walking_sheet(tmp_path / "odd.png", (50, 50)))
        assert not (folder / "odd.png").exists()  # nothing copied in for a wrong sheet
        form = next(f for f in window.findChildren(RecordForm) if f.document is document)
        record = {"actor_id": "hero_01", "display_name": "Roger"}
        form.set_record(record, "hero_01", category="actors")
        app.processEvents()
        box = form.widget().findChild(PictureBox)
        old_picture = box.pixmap().toImage()
        form.pick_picture({"actor_id": "hero_01"}, box, sheet_id=sheet_id)
        assert box.pixmap().toImage() != old_picture  # the box shows the new picture at once
        assert sprite.sprite_sheet_asset_id == sheet_id
        assert sprite.frame_index == 1  # standing, facing down
        assert animator.clip_set_id != before[1] and animator.default_clip == "idle_down"
        assert player.name == before[2]  # the player's entity keeps its own name
        document.commands.undo()
        assert (sprite.sprite_sheet_asset_id, animator.clip_set_id, player.name) == before
        assert get_actor_appearance(document, "hero_01").sprite_sheet_asset_id == before[0]
    finally:
        _close(window)


def test_an_icon_is_chosen_from_its_kind_as_a_picture(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.game_systems_widget import _IconPicker
    from asteria.editor.icon_picker_dialog import IconPickerDialog
    from asteria.editor.image_tools import IconLibrary

    app = QApplication.instance() or QApplication([])
    window = _window(DEMO / "project.asteria.json")
    try:
        document = window.document
        library = IconLibrary(document)
        current = "playable_assets/lucifer/icons/I_Clock.png"
        dialog = IconPickerDialog(library, window, current=current)
        assert dialog.listing.count() == len(library.choices())  # icons only, no other kind
        assert dialog.picked() is None and not dialog.ok_button.isEnabled()
        dialog.filter.setText("clock")
        assert 0 < dialog.listing.count() < 20
        dialog.listing.item(0).setSelected(True)
        dialog.accept()
        assert dialog.chosen and "clock" in dialog.chosen.lower()
        picker = _IconPicker(library)
        picker.setText(current)
        assert picker.name.text() == "Clock" and picker.combo.isHidden()  # in words
        monkeypatch.setattr(
            "asteria.editor.icon_picker_dialog.pick_icon",
            lambda *a, **k: "forged:fire",
        )
        picker.preview.doubleClicked.emit()  # a double-click on the picture chooses
        assert picker.text() == "forged:fire"
        app.processEvents()
    finally:
        _close(window)


def test_a_fighter_chooses_from_every_character_and_a_map_one_becomes_a_battle_sprite(
    monkeypatch,
):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.picture_import import _image_size, _project_dir
    from asteria.editor.sprite_sheet_picker import PicturePickerDialog
    from asteria.runtime.battle_visuals import BattleVisualResolver

    app = QApplication.instance() or QApplication([])
    window = _window(DEMO / "project.asteria.json")
    try:
        document = window.document
        walking = PicturePickerDialog(document, window)
        battle = PicturePickerDialog(document, window, battle=True)
        assert battle.listing.count() >= walking.listing.count()  # every map character too
        known = {a.asset_id for a in document.project.assets.snapshot()}
        row = next(
            i
            for i in range(battle.listing.count())
            if battle.listing.item(i).data(0x0100)[1] not in known
            or not battle.listing.item(i).data(0x0100)[1].startswith("battle.")
        )
        map_sheet = battle.listing.item(row).data(0x0100)[1]
        battle.listing.item(row).setSelected(True)
        battle.accept()
        chosen = battle.chosen
        assert chosen.startswith("battle.combatant.") and chosen != map_sheet
        root = _project_dir(document)
        resolver = BattleVisualResolver(document.project, lambda uri: _image_size(root / uri))
        assert resolver.sprite_sheet(chosen).frames and "idle" in resolver.clip_set(chosen).clips
        again = PicturePickerDialog(document, window, battle=True)  # made once, then reused
        assert again._battle_sheet(map_sheet) == chosen
        app.processEvents()
    finally:
        document.mark_saved()
        _close(window)
