"""Field screen effects and VFX for event programs and sequences (EVT-02, EVT-04).

Presentation world commands handled by the playable field:

* ``SCREEN_FADE`` ``to`` (0 = clear .. 1 = full colour), ``duration`` seconds, ``color`` [r, g, b]
* ``PLAY_VFX``    ``asset_id`` (a battle VFX sprite sheet), ``entity`` (name / id / player) or ``x``/``y``,
  optional ``duration`` and the VFX placement overrides (``scale``, ``anchor``, ``offset``,
  ``opacity``, ``blend``) — placed with the same ``vfx_placement`` / ``vfx_rect`` / ``vfx_keyframe``
  rules as the battle

State is deterministic (advanced by ``update(dt)``) so tests measure exactly what is drawn.
"""

from __future__ import annotations

from dataclasses import dataclass

from asteria.core import Transform
from asteria.runtime.battle_visuals import vfx_keyframe, vfx_placement

FIELD_EFFECT_COMMANDS = ("SCREEN_FADE", "PLAY_VFX")


class FieldEffectError(ValueError):
    pass


@dataclass(slots=True)
class FieldVfx:
    asset_id: str
    entity_id: str | None
    x: float
    y: float
    duration: float
    placement: dict
    age: float = 0.0

    @property
    def done(self):
        return self.age >= self.duration


class FieldEffects:
    def __init__(self):
        self.fade_alpha = 0.0
        self.fade_color = (0, 0, 0)
        self._fade_from = 0.0
        self._fade_to = 0.0
        self._fade_time = 0.0
        self._fade_duration = 0.0
        self.vfx = []

    def handle(self, command, scene, assets, *, player=None):
        args = dict(command.args)
        if command.name == "SCREEN_FADE":
            self._fade_from = self.fade_alpha
            self._fade_to = max(0.0, min(1.0, float(args.get("to", 1.0))))
            self._fade_duration = max(0.0, float(args.get("duration", 0.5)))
            self._fade_time = 0.0
            color = args.get("color", (0, 0, 0))
            self.fade_color = tuple(int(c) for c in color)[:3]
            if self._fade_duration == 0:
                self.fade_alpha = self._fade_to
        elif command.name == "PLAY_VFX":
            asset_id = str(args.get("asset_id", ""))
            try:
                asset = assets.resolve(asset_id)
            except KeyError:
                raise FieldEffectError(f"PLAY_VFX: unknown asset {asset_id}") from None
            meta = asset.meta()
            clip = meta.get("clips", {}).get("play")
            if not clip:
                raise FieldEffectError(f"PLAY_VFX: {asset_id} has no 'play' clip")
            entity_id, x, y = None, float(args.get("x", 0.0)), float(args.get("y", 0.0))
            if args.get("entity"):
                key = str(args["entity"])
                entity = (
                    player
                    if key in ("player", "@player")
                    else scene.get_entity(key) or next((e for e in scene.entities() if e.name == key), None)
                )
                if entity is None or not entity.has(Transform):
                    raise FieldEffectError(f"PLAY_VFX: no entity {key}")
                entity_id = entity.id
            duration = float(args.get("duration", max(0.05, len(clip["frames"]) * float(clip["frame_duration"]))))
            self.vfx.append(FieldVfx(asset_id, entity_id, x, y, duration, vfx_placement(meta, args)))
        else:
            raise FieldEffectError(f"not a field effect command: {command.name}")

    def update(self, dt):
        if self._fade_duration > 0 and self._fade_time < self._fade_duration:
            self._fade_time = min(self._fade_duration, self._fade_time + dt)
            k = self._fade_time / self._fade_duration
            self.fade_alpha = self._fade_from + (self._fade_to - self._fade_from) * k
        for effect in self.vfx:
            effect.age += dt
        self.vfx = [v for v in self.vfx if not v.done]

    @staticmethod
    def keyframe(effect, frame_count):
        return vfx_keyframe(effect.age, effect.duration, frame_count)
