"""RPG-09: behavior tree runtime for field AI, its editor API and GUI."""

import pytest

from asteria.core import Entity, Scene, Transform
from asteria.rpg.behavior_tree import BehaviorNode as N
from asteria.rpg.behavior_tree import BehaviorTree
from asteria.runtime.behavior_tree import BehaviorTreeSystem
from asteria.runtime.character_control import (
    AIController2DComponent,
    CharacterController2DComponent,
    CharacterControllerSystem,
)

GUARD = BehaviorTree(
    "guard",
    N(
        "selector",
        children=(
            N("sequence", children=(N("player_within", {"radius": 40}), N("chase", {"arrive": 4, "lose_radius": 80}))),
            N("patrol", {"points": "0,0; 20,0"}),
        ),
    ),
)


def _scene(tree, *, controller=True, x=0.0):
    scene = Scene("S")
    bt = BehaviorTreeSystem({tree.tree_id: tree}, target_id="hero")
    scene.scheduler.add(bt)
    scene.scheduler.add(CharacterControllerSystem())
    hero = scene.add_entity(Entity("Hero"))
    hero.add_component(Transform(200.0, 0.0))
    hero.id = "hero" if hasattr(hero, "id") and False else hero.id
    bt.target_id = hero.id
    guard = scene.add_entity(Entity("Guard"))
    guard.add_component(Transform(x, 0.0))
    ai = AIController2DComponent()
    ai.driver, ai.tree_id = "behavior_tree", tree.tree_id
    guard.add_component(ai)
    if controller:
        c = CharacterController2DComponent()
        c.speed = 40.0
        guard.add_component(c)
    return scene, bt, hero, guard


def _run(scene, seconds, dt=1 / 30):
    for _ in range(round(seconds / dt)):
        scene.update(dt)


def test_guard_patrols_chases_on_sight_and_returns_home():
    scene, bt, hero, guard = _scene(GUARD)
    _run(scene, 0.4)
    assert 0 < guard.get(Transform).x < 20  # patrolling toward (20, 0)
    hero.get(Transform).x = 50.0
    _run(scene, 1.0)
    assert abs(guard.get(Transform).x - 50.0) <= 4.5  # chased the player within arrive range
    hero.get(Transform).x = 400.0
    _run(scene, 2.0)
    assert -1 <= guard.get(Transform).x <= 21  # lost the player, back to patrolling between 0 and 20
    assert bt.status[guard.id] == "running"


def test_wait_cooldown_repeater_parallel_and_switch_actions():
    switches = {}
    tree = BehaviorTree(
        "t",
        N(
            "sequence",
            children=(
                N("wait", {"seconds": 0.5}),
                N("cooldown", {"seconds": 1.0}, children=(N("set_switch", {"name": "rang"}),)),
                N(
                    "parallel",
                    {"success_count": 1},
                    children=(N("chance", {"probability": 1.0}), N("wait", {"seconds": 9})),
                ),
            ),
        ),
    )
    scene, bt, hero, guard = _scene(tree, controller=False)
    bt.set_switch = lambda name, value: switches.__setitem__(name, value)
    seen = []
    for _ in range(18):  # 0.6 s
        scene.update(1 / 30)
        seen.append(bt.status[guard.id])
        if len(seen) == 9:
            assert switches == {}  # still waiting at 0.3 s
    assert switches == {"rang": True} and "success" in seen  # parallel succeeded once one child did


def test_entities_without_a_controller_are_stepped_directly_and_bad_trees_fail():
    scene, bt, hero, guard = _scene(
        BehaviorTree("go", N("move_to", {"x": 10, "y": 0, "speed": 20, "arrive": 0.01})), controller=False
    )
    _run(scene, 1.0)
    assert guard.get(Transform).x == pytest.approx(10.0, abs=0.01) and bt.status[guard.id] == "success"
    guard.get(AIController2DComponent).tree_id = "missing"
    scene.update(0.1)
    assert bt.status[guard.id] == "failure"
    with pytest.raises(ValueError):
        N("sequence")  # composites need children
    with pytest.raises(ValueError):
        N("wait", children=(N("wait"),))  # leaves take none


def test_a_tree_in_the_game_session_starts_its_encounter(runtime):
    game = runtime.game
    db = game.project.rpg_database
    db.add_behavior_tree(
        BehaviorTree(
            "ambusher",
            N(
                "sequence",
                children=(N("player_within", {"radius": 30}), N("start_encounter", {"encounter_id": "boss_room"})),
            ),
        )
    )
    game.project.validate()
    game.set_player_position(0.0, 0.0)
    imp = game.scene.add_entity(Entity("Imp"))
    imp.add_component(Transform(100.0, 0.0))
    ai = AIController2DComponent()
    ai.driver, ai.tree_id = "behavior_tree", "ambusher"
    imp.add_component(ai)
    game.field_update(0.1)
    assert game.mode == "field" and game.behavior_trees.status[imp.id] == "failure"
    imp.get(Transform).x = 20.0
    assert game.field_update(0.1) == "boss_room" and game.mode == "battle"


def test_editor_api_and_gui_edit_trees_with_undo():
    pytest.importorskip("PySide6")
    from pathlib import Path

    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor.behavior_tree_widget import BehaviorTreeEditorWidget
    from asteria.project import Project

    QApplication.instance() or QApplication([])
    ref = Path(__file__).parents[1] / "reference_projects/complex_reference_rpg/project.asteria.json"
    document = EditorDocument()
    document.set_project(Project.load_json(ref, document.component_registry), file_path=ref)
    widget = BehaviorTreeEditorWidget(document)
    assert widget.create_tree("sentry", "selector")
    assert widget.add_child("sequence") and widget.select_node((1,))
    assert widget.add_child("player_within") and widget.select_node((1, 1))
    widget.fields["radius"].setText("72")
    assert widget.apply_params()
    tree = document.project.rpg_database.behavior_trees["sentry"]
    assert tree.node((1, 1)).params["radius"] == 72.0 and widget.nodes.topLevelItemCount() == 1
    widget.select_node((1, 1))
    assert widget.move_node(-1) and tree is not document.project.rpg_database.behavior_trees["sentry"]
    assert document.project.rpg_database.behavior_trees["sentry"].node((1, 0)).kind == "player_within"
    widget.select_node(())
    assert not widget.remove_node()  # the root stays
    assert widget.select_node((1, 0)) and widget.remove_node()
    for _ in range(5):
        document.undo()
    assert [c.kind for c in document.project.rpg_database.behavior_trees["sentry"].root.children] == ["wait"]
    roundtrip = Project.from_data(document.project.to_data(), document.component_registry)
    assert "sentry" in roundtrip.rpg_database.behavior_trees
