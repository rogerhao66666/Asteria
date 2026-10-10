"""CB8: animation state machine, transition parameters and runtime frame events (ASTERIA_SPEC §11)."""

import json

import pytest

from asteria.core import Entity, Scene, Transform
from asteria.graphics import SpriteClip, SpriteKeyframe
from asteria.runtime import (
    AnimationClipSet,
    AnimationCondition,
    AnimationStateMachine,
    AnimationStateMachineDefinition,
    AnimationSystem,
    AnimationTransition,
    Animator2DComponent,
    AnimatorState,
    SpriteRenderer2D,
)


def _clips():
    return {
        "idle": SpriteClip("idle", [SpriteKeyframe(0, 0.5)], True),
        "walk": SpriteClip(
            "walk",
            [SpriteKeyframe(1, 0.1, ("footstep",)), SpriteKeyframe(2, 0.1), SpriteKeyframe(3, 0.1, ("footstep",))],
            True,
        ),
        "attack": SpriteClip("attack", [SpriteKeyframe(4, 0.1), SpriteKeyframe(5, 0.1, ("hit",))], False),
    }


def _definition():
    return AnimationStateMachineDefinition(
        states={"idle": "idle", "walk": "walk", "attack": "attack"},
        initial="idle",
        transitions=(
            AnimationTransition("idle", "walk", (AnimationCondition("speed", ">", 0.1),)),
            AnimationTransition("walk", "idle", (AnimationCondition("speed", "<=", 0.1),)),
            AnimationTransition("*", "attack", (AnimationCondition("attack"),), priority=10),
            AnimationTransition("attack", "idle", when_finished=True),
        ),
        parameters={"speed": 0.0},
        triggers=("attack",),
    )


def test_keyframe_events_fire_on_entry_including_loops():
    animator = AnimatorState(_clips()["walk"])
    assert animator.drain_events() == [("walk", 0, "footstep")]
    animator.update(0.35)  # frames 1, 2 then wrap to 0
    assert animator.drain_events() == [("walk", 2, "footstep"), ("walk", 0, "footstep")]


def test_parameters_triggers_any_state_and_wait_for_finish():
    clips = AnimationClipSet(_clips())
    animator = AnimatorState(clips.get("idle"))
    machine = AnimationStateMachine(_definition(), clips, animator)
    machine.set("speed", 1.0)
    assert machine.update(0.01) == "walk" and animator.clip.name == "walk"
    machine.trigger("attack")
    assert machine.update(0.01) == "attack" and machine.parameters["attack"] is False  # consumed
    assert machine.update(0.05) == "attack"  # attack still playing
    machine.update(0.3)  # attack finishes
    assert animator.finished
    assert machine.update(0.01) == "idle"  # waits for finish, ignores "speed" ordering
    with pytest.raises(KeyError):
        machine.set("nope", 1)


def test_definition_validation_and_round_trip():
    definition = _definition()
    assert AnimationStateMachineDefinition.from_data(json.loads(json.dumps(definition.to_data()))) == definition
    with pytest.raises(ValueError):
        AnimationStateMachineDefinition({"a": "idle"}, "missing")
    with pytest.raises(ValueError):
        AnimationStateMachineDefinition({"a": "idle"}, "a", (AnimationTransition("a", "b"),))
    with pytest.raises(ValueError):
        AnimationStateMachineDefinition(
            {"a": "idle", "b": "walk"}, "a", (AnimationTransition("a", "b", (AnimationCondition("x"),)),)
        )
    with pytest.raises(ValueError):
        AnimationStateMachine(
            AnimationStateMachineDefinition({"a": "fly"}, "a"),
            AnimationClipSet(_clips()),
            AnimatorState(_clips()["idle"]),
        )


def test_animation_system_drives_machines_and_publishes_frame_events():
    clips = {"hero": AnimationClipSet(_clips(), _definition())}
    scene = Scene("S")
    system = AnimationSystem(clips.get)
    scene.scheduler.add(system)
    hero = scene.add_entity(Entity("Hero"))
    hero.add_component(Transform())
    hero.add_component(SpriteRenderer2D())
    spec = hero.add_component(Animator2DComponent())
    spec.clip_set_id, spec.default_clip = "hero", "idle"
    heard = []
    system.listeners.append(lambda entity_id, clip, index, name: heard.append((clip, name)))
    scene.update(0.01)
    system.set_parameter(hero.id, "speed", 2.0)
    scene.update(0.01)
    assert system.state_machine(hero.id).state == "walk"
    assert hero.get(SpriteRenderer2D).frame_index == 1 and ("walk", "footstep") in heard
    system.trigger(hero.id, "attack")
    scene.update(0.15)
    assert ("attack", "hit") in heard and hero.get(SpriteRenderer2D).frame_index == 5


def test_reference_loader_reads_events_and_state_machine(tmp_path):
    from asteria.reference_data import load_animation_set

    data = {
        "clips": {
            name: {
                "loop": clip.loop,
                "keyframes": [
                    {"frame_index": k.frame_index, "duration": k.duration, "events": list(k.events)}
                    for k in clip.keyframes
                ],
            }
            for name, clip in _clips().items()
        },
        "state_machine": _definition().to_data(),
    }
    path = tmp_path / "hero_animation.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    loaded = load_animation_set(path)
    assert loaded.get("walk").keyframes[0].events == ("footstep",)
    assert loaded.state_machine == _definition()
