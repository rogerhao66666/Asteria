"""What a skill costs, and what it takes from its target, is up to the project: any resource
(also the user's own health), a share of a maximum or of what is left, paid once per cast."""

import dataclasses

import pytest
from test_octopath_style_battle import DAMAGE, _battle, _project

from asteria.gameplay import Effect, EffectOperation, EffectOperationKind
from asteria.gameplay.abilities import AbilityCost, AbilityEffect
from asteria.gameplay.formulas import FormulaTerm, ValueFormula

SP = "technique"


def _ability(project, ability_id, *, costs=(), effect=None, hits=()):
    abilities = project.gameplay_library.abilities
    base = abilities.get("strike")
    effects = (
        base.effects if effect is None else (AbilityEffect("selected", Effect("e", (effect,))),)
    )
    abilities._definitions[ability_id] = dataclasses.replace(
        base, ability_id=ability_id, costs=tuple(costs), effects=effects, hits=hits
    )
    db = project.rpg_database
    db.battle_targeting[ability_id] = dataclasses.replace(
        db.battle_targeting["strike"], ability_id=ability_id
    )
    return ability_id


def _grant(game, hero, ability_id):
    member = game.battle.member(hero)
    game.battle.set_member_abilities(hero, (*member.ability_ids, ability_id))


def _pool(game, member):
    return game.battle.member(member).subject.resources


def test_a_multi_hit_skill_pays_its_cost_once():
    project = _project()
    _ability(
        project,
        "combo",
        costs=[AbilityCost(SP, ValueFormula((FormulaTerm("constant", "", 10.0),)))],
        hits=[{"tags": [], "power": 1.0}] * 4,
    )
    game, hero, boss = _battle(project)
    _grant(game, hero, "combo")
    before = _pool(game, hero).current(SP)
    game.use_ability(hero, "combo", (boss,))
    assert before - _pool(game, hero).current(SP) == pytest.approx(10.0)  # not 4 x 10


def test_a_skill_can_cost_a_share_of_the_users_own_health():
    project = _project()
    share = ValueFormula((FormulaTerm("source_resource_max", DAMAGE, 0.25),))
    _ability(project, "blood_price", costs=[AbilityCost(DAMAGE, share)])
    game, hero, boss = _battle(project)
    _grant(game, hero, "blood_price")
    pool = _pool(game, hero)
    before, maximum = pool.current(DAMAGE), pool.maximum(DAMAGE)
    game.use_ability(hero, "blood_price", (boss,))
    assert before - pool.current(DAMAGE) == pytest.approx(0.25 * maximum)


def test_a_skill_can_take_a_share_of_the_targets_remaining_health():
    project = _project()
    take = ValueFormula((FormulaTerm("target_resource_current", DAMAGE, -0.3),))
    _ability(
        project,
        "gravity",
        effect=EffectOperation(EffectOperationKind.RESOURCE_DELTA, DAMAGE, take),
    )
    game, hero, boss = _battle(project)
    _grant(game, hero, "gravity")
    pool = _pool(game, boss)
    pool.set_current(DAMAGE, 5000)
    game.use_ability(hero, "gravity", (boss,))
    assert 5000 - pool.current(DAMAGE) == pytest.approx(1500.0, rel=0.05)


def _with_costs(project, ability_id, **extra):
    abilities = project.gameplay_library.abilities
    abilities._definitions[ability_id] = dataclasses.replace(abilities.get(ability_id), **extra)


def test_a_skill_can_spend_items_and_currency():
    project = _project()
    _ability(project, "bomb_toss", hits=[{"tags": [], "power": 1.0}] * 3)
    _with_costs(
        project,
        "bomb_toss",
        item_costs={"fire_dust": 2},
        currency_costs={"gold": 100},
    )
    game, hero, boss = _battle(project)
    _grant(game, hero, "bomb_toss")
    bag = game.save.rpg_state.inventory
    funds = game.save.rpg_state.currencies
    bag.add("fire_dust", 5)
    funds["gold"] = 250
    dust, gold = bag.count("fire_dust"), funds["gold"]
    game.use_ability(hero, "bomb_toss", (boss,))
    assert bag.count("fire_dust") == dust - 2  # once per cast, not once per hit
    assert funds["gold"] == gold - 100


def test_a_skill_is_unusable_without_what_it_spends():
    project = _project()
    _ability(project, "bomb_toss")
    _with_costs(project, "bomb_toss", item_costs={"fire_dust": 99}, currency_costs={"gold": 5})
    game, hero, boss = _battle(project)
    _grant(game, hero, "bomb_toss")
    reason = game.ability_unavailable(hero, "bomb_toss")
    assert "Fire Dust" in reason
    from asteria.runtime.game_session import GameSessionError

    with pytest.raises(GameSessionError):
        game.use_ability(hero, "bomb_toss", (boss,))
    game.save.rpg_state.inventory.add("fire_dust", 99)
    game.save.rpg_state.currencies["gold"] = 0.0
    assert "gold" in game.ability_unavailable(hero, "bomb_toss")


def test_cost_fields_round_trip_and_default_to_nothing():
    from asteria.gameplay import AbilityDefinition

    project = _project()
    base = project.gameplay_library.abilities.get("strike")
    assert "item_costs" not in base.to_data() and "currency_costs" not in base.to_data()
    paid = dataclasses.replace(base, item_costs={"a": 2}, currency_costs={"gold": 5})
    again = AbilityDefinition.from_data(paid.to_data())
    assert again.item_costs == {"a": 2} and again.currency_costs == {"gold": 5}
    with pytest.raises(ValueError):
        dataclasses.replace(base, item_costs={"a": 0})


def test_a_skill_can_take_its_damage_type_from_what_the_user_wields():
    """One skill, many weapons: ``follow_tags`` maps a carried tag to the damage tag it deals."""
    project = _project()
    strike_effect = EffectOperation(
        EffectOperationKind.RESOURCE_DELTA,
        DAMAGE,
        ValueFormula((FormulaTerm("constant", "", -1000.0),)),
    )
    _ability(project, "plain", effect=strike_effect)
    _ability(project, "adapt", effect=strike_effect)
    _with_costs(project, "adapt", follow_tags={"equip.sword": "weapon.sword"})
    game, hero, boss = _battle(project)  # the boss is weak to swords, the hero carries one
    for ability_id in ("plain", "adapt"):
        _grant(game, hero, ability_id)

    def hit(ability_id):
        pool = _pool(game, boss)
        pool.set_current(DAMAGE, 8000)
        game.use_ability(hero, ability_id, (boss,))
        return 8000 - pool.current(DAMAGE)

    assert hit("adapt") == pytest.approx(hit("plain") * 1.5, rel=0.01)
    assert not game.battle.member(hero).subject.tags.contains("weapon.sword")  # nothing leaks


def test_follow_tags_round_trip_and_validate():
    from asteria.gameplay import AbilityDefinition

    base = _project().gameplay_library.abilities.get("strike")
    assert "follow_tags" not in base.to_data()
    follow = dataclasses.replace(base, follow_tags={"equip.bow": "weapon.bow"})
    assert AbilityDefinition.from_data(follow.to_data()).follow_tags == {"equip.bow": "weapon.bow"}
    with pytest.raises(ValueError):
        dataclasses.replace(base, follow_tags={"": "x"})
