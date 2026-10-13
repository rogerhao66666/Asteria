"""CB14: generic character placement, actor links, appearance and inspector (no Generator)."""

from pathlib import Path

import pytest
from PIL import Image

from asteria.assets.character_visual import CharacterVisualSet
from asteria.core import Scene, Transform
from asteria.editor import EditorDocument
from asteria.editor.create_character_command import CreateCharacterCommand
from asteria.project import Project
from asteria.runtime import ActorLinkComponent, Animator2DComponent, SpriteRenderer2D

SHEET = (
    Path(__file__).resolve().parents[1]
    / "reference_projects"
    / "complex_reference_rpg"
    / "playable_assets"
    / "player_field_sheet.png"
)  # 3x4, 64x64 frames (CC0)


def test_walking_sheet_visual_set_infers_frames_and_rejects_bad_grids(tmp_path):
    visual = CharacterVisualSet.from_walking_sheet(SHEET, key="Field Hero!")
    assert visual.key == "field_hero"
    assert visual.frame_size == (64, 64) and visual.anchor == (32, 64)
    assert visual.walking_asset.kind == "character.walking"
    odd = tmp_path / "odd.png"
    Image.new("RGBA", (100, 100)).save(odd)
    with pytest.raises(ValueError):
        CharacterVisualSet.from_walking_sheet(odd, key="odd")


def test_create_character_from_any_walking_sheet_links_entity_to_actor():
    project = Project("Game")
    scene = project.add_scene(Scene("Map"))
    visual = CharacterVisualSet.from_walking_sheet(SHEET, key="ranger")
    command = CreateCharacterCommand(visual, project, scene, (2, 3), display_name="Ranger")
    created = command.execute()

    entity = scene.get_entity(created.entity_id)
    assert entity.get(SpriteRenderer2D).sprite_sheet_asset_id == "character/ranger/walking"
    assert entity.get(Animator2DComponent).clip_set_id == "animation.ranger"
    assert entity.get(ActorLinkComponent).actor_id == "actor.ranger"
    assert project.rpg_database.actors["actor.ranger"].display_name == "Ranger"
    assert dict(project.assets.resolve("character/ranger/walking").metadata)["frame_size"] == (
        64,
        64,
    )
    assert SHEET.is_file()  # the command never owns or deletes a referenced sheet

    command.undo()
    assert (
        scene.get_entity(created.entity_id) is None
        and "actor.ranger" not in project.rpg_database.actors
    )
    command.redo()
    assert scene.get_entity(created.entity_id) is not None


def test_actor_appearance_updates_every_linked_entity_in_one_undo_step():
    from asteria.editor.actor_appearance import apply_actor_appearance, get_actor_appearance

    project = Project("Game")
    scene = project.add_scene(Scene("Map"))
    document = EditorDocument(project)
    created = CreateCharacterCommand(
        CharacterVisualSet.from_walking_sheet(SHEET, key="mage"),
        project,
        scene,
        (0, 0),
        display_name="Mage",
    ).execute()
    entity = scene.get_entity(created.entity_id)

    assert apply_actor_appearance(
        document, "actor.mage", "sheet.other", frame_index=4, flip_x=True
    )
    sprite = entity.get(SpriteRenderer2D)
    assert (sprite.sprite_sheet_asset_id, sprite.frame_index, sprite.flip_x) == (
        "sheet.other",
        4,
        True,
    )
    assert get_actor_appearance(document, "actor.mage").sprite_sheet_asset_id == "sheet.other"
    document.undo()
    assert sprite.sprite_sheet_asset_id == "character/mage/walking"


def test_inspector_offers_actor_sprite_and_clip_choices():
    from asteria.editor.inspector import build_inspector_fields, inspector_choices

    project = Project("Game")
    scene = project.add_scene(Scene("Map"))
    document = EditorDocument(project)
    created = CreateCharacterCommand(
        CharacterVisualSet.from_walking_sheet(SHEET, key="knight"),
        project,
        scene,
        (0, 0),
        display_name="Knight",
    ).execute()
    entity = scene.get_entity(created.entity_id)
    document.asset_views.set_sprite_sheet("character/knight/walking", object())
    document.asset_views.set_clip_set("animation.knight", object())

    def choices(component, name):
        field = next(f for f in build_inspector_fields(component) if f.name == name)
        return [value for _, value in inspector_choices(document, component, field)]

    assert choices(entity.get(ActorLinkComponent), "actor_id") == ["", "actor.knight"]
    assert choices(entity.get(SpriteRenderer2D), "sprite_sheet_asset_id") == [
        "",
        "character/knight/walking",
    ]
    assert choices(entity.get(Animator2DComponent), "clip_set_id") == ["", "animation.knight"]
    link = entity.get(ActorLinkComponent)
    link.actor_id = "actor.gone"
    assert choices(link, "actor_id")[-1] == "actor.gone"  # a dangling id stays visible


def test_editor_places_sheet_character_copies_it_and_lists_it_with_a_thumbnail(
    tmp_path, monkeypatch
):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox

    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.storage import save_document

    app = QApplication.instance() or QApplication([])
    project = Project("Game")
    project.add_scene(Scene("Map"))
    window = AsteriaEditorWindow(project)
    try:
        save_document(window.document, tmp_path / "game.asteria.json")
        visual = window.place_character_from_sheet(SHEET, "Field Hero")
        assert isinstance(visual, CharacterVisualSet)
        assert (tmp_path / "characters" / "field_hero.png").is_file()
        assert visual.walking_asset.source.uri == str(Path("characters") / "field_hero.png")

        created = window._place_character_at((4, 5))
        assert (
            created is not None
            and created.entity.get(ActorLinkComponent).actor_id == "actor.field_hero"
        )
        assert created.entity.get(Transform).x > 0

        window.refresh_asset_list()
        items = [window.asset_list.item(i) for i in range(window.asset_list.count())]
        sheet_item = next(i for i in items if "character.walking" in i.text())
        assert not sheet_item.icon().isNull()

        window.document.select_component(created.entity.get(SpriteRenderer2D))
        window.refresh_inspector()
        table = window.inspector.table
        widgets = [table.cellWidget(r, 1) for r in range(table.rowCount())]
        assert any(isinstance(w, QComboBox) for w in widgets)  # sprite sheet picker
        combo = next(w for w in widgets if isinstance(w, QComboBox))
        assert not combo.currentText().startswith(
            "Missing"
        )  # the placed sheet is a loaded choice at once
        rows = [r for r in range(table.rowCount()) if table.cellWidget(r, 1) is not None]
        assert all(
            table.item(r, 1).text() == "" for r in rows
        )  # no value text beneath the widgets
        assert any(isinstance(w, QCheckBox) for w in widgets)  # flip_x / visible
    finally:
        window.document.mark_saved()
        window.close()
        app.processEvents()
