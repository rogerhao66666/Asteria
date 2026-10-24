"""Event conditions can ask about the party: levels, items, gold, jobs, who is in the party,
reputation and quest status (source ``rpg``)."""

import sys
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

import run_trial_smoke as smoke  # noqa: E402

from asteria.events.conditions import EventCondition  # noqa: E402


def _holds(game, name, operator="==", value=True):
    return EventCondition("rpg", name, operator, value, None).evaluate(game.save.event_context)


def test_rpg_conditions_read_the_party_state():
    _project, game = smoke.load()
    assert _holds(game, "level:hero_01", "==", 1)
    assert not _holds(game, "level:hero_01", ">=", 5)
    game.grant_actor_experience("hero_01", 5000, level_threshold=1000)
    assert _holds(game, "level:hero_01", ">=", 5)
    assert _holds(game, "item:healing_herb", ">=", 1)
    assert not _holds(game, "item:phoenix_seed", ">=", 99)
    assert _holds(game, "gold", ">=", 100)
    assert not _holds(game, "party:hero_02")  # the hero starts alone
    game.join_party("hero_02")
    assert _holds(game, "party:hero_02") and not _holds(game, "party:hero_03")
    game.join_party("hero_03")
    assert _holds(game, "party:hero_03")
    assert _holds(game, "job:hero_01:brave")  # Roger sets out a Brave
    assert not _holds(game, "job:hero_01:sage")
    game.world.reputation["wardens"] = 30.0
    assert _holds(game, "reputation:wardens", ">=", 25)
    assert _holds(game, "quest:q_patrol", "==", "inactive")
    game.start_quest("q_patrol")
    assert _holds(game, "quest:q_patrol", "==", "active")


def test_an_unknown_name_is_an_error_not_a_silent_false():
    _project, game = smoke.load()
    with pytest.raises(ValueError, match="unknown rpg condition"):
        _holds(game, "bogus:thing")
