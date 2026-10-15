"""Enemy levels and the difficulty slider."""

import random

import pytest

from asteria.gameplay import GameplaySubject, ResourcePool, StatBlock, TagSet
from asteria.rpg.enemy_levels import DifficultyLevel, EnemyLevelRules


def _enemy():
    resources = ResourcePool()
    resources.define("hp", 100, current=60)
    return GameplaySubject(StatBlock({"atk": 10, "def": 4}), resources, TagSet())


def _rules(**extra):
    return EnemyLevelRules(
        "lv",
        stat_growth={"atk": 0.1},
        resource_growth={"hp": 0.5},
        reward_growth=0.2,
        **extra,
    )


def test_level_one_is_the_base_enemy():
    enemy = _rules().apply(_enemy(), 1)
    assert enemy.stats.get("atk") == 10
    assert enemy.resources.maximum("hp") == 100
    assert enemy.resources.current("hp") == 100  # a fresh enemy starts full


def test_growth_is_linear_per_level_and_untouched_stats_stay():
    enemy = _rules().apply(_enemy(), 5)
    assert enemy.stats.get("atk") == pytest.approx(14)  # 10 * (1 + 0.1 * 4)
    assert enemy.stats.get("def") == 4
    assert enemy.resources.maximum("hp") == pytest.approx(300)  # 100 * (1 + 0.5 * 4)
    assert _rules().reward_multiplier(5) == pytest.approx(1.8)


def test_missing_stat_or_resource_is_skipped():
    rules = EnemyLevelRules("lv", stat_growth={"nope": 1.0}, resource_growth={"mp": 1.0})
    enemy = rules.apply(_enemy(), 9)
    assert enemy.stats.get("atk") == 10 and enemy.resources.maximum("hp") == 100


def test_difficulty_scales_strength_rewards_and_level():
    rules = _rules(
        difficulties=(
            DifficultyLevel("easy", strength=0.5, reward=0.5, level_offset=-1),
            DifficultyLevel("hard", strength=2.0, reward=1.5, level_offset=2),
        ),
        default_difficulty="hard",
    )
    assert rules.difficulty().difficulty_id == "hard"
    assert rules.apply(_enemy(), 1).stats.get("atk") == 20
    assert rules.apply(_enemy(), 1, "easy").stats.get("atk") == 5
    assert rules.reward_multiplier(1, "hard") == 1.5
    assert rules.level_for(party_level=10) == 12
    assert rules.level_for(party_level=10, difficulty_id="easy") == 9
    assert rules.difficulty("missing").difficulty_id == "normal"


def test_level_comes_from_the_map_or_the_party():
    rules = _rules(map_levels={"cave": (3, 5)}, party_level_offset=-1, max_level=8)
    seen = {rules.level_for("cave", random.Random(i)) for i in range(50)}
    assert seen == {3, 4, 5}
    assert rules.level_for("elsewhere", party_level=6) == 5
    assert rules.level_for("elsewhere", party_level=30) == 8  # capped
    assert rules.level_for("elsewhere", party_level=0) == 1  # floored


def test_round_trip_and_validation():
    rules = _rules(
        map_levels={"cave": (2, 4)},
        difficulties=(DifficultyLevel("easy", 0.5, 0.5, -1),),
        default_difficulty="easy",
        party_level_offset=2,
    )
    assert EnemyLevelRules.from_data(rules.to_data()) == rules
    with pytest.raises(ValueError):
        EnemyLevelRules("x", stat_growth={"atk": -1})
    with pytest.raises(ValueError):
        EnemyLevelRules("x", map_levels={"cave": (5, 2)})
    with pytest.raises(ValueError):
        EnemyLevelRules("x", default_difficulty="nope")
    with pytest.raises(ValueError):
        DifficultyLevel("bad", strength=0)
