from asteria.core import Entity, Scene, Transform
from asteria.editor.model import EditorDocument
from asteria.editor.playmode import create_play_session
from asteria.project import Project


def test_play_session_is_runtime_snapshot_not_editor_alias():
    p = Project("Game")
    s = p.add_scene(Scene("Town"))
    hero = s.add_entity(Entity("Hero"))
    hero.add_component(Transform(1, 2))
    doc = EditorDocument(p)
    doc.select_entity(hero)

    session = create_play_session(doc)
    runtime_hero = session.runtime_scene.entities()[0]
    assert runtime_hero is not hero
    runtime_hero.get(Transform).x = 999
    assert hero.get(Transform).x == 1
    assert session.source_scene_id == s.id


def test_play_defaults_to_startup_scene():
    p = Project("Game")
    a = p.add_scene(Scene("Start"))
    p.add_scene(Scene("Other"))
    doc = EditorDocument(p)
    session = create_play_session(doc)
    assert session.runtime_scene.id == a.id
    session.stop()
    assert not session.active
