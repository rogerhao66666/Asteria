"""Jobs can ask for something before they unlock (a level, other jobs), and experience can follow
a curve the author draws instead of one fixed step."""

import dataclasses

import pytest
from test_battle_extensions_session import _session

from asteria.rpg import ClassDefinition
from asteria.rpg.progression import ProgressionMilestone, ProgressionTrackDefinition
from asteria.runtime.game_session import GameSessionError


def _reset(game, actor):
    """The actor at level 1 with no experience."""
    from asteria.rpg.save_state import ActorProgressionState

    state = game.ensure_actor_progression(actor)
    game.save.rpg_state.actor_progression[actor] = ActorProgressionState(
        1,
        0.0,
        unlocked_class_ids=state.unlocked_class_ids,
        active_class_ids=state.active_class_ids,
    )


def _with_job(game, **rules):
    db = game.project.rpg_database
    first = next(iter(db.classes.values()))
    db.classes["elite"] = dataclasses.replace(first, class_id="elite", **rules)
    return db


def test_a_class_data_round_trips_its_unlock_rules():
    base = ClassDefinition("a", "A")
    assert "unlock_level" not in base.to_data()
    rule = ClassDefinition("b", "B", unlock_level=5, unlock_classes=("a",))
    again = ClassDefinition.from_data(rule.to_data())
    assert (again.unlock_level, again.unlock_classes) == (5, ("a",))
    with pytest.raises(ValueError):
        ClassDefinition("c", "C", unlock_level=-1)


def test_a_job_stays_locked_until_its_level_and_prerequisite_jobs_are_met():
    game = _session()
    actor = game.save.rpg_state.party_actor_ids[0]
    _reset(game, actor)
    state = game.ensure_actor_progression(actor)
    held = state.unlocked_class_ids[0]
    _with_job(game, unlock_level=4, unlock_classes=(held,))
    with pytest.raises(GameSessionError, match="level 4"):
        game.set_classes(actor, [held, "elite"])
    game.grant_actor_experience(actor, 3000, level_threshold=1000)
    assert game.set_classes(actor, [held, "elite"]) == (held, "elite")


def test_experience_follows_a_level_track():
    game = _session()
    actor = game.save.rpg_state.party_actor_ids[0]
    _reset(game, actor)
    track = ProgressionTrackDefinition(
        "levels",
        milestones=(
            ProgressionMilestone(1, 0),
            ProgressionMilestone(2, 100),
            ProgressionMilestone(3, 400),
            ProgressionMilestone(4, 1600),
        ),
    )
    game.project.rpg_database.progression_tracks["levels"] = track
    game.grant_actor_experience(actor, 150, level_track="levels")
    assert game.ensure_actor_progression(actor).level == 2
    game.grant_actor_experience(actor, 300, level_track="levels")  # 450 in all
    assert game.ensure_actor_progression(actor).level == 3
    game.grant_actor_experience(actor, 5000, level_track="levels")
    assert game.ensure_actor_progression(actor).level == 4  # the track's last rank
    with pytest.raises(GameSessionError, match="track"):
        game.grant_actor_experience(actor, 1, level_track="missing")
