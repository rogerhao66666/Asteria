"""Full Verification B12: loot, steal, limits, mastery, boost points from the fight, a capturable
pet
that fights and evolves, quests, achievements and enemy levels - all through the real session."""

import random
import sys
from collections import Counter
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

import run_trial_smoke as smoke  # noqa: E402

HERO, BP, HP, SP = "hero_01", "bp", "vitality", "technique"
BOSS = "crimson_warlord"


def _game(job="brave", encounter="boss_room"):
    _project, game = smoke.load()
    game.refine_rng = random.Random(3)
    smoke.prepare(game, Counter(), job)
    game.save.rpg_state.equipment_bag.clear()  # D98: the demo starts with spare gear
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
    game = _game("brave")
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
    game = _game("brave")
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
    game = _game("brave", "swarm")
    pool = game.battle.battle_resources
    pool.change(HERO, BP, -pool.current(HERO, BP))
    wisp = next(e for e in game.active_enemy_ids() if not e.startswith(BOSS))
    subject = game.battle.member(wisp).subject
    subject.resources.set_current(HP, 1)
    subject.tags.remove("trait.dodge")  # wisps dodge some blows; this one must land
    game.use_ability(HERO, "attack_sword", (wisp,))
    assert pool.current(HERO, BP) >= 1


def test_a_goblin_can_be_captured_fights_as_a_unit_and_evolves():
    game = _game("brave", "woods_ambush")
    wisp = next(e for e in game.active_enemy_ids() if e.startswith("goblin_slinger"))
    assert game.capture_chance(wisp) is not None

    class Lucky:
        def random(self):
            return 0.0

    assert game.attempt_capture(HERO, wisp, rng=Lucky())
    pet = game.active_pet()
    assert pet.species_id == "slinger" and pet.level == 2
    _win(game)
    game.start_encounter("boss_room")
    unit = f"pet:{pet.instance_id}"
    assert unit in game.battle.members
    assert {"pet_shot", "pet_bandage"} <= set(game.battle.member(unit).ability_ids)
    pet.level = 5
    assert game.evolve_pet(pet.instance_id) == "war_slinger"


def test_quests_achievements_and_enemy_levels():
    game = _game("brave")
    state = game.save.rpg_state
    log = game.quest_log
    for quest_id in ("q_patrol", "q_beast", "q_crypt"):  # the chain before it
        log.start(quest_id)
        for objective in log._definition(quest_id).objectives:
            log.record_defeat(objective.target, objective.required)
    log.start("slay_vaelor")
    state.inventory.add("healing_herb", 3)
    assert game.enemy_levels  # the boss and its wisps have levels
    assert game.difficulty == "legend"  # the demo's default: foes far above the party
    game.set_difficulty("hard")
    _win(game)
    log = game.quest_log
    assert log.status("slay_vaelor") == "completed"  # the herbs are in the bag, the warlord fell
    game.refresh_achievements()
    unlocked = set(game.world.achievements)
    assert {"warlord_slayer", "quest_done"} <= unlocked
    assert "bone_hunter" not in unlocked  # ten wisps is more than one fight
    with pytest.raises(Exception):  # noqa: B017 - an unknown setting is refused
        game.set_difficulty("impossible")


def test_drop_chances_follow_the_tables_weights():
    from asteria.rpg.drop_tables import roll_drop_table

    _project, game = smoke.load()
    tables = game.project.rpg_database.drop_tables
    rng, rolls, counts = random.Random(5), 20_000, Counter()
    for _ in range(rolls):
        got = roll_drop_table(tables["acolyte_drops"], rng)
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


def test_skills_evolve_as_the_party_wins_battles():
    game = _game("brave")
    build = lambda: set(game.resolve_actor_build(HERO).abilities)  # noqa: E731
    assert "brave_slash" in build() and "brave_slash_ii" not in build()
    assert "arsenal_barrage_ii" not in build()  # that one waits for rank 3 of the track
    _win(game)  # the boss pays battle experience (more with the whole party hired)
    assert "brave_slash_ii" in build() and "brave_slash" not in build()
    game.start_encounter("boss_room")
    assert "brave_slash_ii" in game.battle.member(HERO).ability_ids


def test_a_skill_calls_a_summon_that_fights_beside_the_party():
    _project, game = smoke.load()
    smoke.prepare(game, Counter(), "brave")
    game.join_party("hero_03")  # Vesper the necromancer joins in the story
    game.start_encounter("boss_room")
    assert "spirit_knight" not in game.battle.members
    game.battle.member("hero_03").subject.resources.set_current(SP, 300)
    game.use_ability("hero_03", "call_spirit", None)
    assert "spirit_knight" in game.battle.members
    assert {"spirit_cleave", "spirit_ward"} <= set(game.battle.member("spirit_knight").ability_ids)
    state = game.battle.combatants.state("spirit_knight")
    assert state.summon_owner_id == "hero_03"
    boss = game.active_enemy_ids()[0]
    game.use_ability("spirit_knight", "spirit_cleave", (boss,))
    game.battle.member("hero_03").subject.resources.set_current(SP, 300)
    with pytest.raises(Exception, match="already in the battle"):  # noqa: B017
        game.use_ability("hero_03", "call_spirit", None)


def test_a_transformation_changes_stats_tags_and_skills_and_can_be_undone():
    game = _game("brave")
    boss = game.active_enemy_ids()[0]
    boss_pool = game.battle.member(boss).subject.resources

    def blow():
        boss_pool.set_current(HP, 900000)
        game.battle.member(HERO).subject.resources.set_current(SP, 280)
        game.use_ability(HERO, "attack_sword", (boss,))
        return 900000 - boss_pool.current(HP)

    plain = [blow() for _ in range(6)]
    assert "dragon_claw" not in game.battle.member(HERO).ability_ids
    pool = game.battle.battle_resources
    pool.change(HERO, BP, 2 - pool.current(HERO, BP))
    game.use_ability(HERO, "dragon_form", None)
    member = game.battle.member(HERO)
    assert {"dragon_claw", "dragon_breath", "dragon_revert"} <= set(member.ability_ids)
    assert member.subject.tags.contains("form.dragon")
    dragon = [blow() for _ in range(6)]
    assert sum(dragon) > sum(plain)  # the form hits harder
    game.use_ability(HERO, "dragon_claw", (boss,))
    game.use_ability(HERO, "dragon_revert", None)
    member = game.battle.member(HERO)
    assert "dragon_claw" not in member.ability_ids
    assert not member.subject.tags.contains("form.dragon")


def test_the_swarm_can_be_fled_but_the_warlords_hall_cannot():
    from asteria.runtime.game_session import GameSessionError

    game = _game("brave", "boss_room")
    assert "no_escape" in game.escape_unavailable()
    with pytest.raises(GameSessionError, match="cannot escape"):
        game.attempt_escape(HERO)
    game = _game("brave", "swarm")
    assert game.escape_unavailable() == "" and 0 < game.escape_chance() <= 1
    rng = random.Random(1)
    for _ in range(50):
        if game.mode != "battle":
            break
        game.attempt_escape(HERO, rng=rng)
    assert game.mode == "field"


def test_a_save_after_a_fight_with_a_pet_loads_again():
    from asteria.runtime.game_save import GameRuntimeSave

    project, game = smoke.load()
    game.add_pet("slinger", level=2)
    game.start_encounter("woods_ambush")
    assert any(m.startswith("pet:") for m in game.battle.members)
    _win(game)
    game.sync_world_state()
    restored = GameRuntimeSave.from_data(game.save.to_data(), project)
    assert [p.species_id for p in restored.rpg_state.pets] == ["slinger"]
    assert not any(k.startswith("pet:") for k in restored.rpg_state.actor_snapshots)


def test_a_quest_finished_by_a_fight_is_completed_for_the_events_at_once():
    game = _game("brave", "woods_ambush")
    game.start_quest("q_patrol")
    _win(game)  # three slingers
    game.start_encounter("woods_patrol")
    _win(game)  # two more: the contract asked for four
    context = game.save.event_context
    assert context.get_switch("quest.q_patrol.completed")
    assert not context.get_switch("quest.q_patrol.active")


def test_a_fight_can_end_when_its_leader_falls():
    game = _game("brave", "woods_boss")
    beast = next(e for e in game.active_enemy_ids() if e.startswith("goblin_beast"))
    assert not game.battle.resolve_outcome().finished
    game.battle.member(beast).subject.resources.set_current(HP, 0)
    outcome = game.battle.resolve_outcome()
    assert outcome.finished and "heroes" in outcome.winning_sides
    assert "beast_down" in outcome.objective_ids  # the slingers beside him do not matter


def test_a_fight_without_that_leader_is_not_ended_by_his_objective():
    game = _game("brave", "crypt_patrol")
    assert not game.battle.resolve_outcome().finished
