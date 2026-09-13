import pytest

from asteria.core import Entity, Scene, Transform
from asteria.editor import EditorDocument, SceneEntityAuthoringController
from asteria.project import Project
from asteria.runtime import Camera2DComponent


def make():
    p=Project("Game")
    a=Scene("A"); b=Scene("B")
    p.add_scene(a); p.add_scene(b)
    doc=EditorDocument(p)
    return p,a,b,doc,SceneEntityAuthoringController(doc)


def test_scene_full_lifecycle_and_startup():
    p,a,b,doc,c=make()
    c.set_startup_scene(b)
    assert p.startup_scene_id==b.id
    extra=c.add_scene("C")
    assert [s.name for s in p.scenes()]==["A","B","C"]
    c.rename(extra,"Boss")
    assert extra.name=="Boss"
    c.reorder_scene(extra,0)
    assert p.scenes()[0] is extra
    c.remove_scene(b)
    assert b not in p.scenes()
    assert doc.commands.can_undo


def test_scene_operations_round_trip_through_undo_redo():
    p,a,b,doc,c=make()
    c.set_startup_scene(b)
    c.reorder_scene(b,0)
    assert p.scenes()[0] is b
    assert doc.undo()
    assert p.scenes()[1] is b
    assert doc.undo()
    assert p.startup_scene_id==a.id
    assert doc.redo()
    assert p.startup_scene_id==b.id


def test_entity_create_rename_enable_reorder_move_delete():
    p,a,b,doc,c=make()
    e1=c.add_entity(a,"One")
    e2=c.add_entity(a,"Two")
    c.rename(e1,"Hero")
    c.set_entity_enabled(e1,False)
    assert not e1.enabled
    c.reorder_entity(e2,0)
    assert a.entities()[0] is e2
    c.move_entity_to_scene(e1,b)
    assert e1.scene is b
    c.remove_entity(e1)
    assert e1.scene is None


def test_duplicate_entity_preserves_components_but_freshens_identity():
    p,a,b,doc,c=make()
    e=c.add_entity(a,"Hero")
    t=c.add_component(e,Transform)
    t.x=12.0; t.y=-4.0
    copy=c.duplicate_entity(e)
    assert copy.id != e.id
    assert copy.name=="Hero Copy"
    assert copy.get(Transform).x==12.0
    assert copy.get(Transform).y==-4.0


def test_component_add_remove_is_undoable():
    p,a,b,doc,c=make()
    e=c.add_entity(a,"Camera")
    comp=c.add_component(e,Camera2DComponent)
    assert e.has(Camera2DComponent)
    c.remove_component(comp)
    assert not e.has(Camera2DComponent)
    assert doc.undo()
    assert e.has(Camera2DComponent)
    assert e.get(Camera2DComponent) is comp


def test_multi_entity_delete_is_single_undoable_transaction():
    p,a,b,doc,c=make()
    es=[c.add_entity(a,f"E{i}") for i in range(4)]
    c.delete_entities(es[1:4])
    assert a.entities()==(es[0],)
    assert doc.commands.undo_label=="Delete 3 Entities"
    assert doc.undo()
    assert set(a.entities())==set(es)


def test_multi_duplicate_is_single_undoable_transaction():
    p,a,b,doc,c=make()
    es=[c.add_entity(a,f"E{i}") for i in range(3)]
    copies=c.duplicate_entities(es)
    assert len(copies)==3
    assert len(a.entities())==6
    assert len({x.id for x in a.entities()})==6
    assert doc.undo()
    assert a.entities()==tuple(es)


def test_move_between_scenes_restores_original_order_on_undo():
    p,a,b,doc,c=make()
    e1=c.add_entity(a,"One")
    e2=c.add_entity(a,"Two")
    e3=c.add_entity(a,"Three")
    c.move_entity_to_scene(e2,b)
    assert a.entities()==(e1,e3)
    assert b.entities()==(e2,)
    assert doc.undo()
    assert a.entities()==(e1,e2,e3)


def test_same_scene_move_uses_reorder_path():
    p,a,b,doc,c=make()
    es=[c.add_entity(a,f"E{i}") for i in range(3)]
    c.move_entity_to_scene(es[0],a,2)
    assert a.entities()==(es[1],es[2],es[0])


def test_controller_declares_complete_structure_coverage():
    _,_,_,_,c=make()
    assert all(getattr(c.coverage,name) for name in c.coverage.__dataclass_fields__)


def test_last_scene_cannot_be_removed():
    p=Project("Only")
    scene=Scene("Only")
    p.add_scene(scene)
    doc=EditorDocument(p)
    c=SceneEntityAuthoringController(doc)
    with pytest.raises(Exception):
        c.remove_scene(scene)
