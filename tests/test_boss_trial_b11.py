"""Boss Trial B11: the second skill wave works in the demo project itself - forms, costs of every
kind, boost points handed around, ailments that take the choice away, and the companion."""

import random
import sys
from collections import Counter
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "boss_trial_demo"
sys.path.insert(0, str(DEMO))

import run_trial_smoke as smoke  # noqa: E402

from asteria.rpg.interactions import InteractionRule  # noqa: E402


def smoke_tags():
    elements = ("fire", "ice", "lightning", "light", "dark")
    weapons = ("sword", "axe", "spear", "dagger", "bow", "staff")
    return (*(f"damage.{e}" for e in elements), *(f"weapon.{w}" for w in weapons))


HERO, MIRA, BP, HP, SP = "hero_01", "hero_02", "bp", "vitality", "technique"


def _game(job="hero", encounter="boss_room"):
    project, game = smoke.load()
    for kind in (*smoke_tags(),):  # a probe rule per damage tag shows which tags a hit carried
        project.rpg_database.interaction_rules[f"probe_{kind}"] = InteractionRule(
            f"probe_{kind}", source_tags_all=(kind,), multiplier=1.0
        )
    game.refine_rng = random.Random(3)
    smoke.prepare(game, Counter(), job)
    game.start_encounter(encounter)
    return game


def _fresh(game):
    for member_id in (*game.active_hero_ids(), *game.active_enemy_ids()):
        pool = game.battle.member(member_id).subject.resources
        pool.set_current(HP, pool.maximum(HP))
        if pool.maximum(SP) > 0:
            pool.set_current(SP, pool.maximum(SP))
    game.drain_battle_log()


def _set_bp(game, member, value):
    pool = game.battle.battle_resources
    pool.change(member, BP, value - pool.current(member, BP))


def _cast(game, actor, ability, target, **kw):
    return game.use_ability(actor, ability, (target,) if target else None, **kw)


def _applied(game):
    return {
        e.data["state"]
        for e in game.drain_battle_log()
        if e.kind == "state_applied" and e.data.get("applied")
    }


def _tags_dealt(game):
    """The damage tags the last action's hits carried (through the probe rules)."""
    return {
        rule.removeprefix("probe_")
        for e in game.drain_battle_log()
        if e.kind == "action"
        for _target, outcome in e.outcomes
        for rule in outcome.value.matched_rules
        if rule.startswith("probe_")
    }


def test_the_companion_stands_beside_the_hero():
    game = _game()
    assert {HERO, MIRA} <= set(game.active_hero_ids())  # (the whole party is hired)
    assert {"mend", "purge", "bp_gift", "second_breath", "dawn_hymn"} <= set(
        game.battle.member(MIRA).ability_ids
    )
    assert "attack_staff" in game.battle.member(MIRA).ability_ids  # her staff


def test_the_hero_wields_every_weapon_and_both_light_and_dark():
    project, game = smoke.load()
    assert {
        f"capability.weapon.{k}" for k in ("sword", "axe", "spear", "dagger", "bow", "staff")
    } <= set(project.rpg_database.classes["hero"].granted_tags)
    game = _game("hero")
    assert {"dawn_and_dusk", "twilight_judgment", "dark_pact"} <= set(
        game.battle.member(HERO).ability_ids
    )


@pytest.mark.parametrize(
    "job, skill, form, tag",
    [
        ("hero", "dawn_and_dusk", "light", "damage.light"),
        ("hero", "dawn_and_dusk", "dark", "damage.dark"),
        ("weapon_master", "elemental_edge", "fire", "damage.fire"),
        ("weapon_master", "elemental_edge", "ice", "damage.ice"),
        ("sage", "arcane_tome", "lightning", "damage.lightning"),
        ("sage", "arcane_tome", "dark", "damage.dark"),
    ],
)
def test_one_skill_deals_the_element_of_the_form_cast(job, skill, form, tag):
    game = _game(job)
    boss = game.active_enemy_ids()[0]
    _fresh(game)
    _cast(game, HERO, skill, boss, form=form)
    assert tag in _tags_dealt(game)


def test_a_skill_follows_the_weapon_in_hand():
    game = _game("weapon_master")
    boss = game.active_enemy_ids()[0]
    _fresh(game)
    _cast(game, HERO, "versatile_strike", boss)
    assert "weapon.sword" in _tags_dealt(game)  # the hero carries Sunbrand


def test_costs_can_be_health_items_and_gold():
    game = _game("hero")
    boss = game.active_enemy_ids()[0]
    _fresh(game)
    pool = game.battle.member(HERO).subject.resources
    pool.set_current(HP, 650)  # the pact asks for 700 health: it cannot be paid
    assert game.ability_unavailable(HERO, "dark_pact")
    pool.set_current(HP, 5000)
    assert not game.ability_unavailable(HERO, "dark_pact")
    game = _game("forgemaster")
    boss = game.active_enemy_ids()[0]
    state = game.save.rpg_state
    dust, gold = state.inventory.count("fire_dust"), state.currencies["gold"]
    _fresh(game)
    _cast(game, HERO, "molten_strike", boss)
    _cast(game, HERO, "gilded_hammer", boss)
    assert state.inventory.count("fire_dust") == dust - 1
    assert state.currencies["gold"] == gold - 200
    state.currencies["gold"] = 50
    with pytest.raises(Exception, match="gold|afford|enough|cost"):
        _cast(game, HERO, "gilded_hammer", boss)


def test_boost_points_can_be_given_moved_and_refilled():
    game = _game("hero")
    _fresh(game)
    _set_bp(game, HERO, 3)
    _set_bp(game, MIRA, 0)
    _cast(game, HERO, "pass_the_torch", MIRA)  # pays 2, gives 2
    pool = game.battle.battle_resources
    assert (pool.current(HERO, BP), pool.current(MIRA, BP)) == (1, 2)
    _set_bp(game, HERO, 0)
    _cast(game, MIRA, "bp_gift", HERO)
    assert pool.current(HERO, BP) == 2
    _set_bp(game, MIRA, 0)
    _cast(game, MIRA, "second_breath", None)
    assert pool.current(MIRA, BP) == 2
    _set_bp(game, HERO, 0)
    _cast(game, HERO, "rekindle", None)
    assert pool.current(HERO, BP) == 2
    game.battle.member(HERO).subject.resources.set_current(HP, 2000)
    game.battle.member(MIRA).subject.resources.set_current(HP, 100)
    _set_bp(game, MIRA, 0)
    _cast(game, HERO, "martyrs_gift", MIRA)
    assert game.battle.member(MIRA).subject.resources.current(HP) > 1000
    assert game.battle.member(HERO).subject.resources.current(HP) <= 1200
    assert pool.current(MIRA, BP) == 1


@pytest.mark.parametrize(
    "job, skill, states",
    [
        ("weapon_master", "cripple", {"slow", "defense_down"}),
        ("sage", "hex", {"magic_down", "power_down", "blind"}),
        ("sage", "bewilder", {"confuse", "silence"}),
        ("rogue", "charm", {"charm"}),
        ("rogue", "venom_edge", {"poison", "bleed"}),
        ("rogue", "blinding_powder", {"blind"}),
        ("guardian", "maddening_howl", {"berserk"}),
        ("forgemaster", "armor_crush", {"defense_down", "power_down"}),
    ],
)
def test_debuff_and_ailment_skills_land_their_states(job, skill, states):
    game = _game(job)
    boss = game.active_enemy_ids()[0]
    seen = set()
    for _ in range(40):
        _fresh(game)
        try:
            _cast(game, HERO, skill, boss)
        except Exception:  # noqa: BLE001 - a cooldown or a missed roll just goes again
            continue
        seen |= _applied(game)
        if states <= seen:
            break
    assert states <= seen, seen


def test_buff_skills_reach_the_whole_party():
    game = _game("weapon_master")
    _fresh(game)
    _cast(game, HERO, "war_cry", None)
    for member in (HERO, MIRA):
        active = {s.state_id for s in game.battle.member(member).subject.states.active_states()}
        assert {"attack_up", "keen_mind"} <= active


def test_ailments_take_the_choice_away():
    game = _game("hero")
    boss = game.active_enemy_ids()[0]
    policies = game.save and smoke.load()[0].rpg_database.battle_state_policies
    assert policies["confuse"].target_override == "random_any"
    assert policies["charm"].target_override == "random_ally"
    assert policies["berserk"].target_override == "random_opponent"
    _fresh(game)
    for _ in range(30):
        if game.battle.apply_state("berserk", boss, HERO).applied:
            break
    assert game.ability_unavailable(HERO, "dawn_and_dusk")  # berserk: weapon attacks only
    assert not game.ability_unavailable(HERO, "attack_sword")


def test_doom_kills_the_adds_but_never_a_boss():
    game = _game("sage", "swarm")
    boss = next(e for e in game.active_enemy_ids() if "crimson" in e)
    add = next(e for e in game.active_enemy_ids() if e != boss)
    for target in (boss, add):
        for _ in range(30):
            result = game.battle.apply_state("doom", HERO, target)
            if result.applied:
                break
    states = {
        e: {s.state_id for s in game.battle.member(e).subject.states.active_states()}
        for e in (boss, add)
    }
    assert "doom" in states[add] and "doom" not in states[boss]
    for _ in range(6):
        game.battle.battle_states.apply_trigger(
            "rpg.battle.turn_ended", (game.battle.member(add), game.battle.member(boss))
        )
    assert game.battle.member(add).subject.resources.current(HP) == 0
    assert game.battle.member(boss).subject.resources.current(HP) > 0
