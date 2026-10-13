"""Field screen effects and VFX for event programs and sequences (EVT-02, EVT-04).

Presentation world commands handled by the playable field:

* ``SCREEN_FADE`` ``to`` (0 = clear .. 1 = full colour), ``duration`` seconds, ``color`` [r, g, b]
* ``PLAY_VFX``    ``asset_id`` (a battle VFX sprite sheet), ``entity`` (name / id / player) or
  ``x``/``y``,
  optional ``duration`` and the VFX placement overrides (``scale``, ``anchor``, ``offset``,
  ``opacity``, ``blend``) — placed with the same ``vfx_placement`` / ``vfx_rect`` /
  ``vfx_keyframe``
  rules as the battle. ``asset_id`` may also name a particle effect (VFX-01): it plays once there
  (a looping effect emits for ``duration`` seconds, default 1) and follows the entity.

``ParticleEmitter2D`` components on field entities emit continuously (``sync_emitters`` each
frame).

State is deterministic (advanced by ``update(dt)``) so tests measure exactly what is drawn.
"""

from __future__ import annotations

from dataclasses import dataclass

from asteria.core import Transform, world_position
from asteria.presentation.particles import ParticleSystem, effect_definition
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


@dataclass(slots=True)
class FieldParticles:
    """A particle system in the field: a ``PLAY_VFX`` one-shot or an entity's
    ``ParticleEmitter2D``."""

    system: ParticleSystem
    entity_id: str | None
    offset: tuple[float, float] = (0.0, 0.0)
    effect_id: str = ""


class FieldEffects:
    def __init__(self):
        self.fade_alpha = 0.0
        self.fade_color = (0, 0, 0)
        self._fade_from = 0.0
        self._fade_to = 0.0
        self._fade_time = 0.0
        self._fade_duration = 0.0
        self.vfx = []
        self.particles = []  # one-shots from PLAY_VFX
        self.emitters = {}  # entity id -> FieldParticles of its ParticleEmitter2D

    def all_particles(self):
        return [*self.emitters.values(), *self.particles]

    def sync_emitters(self, scene, assets):
        """Start, follow, pause or drop the emitters of the scene's ``ParticleEmitter2D``
        components (their
        effects from the project ``assets``), and move one-shots that follow an entity."""
        from asteria.runtime.environment2d import ParticleEmitter2DComponent

        seen = set()
        for entity in scene.entities() if scene is not None else ():
            component = entity.try_get(ParticleEmitter2DComponent)
            if (
                component is None
                or not component.enabled
                or not entity.enabled
                or not entity.has(Transform)
            ):
                continue
            current = self.emitters.get(entity.id)
            if (
                current is None
                or current.effect_id != component.effect_id
                or current.system.scale != component.scale
            ):
                definition = effect_definition(assets, component.effect_id)
                if definition is None:
                    continue  # no such effect (yet): nothing to show
                x, y = world_position(entity)
                current = FieldParticles(
                    ParticleSystem(definition, x=x, y=y, seed=entity.id, scale=component.scale),
                    entity.id,
                    (component.offset_x, component.offset_y),
                    component.effect_id,
                )
                self.emitters[entity.id] = current
            seen.add(entity.id)
            current.offset = (component.offset_x, component.offset_y)
            current.system.emitting = bool(component.playing)
            x, y = world_position(entity)
            current.system.move_to(x + current.offset[0], y + current.offset[1])
        for entity_id in list(self.emitters):
            if entity_id not in seen:
                del self.emitters[entity_id]
        for one_shot in self.particles:
            entity = (
                scene.get_entity(one_shot.entity_id)
                if one_shot.entity_id and scene is not None
                else None
            )
            if entity is not None and entity.has(Transform):
                x, y = world_position(entity)
                one_shot.system.move_to(x + one_shot.offset[0], y + one_shot.offset[1])

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
            definition = effect_definition(assets, asset_id)
            if definition is not None:
                self._play_particles(definition, args, scene, player)
                return
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
                    else scene.get_entity(key)
                    or next((e for e in scene.entities() if e.name == key), None)
                )
                if entity is None or not entity.has(Transform):
                    raise FieldEffectError(f"PLAY_VFX: no entity {key}")
                entity_id = entity.id
            duration = float(
                args.get(
                    "duration", max(0.05, len(clip["frames"]) * float(clip["frame_duration"]))
                )
            )
            self.vfx.append(
                FieldVfx(asset_id, entity_id, x, y, duration, vfx_placement(meta, args))
            )
        else:
            raise FieldEffectError(f"not a field effect command: {command.name}")

    def _play_particles(self, definition, args, scene, player):
        entity_id, x, y = None, float(args.get("x", 0.0)), float(args.get("y", 0.0))
        if args.get("entity"):
            key = str(args["entity"])
            entity = (
                player
                if key in ("player", "@player")
                else scene.get_entity(key)
                or next((e for e in scene.entities() if e.name == key), None)
            )
            if entity is None or not entity.has(Transform):
                raise FieldEffectError(f"PLAY_VFX: no entity {key}")
            entity_id = entity.id
            x, y = world_position(entity)
        offset = args.get("offset", (0.0, 0.0))
        offset = (float(offset[0]), float(offset[1]))
        duration = args.get("duration")
        emit_for = (
            float(duration)
            if duration is not None
            else (1.0 if definition.looping else definition.duration)
        )
        system = ParticleSystem(
            definition,
            x=x + offset[0],
            y=y + offset[1],
            seed=len(self.particles),
            scale=float(args.get("scale", 1.0)),
            emit_for=emit_for,
        )
        self.particles.append(FieldParticles(system, entity_id, offset, definition.effect_id))

    def update(self, dt):
        if self._fade_duration > 0 and self._fade_time < self._fade_duration:
            self._fade_time = min(self._fade_duration, self._fade_time + dt)
            k = self._fade_time / self._fade_duration
            self.fade_alpha = self._fade_from + (self._fade_to - self._fade_from) * k
        for effect in self.vfx:
            effect.age += dt
        self.vfx = [v for v in self.vfx if not v.done]
        for field_particles in self.all_particles():
            field_particles.system.update(dt)
        self.particles = [p for p in self.particles if not p.system.finished]

    @staticmethod
    def keyframe(effect, frame_count):
        return vfx_keyframe(effect.age, effect.duration, frame_count)
