"""ENG-02 / ENG-16 / ENG-17 / ANI-05: character controller, input/AI controllers, ground and
one-way
platforms, hitbox/hurtbox, and entity action timelines (hitbox, i-frame, cancel, combo, movement
windows)."""

import pytest

from asteria.core import (
    ComponentRegistry,
    Entity,
    Scene,
    Transform,
    deserialize_component,
    serialize_component,
)
from asteria.gameplay.action_timeline import ActionCue, ActionTimeline
from asteria.runtime.character_control import (
    AIController2DComponent,
    CharacterController2DComponent,
    CharacterControllerSystem,
    Hitbox2DComponent,
    HitboxSystem,
    Hurtbox2DComponent,
    PlayerInput2DComponent,
    PlayerInputSystem,
    register_character_components,
)
from asteria.runtime.collision import Collider2DComponent
from asteria.runtime.components2d import Animator2DComponent
from asteria.runtime.entity_actions import EntityActionSystem
from asteria.runtime.input import InputSnapshot


def _entity(scene, name, x, y, *components):
    entity = scene.add_entity(Entity(name))
    entity.add_component(Transform(x, y))
    for component in components:
        entity.add_component(component)
    return entity


def _solid(scene, name, x, y, w, h, *, one_way=False):
    collider = Collider2DComponent()
    collider.width, collider.height, collider.one_way = w, h, one_way
    return _entity(scene, name, x, y, collider)


def _controller(**fields):
    c = CharacterController2DComponent()
    for k, v in fields.items():
        setattr(c, k, v)
    return c


def _run(scene, seconds, dt=1 / 60):
    for _ in range(round(seconds / dt)):
        scene.update(dt)


def test_topdown_controller_stops_at_walls_and_slides_along_them():
    scene = Scene("S")
    scene.scheduler.add(CharacterControllerSystem())
    _solid(scene, "Wall", 40, 0, 10, 200)
    hero = _entity(scene, "Hero", 0, 0, _controller(speed=60))
    hero.get(CharacterController2DComponent).set_intent(1, 1)
    _run(scene, 1.0)
    t = hero.get(Transform)
    c = hero.get(CharacterController2DComponent)
    assert t.x <= 40 - 5 - 6 + 1e-6 and t.y > 30 and c.hit_wall  # blocked on x, kept sliding on y


def test_side_view_gravity_ground_detection_jump_and_ceiling():
    scene = Scene("S")
    scene.scheduler.add(CharacterControllerSystem())
    floor = _solid(scene, "Floor", 0, 100, 400, 20)
    _solid(scene, "Ceiling", 0, 20, 400, 10)
    hero = _entity(scene, "Hero", 0, 60, _controller(mode="side", gravity=600, jump_speed=400))
    c = hero.get(CharacterController2DComponent)
    _run(scene, 1.0)
    t = hero.get(Transform)
    assert (
        c.grounded and c.ground_id == floor.id and t.y == pytest.approx(90 - 8, abs=0.3)
    )  # resting on the floor top
    c.set_intent(0, 0, jump=True)
    scene.update(1 / 60)
    assert not c.grounded and c.velocity_y < 0
    _run(scene, 0.3)
    assert c.hit_ceiling or t.y >= 25 + 8 - 0.3  # stopped under the ceiling, never through it
    _run(scene, 1.0)
    assert c.grounded


def test_one_way_platform_lets_you_jump_through_and_land_on_top():
    scene = Scene("S")
    scene.scheduler.add(CharacterControllerSystem())
    _solid(scene, "Floor", 0, 200, 400, 20)
    platform = _solid(scene, "Platform", 0, 120, 60, 4, one_way=True)
    hero = _entity(scene, "Hero", 0, 182, _controller(mode="side", gravity=600, jump_speed=420))
    c = hero.get(CharacterController2DComponent)
    _run(scene, 0.2)
    assert c.grounded
    c.set_intent(0, 0, jump=True)
    for _ in range(120):
        scene.update(1 / 60)
        if c.grounded and c.ground_id == platform.id:
            break
    assert c.ground_id == platform.id and hero.get(Transform).y == pytest.approx(118 - 8, abs=0.3)


def test_player_input_and_ai_controllers_drive_the_same_controller():
    from asteria.runtime.field_ai import FieldAIComponent, FieldAISystem

    snapshot = {"value": InputSnapshot({"move_right": 1.0})}
    scene = Scene("S")
    scene.scheduler.add(PlayerInputSystem(lambda: snapshot["value"]))
    scene.scheduler.add(FieldAISystem())
    scene.scheduler.add(CharacterControllerSystem())
    hero = _entity(scene, "Hero", 0, 0, _controller(speed=30), PlayerInput2DComponent())
    _solid(scene, "Wall", 60, 0, 10, 40)
    ai = FieldAIComponent()
    ai.behaviour, ai.target_entity_id, ai.detect_radius = "chase", hero.id, 500
    slime = _entity(scene, "Slime", 100, 0, _controller(speed=40), ai, AIController2DComponent())
    _run(scene, 1.0)
    assert hero.get(Transform).x == pytest.approx(30, abs=0.6)  # input → controller
    assert (
        slime.get(Transform).x >= 60 + 5 + 6 - 1e-6
    )  # the chaser is blocked by the wall like the player
    slime.get(AIController2DComponent).driver = "none"
    slime.get(CharacterController2DComponent).set_intent(
        0, 0
    )  # whoever owns the entity now sets its intent
    x = slime.get(Transform).x
    _run(scene, 0.5)
    assert slime.get(Transform).x == x  # driver none: field AI no longer moves it


def test_hitbox_hits_other_teams_once_per_activation_and_respects_invincibility():
    scene = Scene("S")
    hits = HitboxSystem()
    scene.scheduler.add(hits)
    sword = Hitbox2DComponent()
    sword.team, sword.active, sword.hit_tag = "hero", True, "slash"
    hero = _entity(scene, "Hero", 0, 0, sword)
    guard = Hurtbox2DComponent()
    guard.team = "enemy"
    foe = _entity(scene, "Foe", 8, 0, guard)
    ally_box = Hurtbox2DComponent()
    ally_box.team = "hero"
    _entity(scene, "Ally", 4, 0, ally_box)
    seen = []
    hits.listeners.append(seen.append)
    scene.update(0.016)
    assert [(e.attacker_id, e.target_id, e.hit_tag) for e in hits.events] == [
        (hero.id, foe.id, "slash")
    ]
    scene.update(0.016)
    assert hits.events == [] and len(seen) == 1  # once per activation
    sword.active = False
    scene.update(0.016)
    sword.active = True
    hits.grant_invincibility(foe.id, 0.05)
    scene.update(0.016)
    assert hits.events == []  # i-frames
    scene.update(0.05)
    assert [e.target_id for e in hits.events] == [foe.id]
    sword.active = False
    scene.update(0.016)
    guard.invincible, sword.active = True, True
    scene.update(0.016)
    assert hits.events == []


def test_action_timeline_drives_movement_hitbox_iframes_and_cancel_combo_windows():
    scene = Scene("S")
    hits = HitboxSystem()
    actions = EntityActionSystem(hitboxes=hits)
    for system in (actions, CharacterControllerSystem(), hits):
        scene.scheduler.add(system)
    sword = Hitbox2DComponent()
    sword.team, sword.width = "hero", 20
    hero = _entity(
        scene,
        "Hero",
        0,
        0,
        _controller(speed=60),
        sword,
        Animator2DComponent(),
        Hurtbox2DComponent(),
    )
    target = Hurtbox2DComponent()
    target.team = "enemy"
    foe = _entity(scene, "Foe", 30, 0, target)
    timeline = ActionTimeline(
        "lunge",
        [
            ActionCue("pose", 0.0, "animation", {"clip": "attack"}),
            ActionCue("step", 0.0, "movement", {"x": 1, "y": 0, "duration": 0.3}),
            ActionCue("dodge", 0.0, "iframe", {"duration": 0.2}),
            ActionCue("swing", 0.2, "hitbox", {"duration": 0.15, "hit_tag": "lunge"}),
            ActionCue("spark", 0.2, "vfx", {"asset_id": "battle.fx.slash"}),
            ActionCue("combo", 0.3, "combo_window", {"duration": 0.2, "next": "lunge_2"}),
            ActionCue("recover", 0.35, "cancel_window", {"duration": 0.2}),
        ],
    )
    actions.play(hero.id, timeline)
    scene.update(0.1)
    assert hero.get(Animator2DComponent).default_clip == "attack" and hits.invincible(hero.id)
    assert not sword.active and not actions.cancel(hero.id, scene)  # no cancel before its window
    seen, cues = [], []
    for _ in range(4):
        scene.update(0.05)
        seen += hits.events
        cues += actions.events
    assert sword.active and [e.hit_tag for e in seen] == ["lunge"] and seen[0].target_id == foe.id
    assert hero.get(Transform).x == pytest.approx(
        60 * 0.3, abs=1.0
    )  # moved only during the movement window
    assert [(e.cue_id, e.payload["asset_id"]) for e in cues if e.kind == "vfx"] == [
        ("spark", "battle.fx.slash")
    ]
    assert actions.window_open(hero.id, "combo") and actions.combo_next(hero.id) == "lunge_2"
    scene.update(0.06)
    assert not sword.active and actions.window_open(hero.id, "cancel")
    assert actions.cancel(hero.id, scene) and not actions.active(hero.id)


def test_new_components_serialize_and_old_collider_records_still_load():
    registry = register_character_components(ComponentRegistry())
    registry.register(Collider2DComponent)
    c = _controller(mode="side", speed=90.0)
    restored = deserialize_component(serialize_component(c), registry)
    assert restored.mode == "side" and restored.speed == 90 and not restored.grounded
    old = {"type": "asteria.Collider2D", "version": 1, "fields": {"width": 8.0, "height": 8.0}}
    assert deserialize_component(old, registry).one_way is False


def test_controllers_actions_and_hits_run_in_the_game_session_field_update(runtime):
    from asteria.runtime.field_ai import FieldAIComponent

    game = runtime.game
    game.set_player_position(0.0, 0.0)
    hurt = Hurtbox2DComponent()
    hurt.team = "hero"
    game.player.add_component(hurt)
    ai = FieldAIComponent()
    ai.behaviour, ai.detect_radius = "chase", 500.0
    claw = Hitbox2DComponent()
    claw.team, claw.width = "enemy", 24.0
    imp = _entity(
        game.scene, "Imp", 60.0, 0.0, _controller(speed=40.0), ai, AIController2DComponent(), claw
    )
    for _ in range(60):
        game.field_update(1 / 60)
    assert 10.0 < imp.get(Transform).x < 60.0  # chased through its controller
    game.entity_actions.play(
        imp.id, ActionTimeline("bite", [ActionCue("bite", 0.0, "hitbox", {"duration": 0.2})])
    )
    found = []
    for _ in range(30):
        game.field_update(1 / 60)
        found += game.hits.events
    assert [(e.attacker_id, e.target_id) for e in found] == [(imp.id, game.player.id)]
    assert not claw.active and not game.entity_actions.active(imp.id)


def test_project_action_timelines_are_authored_as_records_and_played_from_events(runtime):
    from asteria.editor import EditorDocument
    from asteria.editor.integrated_authoring import IntegratedAuthoringControllers
    from asteria.events import EventInstruction, EventProgram

    game = runtime.game
    document = EditorDocument()
    document.set_project(game.project)
    adapter = {
        a.category_id: a for a in IntegratedAuthoringControllers(document).rpg_categories()
    }["action_timelines"]
    lunge = ActionTimeline(
        "lunge", [ActionCue("step", 0.0, "movement", {"x": 1, "y": 0, "duration": 0.5})]
    )
    adapter.create("lunge", lunge)
    data = adapter.encode(adapter.get("lunge"))
    data["cues"][0]["payload"]["duration"] = 0.25
    adapter.edit("lunge", adapter.decode(data))
    assert game.project.gameplay_library.timelines["lunge"].cues[0].payload["duration"] == 0.25
    imp = _entity(game.scene, "Imp", 0.0, 30.0, _controller(speed=40.0))
    game.project.event_programs.register(
        "imp_lunge",
        EventProgram(
            (
                EventInstruction(
                    "WORLD",
                    {"command": "PLAY_ACTION", "args": {"entity": "Imp", "timeline_id": "lunge"}},
                ),
            )
        ),
    )
    game.events.start("imp_lunge")
    game.update_events(0.0)
    for _ in range(30):
        game.field_update(1 / 60)
    assert imp.get(Transform).x == pytest.approx(40 * 0.25, abs=0.8) and not game.event_errors
    document.undo()
    assert game.project.gameplay_library.timelines["lunge"].cues[0].payload["duration"] == 0.5


def test_four_players_use_independent_entity_input_snapshots():
    scene = Scene("Network field")
    inputs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    entities = [
        _entity(scene, str(i), 0, 0, PlayerInput2DComponent(), CharacterController2DComponent())
        for i in range(4)
    ]
    mapping = {
        e.id: InputSnapshot(
            {
                "move_right": max(x, 0),
                "move_left": max(-x, 0),
                "move_down": max(y, 0),
                "move_up": max(-y, 0),
            }
        )
        for e, (x, y) in zip(entities, inputs)
    }
    system = PlayerInputSystem(
        lambda: InputSnapshot({"move_x": 1}), entity_snapshot_provider=lambda e: mapping[e.id]
    )
    system.update(scene, 0.05)
    assert [
        (
            e.get(CharacterController2DComponent).intent_x,
            e.get(CharacterController2DComponent).intent_y,
        )
        for e in entities
    ] == inputs
