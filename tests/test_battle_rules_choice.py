"""Battle rules an encounter picks (escape:, rules:, objective: tags), objectives that decide a
fight, and a combo skill that runs an action sequence."""

import sys
from collections import Counter
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

import run_trial_smoke as smoke  # noqa: E402


def _game(encounter):
    _project, game = smoke.load()
    smoke.prepare(game, Counter(), tier=1)
    game.start_encounter(encounter)
    return game


def test_an_encounter_names_its_escape_rule_rules_and_objectives():
    game = _game("woods_patrol")
    assert game._escape_rule().rule_id == "woods_escape" and game.rules.rules_id == "trial"
    assert "vigil_survive" not in game.battle.objectives.definitions  # it belongs to the vigil
    game = _game("acolyte_vigil")
    assert game.rules.rules_id == "vigil_gauntlet" and game.escape_unavailable()
    assert "vigil_survive" in game.battle.objectives.definitions


def test_an_objective_decides_the_fight_and_knocks_the_losers_out():
    game = _game("acolyte_vigil")
    for _ in range(400):  # turns pass (nobody acts) until the eighth round
        if not game.active_enemy_ids():
            break
        game.end_turn()
        if game.current_turn_actor() is None:
            game.battle.start_next_round()
    assert not game.active_enemy_ids() and game.active_hero_ids()  # the vigil was held
    game = _game("woods_boss")  # the beast falls: its slingers give up too
    beast = next(m for m in game.active_enemy_ids() if m.startswith("goblin_beast"))
    game.battle.member(beast).subject.resources.set_current("vitality", 0.0)
    game.end_turn()
    assert not game.active_enemy_ids()


def test_a_combo_skill_runs_its_sequence_with_the_party():
    game = _game("boss_room")
    game.battle.battle_resources.change("hero_01", "momentum", 5)
    boss = game.active_enemy_ids()[0]
    game.battle_log.clear()
    game.use_ability("hero_01", "party_rush", (boss,))
    blows = [e.member_id for e in game.battle_log if e.ability_id == "rush_blow"]
    assert blows[0] == "hero_01" and len(set(blows)) >= 2  # Aldric leads, others follow
    assert game.battle.battle_resources.current("hero_01", "momentum") == 3
