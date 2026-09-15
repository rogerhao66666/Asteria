import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from asteria.core import Scene, Transform
from asteria.editor.shell import AsteriaEditorWindow
from asteria.project import Project
from asteria.rpg import ActorDefinition
from asteria.runtime import ActorLinkComponent, SpriteRenderer2D

_app = QApplication.instance() or QApplication([])


def _project_with_actor():
    p = Project("Game")
    p.add_scene(Scene("Town"))
    p.rpg_database.add_actor(ActorDefinition("hero_01", "Aria"))
    return p


def test_place_actor_creates_a_linked_entity_not_a_tile(tmp_path):
    window = AsteriaEditorWindow(_project_with_actor())
    window.document.set_project(window.document.project, file_path=tmp_path / "game.asteria.json")
    scene = window.document.project.scenes()[0]
    assert len(scene.entities()) == 0

    assert window.scene_controller.place_actor("hero_01")

    entities = scene.entities()
    assert len(entities) == 1
    entity = entities[0]
    assert entity.name == "Aria"
    link = entity.try_get(ActorLinkComponent)
    assert link is not None and link.actor_id == "hero_01"
    # A bare Entity() has no Transform; without one the entity has no
    # position and build_entity_sprite_draws silently skips it.
    assert entity.try_get(Transform) is not None
    # A placed character is drawn a sprite so it is visible immediately.
    assert entity.try_get(SpriteRenderer2D) is not None

    assert window.document.commands.can_undo
    window.document.undo()
    assert len(scene.entities()) == 0
    window.close(); _app.processEvents()


def test_place_actor_prefills_sprite_from_a_stored_appearance(tmp_path):
    project_path = tmp_path / "game.asteria.json"
    window = AsteriaEditorWindow(_project_with_actor())
    window.document.set_project(window.document.project, file_path=project_path)
    window.apply_actor_appearance("hero_01", "sheet-1", frame_index=2, flip_x=True)
    # apply_actor_appearance with no linked entities yet only writes the
    # store; place_actor should still pick it up for a *new* placement.

    assert window.scene_controller.place_actor("hero_01")
    entity = window.document.project.scenes()[0].entities()[0]
    sprite = entity.try_get(SpriteRenderer2D)
    assert sprite is not None
    assert sprite.sprite_sheet_asset_id == "sheet-1"
    assert sprite.frame_index == 2
    assert sprite.flip_x is True
    window.document.mark_saved()
    window.close(); _app.processEvents()


def test_apply_actor_appearance_syncs_name_and_sprite_onto_every_linked_entity(tmp_path):
    project_path = tmp_path / "game.asteria.json"
    window = AsteriaEditorWindow(_project_with_actor())
    window.document.set_project(window.document.project, file_path=project_path)
    window.scene_controller.place_actor("hero_01")
    entity = window.document.project.scenes()[0].entities()[0]
    assert entity.try_get(SpriteRenderer2D) is not None

    window.document.project.rpg_database.actors["hero_01"] = ActorDefinition(
        "hero_01", "Aria Windrunner"
    )
    assert window.apply_actor_appearance("hero_01", "sheet-2", frame_index=1)

    assert entity.name == "Aria Windrunner"
    sprite = entity.try_get(SpriteRenderer2D)
    assert sprite is not None
    assert sprite.sprite_sheet_asset_id == "sheet-2"
    assert sprite.frame_index == 1
    assert window.actor_appearance("hero_01").sprite_sheet_asset_id == "sheet-2"
    assert window.document.commands.can_undo
    window.document.mark_saved()
    window.close(); _app.processEvents()


def test_place_actor_on_map_action_needs_a_scene_but_not_an_actor():
    p = Project("Game")
    window = AsteriaEditorWindow(p)
    window._refresh_actions()
    assert not window.place_actor_action.isEnabled()  # nowhere to place it

    # An empty cast is fine — the picker can define a character inline.
    p.add_scene(Scene("Town"))
    window._refresh_actions()
    assert window.place_actor_action.isEnabled()
    window.close(); _app.processEvents()


def test_placing_a_character_can_define_the_actor_inline(tmp_path, monkeypatch):
    import asteria.editor.shell as shell_module

    p = Project("Game")
    p.add_scene(Scene("Town"))
    window = AsteriaEditorWindow(p)
    window.document.set_project(p, file_path=tmp_path / "game.asteria.json")
    assert not p.rpg_database.actors

    monkeypatch.setattr(
        shell_module.QInputDialog, "getItem",
        staticmethod(lambda *a, **k: (window.NEW_ACTOR_CHOICE, True)),
    )
    monkeypatch.setattr(
        shell_module.QInputDialog, "getText",
        staticmethod(lambda *a, **k: ("Village Girl", True)),
    )
    assert window.place_actor_on_map()
    # Placement is now pointer-driven: the menu arms it, a map click commits.
    assert window.viewport._pending_actor_id == "village_girl"
    assert window.scene_controller.place_actor("village_girl")

    assert "village_girl" in p.rpg_database.actors
    entity = p.scenes()[0].entities()[0]
    assert entity.name == "Village Girl"
    assert entity.try_get(ActorLinkComponent).actor_id == "village_girl"
    window.document.mark_saved()
    window.close(); _app.processEvents()


def test_place_actor_on_map_menu_action_uses_the_picked_actor(tmp_path, monkeypatch):
    window = AsteriaEditorWindow(_project_with_actor())
    window.document.set_project(window.document.project, file_path=tmp_path / "game.asteria.json")
    import asteria.editor.shell as shell_module

    monkeypatch.setattr(
        shell_module.QInputDialog, "getItem",
        staticmethod(lambda *a, **k: ("Aria (hero_01)", True)),
    )
    assert window.place_actor_on_map()
    assert window.viewport._pending_actor_id == "hero_01"
    assert window.scene_controller.place_actor("hero_01")
    entity = window.document.project.scenes()[0].entities()[0]
    assert entity.name == "Aria"
    window.document.mark_saved()
    window.close(); _app.processEvents()


def test_inspector_shows_actor_id_as_a_combo_of_existing_actors():
    from asteria.editor.widgets import InspectorWidget
    from asteria.editor.inspector import build_inspector_fields
    from PySide6.QtWidgets import QComboBox

    p = _project_with_actor()
    p.rpg_database.add_actor(ActorDefinition("hero_02", "Bram"))
    scene = p.scenes()[0]
    from asteria.core import Entity

    entity = scene.add_entity(Entity("Marker"))
    link = entity.add_component(ActorLinkComponent())
    link.actor_id = "hero_02"

    from asteria.editor.model import EditorDocument

    document = EditorDocument(p)
    document.selection.set_single("component", link)
    inspector = InspectorWidget(document)
    inspector.show_component("ActorLink", build_inspector_fields(link))

    combo = inspector.table.cellWidget(0, 1)
    assert isinstance(combo, QComboBox)
    assert combo.currentData() == "hero_02"
    labels = [combo.itemText(i) for i in range(combo.count())]
    assert "Aria (hero_01)" in labels
    assert "Bram (hero_02)" in labels


def test_character_tab_appearance_panel_applies_to_a_placed_actor(tmp_path):
    from asteria.assets.types import AssetRecord
    from asteria.editor.workspace import WorkspaceMode

    project = _project_with_actor()
    sheet_record = AssetRecord.create(kind="sprite_sheet", source_path="s.json", name="Hero Sheet")
    project.assets.add(sheet_record)

    window = AsteriaEditorWindow(project)
    window.document.set_project(window.document.project, file_path=tmp_path / "game.asteria.json")
    # This project references a sprite sheet sidecar that does not exist, so
    # auto-generating art on placement bails out; the panel still applies one.
    window.scene_controller.place_actor("hero_01")
    entity = window.document.project.scenes()[0].entities()[0]

    window.workspace.set_mode(WorkspaceMode.RPG)
    hub = window.rpg_authoring.child
    idx = hub.category.findData("units")
    hub.category.setCurrentIndex(idx)
    hub.refresh()
    assert hub.selected_id == "hero_01"
    assert not hub.appearance_panel.isHidden()
    assert hub.appearance_sheet_combo.currentData() == sheet_record.id

    hub.appearance_frame_spin.setValue(4)
    hub.appearance_flip_checkbox.setChecked(True)
    assert hub._apply_appearance()

    sprite = entity.try_get(SpriteRenderer2D)
    assert sprite is not None
    assert sprite.sprite_sheet_asset_id == sheet_record.id
    assert sprite.frame_index == 4
    assert sprite.flip_x is True
    window.document.mark_saved()
    window.close(); _app.processEvents()


def test_appearance_panel_is_usable_before_the_project_is_ever_saved():
    from asteria.assets.types import AssetRecord
    from asteria.editor.workspace import WorkspaceMode

    project = _project_with_actor()
    project.assets.add(AssetRecord.create(kind="sprite_sheet", source_path="s.json"))
    window = AsteriaEditorWindow(project)
    window.workspace.set_mode(WorkspaceMode.RPG)
    hub = window.rpg_authoring.child
    idx = hub.category.findData("units")
    hub.category.setCurrentIndex(idx)
    hub.refresh()
    assert hub.appearance_apply_button.isEnabled()
    assert hub.appearance_generate_button.isEnabled()
    assert "Save the project" not in hub.appearance_hint.text()
    window.document.mark_saved()
    window.close(); _app.processEvents()


def test_apply_actor_appearance_works_without_a_saved_project():
    window = AsteriaEditorWindow(_project_with_actor())
    assert window.scene_controller.place_actor("hero_01")
    # No sidecar to write yet, but the map entities still pick up the sprite.
    assert window.apply_actor_appearance("hero_01", "sheet-1")
    entity = window.document.project.scenes()[0].entities()[0]
    assert entity.try_get(SpriteRenderer2D).sprite_sheet_asset_id == "sheet-1"
    window.document.mark_saved()
    window.close(); _app.processEvents()
