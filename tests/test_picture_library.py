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
        assert tabs[0].startswith("Characters") and tabs[-1].startswith("All")
        shown = [dialog.listing.item(i).data(0x0100)[1] for i in range(dialog.listing.count())]
        assert shown and all(sheet_category(document, s) == "characters" for s in shown)
        kinds = {sheet_category(document, s) for s in document.asset_views.sprite_sheet_ids()}
        assert {"characters", "tilesets", "objects"} <= kinds  # the map's tiles are apart
        battle = PicturePickerDialog(document, window, battle=True)
        assert battle.tabs.tabText(0).startswith("Characters")
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
