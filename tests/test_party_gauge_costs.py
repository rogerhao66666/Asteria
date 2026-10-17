"""A skill can spend a party-wide gauge (a limit gauge shared by the whole party)."""

import dataclasses

import pytest
from test_battle_extensions_session import _first_encounter, _session

from asteria.gameplay import AbilityDefinition
from asteria.rpg import BattleExtensionRules

HP = "vitality"


def _game():
    rules = BattleExtensionRules("ext", damage_resource=HP, shared_gauges={"unity": 100})
    game = _session(rules)
    abilities = game.project.gameplay_library.abilities
    base = abilities.get("attack_axe")
    abilities._definitions["unity_strike"] = dataclasses.replace(
        base, ability_id="unity_strike", gauge_costs={"unity": 50}
    )
    db = game.project.rpg_database
    db.battle_targeting["unity_strike"] = dataclasses.replace(
        db.battle_targeting["attack_axe"], ability_id="unity_strike"
    )
    game.start_encounter(_first_encounter(game))
    hero = game.save.rpg_state.party_active_actor_ids[0]
    member = game.battle.member(hero)
    game.battle.set_member_abilities(hero, (*member.ability_ids, "unity_strike"))
    foe = next(m for m, x in game.battle.members.items() if x.side == "enemies")
    return game, hero, foe


def test_the_gauge_costs_round_trip_and_validate():
    base = AbilityDefinition.from_data(
        _session().project.gameplay_library.abilities.get("attack_axe").to_data()
    )
    assert "gauge_costs" not in base.to_data()
    paid = dataclasses.replace(base, gauge_costs={"unity": 40})
    assert AbilityDefinition.from_data(paid.to_data()).gauge_costs == {"unity": 40.0}
    with pytest.raises(ValueError):
        dataclasses.replace(base, gauge_costs={"unity": 0})


def test_a_skill_waits_for_the_party_gauge_and_spends_it():
    game, hero, foe = _game()
    assert "unity" in game.ability_unavailable(hero, "unity_strike")
    game.change_party_gauge("unity", 80)
    assert game.ability_unavailable(hero, "unity_strike") == ""
    game.use_ability(hero, "unity_strike", (foe,))
    assert game.party_gauge("unity") == 30.0  # 50 spent
    assert "unity" in game.ability_unavailable(hero, "unity_strike")  # not enough left
