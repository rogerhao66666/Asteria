from asteria.core import ComponentRegistry, Scene
from asteria.gameplay import AbilityDefinition, GameplayLibrary, GameplayPresetCatalog
from asteria.project import Project
from asteria.rpg import (
    ActorDefinition,
    ClassDefinition,
    ItemDefinition,
    RpgDatabase,
    simple_rpg_database,
)


def make_library_for(db):
    lib = GameplayLibrary()
    catalog = GameplayPresetCatalog.defaults()
    refs = set()
    if isinstance(db, RpgDatabase):
        for actor in db.actors.values():
            refs.update(actor.abilities)
        for cls in db.classes.values():
            refs.update(cls.granted_abilities)
        for equipment in db.equipment.values():
            refs.update(equipment.granted_abilities)
        for attachment in db.attachments.values():
            refs.update(attachment.granted_abilities)
        for enemy in db.enemies.values():
            refs.update(enemy.abilities)
        for track in db.progression_tracks.values():
            for milestone in track.milestones:
                refs.update(milestone.granted_abilities)
    for ability_id in sorted(refs):
        definition = catalog.abilities.get(ability_id, AbilityDefinition(ability_id))
        lib.add_ability(definition)
    return lib


def make_project(db=None):
    p = Project("RPG Project", rpg_database=db, gameplay_library=make_library_for(db))
    p.add_scene(Scene("Start"))
    return p


def test_project_v4_owns_canonical_rpg_database():
    db = simple_rpg_database()
    project = make_project(db)
    data = project.to_data()
    assert data["version"] == 10
    assert data["rpg_database"]["schema"] == "asteria.rpg.database"
    loaded = Project.from_data(data, ComponentRegistry())
    assert loaded.rpg_database.actors.keys() == db.actors.keys()
    assert loaded.rpg_database.items.keys() == db.items.keys()
    assert loaded.rpg_database.equipment.keys() == db.equipment.keys()
    assert loaded.rpg_database.attachments.keys() == db.attachments.keys()


def test_project_rpg_database_roundtrip_preserves_arbitrary_project_defined_keys():
    db = RpgDatabase()
    db.add_class(ClassDefinition("thermodynamicist", stat_bonuses={"pressure": 7}))
    db.add_actor(
        ActorDefinition(
            "probe",
            class_id="thermodynamicist",
            base_stats={"temperature": 300},
            base_resources={"charge": 12},
            tags=["custom.sensor"],
            abilities=["measure"],
        )
    )
    db.add_item(ItemDefinition("calibration_token"))
    loaded = Project.from_data(make_project(db).to_data(), ComponentRegistry())
    actor = loaded.rpg_database.build_actor("probe")
    assert actor.stats.get("temperature") == 300
    assert actor.stats.get("pressure") == 7
    assert actor.resources.current("charge") == 12
    assert actor.tags.contains("custom.sensor")
    assert actor.abilities == ("measure",)


def test_project_v3_backward_read_gets_empty_rpg_database():
    p = make_project()
    data = p.to_data()
    data["version"] = 3
    data.pop("game_start",None); data.pop("input_map",None); data.pop("prefabs",None)
    data.pop("battle_presentation_library", None)
    data.pop("rpg_database")
    data.pop("lifecycle_event_bindings")
    data.pop("gameplay_library")
    loaded = Project.from_data(data, ComponentRegistry())
    assert loaded.rpg_database.to_data()["actors"] == []
    assert loaded.rpg_database.to_data()["items"] == []


def test_project_v2_backward_read_gets_empty_rpg_database():
    p = make_project()
    data = p.to_data()
    data["version"] = 2
    data.pop("game_start",None); data.pop("input_map",None); data.pop("prefabs",None)
    data.pop("battle_presentation_library", None)
    data.pop("rpg_database")
    data.pop("lifecycle_event_bindings")
    data.pop("event_programs")
    data.pop("scene_event_bindings")
    data.pop("gameplay_library")
    loaded = Project.from_data(data, ComponentRegistry())
    assert loaded.rpg_database.to_data()["actors"] == []


def test_project_rejects_non_rpg_database():
    try:
        make_project(object())
    except TypeError as exc:
        assert "RpgDatabase" in str(exc)
    else:
        raise AssertionError("expected TypeError")
