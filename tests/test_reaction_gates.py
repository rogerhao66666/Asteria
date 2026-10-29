"""Reactions inside a real battle session: a reactor can be required to carry tags (a counter
stance), and the reaction shows up as an action in the battle log."""

import pytest
from test_break_battle import DAMAGE, _battle, _project

from asteria.rpg.reactions import ReactionDefinition


def _project_with_counter(reactor_tags=("stance.counter",)):
    project = _project()
    project.rpg_database.add_reaction(
        ReactionDefinition(
            "boss_counter",
            "rpg.battle.after_action",
            "event_targets",
            target_selector="event_source",
            ability_id="boss_cleave",
            reactor_tags=reactor_tags,
        )
    )
    return project


def test_reactor_tags_round_trip_and_default():
    plain = ReactionDefinition("r", "t", "event_targets").to_data()
    assert "reactor_tags" not in plain
    gated = ReactionDefinition("r", "t", "event_targets", reactor_tags=["b", "a"])
    assert ReactionDefinition.from_data(gated.to_data()).reactor_tags == ("a", "b")


def _hero_hp(game, hero):
    return game.battle.member(hero).subject.resources.current(DAMAGE)


def test_a_gated_reaction_waits_for_the_tag():
    game, hero, boss = _battle(_project_with_counter())
    game.drain_battle_log()
    before = _hero_hp(game, hero)
    game.use_ability(hero, "oct_sword", (boss,))
    assert _hero_hp(game, hero) == before  # the boss has no counter stance: no counter
    assert not [e for e in game.drain_battle_log() if e.member_id == boss]

    game.battle.member(boss).subject.tags.add("stance.counter")
    before = _hero_hp(game, hero)
    game.use_ability(hero, "oct_sword", (boss,))
    assert _hero_hp(game, hero) < before  # it strikes back
    entries = [e for e in game.drain_battle_log() if e.kind == "action" and e.member_id == boss]
    assert entries and entries[0].ability_id == "boss_cleave"
    assert entries[0].target_ids == (hero,)


def test_projects_without_reactions_are_unchanged():
    game, hero, boss = _battle()
    before = _hero_hp(game, hero)
    game.use_ability(hero, "oct_sword", (boss,))
    assert _hero_hp(game, hero) == pytest.approx(before)
