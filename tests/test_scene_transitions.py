"""CB4d: scene transitions with fades and persistent entities (ASTERIA_SPEC §8 Scene)."""

import pytest

from asteria.core import (
    Application,
    Entity,
    PersistentComponent,
    Scene,
    SceneTransition,
    Transform,
)


def _scenes():
    town, cave = Scene("Town"), Scene("Cave")
    companion = town.add_entity(Entity("Companion"))
    companion.add_component(Transform(3, 4))
    companion.add_component(PersistentComponent())
    town.add_entity(Entity("Shopkeeper"))
    return town, cave, companion


def test_instant_change_moves_persistent_entities_only():
    town, cave, companion = _scenes()
    app = Application(backend=None)
    app.set_scene(town)
    app.change_scene(cave)
    assert app.scene is cave
    assert companion.scene is cave and [e.name for e in town.entities()] == ["Shopkeeper"]


def test_fade_covers_then_swaps_then_reveals():
    town, cave, companion = _scenes()
    app = Application(backend=None)
    app.set_scene(town)
    app.change_scene(cave, SceneTransition(fade_out=0.2, fade_in=0.4, color=(10, 20, 30)))
    assert app.scene is town and app.transition_color == (10, 20, 30)
    assert app.advance_transition(0.1) and app.transition_cover == pytest.approx(0.5)
    app.advance_transition(0.1)
    assert (
        app.scene is cave
        and companion.scene is cave
        and app.transition_cover == pytest.approx(1.0)
    )
    app.advance_transition(0.2)
    assert app.transition_cover == pytest.approx(0.5)
    assert not app.advance_transition(0.3)
    assert app.transition_cover == 0.0 and app.transition_color is None


def test_transition_rejects_negative_durations():
    with pytest.raises(ValueError):
        SceneTransition(fade_out=-1)


def test_event_transfer_carries_persistent_entities():
    from pathlib import Path

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.game_save import GameRuntimeSave
    from asteria.runtime.game_session import GameSessionRuntime

    root = Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    start = project.scene(project.startup_scene_id)
    pet = start.add_entity(Entity("Pet"))
    pet.add_component(Transform())
    pet.add_component(PersistentComponent())
    town = project.add_scene(Scene("Town"))
    save = GameRuntimeSave.load_json(root / "saves" / "boss_stress.asteria-save.json", project)
    game = GameSessionRuntime(project, save)
    game.transfer_player(town.id, 1, 2)
    assert game.player.scene is town and pet.scene is town
