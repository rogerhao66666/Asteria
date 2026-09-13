import pytest

from asteria.core import Scene
from asteria.editor import EditorDocument
from asteria.editor.rpg_actor_class_authoring import (
    RpgActorClassAuthoringController,
    RpgActorClassAuthoringError,
)
from asteria.gameplay import AbilityDefinition
from asteria.project import Project
from asteria.rpg import ClassAssignment


def make():
    p=Project("Game")
    p.add_scene(Scene("Main"))
    for ability_id in ("slash","guard","fire","heal"):
        p.gameplay_library.add_ability(AbilityDefinition(ability_id))
    doc=EditorDocument(p)
    return p,doc,RpgActorClassAuthoringController(doc)


def test_class_complete_fields_and_edit():
    p,doc,c=make()
    cls=c.create_class(
        "warrior","Warrior",
        stat_bonuses={"power":4},
        resource_bonuses={"mp":2},
        granted_tags=("melee","heavy"),
        granted_abilities=("slash","guard"),
    )
    assert cls.stat_bonuses["power"]==4
    edited=c.edit_class(
        "warrior",
        display_name="Vanguard",
        stat_bonuses={"power":7,"defense":3},
        resource_bonuses={"mp":5},
        granted_tags=("frontline",),
        granted_abilities=("slash",),
    )
    assert edited.display_name=="Vanguard"
    assert edited.resource_bonuses=={"mp":5.0}
    assert doc.undo()
    assert p.rpg_database.classes["warrior"].display_name=="Warrior"


def test_actor_complete_fields_and_multiclass_assignments():
    p,doc,c=make()
    c.create_class("warrior",granted_abilities=("slash",))
    c.create_class("mage",granted_abilities=("fire",))
    actor=c.create_actor(
        "hero","Hero",
        class_assignments=(
            ClassAssignment("warrior",assignment_id="main",role="primary",priority=0,tags=("lead",)),
            ClassAssignment("mage",assignment_id="sub",role="secondary",priority=10,enabled=False),
        ),
        base_stats={"hp":100,"power":12},
        base_resources={"mp":{"minimum":0,"maximum":30,"current":20}},
        tags=("human","player"),
        abilities=("heal",),
    )
    assert len(actor.class_assignments)==2
    assert actor.base_resources["mp"]["current"]==20
    assert actor.abilities==("heal",)


def test_assignment_all_fields_are_editable():
    p,doc,c=make()
    c.create_class("a"); c.create_class("b")
    c.create_actor("hero",class_assignments=(ClassAssignment("a",assignment_id="slot"),))
    c.edit_assignment(
        "hero","slot",class_id="b",role="support",enabled=False,priority=20,tags=("magic",)
    )
    a=p.rpg_database.actors["hero"].class_assignments[0]
    assert (a.class_id,a.role,a.enabled,a.priority,a.tags)==("b","support",False,20,("magic",))


def test_assignment_progression_track_reference_is_validated():
    p,doc,c=make()
    c.create_class("a")
    c.create_actor("hero")
    with pytest.raises(RpgActorClassAuthoringError):
        c.add_assignment("hero","a",progression_track_ids=("missing",))


def test_unknown_ability_is_rejected_for_actor_and_class():
    p,doc,c=make()
    with pytest.raises(RpgActorClassAuthoringError):
        c.create_class("bad",granted_abilities=("missing",))
    with pytest.raises(RpgActorClassAuthoringError):
        c.create_actor("bad",abilities=("missing",))


def test_class_delete_refuses_dangling_actor_reference():
    p,doc,c=make()
    c.create_class("a")
    c.create_actor("hero",class_assignments=(ClassAssignment("a"),))
    with pytest.raises(RpgActorClassAuthoringError):
        c.delete_class("a")
    c.remove_assignment("hero","a")
    c.delete_class("a")
    assert "a" not in p.rpg_database.classes


def test_duplicate_actor_and_class_use_fresh_ids():
    p,doc,c=make()
    c.create_class("a","A",granted_abilities=("slash",))
    c.create_actor("hero","Hero",class_assignments=(ClassAssignment("a"),),abilities=("heal",))
    cc=c.duplicate_class("a","b")
    aa=c.duplicate_actor("hero","hero2")
    assert cc.class_id=="b"
    assert aa.actor_id=="hero2"
    assert aa.abilities==("heal",)


def test_atomic_definition_edit_marks_dirty_and_roundtrips_undo_redo():
    p,doc,c=make()
    c.create_class("a")
    before=doc.commands.current_state_id
    c.edit_class("a",stat_bonuses={"power":10})
    assert doc.commands.current_state_id!=before
    assert p.rpg_database.classes["a"].stat_bonuses["power"]==10
    assert doc.undo()
    assert p.rpg_database.classes["a"].stat_bonuses=={}
    assert doc.redo()
    assert p.rpg_database.classes["a"].stat_bonuses["power"]==10


def test_actor_edit_replaces_all_authorable_fields():
    p,doc,c=make()
    c.create_class("a")
    c.create_actor("hero")
    edited=c.edit_actor(
        "hero",
        display_name="Renamed",
        class_assignments=(ClassAssignment("a",role="custom"),),
        base_stats={"speed":9},
        base_resources={"focus":5},
        tags=("rare",),
        abilities=("fire",),
    )
    assert edited.display_name=="Renamed"
    assert edited.class_assignments[0].role=="custom"
    assert edited.base_stats=={"speed":9.0}
    assert edited.base_resources["focus"]["maximum"]==5
    assert edited.tags==("rare",)
    assert edited.abilities==("fire",)


def test_database_and_project_validate_after_supported_authoring():
    p,doc,c=make()
    c.create_class("warrior",granted_abilities=("slash",))
    c.create_actor(
        "hero",
        class_assignments=(ClassAssignment("warrior"),),
        abilities=("heal",),
    )
    assert c.validate()==()
    assert p.validate()


def test_coverage_manifest_has_no_false_capabilities():
    _,_,c=make()
    assert all(getattr(c.coverage,n) for n in c.coverage.__dataclass_fields__)
