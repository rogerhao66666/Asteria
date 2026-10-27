"""D91: every number and tag of the game is defined, every record can say what it is."""

from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.gameplay.modifiers import StatModifier
from asteria.project import Project
from asteria.rpg.effect_text import amount, modifier_lines
from asteria.rpg.stat_definitions import StatDefinition
from asteria.rpg.tag_definitions import TagDefinition, built_in, definition_for

DEMO = Path(__file__).parents[1] / "reference_projects/full_verification_demo"


@pytest.fixture(scope="module")
def demo():
    return Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)


def test_a_tag_or_a_family_is_defined_and_the_closest_wins():
    family = TagDefinition("weak.*", "Weakness")
    own = TagDefinition("weak.fire", "Weak to Fire")
    defined = {d.tag_id: d for d in (family, own, TagDefinition("weak.f*"))}
    assert definition_for(defined, "weak.fire") is own
    assert definition_for(defined, "weak.frost").tag_id == "weak.f*"  # the longer family
    assert definition_for(defined, "weak.ice") is family
    assert definition_for(defined, "resist.ice") is None
    assert TagDefinition.from_data(own.to_data()) == own
    with pytest.raises(ValueError):
        TagDefinition("we*ak")


def test_the_engine_says_what_it_does_with_its_own_tags():
    assert "cannot run" in built_in("no_escape")
    assert "scheduler" in built_in("scheduler:swift")
    assert built_in("weak.fire") == ""


def test_a_value_is_written_the_stats_way():
    share = StatDefinition("lifesteal", display="share")
    percent = StatDefinition("crit", display="percent")
    assert amount(0.12, "add", share) == "+12%"
    assert amount(3, "add", percent) == "+3%"
    assert amount(-5, "add") == "-5"
    assert amount(1.6, "multiply") == "x1.6"
    mods = (
        StatModifier("a", "magic", "add", 10.0),
        StatModifier("b", "magic", "add", 8.0),
        StatModifier("c", "defense", "multiply", 1.5),
        StatModifier("d", "crit", "add", 3.0, required_tags=("weapon.sword",)),
    )
    lines = modifier_lines(mods, str.upper, {"crit": percent})
    assert lines == ["MAGIC +18", "DEFENSE x1.5", "CRIT +3% (when weapon.sword)"]


@pytest.mark.parametrize(
    "module, cls, args",
    [
        ("asteria.rpg.ability_build", "PassiveDefinition", ("iron_skin", "Iron Skin")),
        ("asteria.gameplay.states", "StateDefinition", ("burn", 3.0)),
        ("asteria.rpg.actors", "ClassDefinition", ("knight", "Knight")),
        ("asteria.rpg.actors", "ActorDefinition", ("hero", "Hero")),
        ("asteria.rpg.enemies", "EnemyDefinition", ("slime", "Slime")),
        ("asteria.rpg.items", "EquipmentDefinition", ("sword", "Sword")),
        ("asteria.rpg.items", "AttachmentDefinition", ("ruby", "Ruby")),
    ],
)
def test_every_player_facing_record_can_say_what_it_is(module, cls, args):
    import importlib

    kind = getattr(importlib.import_module(module), cls)
    bare = kind(*args)
    assert "description" not in bare.to_data()  # written only when set
    assert kind.OPTIONAL_DATA["description"] == ""  # shown in the editor while empty
    told = kind(*args, description="What it is.")
    assert kind.from_data(told.to_data()).description == "What it is."


def test_the_demo_defines_every_stat_and_tag_it_uses(demo):
    from asteria.editor.problems import used_stats
    from asteria.editor.tag_usage import project_tags

    db = demo.rpg_database
    assert used_stats(demo) <= set(db.stat_definitions)
    assert all(definition_for(db.tag_definitions, t) for t in project_tags(demo))
    assert all(set(a.base_stats) <= {"str", "dex", "int", "luk", "vit", "speed"}
               for a in db.actors.values())  # fmt: skip


def test_the_tag_page_lists_who_carries_and_what_reads(demo):
    from asteria.editor.tag_usage import tag_usage

    text = tag_usage(demo, "capability.weapon.*")
    assert "Classes brave" in text and "Any capabilities" in text
    assert "Engine:" in tag_usage(demo, "no_escape")
    groups = tag_usage(demo, "consumable")  # a menu category reads it, it carries nothing
    assert "Menu pages items (Category)" in groups  # D96: the Items page's tab


def test_an_undefined_tag_is_a_problem_once_tags_are_defined(demo):
    from asteria.editor.problems import Problem, _tags

    found = []
    _tags(demo, found)
    assert found == []
    demo.rpg_database.tag_definitions.pop("weak.*")
    try:
        _tags(demo, found)
        assert any("tag weak.fire is used but not defined" in p.message for p in found)
        assert all(isinstance(p, Problem) for p in found)
    finally:
        demo.rpg_database.add_tag_definition(TagDefinition("weak.*", "Weakness"))


def test_jobs_decide_who_wields_what_and_the_brave_wields_all(demo):
    db = demo.rpg_database
    kinds = {t.split(".", 1)[1] for e in db.equipment.values() for t in e.tags if "equip." in t}
    for piece in db.equipment.values():
        own = [t.split(".", 1)[1] for t in piece.tags if t.startswith("equip.")]
        if piece.slot == "weapon" and own:
            assert piece.any_capabilities == tuple(f"capability.weapon.{k}" for k in own)
    brave = set(db.classes["brave"].granted_tags)
    assert {f"capability.weapon.{k}" for k in kinds} <= brave
    assert {"brave_slash", "dawn_and_dusk", "twilight_judgment"} <= set(
        db.classes["brave"].granted_abilities
    )
    assert "hero" not in db.classes


def test_the_skill_tree_says_what_a_passive_does(demo):
    from asteria.runtime.game_session import GameSessionRuntime
    from asteria.runtime.skill_tree_screen import StatNames, describe_reward

    game = GameSessionRuntime(demo, demo.game_start.instantiate(demo))
    names = StatNames(game)
    assert names.passive("arcane_focus").startswith("Arcane Focus (")
    assert "+18" in names.passive("arcane_focus")

    class Reward:
        stat_bonuses = {"boss_damage": 2.0}
        resource_bonuses = {}
        granted_abilities = ()
        unlocked_passives = ("arcane_focus",)
        granted_tags = ()

    lines = describe_reward(Reward(), {}, names, game.tr, names.passive)
    assert lines[0].endswith("+2%")  # boss damage is a percent stat
    assert "Arcane Focus (" in lines[1]
