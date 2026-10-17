"""Skill forms: one skill, several ways to cast it (an element, a weapon, a power level), each with
its own damage types, strength and extra cost; chosen when the skill is used."""

import dataclasses

import pytest
from test_octopath_style_battle import BP, DAMAGE, _battle, _project

from asteria.gameplay import AbilityDefinition, Effect, EffectOperation, EffectOperationKind
from asteria.gameplay.abilities import AbilityEffect
from asteria.gameplay.formulas import FormulaTerm, ValueFormula
from asteria.rpg.interactions import InteractionRule
from asteria.runtime.game_session import GameSessionError

SP = "technique"
FORMS = (
    {"form_id": "fire", "label": "Fire", "tags": ["damage.fire"]},
    {"form_id": "might", "label": "Might", "power": 2.0},
    {
        "form_id": "costly",
        "label": "Costly",
        "tags": ["damage.fire"],
        "resource_costs": {SP: 30},
        "battle_costs": {BP: 1},
    },
    {"form_id": "burning", "label": "Burning", "apply_states": [{"state": "oct_venom"}]},
)


def _project_with_forms():
    project = _project()
    project.rpg_database.interaction_rules["weak_fire_x2"] = InteractionRule(
        "weak_fire_x2",
        source_tags_all=("damage.fire",),
        target_tags_all=("weak.fire",),
        multiplier=2.0,
    )
    abilities = project.gameplay_library.abilities
    base = abilities.get("strike")
    hit = EffectOperation(
        EffectOperationKind.RESOURCE_DELTA,
        DAMAGE,
        ValueFormula((FormulaTerm("constant", "", -1000.0),)),
    )
    abilities._definitions["shape"] = dataclasses.replace(
        base,
        ability_id="shape",
        effects=(AbilityEffect("selected", Effect("e", (hit,))),),
        forms=FORMS,
    )
    db = project.rpg_database
    db.battle_targeting["shape"] = dataclasses.replace(
        db.battle_targeting["strike"], ability_id="shape"
    )
    return project


def _setup():
    game, hero, boss = _battle(_project_with_forms())
    member = game.battle.member(hero)
    game.battle.set_member_abilities(hero, (*member.ability_ids, "shape"))
    game.battle.member(boss).subject.tags.add("weak.fire")
    return game, hero, boss


def _hit(game, hero, boss, **kwargs):
    pool = game.battle.member(boss).subject.resources
    pool.set_current(DAMAGE, 9000)
    game.use_ability(hero, "shape", (boss,), **kwargs)
    return 9000 - pool.current(DAMAGE)


def test_the_form_decides_damage_type_and_strength():
    game, hero, boss = _setup()
    base = _hit(game, hero, boss, form="burning")  # no tags, power 1
    fire = _hit(game, hero, boss, form="fire")
    assert fire > base * 1.5  # the boss is weak to fire, and only this form deals it
    assert _hit(game, hero, boss, form="might") == pytest.approx(base * 2.0, rel=0.01)  # power 2
    assert _hit(game, hero, boss) == pytest.approx(fire, rel=0.01)  # first form by default


def test_a_form_can_cost_more_and_a_cast_leaves_nothing_behind():
    game, hero, boss = _setup()
    pool = game.battle.member(hero).subject.resources
    game.battle.battle_resources.change(hero, BP, 3)
    sp, bp = pool.current(SP), game.battle.battle_resources.current(hero, BP)
    _hit(game, hero, boss, form="costly")
    assert sp - pool.current(SP) == pytest.approx(30.0)
    assert bp - game.battle.battle_resources.current(hero, BP) == pytest.approx(1.0)
    assert not game.battle.member(hero).subject.tags.contains("damage.fire")


def test_an_unaffordable_or_unknown_form_is_refused():
    game, hero, boss = _setup()
    pool = game.battle.member(hero).subject.resources
    pool.set_current(SP, 5)
    with pytest.raises(GameSessionError):
        game.use_ability(hero, "shape", (boss,), form="costly")
    with pytest.raises(GameSessionError):
        game.use_ability(hero, "shape", (boss,), form="no_such_form")


def test_a_form_can_add_states():
    game, hero, boss = _setup()
    game.use_ability(hero, "shape", (boss,), form="burning")
    states = game.battle.member(boss).subject.states.active_states()
    assert "oct_venom" in {s.state_id for s in states}


def test_forms_round_trip_and_validate():
    base = _project().gameplay_library.abilities.get("strike")
    assert "forms" not in base.to_data()
    shaped = dataclasses.replace(base, forms=FORMS)
    again = AbilityDefinition.from_data(shaped.to_data())
    assert [f["form_id"] for f in again.forms] == ["fire", "might", "costly", "burning"]
    assert again.forms[1]["power"] == 2.0 and again.forms[2]["resource_costs"] == {SP: 30.0}
    with pytest.raises(ValueError):
        dataclasses.replace(base, forms=({"form_id": "a"}, {"form_id": "a"}))
    with pytest.raises(ValueError):
        dataclasses.replace(base, forms=({"form_id": "a", "power": 0},))
    with pytest.raises(ValueError):
        dataclasses.replace(base, forms=({"form_id": ""},))


def test_the_battle_menu_asks_which_form_before_the_target():
    from asteria.runtime.battle_commands import BattleCommands

    game, hero, boss = _setup()
    commands = BattleCommands(game)
    pool = game.battle.member(boss).subject.resources
    pool.set_current(DAMAGE, 9000)
    rows = commands.entries(hero)
    index = [r.action_id for r in rows].index("shape")
    commands.cursor = index
    assert commands.press("confirm", hero) is False  # not done yet
    assert commands.mode == "forms"
    assert [r.action_id for r in commands.entries(hero)] == [f["form_id"] for f in FORMS]
    commands.cursor = 1  # Might
    acted = commands.press("confirm", hero)
    if not acted:  # one foe: the target is picked for us; several: ask
        assert commands.mode == "target"
        acted = commands.press("confirm", hero)
    assert acted and 9000 - pool.current(DAMAGE) > 0
    commands.reset()
    commands.cursor = index
    commands.press("confirm", hero)
    commands.press("cancel", hero)
    assert commands.mode == "command"  # backing out of the form list returns to the skills
