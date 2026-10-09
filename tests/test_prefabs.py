"""CB7: prefabs, variants, overrides, scene placement and propagation (ASTERIA_SPEC §10)."""

import pytest

from asteria.core import Entity, Scene, Transform
from asteria.core.prefab import (
    PrefabDefinition,
    PrefabError,
    PrefabInstanceComponent,
    PrefabLibrary,
    instance_overrides,
    instantiate,
    prefab_from_entity,
)
from asteria.editor import EditorDocument
from asteria.editor.prefab_commands import (
    InstantiatePrefabCommand,
    ReplacePrefabsCommand,
    RevertInstanceCommand,
    apply_instance_to_prefab_command,
)
from asteria.project import Project
from asteria.runtime import Interaction2DComponent, SpriteRenderer2D

REGISTRY = EditorDocument().component_registry


def _chest_entity():
    entity = Entity("Chest")
    entity.add_component(Transform(40, 50))
    sprite = entity.add_component(SpriteRenderer2D())
    sprite.sprite_sheet_asset_id, sprite.frame_index = "sheet.chest", 0
    talk = entity.add_component(Interaction2DComponent())
    talk.event_program_id = "open_chest"
    return entity


def _project_with_chest():
    project = Project("Game")
    scene = project.add_scene(Scene("Map"))
    project.prefabs.add(prefab_from_entity(_chest_entity(), "chest"))
    return project, scene


def test_prefab_capture_resets_placement_and_variants_override_and_remove():
    library = PrefabLibrary()
    library.add(prefab_from_entity(_chest_entity(), "chest"))
    assert library.resolve("chest")["asteria.Transform"]["x"] == 0.0
    gold = PrefabDefinition(
        "gold_chest", "Gold Chest",
        ({"type": "asteria.SpriteRenderer2D", "version": 1, "fields": {"frame_index": 3}},),
        base_prefab_id="chest",
    )
    library.add(gold)
    resolved = library.resolve("gold_chest")
    assert resolved["asteria.SpriteRenderer2D"]["frame_index"] == 3
    assert resolved["asteria.SpriteRenderer2D"]["sprite_sheet_asset_id"] == "sheet.chest"
    library.set(PrefabDefinition("mimic", "Mimic", (), "chest", ("asteria.Interaction2D",)))
    assert "asteria.Interaction2D" not in library.resolve("mimic")
    with pytest.raises(PrefabError):
        library.set(PrefabDefinition("chest", "Loop", (), "gold_chest"))
    assert library.get("chest").base_prefab_id == ""          # the failed edit was rolled back
    with pytest.raises(PrefabError):
        library.remove("chest")                                # still the base of variants


def test_instances_keep_overrides_and_placement_when_the_prefab_changes():
    project, scene = _project_with_chest()
    a = InstantiatePrefabCommand(project, REGISTRY, scene, "chest", 10, 20).execute()
    b = InstantiatePrefabCommand(project, REGISTRY, scene, "chest", 70, 80).execute()
    b.get(SpriteRenderer2D).frame_index = 9                    # override on one instance
    assert instance_overrides(b, project.prefabs.resolve("chest")) == {"asteria.SpriteRenderer2D": {"frame_index": 9}}

    changed = prefab_from_entity(_chest_entity(), "chest")
    sprite_record = next(r for r in changed.components if r["type"] == "asteria.SpriteRenderer2D")
    sprite_record["fields"].update(sprite_sheet_asset_id="sheet.chest_v2", frame_index=1)
    command = ReplacePrefabsCommand(project, REGISTRY, {"chest": changed})
    command.execute()
    assert (a.get(SpriteRenderer2D).sprite_sheet_asset_id, a.get(SpriteRenderer2D).frame_index) == ("sheet.chest_v2", 1)
    assert (b.get(SpriteRenderer2D).sprite_sheet_asset_id, b.get(SpriteRenderer2D).frame_index) == ("sheet.chest_v2", 9)
    assert (a.get(Transform).x, b.get(Transform).x) == (10, 70)
    command.undo()
    assert a.get(SpriteRenderer2D).sprite_sheet_asset_id == "sheet.chest"
    assert project.prefabs.resolve("chest")["asteria.SpriteRenderer2D"]["frame_index"] == 0


def test_variant_instances_follow_base_changes():
    project, scene = _project_with_chest()
    project.prefabs.add(PrefabDefinition(
        "gold_chest", "Gold Chest",
        ({"type": "asteria.SpriteRenderer2D", "version": 1, "fields": {"frame_index": 3}},), "chest",
    ))
    gold = InstantiatePrefabCommand(project, REGISTRY, scene, "gold_chest").execute()
    base = prefab_from_entity(_chest_entity(), "chest")
    next(r for r in base.components if r["type"] == "asteria.Interaction2D")["fields"]["event_program_id"] = "open_v2"
    ReplacePrefabsCommand(project, REGISTRY, {"chest": base}).execute()
    assert gold.get(Interaction2DComponent).event_program_id == "open_v2"
    assert gold.get(SpriteRenderer2D).frame_index == 3


def test_apply_instance_to_prefab_and_revert_instance():
    project, scene = _project_with_chest()
    a = InstantiatePrefabCommand(project, REGISTRY, scene, "chest", 1, 1).execute()
    b = InstantiatePrefabCommand(project, REGISTRY, scene, "chest", 2, 2).execute()
    a.get(SpriteRenderer2D).frame_index = 4
    apply_instance_to_prefab_command(project, REGISTRY, a).execute()
    assert project.prefabs.resolve("chest")["asteria.SpriteRenderer2D"]["frame_index"] == 4
    assert b.get(SpriteRenderer2D).frame_index == 4 and b.get(Transform).x == 2
    b.get(SpriteRenderer2D).opacity = 0.5
    revert = RevertInstanceCommand(project, REGISTRY, b)
    revert.execute()
    assert b.get(SpriteRenderer2D).opacity == 1.0 and b.get(Transform).x == 2
    revert.undo()
    assert b.get(SpriteRenderer2D).opacity == 0.5


def test_prefabs_and_instances_round_trip_with_the_project():
    project, scene = _project_with_chest()
    InstantiatePrefabCommand(project, REGISTRY, scene, "chest", 5, 6).execute()
    data = project.to_data()
    assert data["version"] == 10
    restored = Project.from_data(data, REGISTRY)
    assert restored.prefabs.ids() == ("chest",)
    entity = next(e for e in restored.scene(scene.id).entities() if e.has(PrefabInstanceComponent))
    assert entity.get(PrefabInstanceComponent).prefab_id == "chest" and entity.get(Transform).x == 5
    assert instantiate(restored.prefabs, "chest", REGISTRY).get(Interaction2DComponent).event_program_id == "open_chest"


def test_editor_prefab_menu_flow_with_undo():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    project = Project("Game")
    scene = project.add_scene(Scene("Map"))
    chest = scene.add_entity(_chest_entity())
    window = AsteriaEditorWindow(project)
    try:
        window.document.select_entity(chest)
        assert window.create_prefab_from_selection("chest") is not None
        assert chest.get(PrefabInstanceComponent).prefab_id == "chest"
        assert window.place_prefab("chest", 100, 120) is not None
        placed = window._selected_entity()
        assert placed is not chest and placed.get(Transform).x == 100
        window.document.undo()
        assert scene.get_entity(placed.id) is None
        window.document.undo()
        assert project.prefabs.ids() == () and not chest.has(PrefabInstanceComponent)
    finally:
        window.document.mark_saved()
        window.close()
        app.processEvents()
