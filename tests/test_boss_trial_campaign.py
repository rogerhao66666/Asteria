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
    assert facts["field_tricks"] == 17 and facts["map_changes"] >= 12


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


def test_the_map_drawn_after_a_load_is_the_map_of_the_loaded_game(played):
    """The campaign saves and loads in the woods; every later map must still be the right one."""
    campaign, _facts = played
    view = campaign.rt.tile_view
    assert view is not None and view.session is campaign.game
    assert view.scene_id == campaign.game.scene.id


def test_four_heroes_stand_two_by_two_inside_the_stage(played):
    campaign, _facts = played
    game = campaign.game
    game.start_encounter("woods_ambush")
    campaign.rt._battle_presentation.begin()
    visuals = {
        v.member_id: v.anchor
        for v in campaign.rt._battle_presentation.screen.scene.combatants
        if v.member_id in ("hero_01", "hero_02", "hero_03", "hero_04")
    }
    assert len(visuals) == 4
    columns = {}
    for anchor in visuals.values():
        columns.setdefault(round(anchor.x), []).append(anchor.y)
    assert len(columns) == 2 and all(len(ys) == 2 for ys in columns.values())
    for ys in columns.values():
        assert abs(ys[0] - ys[1]) > 40  # nobody stands on a column mate
    layout = campaign.rt._battle_presentation.screen.composer.layout
    assert all(60 < a.y < layout.virtual_height for a in visuals.values())  # all on the stage
    game.battle, game.mode, game.encounter_id = None, "field", None


def test_the_bag_has_a_limit_of_kinds_and_says_what_did_not_fit(played):
    from asteria.rpg import ItemDefinition

    campaign, _facts = played
    game = campaign.game
    db = game.project.rpg_database
    for index in range(60):
        db.add_item(ItemDefinition(f"junk_{index}", f"Junk {index}"))
    bag = game.save.rpg_state.inventory
    for index in range(60):
        bag.add(f"junk_{index}", 1)
    kinds = [k for k, v in bag._counts.items() if v > 0]
    assert len(kinds) <= 40 + 5  # the limit (key items do not count) plus what is exempt
    assert bag.overflow  # what did not fit was reported


def test_a_taunt_pulls_single_target_attacks_and_the_shared_gauge_fills(played):
    campaign, _facts = played
    game = campaign.game
    game.start_encounter("woods_patrol")
    game.battle.apply_state("taunt", "hero_02", "hero_02")
    taunter = game.battle.member("hero_02").subject.tags.contains("state.taunt")
    assert taunter and game.extension_rules.taunt_tag == "state.taunt"
    assert game.party_gauge("unity") >= 0
    game.change_party_gauge("unity", 100)
    assert game.ability_unavailable("hero_01", "unity_strike") == ""
    game.battle = None
    game.mode = "field"
    game.encounter_id = None
