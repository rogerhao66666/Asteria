"""The whole Boss Trial campaign, played through the game host from the first talk to the last
banner: four maps, three bosses, four party members, every system the list asks for."""

import sys
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "boss_trial_demo"
sys.path.insert(0, str(DEMO))

import run_campaign  # noqa: E402


@pytest.fixture(scope="module")
def played():
    campaign = run_campaign.Campaign(log=lambda *_: None)
    facts = campaign.run()
    return campaign, facts


def test_the_campaign_is_won_with_the_whole_party(played):
    campaign, facts = played
    assert facts["game_complete"] == 1 and facts["party_size"] == 4
    assert set(campaign.game.save.rpg_state.party_active_actor_ids) == {
        "hero_01",
        "hero_02",
        "hero_03",
        "hero_04",
    }
    missing = [key for key in run_campaign.REQUIRED if not facts.get(key)]
    assert not missing, missing


def test_the_quest_chain_pays_out_and_moves_reputation(played):
    campaign, facts = played
    log = campaign.game.quest_log
    for quest in ("q_patrol", "q_beast", "q_crypt", "slay_vaelor"):
        assert log.status(quest) == "completed", quest
    assert facts["warden_rep"] >= 60  # Ally of the Wardens
    assert campaign.game.world.reputation["bonewalkers"] < 0
    assert campaign.game.world.counters["contracts"] >= 2
    unlocked = set(campaign.game.world.achievements)
    assert {"road_cleared", "beast_slayer", "ancient_laid_to_rest", "warlord_slayer"} <= unlocked


def test_progress_came_from_play_not_from_a_fixture(played):
    campaign, facts = played
    assert facts["levels"] >= 8 and facts["tree_ranks"] > 20
    assert facts["skills_cast"] >= 20 and facts["victories"] >= 6
    state = campaign.game.save.rpg_state
    assert state.equipment_bag or facts["victories"]  # fights dropped gear into the bag
    assert campaign.game.ensure_actor_progression("hero_01").level >= 9
    assert facts["weather_rain"] and facts["weather_dust"] and facts["foes_roamed"]
    assert facts["field_tricks"] == 9 and facts["map_changes"] >= 12


def test_every_foe_has_a_drop_table_with_the_chances_its_weights_say(played):
    import random
    from collections import Counter

    from asteria.rpg.drop_tables import roll_drop_table

    campaign, _facts = played
    db = campaign.game.project.rpg_database
    for enemy_id in (
        "goblin_slinger",
        "goblin_berserker",
        "goblin_beast",
        "skeleton_grunt",
        "skeleton_hunter",
        "skeleton_ancient",
        "mender_wisp",
        "crimson_warlord",
    ):
        assert db.enemies[enemy_id].reward.drop_table_id in db.drop_tables, enemy_id
    table = db.drop_tables["goblin_loot"]  # 4 entries of weight 3, 3, 1, 1 and 4 for nothing
    rng, counts, rolls = random.Random(2), Counter(), 20_000
    for _ in range(rolls):
        counts.update(roll_drop_table(table, rng).keys() or ["nothing"])
    assert counts["healing_herb"] / rolls == pytest.approx(3 / 12, abs=0.02)
    assert counts["w_axe"] / rolls == pytest.approx(1 / 12, abs=0.015)
    assert counts["nothing"] / rolls == pytest.approx(4 / 12, abs=0.02)
    assert campaign.game.save.rpg_state.equipment_bag, "the fights dropped no gear at all"
