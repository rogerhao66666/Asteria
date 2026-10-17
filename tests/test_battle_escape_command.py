"""Running away: the escape rule of the project is a command of the battle menu and of the session;
an encounter tagged ``no_escape`` refuses it."""

import dataclasses

import pytest
from test_battle_extensions_session import _first_encounter, _session

from asteria.rpg.battle_lifecycle import BattleEscapeRule
from asteria.runtime.battle_commands import BattleCommands
from asteria.runtime.game_session import GameSessionError


def _game(chance=1.0, tags=()):
    game = _session()
    db = game.project.rpg_database
    db.escape_rules.clear()
    db.escape_rules["run"] = BattleEscapeRule(
        "run", "heroes", base_chance=chance, maximum_chance=1.0
    )
    encounter = _first_encounter(game)
    db.encounters[encounter] = dataclasses.replace(db.encounters[encounter], tags=tags)
    game.start_encounter(encounter)
    return game


def test_escaping_leaves_the_battle_without_rewards():
    game = _game(1.0)
    hero = game.active_hero_ids()[0]
    gold = game.save.rpg_state.currencies.get("gold", 0)
    assert game.escape_chance() == 1.0
    result = game.attempt_escape(hero)
    assert result.succeeded and game.mode == "field" and game.battle is None
    assert game.save.rpg_state.currencies.get("gold", 0) == gold


def test_a_failed_escape_keeps_the_fight_going():
    game = _game(0.0)
    result = game.attempt_escape(game.active_hero_ids()[0])
    assert not result.succeeded and game.mode == "battle"


def test_a_no_escape_encounter_refuses():
    game = _game(1.0, tags=("no_escape",))
    assert "no_escape" in game.escape_unavailable()
    with pytest.raises(GameSessionError, match="cannot escape"):
        game.attempt_escape(game.active_hero_ids()[0])


def test_the_menu_has_an_escape_row_that_runs():
    game = _game(1.0)
    hero = game.active_hero_ids()[0]
    commands = BattleCommands(game, style="root")
    rows = commands.entries(hero)
    row = next(r for r in rows if r.action_id == "root:Escape")
    assert row.enabled
    commands.cursor = rows.index(row)
    assert commands.press("confirm", hero)  # the turn is used
    assert game.mode == "field"
