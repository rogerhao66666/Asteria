"""Victory aftermath: summed rewards, level changes and the pages a results screen shows."""

from types import SimpleNamespace

from asteria.rpg.victory import ActorAftermath, VictoryAftermath, build_aftermath


def _applied(currencies=None, items=None):
    return SimpleNamespace(currencies=currencies or {}, items=items or {})


def _state(level, atk, abilities=()):
    return {"level": level, "stats": {"atk": atk, "hp": 100}, "abilities": tuple(abilities)}


def test_rewards_are_summed_across_enemies():
    aftermath = build_aftermath(
        [_applied({"gold": 10}, {"potion": 1}), _applied({"gold": 5}, {"potion": 2, "key": 1})],
        {},
        {},
    )
    assert aftermath.currencies == (("gold", 15.0),)
    assert aftermath.items == (("key", 1), ("potion", 3))


def test_level_change_lists_only_the_stats_that_rose_and_new_abilities():
    aftermath = build_aftermath(
        [_applied()],
        {"hero": _state(2, 10, ("slash",))},
        {"hero": _state(3, 14, ("slash", "fire"))},
        names={"hero": "Hero"},
        experience={"hero": 120},
    )
    (actor,) = aftermath.actors
    assert actor.name == "Hero" and actor.leveled_up
    assert actor.stat_changes == (("atk", 10.0, 14.0),)
    assert actor.new_abilities == ("fire",)
    assert actor.experience_gained == 120


def test_pages_follow_rewards_then_heroes_then_spoils():
    aftermath = build_aftermath(
        [_applied({"gold": 30}, {"potion": 2})],
        {"a": _state(1, 5), "b": _state(1, 5)},
        {"a": _state(2, 8, ("fire",)), "b": _state(1, 5)},
        defeated=("slime", "bat"),
        names={"a": "Ann", "b": "Bob"},
        experience={"a": 50, "b": 0},
        bonus_notes=("Overkill x2",),
    )
    pages = aftermath.pages(item_names={"potion": "Potion"}, stat_names={"atk": "Attack"})
    assert [p.kind for p in pages] == ["rewards", "actor", "drops"]  # Bob gained nothing
    assert pages[0].lines == ("Defeated: slime, bat", "gold  +30", "Overkill x2")
    assert pages[1].title == "Ann"
    assert pages[1].lines == ("EXP  +50", "Level 1 -> 2", "Attack  5 -> 8", "Learned fire")
    assert pages[2].lines == ("Potion  x2",)


def test_no_items_means_no_spoils_page_and_an_empty_battle_still_has_one_page():
    pages = VictoryAftermath().pages()
    assert [p.kind for p in pages] == ["rewards"]


def test_actor_without_a_before_state_counts_as_unchanged_level():
    aftermath = build_aftermath([], {}, {"new": _state(4, 9)})
    assert not aftermath.actors[0].leveled_up and aftermath.actors[0].stat_changes == ()
    assert ActorAftermath("x").to_data()["level_after"] == 1
