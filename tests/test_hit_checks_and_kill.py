"""Per-hit outcome checks (crit / evade) and the instant-KO option of ability ``hits``.

Everything is authored data: a hit names outcome checks to roll and an optional ``kill`` block;
which tags a check emits and what they do is still up to interaction rules.
"""

import dataclasses

import pytest
from test_octopath_style_battle import DAMAGE, _battle, _project

from asteria.gameplay import AbilityDefinition
from asteria.rpg.interactions import (
    InteractionDisposition,
    InteractionRule,
    OutcomeCheckDefinition,
)


def _with_hits(hits, *, crit_chance=1.0, evade_chance=0.0):
    project = _project()
    db = project.rpg_database
    db.outcome_checks["crit"] = OutcomeCheckDefinition(
        "crit", crit_chance, success_tags=("outcome.crit",)
    )
    db.outcome_checks["land"] = OutcomeCheckDefinition(
        "land", 1.0 - evade_chance, failure_tags=("outcome.evade",)
    )
    db.interaction_rules["crit_x2"] = InteractionRule(
        "crit_x2", source_tags_all=("outcome.crit",), multiplier=2.0
    )
    db.interaction_rules["evade_null"] = InteractionRule(
        "evade_null",
        source_tags_all=("outcome.evade",),
        disposition=InteractionDisposition.NULLIFY,
        priority=5,
    )
    abilities = project.gameplay_library.abilities
    abilities._definitions["oct_sword"] = dataclasses.replace(
        abilities.get("oct_sword"), hits=hits
    )
    return project


def _damage(hits, **kwargs):
    game, hero, boss = _battle(_with_hits(hits, **kwargs))
    pool = game.battle.member(boss).subject.resources
    pool.set_current(DAMAGE, max(pool.current(DAMAGE), 8000))
    before = pool.current(DAMAGE)
    game.use_ability(hero, "oct_sword", (boss,))
    return before - pool.current(DAMAGE), game, boss


def test_a_hit_without_checks_is_unchanged():
    plain, _, _ = _damage(({"tags": [], "power": 1.0},))
    assert plain > 0


def test_critical_check_multiplies_only_when_it_succeeds():
    plain, _, _ = _damage(({"tags": [], "power": 1.0},))
    crit, _, _ = _damage(({"tags": [], "power": 1.0, "checks": ["crit"]},))
    miss, _, _ = _damage(({"tags": [], "power": 1.0, "checks": ["crit"]},), crit_chance=0.0)
    assert crit == pytest.approx(plain * 2.0)
    assert miss == pytest.approx(plain)


def test_evade_check_nullifies_that_hit_through_a_rule():
    hit_a = {"tags": [], "power": 1.0, "checks": ["land"]}
    dodged, _, _ = _damage((hit_a,), evade_chance=1.0)
    assert dodged == 0


def test_each_hit_rolls_its_own_check():
    hits = (
        {"tags": [], "power": 1.0, "checks": ["land"]},
        {"tags": [], "power": 1.0},
    )
    plain, _, _ = _damage(({"tags": [], "power": 1.0},))
    both, _, _ = _damage(hits, evade_chance=1.0)
    assert both == pytest.approx(plain)  # first dodged, second lands


def test_check_tags_do_not_leak_to_the_next_action():
    _, game, boss = _damage(({"tags": [], "power": 1.0, "checks": ["crit"]},))
    hero = game.save.rpg_state.party_active_actor_ids[0]
    assert not game.battle.member(hero).subject.tags.contains("outcome.crit")


def test_instant_kill_respects_chance_and_immunity():
    kill = {"chance": 1.0, "resource": DAMAGE, "immune_tags": ["kill_immune"]}
    dealt, game, boss = _damage(({"tags": [], "power": 1.0, "kill": kill},))
    assert game.battle.member(boss).subject.resources.current(DAMAGE) == 0

    game, hero, boss = _battle(_with_hits(({"tags": [], "power": 1.0, "kill": kill},)))
    subject = game.battle.member(boss).subject
    subject.tags.add("kill_immune")
    subject.resources.set_current(DAMAGE, 8000)
    game.use_ability(hero, "oct_sword", (boss,))
    assert subject.resources.current(DAMAGE) > 0  # immune: only the normal damage

    never = {"chance": 0.0, "resource": DAMAGE}
    _, game, boss = _damage(({"tags": [], "power": 1.0, "kill": never},))
    assert game.battle.member(boss).subject.resources.current(DAMAGE) > 0


def test_immune_target_can_take_a_fraction_instead():
    kill = {
        "chance": 1.0,
        "resource": DAMAGE,
        "immune_tags": ["kill_immune"],
        "immune_fraction": 0.25,
    }
    game, hero, boss = _battle(_with_hits(({"tags": [], "power": 1.0, "kill": kill},)))
    subject = game.battle.member(boss).subject
    subject.tags.add("kill_immune")
    subject.resources.set_current(DAMAGE, 8000)
    maximum = subject.resources.maximum(DAMAGE)
    plain, _, _ = _damage(({"tags": [], "power": 1.0},))
    game.use_ability(hero, "oct_sword", (boss,))
    lost = 8000 - subject.resources.current(DAMAGE)
    assert lost >= plain + 0.25 * maximum - 1


def test_hit_validation_and_round_trip():
    base = _project().gameplay_library.abilities.get("oct_sword")
    good = dataclasses.replace(
        base,
        hits=(
            {
                "tags": ["a"],
                "power": 1.5,
                "checks": ["crit"],
                "kill": {"chance": 0.3, "resource": DAMAGE},
            },
        ),
    )
    again = AbilityDefinition.from_data(good.to_data())
    assert again.hits[0]["checks"] == ["crit"]
    assert again.hits[0]["kill"]["chance"] == 0.3
    with pytest.raises(ValueError):
        dataclasses.replace(base, hits=({"tags": [], "kill": {"chance": 1.5, "resource": "x"}},))
    with pytest.raises(ValueError):
        dataclasses.replace(base, hits=({"tags": [], "bogus": 1},))


def test_blank_editor_template_adds_nothing():
    from asteria.editor.authoring_hub_widget import StructuredRecordEditor

    template = StructuredRecordEditor.LIST_TEMPLATES["hits"]
    base = _project().gameplay_library.abilities.get("oct_sword")
    blank = dataclasses.replace(base, hits=(dict(template),))
    assert "checks" not in blank.hits[0] and "kill" not in blank.hits[0]
