"""Concrete runtime Systems (ASTERIA_SPEC §7 system-oriented runtime).

Add them to ``Scene.scheduler``; ``Scene.update`` then runs them in ``order``.
"""

from __future__ import annotations

from asteria.core import System, Transform

from .animation_binding import Animator2DBinding
from .animation_state_machine import AnimationStateMachine
from .camera import Camera2D, CameraDirector, CameraFollow2D, CameraTargetGroup
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
    """Drives each active Camera2D: follow (dead zone, smoothing, look-ahead, bounds) or a target
    group,
    then authored shots and shake from its ``CameraDirector`` (cutscene / boss focus, CAM-02).

    ``camera(entity_id)`` is the view to render; the camera entity's Transform tracks its top-left.
    """

    order = 200

    def __init__(self, world_bounds=None):
        self.world_bounds = world_bounds
        self.cameras: dict[str, Camera2D] = {}
        self._follow_cameras: dict[str, Camera2D] = {}
        self._follows: dict[str, CameraFollow2D] = {}
        self._last_target: dict[str, tuple[float, float]] = {}
        self.directors: dict[str, CameraDirector] = {}

    def camera(self, entity_id):
        return self.cameras.get(str(entity_id))

    def director(self, entity_id):
        return self.directors.setdefault(str(entity_id), CameraDirector())

    def update(self, scene, dt):
        for entity, spec, transform in scene.query(Camera2DComponent, Transform):
            if not spec.active:
                continue
            base = self._follow_cameras.get(entity.id)
            if base is None:
                base = self._follow_cameras[entity.id] = Camera2D(transform.x, transform.y)
            base.width, base.height, base.zoom = spec.width, spec.height, spec.zoom
            follow = self._follows.get(entity.id)
            if follow is None:
                follow = self._follows[entity.id] = CameraFollow2D(base)
            follow.deadzone_x, follow.deadzone_y, follow.smoothing = (
                spec.deadzone_x,
                spec.deadzone_y,
                spec.smoothing,
            )
            follow.world_bounds = spec.bounds or self.world_bounds
            follow.look_ahead_x, follow.look_ahead_y = spec.look_ahead_x, spec.look_ahead_y
            group = [scene.get_entity(x) for x in spec.group_ids]
            group = [g.get(Transform) for g in group if g is not None and g.has(Transform)]
            target = scene.get_entity(spec.follow_entity_id) if spec.follow_entity_id else None
            if group:
                frame = CameraTargetGroup(spec.group_padding, spec.min_zoom, spec.max_zoom)
                cx, cy, base.zoom = frame.frame(
                    [(g.x, g.y) for g in group], spec.width, spec.height
                )
                follow.update(cx, cy, dt)
            elif target is not None and target.has(Transform):
                tt = target.get(Transform)
                last = self._last_target.get(entity.id)
                velocity = (
                    ((tt.x - last[0]) / dt, (tt.y - last[1]) / dt)
                    if last is not None and dt > 0
                    else None
                )
                self._last_target[entity.id] = (tt.x, tt.y)
                follow.update(tt.x, tt.y, dt, velocity=velocity)
            else:
                base.x, base.y = transform.x, transform.y
            view_w, view_h = base.width / base.zoom, base.height / base.zoom
            cx, cy, zoom = self.director(entity.id).update(
                dt, (base.x + view_w / 2, base.y + view_h / 2, base.zoom)
            )
            camera = self.cameras.setdefault(entity.id, Camera2D())
            camera.width, camera.height, camera.zoom = base.width, base.height, zoom
            camera.x, camera.y = cx - base.width / zoom / 2, cy - base.height / zoom / 2
            if target is not None or group:
                transform.x, transform.y = base.x, base.y
