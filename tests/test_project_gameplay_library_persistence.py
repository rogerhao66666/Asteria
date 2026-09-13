import pytest

from asteria.core import ComponentRegistry, Scene
from asteria.gameplay import AbilityDefinition, GameplayLibrary, GameplayPresetCatalog
from asteria.project import Project
from asteria.rpg import ActorDefinition, RpgDatabase


def library_with_defaults():
    catalog = GameplayPresetCatalog.defaults()
    lib = GameplayLibrary()
    for key, value in catalog.formulas.items():
        lib.add_formula(key, value)
    for value in catalog.abilities.values():
        lib.add_ability(value)
    for value in catalog.timelines.values():
        lib.add_timeline(value)
    return lib


def make_project(db=None, lib=None):
    p = Project("Game", rpg_database=db, gameplay_library=lib)
    p.add_scene(Scene("Start"))
    return p


def test_project_v6_persists_canonical_gameplay_library():
    lib = library_with_defaults()
    project = make_project(lib=lib)
    raw = project.to_data()
    assert raw["version"] == 8
    assert raw["gameplay_library"]["schema"] == "asteria.gameplay_library"
    restored = Project.from_data(raw, ComponentRegistry())
    assert restored.gameplay_library.to_data() == lib.to_data()


def test_project_v6_validates_rpg_ability_references():
    db = RpgDatabase()
    db.add_actor(ActorDefinition("probe", abilities=["measure"]))
    with pytest.raises(ValueError, match="unknown ability measure"):
        make_project(db=db).to_data()

    lib = GameplayLibrary()
    lib.add_ability(AbilityDefinition("measure"))
    raw = make_project(db=db, lib=lib).to_data()
    assert raw["version"] == 8


def test_pre_v6_project_remains_readable_without_inventing_ability_definitions():
    db = RpgDatabase()
    db.add_actor(ActorDefinition("legacy", abilities=["old_skill"]))
    lib = GameplayLibrary()
    lib.add_ability(AbilityDefinition("old_skill"))
    raw = make_project(db=db, lib=lib).to_data()
    raw["version"] = 5
    raw.pop("game_start",None)
    raw.pop("battle_presentation_library", None)
    raw.pop("gameplay_library")
    restored = Project.from_data(raw, ComponentRegistry())
    assert restored.rpg_database.actors["legacy"].abilities == ("old_skill",)
    assert restored.gameplay_library.abilities.ids() == ()
    # Migration is explicit: canonical v6 save cannot silently keep a dangling ref.
    with pytest.raises(ValueError, match="unknown ability old_skill"):
        restored.to_data()


def test_project_rejects_non_gameplay_library():
    with pytest.raises(TypeError, match="GameplayLibrary"):
        make_project(lib=object())
