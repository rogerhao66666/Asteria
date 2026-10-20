"""Full Verification stats: STR / DEX / INT / LUK the player spends, written formulas,
accuracy against evasion, physical and magic defence, element attack and resistance, skill
descriptions - and builds that do not compound after a fight."""

import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

import run_trial_smoke as smoke  # noqa: E402
import trial_stats  # noqa: E402

HERO = smoke.HERO


def _game():
    _project, game = smoke.load()
    return game


def test_attribute_points_become_stats_through_the_formulas():
    game = _game()
    db = game.project.rpg_database
    nodes = {n.node_id for n in db.progression_graphs["attributes"].nodes}
    assert {"attr_str", "attr_dex", "attr_int", "attr_luk"} <= nodes
    assert set(db.derived_stats) >= {"power", "magic_defense", "accuracy", "evade", "crit"}
    before = game.resolve_actor_build(HERO).stats
    allocation = game.save.rpg_state.progression_allocations[HERO]
    allocation.grant("stat_points", 1)
    allocation.allocate("attributes", "attr_luk")
    after = game.resolve_actor_build(HERO).stats
    assert after.get("luk") == before.get("luk") + 1
    assert after.get("evade") == before.get("evade") + 1.0  # evade += 1 x LUK
    assert after.get("crit") == before.get("crit") + 0.5


def test_magic_meets_magic_defence_and_elements_have_attack_and_resistance():
    game = _game()
    library = game.project.gameplay_library.abilities
    terms = library.get("fire_bolt").effects[0].effect.operations[0].value.terms
    assert {(t.source.value, t.key) for t in terms} >= {
        ("source_stat", "magic"),
        ("target_stat", "magic_defense"),
    }
    db = game.project.rpg_database
    fire = db.interaction_rules["element_fire"]
    assert fire.multiplier_source_terms == {"fire_attack": 0.01}
    assert fire.multiplier_target_terms == {"fire_resist": -0.01}
    ring = {m.stat for m in db.equipment["a_ruby_ring"].modifiers}
    assert "fire_attack" in ring
    assert db.enemies["crimson_warlord"].stats["fire_resist"] == 40
    land = db.outcome_checks["land"]
    assert land.source_stat_terms == {"accuracy": 0.003}
    assert land.target_stat_terms == {"evade": -0.003}


def test_every_skill_says_physical_or_magic_and_its_element():
    library = _game().project.gameplay_library.abilities
    assert library.get("fire_bolt").description.startswith("Magic / Fire")
    assert library.get("valiant_slash").description.startswith("Physical + Magic / Light")
    assert library.get("attack_sword").description == "Physical / Non-elemental"
    assert "drains MP" in library.get("dark_bolt").description
    assert library.get("mend").description == "Healing"
    assert trial_stats.EXTRAS["ice_bolt"] == (("freeze", "targets"),)


def test_a_fight_does_not_compound_the_heroes_stats():
    game = _game()
    first = game.resolve_actor_build(HERO).stats.get("power")
    for _ in range(3):
        game.start_encounter("woods_ambush")
        game._write_battle_heroes_to_save()
        game.mode, game.battle = "field", None
    assert game.resolve_actor_build(HERO).stats.get("power") == first
