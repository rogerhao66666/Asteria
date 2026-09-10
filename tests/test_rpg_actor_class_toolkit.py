from asteria.rpg import (
    ActorDefinition,
    ClassDefinition,
    RpgDatabase,
    simple_rpg_database,
)


def test_actor_class_roundtrip():
    cls = ClassDefinition(
        "mage", "Mage", stat_bonuses={"magic": 5}, granted_abilities=["spark"]
    )
    actor = ActorDefinition(
        "lina",
        "Lina",
        class_id="mage",
        base_stats={"magic": 10},
        base_resources={"focus": 40},
        tags=["actor.party"],
    )
    assert ClassDefinition.from_data(cls.to_data()) == cls
    assert ActorDefinition.from_data(actor.to_data()) == actor


def test_class_composes_on_frozen_generic_primitives():
    db = RpgDatabase()
    db.add_class(
        ClassDefinition(
            "fighter",
            stat_bonuses={"power": 3},
            resource_bonuses={"guard": 5},
            granted_tags=["role.frontline"],
            granted_abilities=["strike"],
        )
    )
    db.add_actor(
        ActorDefinition(
            "a",
            class_id="fighter",
            base_stats={"power": 7},
            base_resources={"guard": 10},
            abilities=["focus"],
        )
    )
    actor = db.build_actor("a")
    assert actor.stats.get("power") == 10
    assert actor.resources.maximum("guard") == 15
    assert actor.tags.contains("role.frontline")
    assert actor.abilities == ("focus", "strike")


def test_rpg_database_deterministic_roundtrip():
    db = simple_rpg_database()
    assert RpgDatabase.from_data(db.to_data()).to_data() == db.to_data()


def test_simple_rpg_preset_is_immediately_playable_data():
    actor = simple_rpg_database().build_actor("hero")
    assert actor.resources.current("hp") == 100
    assert actor.resources.current("mp") == 30
    assert actor.stats.get("attack") == 12
    assert "basic_attack" in actor.abilities
    assert actor.tags.contains("actor.player")


def test_rpg_names_are_toolkit_content_not_gameplay_core_requirements():
    db = RpgDatabase()
    db.add_class(ClassDefinition("thermodynamic", stat_bonuses={"temperature": 3}))
    db.add_actor(
        ActorDefinition(
            "reactor",
            class_id="thermodynamic",
            base_stats={"temperature": 400},
            base_resources={"pressure": 20},
        )
    )
    actor = db.build_actor("reactor")
    assert actor.stats.get("temperature") == 403
    assert actor.resources.current("pressure") == 20
