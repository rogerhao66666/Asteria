"""Versioned project-owned multiplayer rule configuration."""

import pytest

from asteria.multiplayer.rules import (
    default_rules,
    load_rules,
    save_rules,
    validate_rules,
)


def test_default_boss_rule_gives_each_damaging_player_full_experience():
    rules = validate_rules(default_rules())
    assert rules["rewards"]["boss"]["eligibility"] == "positive_damage"
    assert rules["rewards"]["boss"]["experience"] == {
        "policy": "full_amount_per_eligible_player",
        "amount": 100,
    }
    assert rules["rewards"]["boss"]["drops"]["assignment"] == "random_eligible_player"


def test_project_rules_round_trip_and_preserve_game_specific_extension(tmp_path):
    path = tmp_path / ".asteria" / "multiplayer-rules.json"
    rules = default_rules()
    rules["game_extension"] = {"raid_tier": 7}
    save_rules(path, rules)
    assert load_rules(path) == rules


@pytest.mark.parametrize(
    "mutate, error",
    [
        (lambda value: value["rewards"]["boss"]["experience"].update(amount=True), "amount"),
        (
            lambda value: value["rewards"]["boss"]["experience"].update(policy="split_total"),
            "policy",
        ),
        (
            lambda value: value["rewards"]["boss"]["drops"].update(assignment="first_claimant"),
            "assignment",
        ),
        (
            lambda value: value["world_pickup"].update(policy="nearest_player"),
            "policy",
        ),
    ],
)
def test_invalid_builtin_rule_options_are_rejected(mutate, error):
    value = default_rules()
    mutate(value)
    with pytest.raises(ValueError, match=error):
        validate_rules(value)


def test_rule_files_reject_non_finite_json_values(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text('{"x": NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON"):
        load_rules(path)


def test_boss_adapter_applies_project_xp_and_drop_policies(tmp_path):
    from asteria.multiplayer.boss_demo import build_boss_adapter
    from asteria.multiplayer.persistence import SQLiteMultiplayerStore

    rules = default_rules()
    rules["rewards"]["boss"]["experience"]["amount"] = 250
    rules["rewards"]["boss"]["drops"]["assignment"] = "every_eligible_player"
    store = SQLiteMultiplayerStore(tmp_path / "boss-rules.sqlite3")
    adapter = build_boss_adapter(store=store, rules=rules)
    adapter.player_attack_damage = 120
    adapter.on_player_joined("p1", "One")
    adapter.on_player_joined("p2", "Two")
    adapter.handle_input("p1", {"attack": True})
    adapter.handle_input("p2", {"attack": True})
    update = adapter.network_tick(0.05)

    xp = [event for event in update.events if event["type"] == "experience_awarded"]
    loot = [event for event in update.events if event["type"] == "loot_awarded"]
    assert {event["player_id"] for event in xp} == {"p1", "p2"}
    assert {event["amount"] for event in xp} == {250}
    assert {event["player_id"] for event in loot} == {"p1", "p2"}
    assert store.get_player("p1")["experience"] == 250
    assert store.get_player("p2")["experience"] == 250
    store.close()
