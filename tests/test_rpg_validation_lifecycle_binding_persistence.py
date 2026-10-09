import pytest

from asteria.core import ComponentRegistry, Scene
from asteria.events import EventInstruction, EventProgram
from asteria.events.lifecycle_bridge import LifecycleEventBinding
from asteria.project import Project
from asteria.rpg import (
    ActorDefinition,
    EncounterDefinition,
    EncounterMember,
    EnemyDefinition,
    LootEntry,
    RewardDefinition,
    RpgDatabase,
)


def project(db=None):
    p = Project("x", rpg_database=db)
    p.add_scene(Scene("s"))
    return p


def test_rpg_database_rejects_unknown_actor_class():
    db = RpgDatabase()
    db.add_actor(ActorDefinition("hero", class_id="missing"))
    with pytest.raises(ValueError, match="unknown class"):
        db.validate()


def test_rpg_database_rejects_unknown_encounter_enemy():
    db = RpgDatabase()
    db.add_encounter(EncounterDefinition("e", members=[EncounterMember("ghost")]))
    with pytest.raises(ValueError, match="unknown enemy"):
        db.validate()


def test_rpg_database_rejects_unknown_loot_item_and_progression_track():
    db = RpgDatabase()
    db.add_enemy(
        EnemyDefinition(
            "boss",
            reward=RewardDefinition(
                experience={"missing_track": 10},
                loot=[LootEntry("missing_item", chance=1)],
            ),
        )
    )
    with pytest.raises(ValueError) as exc:
        db.validate()
    assert "unknown item" in str(exc.value) and "unknown progression track" in str(
        exc.value
    )


def test_lifecycle_binding_roundtrip_in_project_v5():
    p = project()
    p.event_programs.register("after_anything", EventProgram([EventInstruction("END")]))
    p.lifecycle_event_bindings.append(
        LifecycleEventBinding(
            "custom.any.workflow.finished", "after_anything", source_entity_id="source"
        )
    )
    raw = p.to_data()
    assert raw["version"] == 10
    restored = Project.from_data(raw, ComponentRegistry())
    b = restored.lifecycle_event_bindings[0]
    assert b.hook_name == "custom.any.workflow.finished"
    assert b.event_program_id == "after_anything"
    assert b.source_entity_id == "source"


def test_project_rejects_lifecycle_binding_to_missing_program():
    p = project()
    p.lifecycle_event_bindings.append(LifecycleEventBinding("x.done", "missing"))
    with pytest.raises(ValueError, match="unknown event program"):
        p.validate()


def test_project_v4_backward_read_has_no_lifecycle_bindings():
    p = project()
    raw = p.to_data()
    raw["version"] = 4
    raw.pop("game_start",None); raw.pop("input_map",None); raw.pop("prefabs",None)
    raw.pop("battle_presentation_library", None)
    raw.pop("lifecycle_event_bindings")
    raw.pop("gameplay_library")
    restored = Project.from_data(raw, ComponentRegistry())
    assert restored.lifecycle_event_bindings == []
