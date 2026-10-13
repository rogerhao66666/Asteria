"""ANI-02: graphical animation state machine editor; the authored machine drives the runtime clip
set."""

from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.editor.animation_state_machine_authoring import (
    AnimationStateMachineAuthoring,
    StateMachineAuthoringError,
)
from asteria.project import Project

REF = Path(__file__).parents[1] / "reference_projects/complex_reference_rpg/project.asteria.json"
SHEET = "battle.combatant.hero_01"


@pytest.fixture
def api():
    document = EditorDocument()
    document.set_project(Project.load_json(REF, document.component_registry), file_path=REF)
    return AnimationStateMachineAuthoring(document)


def _build(api):
    api.create(SHEET)
    api.add_state(SHEET, "attack", "attack", (200, 40))
    api.add_state(SHEET, "down", "ko")
    api.add_parameter(SHEET, "attacking", False)
    api.add_parameter(SHEET, "hit", trigger=True)
    api.add_transition(SHEET, "idle", "attack", conditions=[("attacking", "==", True)])
    api.add_transition(SHEET, "attack", "idle", when_finished=True)
    api.add_transition(SHEET, "*", "down", conditions=[("hit", "==", True)], priority=5)


def test_states_transitions_and_parameters_are_undoable_edits(api):
    _build(api)
    definition = api.definition(SHEET)
    assert definition.initial == "idle" and set(definition.states) == {"idle", "attack", "down"}
    assert api.layout(SHEET)["attack"] == [200.0, 40.0]
    assert api.simulate(
        SHEET,
        [
            (0.1, {"attacking": True}, []),
            (0.1, {"attacking": False}, []),
            (3, {}, []),
            (0.1, {}, []),
        ],
    ) == [
        "idle",
        "attack",
        "attack",
        "attack",
        "idle",
    ]
    assert (
        api.simulate(SHEET, [(0.1, {}, ["hit"])])[-1] == "down"
    )  # any-state transition with a trigger
    with pytest.raises(StateMachineAuthoringError, match="does not have"):
        api.add_state(SHEET, "fly", "fly_clip_missing")
    with pytest.raises(StateMachineAuthoringError, match="initial"):
        api.remove_state(SHEET, "idle")
    api.remove_state(SHEET, "down")
    assert all("down" not in (t.source, t.target) for t in api.definition(SHEET).transitions)
    for _ in range(9):  # one step per edit (adding a state at a position included)
        api.document.undo()
    assert api.definition(SHEET) is None


def test_the_runtime_clip_set_carries_the_authored_machine(api):
    from asteria.core import Entity, Scene, Transform
    from asteria.runtime.battle_visuals import BattleVisualResolver
    from asteria.runtime.components2d import Animator2DComponent, SpriteRenderer2D
    from asteria.runtime.systems import AnimationSystem

    _build(api)
    resolver = BattleVisualResolver(
        api.document.project, lambda uri: api.animation.image_size(SHEET)
    )
    assert resolver.clip_set(SHEET).state_machine is not None
    scene = Scene("S")
    system = AnimationSystem(resolver.clip_set)
    scene.scheduler.add(system)
    hero = scene.add_entity(Entity("Hero"))
    hero.add_component(Transform())
    hero.add_component(SpriteRenderer2D())
    animator = Animator2DComponent()
    animator.clip_set_id, animator.default_clip = SHEET, "idle"
    hero.add_component(animator)
    scene.update(0.05)
    machine = system.state_machine(hero.id)
    assert machine.state == "idle"
    system.set_parameter(hero.id, "attacking", True)
    scene.update(0.05)
    assert machine.state == "attack" and system.binding(hero.id).animator.clip.name == "attack"


def test_graph_editor_builds_moves_and_previews(api):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.animation_state_machine_widget import AnimationStateMachineWidget

    QApplication.instance() or QApplication([])
    widget = AnimationStateMachineWidget(api.document)
    widget.refresh(select=SHEET)
    assert widget._try(lambda: widget.api.create(SHEET), "Created")
    assert widget.add_state("attack", "attack")
    assert set(widget.graph.nodes) == {"idle", "attack"}
    widget.param_name.setText("attacking")
    widget.param_default.setText("false")
    assert widget.add_parameter()
    widget.source.setCurrentText("idle")
    widget.target.setCurrentText("attack")
    widget.conditions.setText("attacking == true")
    assert widget.add_transition() and widget.transitions.count() == 1
    widget.graph.nodeMoved.emit("attack", 300.0, 120.0)
    assert widget.api.layout(SHEET)["attack"] == [300.0, 120.0]
    assert widget.graph.nodes["attack"].pos().x() == 300.0
    widget.preview_values.setText("attacking=true")
    assert widget.preview_step(0.1) == "attack" and "attack" in widget.preview_label.text()
    assert widget.parse_conditions("speed > 0.5; grounded") == [
        ("speed", ">", 0.5),
        ("grounded", "==", True),
    ]
