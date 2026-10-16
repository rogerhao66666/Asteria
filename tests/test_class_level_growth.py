"""Class growth per level (a warrior gains more attack each level) and level-up points that
players spend to specialise (any named balance, e.g. ``stat_points``)."""

import pytest
from test_session_events import _session

from asteria.rpg import ClassDefinition


def test_class_definition_level_growth_round_trips_and_defaults():
    plain = ClassDefinition("c", "C").to_data()
    assert "level_growth" not in plain
    grown = ClassDefinition("c", "C", level_growth={"attack": 2.5})
    assert ClassDefinition.from_data(grown.to_data()).level_growth == {"attack": 2.5}
    with pytest.raises(ValueError):
        ClassDefinition("c", level_growth={"attack": float("nan")})


def _game(growth):
    project, game = _session()
    db = project.rpg_database
    hero = game.save.rpg_state.party_active_actor_ids[0]
    actor = db.actors[hero]
    class_id = actor.class_assignments[0].class_id
    db.classes[class_id] = ClassDefinition(
        class_id,
        db.classes[class_id].display_name,
        stat_bonuses=dict(db.classes[class_id].stat_bonuses),
        resource_bonuses=dict(db.classes[class_id].resource_bonuses),
        granted_tags=db.classes[class_id].granted_tags,
        granted_abilities=db.classes[class_id].granted_abilities,
        level_growth=growth,
    )
    return game, hero


def _stat(game, hero, name="power"):
    return game.resolve_actor_build(hero).stats.get(name)


def _level(game, hero):
    return game.save.rpg_state.actor_progression[hero].level


def test_stats_grow_with_level_by_the_class_rate():
    game, hero = _game({"power": 3.0})
    game.grant_actor_experience(hero, 0)  # makes sure a progression record exists
    before, start = _stat(game, hero), _level(game, hero)
    game.grant_actor_experience(hero, 4000, level_threshold=1000)
    gained = _level(game, hero) - start
    assert gained >= 3
    assert _stat(game, hero) == pytest.approx(before + 3.0 * gained)


def test_different_classes_grow_differently():
    results = []
    for rate in (1.0, 4.0):
        game, hero = _game({"power": rate})
        game.grant_actor_experience(hero, 0)
        before, start = _stat(game, hero), _level(game, hero)
        game.grant_actor_experience(hero, 3000, level_threshold=1000)
        results.append((_stat(game, hero) - before) / (_level(game, hero) - start))
    assert results == pytest.approx([1.0, 4.0])


def test_no_growth_leaves_stats_alone():
    game, hero = _game({})
    game.grant_actor_experience(hero, 0)
    base = _stat(game, hero)
    game.grant_actor_experience(hero, 3000, level_threshold=1000)
    assert _stat(game, hero) == base


def test_level_up_grants_any_named_points():
    game, hero = _game({})
    game.grant_actor_experience(hero, 0)
    start = _level(game, hero)
    before = dict(game.save.rpg_state.actor_progression[hero].points)
    game.grant_actor_experience(
        hero,
        3000,
        level_threshold=1000,
        points_per_level={"stat_points": 5, "skill_points": 1},
    )
    state = game.save.rpg_state.actor_progression[hero]
    gained = state.level - start
    assert gained >= 2
    assert state.points["stat_points"] - before.get("stat_points", 0) == 5 * gained
    assert state.points["skill_points"] - before.get("skill_points", 0) == gained


def test_class_editor_api_keeps_growth_and_icon():
    from asteria.core import Scene
    from asteria.editor import EditorDocument
    from asteria.editor.rpg_actor_class_authoring import RpgActorClassAuthoringController
    from asteria.project import Project

    project = Project("Game")
    project.add_scene(Scene("Main"))
    api = RpgActorClassAuthoringController(EditorDocument(project))
    db = project.rpg_database
    api.create_class("w", "Warrior", level_growth={"attack": 2.0})
    assert db.classes["w"].level_growth == {"attack": 2.0}
    api.edit_class("w", display_name="Fighter", icon_id="sword")
    assert db.classes["w"].level_growth == {"attack": 2.0}
    assert db.classes["w"].icon_id == "sword"
    api.edit_class("w", level_growth={"attack": 3.0, "defense": 1.0})
    assert db.classes["w"].level_growth == {"attack": 3.0, "defense": 1.0}
    assert db.classes["w"].icon_id == "sword"
    assert api.duplicate_class("w", "w2").level_growth == {"attack": 3.0, "defense": 1.0}
