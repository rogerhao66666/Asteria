"""Particle effects (VFX-01): authored emitter data and a deterministic simulation, independent of any renderer.

A particle effect is a canonical asset of kind ``particle_effect``; its ``emitter`` metadata is a
``ParticleEffectDefinition``. The same effect is used by

* the ``ParticleEmitter2D`` component on any field entity (torches, fountains, auras),
* the ``PLAY_VFX`` event command (a one-shot at an entity or a point),
* a battle action-timeline VFX beat whose ``asset_id`` names it (a burst on the member),
* the editor's live preview.

Positions, speeds, sizes and gravity are in world units (one unit = one map pixel on the field);
angles are degrees, 0 = right, -90 = up. Every number is the author's: nothing is clamped beyond
what keeps the simulation finite.
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, fields
from typing import NamedTuple

from asteria import kernels

PARTICLE_KIND = "particle_effect"
EMITTER_SHAPES = ("point", "circle", "ring", "rect", "line")
PARTICLE_SHAPES = ("circle", "square", "spark", "image")
PARTICLE_BLENDS = ("alpha", "add")


def _pair(value, name):
    if isinstance(value, (int, float)):
        return (float(value), float(value))
    a, b = value
    return (float(a), float(b))


def _rgba(value, name):
    value = tuple(int(round(float(v))) for v in value)
    if len(value) == 3:
        value += (255,)
    if len(value) != 4:
        raise ValueError(f"{name} must be [r, g, b] or [r, g, b, a]")
    return tuple(max(0, min(255, v)) for v in value)


@dataclass(frozen=True, slots=True)
class ParticleEffectDefinition:
    """What an emitter spawns and how each particle moves and changes over its life."""

    effect_id: str
    rate: float = 20.0  # particles per second while emitting
    burst: int = 0  # particles spawned at once when the effect starts
    duration: float = 0.0  # seconds of emission; 0 = emit until stopped (looping)
    max_particles: int = 200
    lifetime: tuple[float, float] = (0.6, 1.2)  # seconds, random in range
    speed: tuple[float, float] = (20.0, 50.0)
    direction: float = -90.0
    spread: float = 30.0  # degrees either side of ``direction``
    gravity: tuple[float, float] = (0.0, 0.0)
    drag: float = 0.0  # fraction of velocity lost per second
    shape: str = "point"
    shape_size: tuple[float, float] = (0.0, 0.0)  # radius (circle / ring) or width, height (rect / line)
    size: tuple[float, float] = (4.0, 1.0)  # at birth, at death
    size_jitter: float = 0.0  # +- fraction of the size per particle
    color_start: tuple[int, int, int, int] = (255, 220, 120, 255)
    color_end: tuple[int, int, int, int] = (255, 90, 30, 0)
    particle: str = "circle"
    image: str = ""  # with particle "image": an icon / image asset id or a PNG path
    blend: str = "alpha"
    spin: tuple[float, float] = (0.0, 0.0)  # degrees per second (squares, sparks, images)
    local: bool = False  # particles move with the emitter instead of staying where they were born

    def __post_init__(self):
        if not str(self.effect_id).strip():
            raise ValueError("effect_id required")
        for name in ("lifetime", "speed", "gravity", "shape_size", "size", "spin"):
            object.__setattr__(self, name, _pair(getattr(self, name), name))
        for name in ("color_start", "color_end"):
            object.__setattr__(self, name, _rgba(getattr(self, name), name))
        for name in ("rate", "duration", "direction", "spread", "drag", "size_jitter"):
            object.__setattr__(self, name, float(getattr(self, name)))
        object.__setattr__(self, "burst", int(self.burst))
        object.__setattr__(self, "max_particles", int(self.max_particles))
        object.__setattr__(self, "local", bool(self.local))
        if self.rate < 0 or self.burst < 0 or self.duration < 0 or self.drag < 0:
            raise ValueError("rate, burst, duration and drag must be >= 0")
        if self.max_particles < 1:
            raise ValueError("max_particles must be >= 1")
        if self.lifetime[0] <= 0 or self.lifetime[1] < self.lifetime[0]:
            raise ValueError("lifetime must be a positive range (min <= max)")
        if self.speed[1] < self.speed[0]:
            raise ValueError("speed range must be min <= max")
        if self.shape not in EMITTER_SHAPES:
            raise ValueError(f"shape must be one of {EMITTER_SHAPES}")
        if self.particle not in PARTICLE_SHAPES:
            raise ValueError(f"particle must be one of {PARTICLE_SHAPES}")
        if self.blend not in PARTICLE_BLENDS:
            raise ValueError(f"blend must be one of {PARTICLE_BLENDS}")
        if self.particle == "image" and not str(self.image).strip():
            raise ValueError('particle "image" needs an image')

    @property
    def looping(self):
        return self.duration == 0

    def to_data(self):
        data = {"schema": "asteria.vfx.particle_effect", "version": 1}
        for f in fields(self):
            value = getattr(self, f.name)
            data[f.name] = list(value) if isinstance(value, tuple) else value
        return data

    @classmethod
    def from_data(cls, data):
        data = dict(data)
        if data.pop("schema", "asteria.vfx.particle_effect") != "asteria.vfx.particle_effect":
            raise ValueError("unsupported particle effect")
        data.pop("version", None)
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown particle effect fields: {sorted(unknown)}")
        return cls(**data)

    def replace(self, **changes):
        values = asdict(self)
        values.update(changes)
        return type(self)(**values)


# Starting points offered by the editor; every value can be changed afterwards.
PRESETS = {
    "fire": dict(
        rate=40,
        lifetime=(0.5, 0.9),
        speed=(18, 38),
        direction=-90,
        spread=18,
        gravity=(0, -20),
        shape="circle",
        shape_size=(4, 4),
        size=(6, 1),
        color_start=(255, 210, 90, 255),
        color_end=(230, 50, 20, 0),
        blend="add",
    ),
    "smoke": dict(
        rate=12,
        lifetime=(1.4, 2.4),
        speed=(8, 16),
        direction=-90,
        spread=25,
        drag=0.4,
        shape="circle",
        shape_size=(3, 3),
        size=(4, 14),
        size_jitter=0.3,
        color_start=(120, 120, 130, 150),
        color_end=(80, 80, 90, 0),
    ),
    "sparkle": dict(
        rate=18,
        lifetime=(0.4, 0.9),
        speed=(4, 14),
        spread=180,
        shape="circle",
        shape_size=(14, 14),
        size=(3, 0),
        particle="spark",
        spin=(-180, 180),
        color_start=(255, 255, 210, 255),
        color_end=(160, 220, 255, 0),
        blend="add",
    ),
    "heal": dict(
        rate=24,
        duration=1.0,
        lifetime=(0.7, 1.1),
        speed=(16, 30),
        direction=-90,
        spread=12,
        shape="rect",
        shape_size=(28, 4),
        size=(4, 2),
        color_start=(150, 255, 170, 255),
        color_end=(90, 220, 255, 0),
        blend="add",
    ),
    "poison": dict(
        rate=10,
        lifetime=(0.8, 1.4),
        speed=(6, 14),
        direction=-90,
        spread=30,
        shape="rect",
        shape_size=(22, 6),
        size=(2, 6),
        color_start=(170, 90, 220, 230),
        color_end=(90, 220, 90, 0),
    ),
    "explosion": dict(
        rate=0,
        burst=80,
        duration=0.05,
        lifetime=(0.3, 0.8),
        speed=(40, 140),
        spread=180,
        drag=2.5,
        size=(7, 1),
        color_start=(255, 240, 160, 255),
        color_end=(200, 40, 10, 0),
        blend="add",
    ),
    "rain_splash": dict(
        rate=30,
        lifetime=(0.2, 0.4),
        speed=(20, 50),
        direction=-90,
        spread=50,
        gravity=(0, 220),
        shape="line",
        shape_size=(120, 0),
        size=(2, 1),
        particle="square",
        color_start=(190, 220, 255, 200),
        color_end=(190, 220, 255, 0),
    ),
}


def preset(name, effect_id):
    return ParticleEffectDefinition(effect_id, **PRESETS[name])


class ParticleView(NamedTuple):
    """One particle as a renderer draws it."""

    x: float
    y: float
    size: float
    color: tuple[int, int, int, int]
    angle: float


class ParticleSystem:
    """One running emitter. ``update(dt)`` advances it deterministically (seeded); ``views()`` lists what to
    draw. ``move_to`` follows an entity; ``stop()`` ends emission and lets the live particles finish."""

    def __init__(self, definition, *, x=0.0, y=0.0, seed=0, scale=1.0, emit_for=None):
        self.definition = definition
        self.x, self.y = float(x), float(y)
        self.scale = float(scale)
        self.rng = random.Random(f"{definition.effect_id}:{seed}")
        self.age = 0.0
        self.emitting = True
        # a looping effect played once (PLAY_VFX) emits for ``emit_for`` seconds
        self.emit_for = definition.duration if emit_for is None else max(0.0, float(emit_for))
        self._carry = 0.0
        self._burst_done = False
        self._particles = kernels.active().ParticleStore()
        self.spawned = 0

    @property
    def count(self):
        return len(self._particles)

    @property
    def finished(self):
        """No more emission and no particle left (a one-shot is over)."""
        return not self._emitting_now() and not len(self._particles)

    def _emitting_now(self):
        return self.emitting and (self.emit_for == 0 or self.age < self.emit_for)

    def stop(self):
        self.emitting = False

    def move_to(self, x, y):
        x, y = float(x), float(y)
        if self.definition.local and (x != self.x or y != self.y):
            self._particles.shift(x - self.x, y - self.y)
        self.x, self.y = x, y

    def _origin(self):
        d, rng, s = self.definition, self.rng, self.scale
        w, h = d.shape_size[0] * s, d.shape_size[1] * s
        if d.shape == "circle":
            r, a = w * math.sqrt(rng.random()), rng.uniform(0, math.tau)
            return self.x + math.cos(a) * r, self.y + math.sin(a) * r
        if d.shape == "ring":
            a = rng.uniform(0, math.tau)
            return self.x + math.cos(a) * w, self.y + math.sin(a) * w
        if d.shape == "rect":
            return self.x + rng.uniform(-w / 2, w / 2), self.y + rng.uniform(-h / 2, h / 2)
        if d.shape == "line":
            return self.x + rng.uniform(-w / 2, w / 2), self.y
        return self.x, self.y

    def _spawn(self, n):
        d, rng, s = self.definition, self.rng, self.scale
        room = d.max_particles - len(self._particles)
        rows = []
        for _ in range(max(0, min(n, room))):
            x, y = self._origin()
            angle = math.radians(d.direction + rng.uniform(-d.spread, d.spread))
            speed = rng.uniform(*d.speed) * s
            rows.append(
                (
                    x,
                    y,
                    math.cos(angle) * speed,
                    math.sin(angle) * speed,
                    0.0,
                    rng.uniform(*d.lifetime),
                    1.0 + rng.uniform(-d.size_jitter, d.size_jitter),
                    rng.uniform(0, 360) if d.spin != (0.0, 0.0) else 0.0,
                    rng.uniform(*d.spin),
                )
            )
        self.spawned += len(rows)
        self._particles.add(rows)

    def update(self, dt):
        dt = max(0.0, float(dt))
        d = self.definition
        if not self._burst_done:
            self._burst_done = True
            self._spawn(d.burst)
        if self._emitting_now():
            self._carry += d.rate * dt
            n = int(self._carry)
            self._carry -= n
            self._spawn(n)
        self.age += dt
        gx, gy = d.gravity[0] * self.scale, d.gravity[1] * self.scale
        self._particles.step(dt, gx, gy, max(0.0, 1.0 - d.drag * dt))

    def views(self):
        d = self.definition
        return [ParticleView(*v) for v in self._particles.views(*d.size, d.color_start, d.color_end, self.scale)]


def effect_definition(assets, asset_id):
    """The ``ParticleEffectDefinition`` of a ``particle_effect`` asset, or None when ``asset_id`` is not one."""
    try:
        asset = assets.resolve(asset_id)
    except (KeyError, ValueError):
        return None
    if asset.kind != PARTICLE_KIND:
        return None
    emitter = dict(asset.metadata).get("emitter") or {}
    return ParticleEffectDefinition.from_data({**emitter, "effect_id": asset.asset_id})


def particle_effect_asset(definition, *, tags=("vfx", "particles")):
    """A canonical asset holding ``definition`` (``source.uri`` is the image of image particles, else "")."""
    from asteria.assets.canonical import AssetSource, CanonicalAsset

    emitter = definition.to_data()
    emitter.pop("effect_id")
    return CanonicalAsset(
        definition.effect_id,
        PARTICLE_KIND,
        AssetSource(definition.image if definition.particle == "image" else ""),
        tags=frozenset(tags),
        metadata=(("emitter", emitter),),
    )
