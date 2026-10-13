import random

from asteria.rpg import (
    EncounterDefinition,
    EncounterMember,
    EnemyDefinition,
    LootEntry,
    RewardDefinition,
    RpgDatabase,
    roll_reward,
    simple_rpg_database,
)


def test_enemy_runtime_uses_generic_gameplay_primitives():
    enemy = EnemyDefinition(
        "x",
        stats={"power": 7},
        resources={"guard": 20},
        tags=["enemy.test"],
        abilities=["hit"],
    )
    runtime = enemy.instantiate()
    assert runtime.stats.get("power") == 7
    assert runtime.resources.current("guard") == 20
    assert runtime.tags.contains("enemy.test")
    assert runtime.abilities == ("hit",)


def test_enemy_and_encounter_roundtrip():
    enemy = EnemyDefinition(
        "slime", resources={"life": 10}, reward=RewardDefinition(currencies={"coin": 3})
    )
    encounter = EncounterDefinition("pair", members=[EncounterMember("slime", count=2)])
    assert EnemyDefinition.from_data(enemy.to_data()) == enemy
    assert EncounterDefinition.from_data(encounter.to_data()) == encounter


def test_reward_roll_is_seedable_and_data_driven():
    reward = RewardDefinition(
        currencies={"gold": 10},
        experience={"job": 5},
        loot=[
            LootEntry("potion", chance=1, minimum=2, maximum=2),
            LootEntry("rare", chance=0),
        ],
    )
    rolled = roll_reward(reward, random.Random(123))
    assert rolled.currencies == {"gold": 10}
    assert rolled.experience == {"job": 5}
    assert rolled.items == {"potion": 2}


def test_reward_keys_are_not_hardcoded_to_gold_or_exp():
    reward = RewardDefinition(currencies={"moon_shard": 4}, experience={"alchemy_mastery": 9})
    rolled = roll_reward(reward, random.Random(1))
    assert rolled.currencies["moon_shard"] == 4
    assert rolled.experience["alchemy_mastery"] == 9


def test_database_v3_roundtrip_and_v2_backward_read():
    db = simple_rpg_database()
    assert RpgDatabase.from_data(db.to_data()).to_data() == db.to_data()
    raw = db.to_data()
    raw["version"] = 2
    raw.pop("enemies")
    raw.pop("encounters")
    old = RpgDatabase.from_data(raw)
    assert old.enemies == {} and old.encounters == {}


def test_simple_rpg_has_ready_enemy_encounter():
    db = simple_rpg_database()
    slime = db.enemies["slime"].instantiate()
    assert slime.resources.current("hp") == 30
    assert db.encounters["field_slimes"].members[0].count == 2
