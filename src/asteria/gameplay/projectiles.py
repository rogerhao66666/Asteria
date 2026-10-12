"""Projectile definitions (ASTERIA_SPEC §20 projectiles; §16 ``Ability.Projectile``).

A ``ProjectileDefinition`` is authored data: how a shot moves (speed, gravity, homing), how long it lives, its hit box,
what it does on a wall, how many targets it passes through, and which ``AttackDefinition`` it applies on a hit. Firing
(count, spread, offset) is chosen where it is fired from — an action timeline ``projectile`` cue or a script — so one
definition serves arrows, fan shots, lobbed bombs and homing orbs alike. ``runtime.projectiles`` runs them.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

WALL_BEHAVIOURS = ("destroy", "bounce", "stop", "pass")


def _number(value, name, *, minimum=None):
    value = float(value)
    if not isfinite(value) or (minimum is not None and value < minimum):
        raise ValueError(f"{name} must be a finite number" + ("" if minimum is None else f" >= {minimum}"))
    return value


@dataclass(frozen=True, slots=True)
class ProjectileDefinition:
    projectile_id: str
    display_name: str = ""
    attack_id: str = ""  # the AttackDefinition applied to each target hit ("" = it only reports hits)
    speed: float = 240.0
    lifetime: float = 1.5
    gravity: float = 0.0  # downward acceleration (side-view arcs, lobbed throws)
    width: float = 8.0
    height: float = 8.0
    pierce: int = 0  # extra targets it passes through; -1 = every target until it ends
    wall: str = "destroy"
    wall_mask: int = 0xFFFFFFFF  # collider layers that count as walls (one-way platforms never do)
    bounce_limit: int = 0  # wall == bounce: bounces before it ends; 0 = until its lifetime ends
    homing_turn: float = 0.0  # degrees per second toward the nearest target; 0 = flies straight
    homing_range: float = 160.0
    sprite: str = ""  # presentation: image / sprite asset id
    clip: str = ""
    align_to_velocity: bool = True
    on_end_event: str = ""  # gameplay event when it ends (wall, lifetime, last target)

    def __init__(
        self,
        projectile_id,
        display_name="",
        *,
        attack_id="",
        speed=240.0,
        lifetime=1.5,
        gravity=0.0,
        width=8.0,
        height=8.0,
        pierce=0,
        wall="destroy",
        wall_mask=0xFFFFFFFF,
        bounce_limit=0,
        homing_turn=0.0,
        homing_range=160.0,
        sprite="",
        clip="",
        align_to_velocity=True,
        on_end_event="",
    ):
        projectile_id = str(projectile_id).strip()
        if not projectile_id:
            raise ValueError("projectile_id is required")
        if wall not in WALL_BEHAVIOURS:
            raise ValueError(f"wall must be one of {WALL_BEHAVIOURS}")
        if int(pierce) < -1:
            raise ValueError("pierce must be >= -1")
        if int(bounce_limit) < 0:
            raise ValueError("bounce_limit must be >= 0")
        set_ = object.__setattr__
        set_(self, "projectile_id", projectile_id)
        set_(self, "display_name", str(display_name or projectile_id))
        set_(self, "attack_id", str(attack_id).strip())
        set_(self, "speed", _number(speed, "speed", minimum=0.0))
        set_(self, "lifetime", _number(lifetime, "lifetime", minimum=0.0))
        set_(self, "gravity", _number(gravity, "gravity"))
        set_(self, "width", _number(width, "width", minimum=0.0))
        set_(self, "height", _number(height, "height", minimum=0.0))
        set_(self, "pierce", int(pierce))
        set_(self, "wall", wall)
        if not 0 <= int(wall_mask) <= 0xFFFFFFFF:
            raise ValueError("wall_mask must be a 32-bit layer mask")
        set_(self, "wall_mask", int(wall_mask))
        set_(self, "bounce_limit", int(bounce_limit))
        set_(self, "homing_turn", _number(homing_turn, "homing_turn", minimum=0.0))
        set_(self, "homing_range", _number(homing_range, "homing_range", minimum=0.0))
        set_(self, "sprite", str(sprite))
        set_(self, "clip", str(clip))
        set_(self, "align_to_velocity", bool(align_to_velocity))
        set_(self, "on_end_event", str(on_end_event).strip())

    def to_data(self):
        data = {"schema": "asteria.projectile", "version": 1}
        data.update({name: getattr(self, name) for name in self.__dataclass_fields__})
        return data

    @classmethod
    def from_data(cls, data):
        data = dict(data)
        if data.pop("schema", None) != "asteria.projectile" or data.pop("version", None) != 1:
            raise ValueError("unsupported projectile definition")
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown projectile fields: {sorted(unknown)}")
        return cls(**data)


__all__ = ["WALL_BEHAVIOURS", "ProjectileDefinition"]
