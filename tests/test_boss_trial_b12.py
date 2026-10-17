"""Boss Trial B12: loot, steal, limits, mastery, boost points from the fight, a capturable pet
that fights and evolves, quests, achievements and enemy levels - all through the real session."""

import random
import sys
from collections import Counter
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "boss_trial_demo"
sys.path.insert(0, str(DEMO))

import run_trial_smoke as smoke  # noqa: E402

HERO, BP, HP, SP = "hero_01", "bp", "vitality", "technique"
BOSS = "crimson_warlord"


def _game(job="hero", encounter="boss_room"):
    _project, game = smoke.load()
    game.refine_rng = random.Random(3)
    smoke.prepare(game, Counter(), job)
    game.start_encounter(encounter)
    return game


def _win(game):
    for member_id in tuple(game.active_enemy_ids()):
        game.battle.member(member_id).subject.resources.set_current(HP, 0)
    return game.finish_victory()


def test_the_warlord_drops_rolled_gear_into_the_equipment_bag():
    game = _game()
    state = game.save.rpg_state
    seen = []
    for _ in range(6):
        game.start_encounter("boss_room") if game.mode != "battle" else None
        _win(game)
        seen = list(state.equipment_bag)
    assert seen and {g.rarity for g in seen} <= {"common", "magic", "rare", "legendary"}
    assert any(g.rolled_affixes for g in seen)  # a non-common roll carries affixes
    assert len({g.instance_id for g in seen}) == len(seen)  # every drop is its own instance


def test_pilfer_steals_once_from_the_boss_then_finds_nothing():
    game = _game("rogue")
    boss = next(e for e in game.active_enemy_ids() if e.startswith(BOSS))
    held = game.save.rpg_state.inventory.count("ancient_thread")
    game.use_ability(HERO, "pilfer", (boss,))
    assert game.save.rpg_state.inventory.count("ancient_thread") >= held + 1
    steals = [e for e in game.drain_battle_log() if e.kind == "steal"]
    assert steals and steals[0].data["stolen"]
    game.battle.member(HERO).subject.resources.set_current(SP, 100)
    game.use_ability(HERO, "pilfer", (boss,))
    assert [e.data["reason"] for e in game.drain_battle_log() if e.kind == "steal"] == [
        "already_stolen"
    ]


def test_an_ultimate_can_be_used_once_per_battle():
    game = _game("hero")
    boss = game.active_enemy_ids()[0]
    pool = game.battle.battle_resources
    pool.change(HERO, BP, 5 - pool.current(HERO, BP))
    game.use_ability(HERO, "twilight_judgment", (boss,))
    pool.change(HERO, BP, 5 - pool.current(HERO, BP))
    game.battle.member(HERO).subject.resources.set_current(SP, 280)
    assert "No uses left" in game.ability_unavailable(HERO, "twilight_judgment")
    with pytest.raises(Exception, match="No uses left"):  # noqa: B017
        game.use_ability(HERO, "twilight_judgment", (boss,))


def test_a_skill_levels_up_with_use_and_the_level_adds_damage():
    game = _game("hero")
    boss = game.active_enemy_ids()[0]
    extensions = game.battle.extensions
    assert extensions.mastery_level(HERO, "dawn_and_dusk") == 0
    for _ in range(3):
        game.battle.member(HERO).subject.resources.set_current(SP, 280)
        game.use_ability(HERO, "dawn_and_dusk", (boss,), form="light")
    assert extensions.mastery_level(HERO, "dawn_and_dusk") == 1
    rules = game.project.rpg_database.interaction_rules
    assert rules["mastery_dawn_and_dusk_1"].multiplier > 1.0


def test_a_kill_and_a_wound_fill_boost_points():
    game = _game("hero", "swarm")
    pool = game.battle.battle_resources
    pool.change(HERO, BP, -pool.current(HERO, BP))
    wisp = next(e for e in game.active_enemy_ids() if not e.startswith(BOSS))
    game.battle.member(wisp).subject.resources.set_current(HP, 1)
    game.use_ability(HERO, "attack_sword", (wisp,))
    assert pool.current(HERO, BP) >= 1


def test_a_wisp_can_be_captured_fights_as_a_unit_and_evolves():
    game = _game("hero", "swarm")
    wisp = next(e for e in game.active_enemy_ids() if not e.startswith(BOSS))
    assert game.capture_chance(wisp) is not None

    class Lucky:
        def random(self):
            return 0.0

    assert game.attempt_capture(HERO, wisp, rng=Lucky())
    pet = game.active_pet()
    assert pet.species_id == "wisp" and pet.level == 2
    _win(game)
    game.start_encounter("boss_room")
    unit = f"pet:{pet.instance_id}"
    assert unit in game.battle.members
    assert {"wisp_bolt", "wisp_mend"} <= set(game.battle.member(unit).ability_ids)
    pet.level = 5
    assert game.evolve_pet(pet.instance_id) == "greater_wisp"


def test_quests_achievements_and_enemy_levels():
    game = _game("hero")
    state = game.save.rpg_state
    log = game.quest_log
    log.start("slay_vaelor")
    state.inventory.add("healing_herb", 3)
    assert game.enemy_levels  # the boss and its wisps have levels
    assert game.difficulty == "normal"
    game.set_difficulty("hard")
    _win(game)
    log = game.quest_log
    assert log.status("slay_vaelor") == "completed"  # the herbs are in the bag, the warlord fell
    game.refresh_achievements()
    unlocked = set(game.world.achievements)
    assert {"warlord_slayer", "quest_done"} <= unlocked
    assert "wisp_hunter" not in unlocked  # ten wisps is more than one fight
    with pytest.raises(Exception):  # noqa: B017 - an unknown setting is refused
        game.set_difficulty("impossible")


def test_drop_chances_follow_the_tables_weights():
    from asteria.rpg.drop_tables import roll_drop_table

    _project, game = smoke.load()
    tables = game.project.rpg_database.drop_tables
    rng, rolls, counts = random.Random(5), 20_000, Counter()
    for _ in range(rolls):
        got = roll_drop_table(tables["wisp_drops"], rng)
        counts.update(got.keys() or ["nothing"])
    # weights 3 + 3 against 4 for nothing: 30% leaf, 30% herb, 40% nothing
    assert counts["ether_leaf"] / rolls == pytest.approx(0.3, abs=0.02)
    assert counts["healing_herb"] / rolls == pytest.approx(0.3, abs=0.02)
    assert counts["nothing"] / rolls == pytest.approx(0.4, abs=0.02)
    spoils = Counter()
    for _ in range(rolls):
        spoils.update(roll_drop_table(tables["warlord_spoils"], rng).keys())
    assert spoils["healing_herb"] == rolls  # guaranteed on every kill
    # two rolls over six weapons and a "nothing" weight of 1: each weapon about 2/7 of kills
    assert spoils["w_sword"] / rolls == pytest.approx(1 - (6 / 7) ** 2, abs=0.02)


def test_advanced_jobs_wait_for_their_level_and_prerequisite_jobs():
    from asteria.runtime.game_session import GameSessionError

    _project, game = smoke.load()
    with pytest.raises(GameSessionError, match="level 4"):
        game.set_classes(HERO, ["knight", "sage"])
    smoke.world(game, "GRANT_EXPERIENCE", actor_id=HERO, amount=12000, level_track="level_curve")
    assert game.ensure_actor_progression(HERO).level == 9  # 150 * 8**2 = 9600 <= 12000
    assert game.set_classes(HERO, ["knight", "mystic"]) == ("knight", "mystic")
    assert game.set_classes(HERO, ["knight", "sage"]) == ("knight", "sage")
