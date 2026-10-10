"""Concrete runtime Systems (ASTERIA_SPEC §7 system-oriented runtime).

Add them to ``Scene.scheduler``; ``Scene.update`` then runs them in ``order``.
"""

from __future__ import annotations

from asteria.core import System, Transform

from .animation_binding import Animator2DBinding
from .animation_state_machine import AnimationStateMachine
from .camera import Camera2D, CameraFollow2D
from .components2d import Animator2DComponent, Camera2DComponent, SpriteRenderer2D


class AnimationSystem(System):
    """Advances every enabled Animator2D and writes its frame to the SpriteRenderer2D.

    Bindings are created lazily and rebuilt when the entity's clip set or
    default clip changes. Entities whose clip set cannot be resolved are
    skipped and reported once in ``diagnostics``.
    """

    order = 100

    def __init__(self, resolve_clip_set):
        self.resolve_clip_set = resolve_clip_set
        self._bindings: dict[str, tuple[tuple[str, str], Animator2DBinding]] = {}
        self._machines: dict[str, AnimationStateMachine] = {}
        self.diagnostics: list[str] = []
        self._reported: set[tuple[str, str]] = set()
        # (entity_id, clip name, keyframe index, event name) entered during the last update.
        self.frame_events: list[tuple[str, str, int, str]] = []
        self.listeners = []

    def binding(self, entity_id):
        value = self._bindings.get(str(entity_id))
        return None if value is None else value[1]

    def state_machine(self, entity_id):
        return self._machines.get(str(entity_id))

    def set_parameter(self, entity_id, name, value):
        self._machines[str(entity_id)].set(name, value)

    def trigger(self, entity_id, name):
        self._machines[str(entity_id)].trigger(name)

    def _report(self, entity, message):
        if (entity.id, message) not in self._reported:
            self._reported.add((entity.id, message))
            self.diagnostics.append(f"{entity.name}: {message}")

    def update(self, scene, dt):
        self.frame_events = []
        seen = set()
        for entity, spec, _sprite in scene.query(Animator2DComponent, SpriteRenderer2D):
            seen.add(entity.id)
            key = (spec.clip_set_id, spec.default_clip)
            cached = self._bindings.get(entity.id)
            if cached is None or cached[0] != key:
                try:
                    binding = Animator2DBinding.create(entity, self.resolve_clip_set)
                except ValueError as exc:
                    self._report(entity, str(exc))
                    self._bindings.pop(entity.id, None)
                    self._machines.pop(entity.id, None)
                    continue
                self._bindings[entity.id] = (key, binding)
                self._machines.pop(entity.id, None)
                clip_set = self.resolve_clip_set(spec.clip_set_id)
                if getattr(clip_set, "state_machine", None) is not None:
                    try:
                        self._machines[entity.id] = AnimationStateMachine(
                            clip_set.state_machine, clip_set, binding.animator
                        )
                    except ValueError as exc:
                        self._report(entity, str(exc))
                cached = self._bindings[entity.id]
            binding = cached[1]
            binding.speed = spec.speed
            if not spec.playing:
                binding.animator.playing = False
            machine = self._machines.get(entity.id)
            if machine is not None:
                machine.evaluate()
            binding.update(dt)
            for clip, keyframe, name in binding.animator.drain_events():
                event = (entity.id, clip, keyframe, name)
                self.frame_events.append(event)
                for listener in tuple(self.listeners):
                    listener(*event)
        for stale in set(self._bindings) - seen:
            del self._bindings[stale]
            self._machines.pop(stale, None)


class CameraFollowSystem(System):
    """Moves each active Camera2D toward the entity named by ``follow_entity_id``."""

    order = 200

    def __init__(self, world_bounds=None):
        self.world_bounds = world_bounds
        self.cameras: dict[str, Camera2D] = {}

    def camera(self, entity_id):
        return self.cameras.get(str(entity_id))

    def update(self, scene, dt):
        for entity, spec, transform in scene.query(Camera2DComponent, Transform):
            if not spec.active:
                continue
            camera = self.cameras.setdefault(entity.id, Camera2D())
            camera.width, camera.height, camera.zoom = spec.width, spec.height, spec.zoom
            target = scene.get_entity(spec.follow_entity_id) if spec.follow_entity_id else None
            if target is None or not target.has(Transform):
                camera.x, camera.y = transform.x, transform.y
                continue
            follow = CameraFollow2D(camera, spec.deadzone_x, spec.deadzone_y, spec.smoothing, self.world_bounds)
            target_transform = target.get(Transform)
            follow.update(target_transform.x, target_transform.y, dt)
            transform.x, transform.y = camera.x, camera.y
