"""Story events change the party: JOIN_PARTY adds an actor to the roster (and the active party
while there is room), LEAVE_PARTY takes it out; battles and saves follow."""

import pytest
from test_battle_extensions_session import _session

from asteria.events.world_commands import WorldCommand
from asteria.runtime.game_session import GameSessionError


def _spare(game):
    """An actor of the project that is not in the party."""
    db = game.project.rpg_database
    return next(a for a in db.actors if a not in game.save.rpg_state.party_actor_ids)


def _drop_last(game):
    state = game.save.rpg_state
    last = state.party_actor_ids[-1]
    state.party_actor_ids = state.party_actor_ids[:-1]
    state.party_active_actor_ids = tuple(a for a in state.party_active_actor_ids if a != last)
    state.party_placements.pop(last, None)
    return last


def test_an_actor_joins_the_roster_and_the_active_party_with_a_slot():
    game = _session()
    actor = _drop_last(game)
    state = game.save.rpg_state
    game.join_party(actor)
    assert actor in state.party_actor_ids and actor in state.party_active_actor_ids
    assert actor in state.party_placements
    assert len(set(state.party_placements.values())) == len(state.party_placements)
    game.join_party(actor)  # joining twice changes nothing
    assert state.party_actor_ids.count(actor) == 1
    game.start_encounter(sorted(game.project.rpg_database.encounters)[0])
    assert actor in game.active_hero_ids()


def test_a_reserve_member_joins_the_roster_only():
    game = _session()
    actor = _drop_last(game)
    game.join_party(actor, active=False)
    state = game.save.rpg_state
    assert actor in state.party_actor_ids and actor not in state.party_active_actor_ids


def test_the_world_commands_join_and_leave():
    game = _session()
    actor = _drop_last(game)
    game.world_commands.dispatch(WorldCommand("JOIN_PARTY", {"actor_id": actor}))
    assert actor in game.save.rpg_state.party_active_actor_ids
    game.world_commands.dispatch(WorldCommand("LEAVE_PARTY", {"actor_id": actor}))
    state = game.save.rpg_state
    assert actor not in state.party_actor_ids and actor not in state.party_active_actor_ids
    with pytest.raises(GameSessionError):
        game.join_party("nobody")
