import pytest

from asteria.core import Entity, Scene, Transform
from asteria.editor import EditorDocument
from asteria.editor.runtime_state_integration import (
    RuntimeStateIntegrationController,
    RuntimeStateIntegrationError,
)
from asteria.project import Project
from asteria.runtime.game_save import GameRuntimeSave


def make(tmp_path):
    p = Project("Game")
    s = Scene("Field")
    p.add_scene(s)
    player = Entity("Player")
    t = Transform()
    t.x = 10.0
    t.y = 20.0
    player.add_component(t)
    s.add_entity(player)
    d = EditorDocument(p)
    d.file_path = tmp_path / "game.asteria.json"
    return p, s, player, d, RuntimeStateIntegrationController(d)


def test_new_save_captures_world_and_rpg_boundaries(tmp_path):
    p, s, player, d, c = make(tmp_path)
    save = c.new_save(
        scene_id=s.id, player_entity_id=player.id, player_facing="right", player_position=(10, 20)
    )
    assert save.project_id == p.id
    assert save.scene_id == s.id
    assert save.player_entity_id == player.id
    assert save.player_facing == "right"
    assert save.player_position == (10.0, 20.0)
    assert save.rpg_state.party_actor_ids == ()


def test_save_file_roundtrip(tmp_path):
    p, s, player, d, c = make(tmp_path)
    save = c.new_save(scene_id=s.id, player_entity_id=player.id, player_position=(31, 47))
    save.event_context.set_switch("boss_defeated", True)
    path = tmp_path / "slot1.save.json"
    assert c.save(path) == path
    loaded = GameRuntimeSave.load_json(path, p)
    assert loaded.player_position == (31.0, 47.0)
    assert loaded.event_context.get_switch("boss_defeated")


def test_load_rejects_save_for_another_project(tmp_path):
    p, s, player, d, c = make(tmp_path)
    c.new_save(scene_id=s.id, player_entity_id=player.id)
    path = tmp_path / "slot.save.json"
    c.save(path)
    p2 = Project("Other")
    p2.add_scene(Scene("Other"))
    with pytest.raises(ValueError):
        GameRuntimeSave.load_json(path, p2)


def test_run_with_loaded_save_uses_saved_scene(tmp_path):
    p, s, player, d, c = make(tmp_path)
    other = Scene("Other")
    p.add_scene(other)
    c.new_save(scene_id=s.id, player_entity_id=player.id, player_position=(4, 5))
    session = c.run()
    assert session.source_scene_id == s.id
    assert session.runtime_save.player_position == (4.0, 5.0)
    assert session.runtime_project is not p


def test_capture_runtime_save_back_to_editor_boundary(tmp_path):
    p, s, player, d, c = make(tmp_path)
    c.new_save(scene_id=s.id, player_entity_id=player.id, player_position=(1, 2))
    session = c.run()
    session.runtime_save.player_position = (90.0, 70.0)
    session.runtime_save.event_context.set_variable("chapter", 3)
    captured = c.capture_from_session(session)
    assert captured.player_position == (90.0, 70.0)
    assert captured.event_context.get_variable("chapter") == 3


def test_capture_does_not_mutate_project_definitions(tmp_path):
    p, s, player, d, c = make(tmp_path)
    before = p.to_data()
    c.new_save(scene_id=s.id, player_entity_id=player.id)
    session = c.run()
    session.runtime_save.event_context.set_switch("runtime_only", True)
    c.capture_from_session(session)
    assert p.to_data() == before


def test_save_requires_path_first_time(tmp_path):
    _, s, player, _, c = make(tmp_path)
    c.new_save(scene_id=s.id, player_entity_id=player.id)
    with pytest.raises(RuntimeStateIntegrationError):
        c.save()


def test_loaded_save_can_be_resaved_to_same_path(tmp_path):
    _, s, player, _, c = make(tmp_path)
    c.new_save(scene_id=s.id, player_entity_id=player.id)
    path = tmp_path / "slot.save.json"
    c.save(path)
    c.load_save(path)
    c.loaded_save.event_context.set_variable("golden_key", 1)
    assert c.save() == path
    reloaded = c.load_save(path)
    assert reloaded.event_context.get_variable("golden_key") == 1


def test_unknown_scene_and_player_entity_are_rejected(tmp_path):
    p, s, player, d, c = make(tmp_path)
    with pytest.raises(ValueError):
        c.new_save(scene_id="00000000-0000-0000-0000-000000000000")
    with pytest.raises(ValueError):
        c.new_save(scene_id=s.id, player_entity_id="00000000-0000-0000-0000-000000000000")


def test_save_json_is_definition_independent(tmp_path):
    p, s, player, d, c = make(tmp_path)
    c.new_save(scene_id=s.id, player_entity_id=player.id, player_position=(8, 9))
    path = tmp_path / "slot.save.json"
    c.save(path)
    raw = path.read_text()
    assert '"asteria.game_runtime_save"' in raw
    assert '"battle_presentation_library"' not in raw
    assert '"scenes"' not in raw
