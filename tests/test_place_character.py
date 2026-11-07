"""The tool strip's character tool: a character that looks like the scene's player rides
under the mouse and is made - actor and map entity - where the author clicks; and Database >
Actors shows and changes how an actor looks on the map."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

DEMO = Path(__file__).resolve().parents[1] / "reference_projects/full_verification_demo"


def _window(app):
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project
    from asteria.runtime.component_registry import default_component_registry

    project = Project.load_json(DEMO / "project.asteria.json", default_component_registry())
    window = AsteriaEditorWindow(project)
    window.document.file_path = DEMO / "project.asteria.json"
    window._resolve_project_resources()
    window.refresh_all()
    return window


def test_the_character_tool_places_a_player_lookalike_at_the_clicked_cell(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.scene.place_character import default_appearance
    from asteria.runtime import ActorLinkComponent, Animator2DComponent, SpriteRenderer2D

    app = QApplication.instance() or QApplication([])
    window = _window(app)
    try:
        window.show()
        app.processEvents()
        scene = window.viewport.current_scene()
        player = next(e for e in scene.entities() if e.name == "Player")
        look = default_appearance(window.document, scene)
        assert look.sprite_sheet_asset_id == player.get(SpriteRenderer2D).sprite_sheet_asset_id
        assert look.clip_set_id == player.get(Animator2DComponent).clip_set_id
        strip = window.tool_strip
        assert strip.buttons["character"].key == "N"
        strip.buttons["character"].click()  # no dialog: the player's look is carried
        assert window.viewport.character_placement_active
        assert window.viewport._placement_ghost is not None
        assert not window.viewport._placement_ghost.isNull()
        assert strip.buttons["character"].isChecked()
        before = set(window.document.project.rpg_database.actors)
        count = len(list(scene.entities()))
        window._place_character_at((10, 6))
        actors = window.document.project.rpg_database.actors
        new_id = next(iter(set(actors) - before))
        assert new_id == "actor.new_character" and actors[new_id].display_name == "New Character"
        entity = next(e for e in scene.entities() if e.name == "New Character")
        assert entity.get(ActorLinkComponent).actor_id == new_id
        assert entity.get(SpriteRenderer2D).sprite_sheet_asset_id == look.sprite_sheet_asset_id
        assert entity.get(Animator2DComponent).clip_set_id == look.clip_set_id
        assert len(list(scene.entities())) == count + 1
        assert not window.viewport.character_placement_active
        assert not strip.buttons["character"].isChecked()
        window.document.commands.undo()  # one step takes both the actor and the entity back
        assert new_id not in actors and len(list(scene.entities())) == count
        strip.buttons["character"].click()
        window.cancel_character_placement()  # Escape
        assert not window.viewport.character_placement_active
        assert window._pending_character_visual is None
    finally:
        window.document.mark_saved()  # closing never asks about unsaved changes here
        window.runtime_monitor.stop()
        window.close()
        window.deleteLater()


def test_the_picture_box_changes_an_actor_look_and_a_fighter_sheet(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.records.form import RecordForm
    from asteria.editor.records.sprite_sheet_picker import PictureBox
    from asteria.editor.scene import actor_appearance
    from asteria.runtime import ActorLinkComponent, SpriteRenderer2D

    app = QApplication.instance() or QApplication([])
    window = _window(app)
    try:
        scene = window.viewport.current_scene()
        monkeypatch.setattr(  # no sidecar written into the demo project
            actor_appearance.ActorAppearanceLibrary, "_save", lambda self: None
        )
        views = window.document.asset_views
        first = views.sprite_sheet_ids()[0]
        views.set_sprite_sheet("another_sheet", views.sprite_sheet(first))  # a second look
        window.place_default_character()  # a placed character is linked to its actor
        window._place_character_at((4, 4))
        linked = next(e for e in scene.entities() if e.try_get(ActorLinkComponent) is not None)
        actor_id = linked.get(ActorLinkComponent).actor_id
        before = linked.get(SpriteRenderer2D).sprite_sheet_asset_id
        form = next(f for f in window.findChildren(RecordForm) if f.document is window.document)
        form.set_record({"actor_id": actor_id, "display_name": "X"}, actor_id, category="actors")
        app.processEvents()
        box = form.widget().findChild(PictureBox)  # the page shown now
        assert box is not None and not box.pixmap().isNull()  # the map look is the picture
        assert "Double-click" in box.toolTip()
        asked = []
        monkeypatch.setattr(
            "asteria.editor.records.sprite_sheet_picker.pick_sprite_sheet",
            lambda document, parent=None, battle=False: asked.append(battle) or "another_sheet",
        )
        box.doubleClicked.emit()  # the double-click asks for a map sheet (the dialog, stubbed)
        assert asked == [False]
        assert linked.get(SpriteRenderer2D).sprite_sheet_asset_id == "another_sheet"
        window.document.commands.undo()
        assert linked.get(SpriteRenderer2D).sprite_sheet_asset_id == before
        # a fighter's record: the box picks its battlefield sheet, and its pictures come first
        data = {
            "profile_id": "hero_01",
            "battlefield_visible": True,
            "assets": {
                "battlefield_asset_id": "battle.combatant.hero_01",
                "portrait_asset_id": None,
            },
            "states": [],
        }
        form.set_record(data, "hero_01", category="combatant_visuals")
        app.processEvents()
        from PySide6.QtWidgets import QToolButton

        titles = [
            b.text()
            for b in form.widget().findChildren(QToolButton)
            if b.objectName() == "FormSectionTitle"
        ]
        assert titles and titles[0].strip().startswith("Pictures")  # the pictures come first
        box = form.widget().findChild(PictureBox)
        assert box is not None
        monkeypatch.setattr(
            "asteria.editor.records.sprite_sheet_picker.pick_sprite_sheet",
            lambda document, parent=None, battle=False: (
                asked.append(battle) or "battle.combatant.hero_02"
            ),
        )
        box.doubleClicked.emit()
        assert asked[-1] is True  # the battle sheets, not the map's
        assert form.record()["assets"]["battlefield_asset_id"] == "battle.combatant.hero_02"
    finally:
        window.document.mark_saved()  # closing never asks about unsaved changes here
        window.runtime_monitor.stop()
        window.close()
        window.deleteLater()
