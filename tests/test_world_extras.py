"""Map areas, New Game Plus, translations and the music room as the Full Verification demo uses
them, and the engine pieces they need: SET_LOCALE / NEW_GAME_PLUS, behaviour-tree sight under
map areas, the host adopting a New Game Plus save."""

import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

import run_trial_smoke as smoke  # noqa: E402

from asteria.core import Entity, Scene, Transform  # noqa: E402
from asteria.events.world_commands import WorldCommand  # noqa: E402
from asteria.rpg.behavior_tree import BehaviorNode as N  # noqa: E402
from asteria.rpg.behavior_tree import BehaviorTree  # noqa: E402
from asteria.runtime.behavior_tree import BehaviorTreeSystem  # noqa: E402


def _game():
    _project, game = smoke.load()
    return game


def test_the_demo_defines_all_four_and_names_them_for_the_editor():
    db = _game().project.rpg_database
    rules = db.map_rule_sets["trial_areas"]
    assert {r.key for r in rules.rules} == {"region:1", "region:2", "region:3", "region:4"}
    assert rules.region_layer == "Regions"
    assert db.new_game_plus_rules["trial_again"].keep_currency_share == 0.5
    assert set(db.locale_tables) == {"en", "zh-TW"}
    tracks = db.music_tracks.values()
    assert len(tracks) == 5 and all(t.icon_id and t.unlock_switch for t in tracks)


def test_set_locale_switches_the_text_the_player_reads():
    game = _game()
    assert game.tr("language.name") == "English"
    game.world_commands.dispatch(WorldCommand("SET_LOCALE", {"locale": "zh-TW"}))
    assert game.tr("language.name") == "繁體中文"
    assert "英雄之廳" in game.expand_message("\\T[plaque.empty]", plain=True)


def test_new_game_plus_waits_for_the_host_with_what_it_carries():
    game = _game()
    state = game.save.rpg_state
    state.currencies["gold"] = 1000.0
    game.save.event_context.set_switch("ngplus.cleared", True)
    game.save.event_context.set_switch("music.heard.town_theme", True)
    game.save.event_context.set_switch("quest.secret", True)  # not carried
    start = game.project.game_start.instantiate(game.project).rpg_state.currencies.get("gold", 0)
    game.world_commands.dispatch(WorldCommand("NEW_GAME_PLUS", {"rules_id": "trial_again"}))
    fresh = game.pending_new_game
    assert fresh is not None and fresh is not game.save
    assert fresh.rpg_state.currencies["gold"] == start + 500.0
    context = fresh.event_context
    assert context.get_switch("ngplus.cleared") and context.get_switch("music.heard.town_theme")
    assert not context.get_switch("quest.secret")


def test_a_behaviour_tree_foe_sees_less_far_when_the_area_says_so():
    tree = BehaviorTree("watch", N("player_within", {"radius": 40}))
    scale = {"value": 1.0}
    system = BehaviorTreeSystem({"watch": tree}, sight_scale=lambda: scale["value"])
    scene = Scene("S")
    scene.scheduler.add(system)
    hero = scene.add_entity(Entity("Hero"))
    hero.add_component(Transform(30.0, 0.0))
    system.target_id = hero.id
    from asteria.runtime.character_control import AIController2DComponent

    guard = scene.add_entity(Entity("Guard"))
    guard.add_component(Transform(0.0, 0.0))
    ai = guard.add_component(AIController2DComponent())
    ai.driver, ai.tree_id = "behavior_tree", "watch"
    scene.update(0.1)
    assert system.status[guard.id] == "success"  # 30 is within 40
    scale["value"] = 0.5  # in the shadows: 40 becomes 20
    scene.update(0.1)
    assert system.status[guard.id] == "failure"
