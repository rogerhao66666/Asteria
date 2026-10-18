"""An inn: REST_PARTY brings every roster member's resources back to full."""

import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

import run_trial_smoke as smoke  # noqa: E402

from asteria.events.world_commands import WorldCommand  # noqa: E402


def test_resting_restores_health_and_technique_of_the_whole_roster():
    _project, game = smoke.load()
    game.join_party("hero_02")  # Mira, hired at the guild
    game.start_encounter("boss_room")
    for member_id in game.active_hero_ids():
        pool = game.battle.member(member_id).subject.resources
        pool.set_current("vitality", 10)
        pool.set_current("technique", 0)
    game._write_battle_heroes_to_save()
    game.battle = None
    game.mode = "field"
    snapshots = game.save.rpg_state.actor_snapshots
    assert snapshots["hero_01"].resources["values"]["vitality"]["current"] == 10
    game.world_commands.dispatch(WorldCommand("REST_PARTY", {}))
    for actor_id in ("hero_01", "hero_02"):
        values = snapshots[actor_id].resources["values"]
        for name in ("vitality", "technique"):
            assert values[name]["current"] == values[name]["maximum"] > 0
    game.start_encounter("boss_room")
    pool = game.battle.member("hero_01").subject.resources
    assert pool.current("vitality") == pool.maximum("vitality")
