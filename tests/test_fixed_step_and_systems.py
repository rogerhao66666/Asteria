"""CB4b: fixed-step simulation and concrete runtime systems (ASTERIA_SPEC §7–§8)."""

import pytest

from asteria.core import Application, ApplicationConfig, Entity, Scene, System, Transform
from asteria.graphics import SpriteClip, SpriteKeyframe
from asteria.runtime import (
    AnimationClipSet,
    AnimationSystem,
    Animator2DComponent,
    Camera2DComponent,
    CameraFollowSystem,
    SpriteRenderer2D,
)


class Recorder(System):
    def __init__(self):
        self.fixed, self.frames = [], []

    def update(self, scene, dt):
        self.frames.append(dt)

    def fixed_update(self, scene, dt):
        self.fixed.append(dt)


def _app(step=0.02, max_steps=5):
    app = Application(backend=None, config=ApplicationConfig(fixed_timestep=step, max_fixed_steps=max_steps))
    scene = Scene("S")
    recorder = Recorder()
    scene.scheduler.add(recorder)
    app.set_scene(scene)
    return app, recorder


def test_fixed_step_accumulates_real_time_into_whole_steps():
    app, recorder = _app()
    assert app.step_fixed(0.05) == 2          # 0.05 = 2 steps + 0.01 left
    assert app.time.fixed_alpha == pytest.approx(0.5)
    assert app.step_fixed(0.01) == 1          # leftover 0.01 + 0.01 = one step
    assert recorder.fixed == [0.02, 0.02, 0.02]
    assert app.time.fixed_steps == 3


def test_slow_frames_are_capped_instead_of_snowballing():
    app, recorder = _app(step=0.01, max_steps=3)
    assert app.step_fixed(0.25) == 3
    assert app.time.fixed_alpha < 1.0
    assert app.step_fixed(0.0) == 0


def test_fixed_step_is_off_by_default_and_must_be_positive():
    assert Application(backend=None).step_fixed(1.0) == 0
    with pytest.raises(ValueError):
        Application(backend=None, config=ApplicationConfig(fixed_timestep=0))


def _animated_entity(scene, clip_set_id="clips"):
    entity = scene.add_entity(Entity("Walker"))
    entity.add_component(Transform())
    entity.add_component(SpriteRenderer2D())
    animator = entity.add_component(Animator2DComponent())
    animator.clip_set_id, animator.default_clip = clip_set_id, "walk"
    return entity


def test_animation_system_advances_frames_and_rebinds_on_clip_change():
    clips = {
        "clips": AnimationClipSet({"walk": SpriteClip("walk", [SpriteKeyframe(0, 0.1), SpriteKeyframe(1, 0.1)], True),
                                   "idle": SpriteClip("idle", [SpriteKeyframe(5, 0.5)], True)}),
    }
    scene = Scene("S")
    system = AnimationSystem(clips.get)
    scene.scheduler.add(system)
    walker = _animated_entity(scene)
    scene.update(0.0)
    assert walker.get(SpriteRenderer2D).frame_index == 0
    scene.update(0.15)
    assert walker.get(SpriteRenderer2D).frame_index == 1
    walker.get(Animator2DComponent).default_clip = "idle"
    scene.update(0.01)
    assert walker.get(SpriteRenderer2D).frame_index == 5

    _animated_entity(scene, clip_set_id="missing").name = "Broken"
    scene.update(0.1)
    scene.update(0.1)
    assert len(system.diagnostics) == 1 and "missing animation clip set" in system.diagnostics[0]


def test_camera_follow_system_tracks_its_target():
    scene = Scene("S")
    system = CameraFollowSystem()
    scene.scheduler.add(system)
    hero = scene.add_entity(Entity("Hero"))
    hero.add_component(Transform(500, 300))
    rig = scene.add_entity(Entity("Camera"))
    rig.add_component(Transform())
    camera = rig.add_component(Camera2DComponent())
    camera.follow_entity_id = hero.id
    scene.update(0.016)
    view = system.camera(rig.id)
    assert (view.x + view.width / 2, view.y + view.height / 2) == (500, 300)
    assert (rig.get(Transform).x, rig.get(Transform).y) == (view.x, view.y)
