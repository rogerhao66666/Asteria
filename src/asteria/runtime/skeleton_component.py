"""Persistent skeletal-animation component and scene rendering adapter."""

from __future__ import annotations

import json
from math import isfinite

from asteria.core import Component, Field, Transform, component_schema, world_position
from asteria.graphics.skeleton_data import skeleton_from_data

from .skeleton_draw import to_texture_draws


@component_schema(
    type_name="asteria.SkeletonAnimation2D",
    version=1,
    fields=(
        Field("skeleton_json", str, "", label="Rig JSON"),
        Field("clip_name", str, "", label="Animation Clip"),
        Field("speed", float, 1.0, minimum=0.0, label="Playback Speed"),
        Field("scale", float, 1.0, minimum=0.001),
        Field("layer", int, 0),
        Field("playing", bool, True),
        Field("visible", bool, True),
    ),
)
class SkeletonAnimation2DComponent(Component):
    """A saved Asteria rig attached to an entity; JSON embeds the native editable rig format."""

    def __init__(
        self,
        skeleton_json="",
        *,
        clip_name="",
        speed=1.0,
        scale=1.0,
        layer=0,
        playing=True,
        visible=True,
    ):
        super().__init__()
        self.skeleton_json = str(skeleton_json)
        self.clip_name = str(clip_name)
        self.speed = float(speed)
        self.scale = float(scale)
        self.layer = int(layer)
        self.playing = bool(playing)
        self.visible = bool(visible)
        if not isfinite(self.speed) or self.speed < 0:
            raise ValueError("skeleton speed must be finite and non-negative")
        if not isfinite(self.scale) or self.scale <= 0:
            raise ValueError("skeleton scale must be finite and positive")


class SkeletonSceneRuntime:
    """Advance attached rigs and convert their slots into renderer-neutral texture commands."""

    def __init__(self):
        self._times = {}
        self._signatures = {}
        self._rigs = {}

    def update(self, scene, dt):
        alive = set()
        step = max(0.0, float(dt))
        for entity, component in scene.query(SkeletonAnimation2DComponent):
            alive.add(entity.id)
            signature = (component.skeleton_json, component.clip_name)
            if self._signatures.get(entity.id) != signature:
                self._signatures[entity.id] = signature
                self._times[entity.id] = 0.0
            if component.playing:
                self._times[entity.id] += step * component.speed
        for entity_id in set(self._times) - alive:
            self._times.pop(entity_id, None)
            self._signatures.pop(entity_id, None)
            self._rigs.pop(entity_id, None)

    def _rig(self, entity, component):
        signature = self._signatures.get(entity.id)
        cached = self._rigs.get(entity.id)
        if cached is not None and cached[0] == signature:
            return cached[1]
        try:
            rig = skeleton_from_data(json.loads(component.skeleton_json))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None
        self._rigs[entity.id] = (signature, rig)
        return rig

    def draw_entity(self, entity, camera, resolve_sprite_sheet):
        component = entity.try_get(SkeletonAnimation2DComponent)
        if (
            component is None
            or entity.try_get(Transform) is None
            or not component.visible
            or not component.skeleton_json
        ):
            return ()
        rig = self._rig(entity, component)
        if rig is None:
            return ()
        clip_name = component.clip_name or None
        if clip_name is not None and clip_name not in rig.clips:
            return ()
        time = self._times.get(entity.id, 0.0)
        pose = rig.pose(clip_name, time)
        origin = world_position(entity)
        rows = rig.draws(pose, clip_name, time, origin=origin, scale=component.scale)
        try:
            return tuple(
                to_texture_draws(
                    rows,
                    resolve_sprite_sheet,
                    camera=camera,
                    layer=component.layer,
                    depth=origin[1],
                )
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ()

    def draw_commands(self, scene, camera, resolve_sprite_sheet):
        if scene is None:
            return ()
        draws = []
        for entity in scene._members(SkeletonAnimation2DComponent):  # disabled ones draw too
            if entity.destroy_requested:
                continue
            draws.extend(self.draw_entity(entity, camera, resolve_sprite_sheet))
        return tuple(sorted(draws, key=lambda draw: (draw.layer, draw.depth, draw.screen_y)))


__all__ = ["SkeletonAnimation2DComponent", "SkeletonSceneRuntime"]
