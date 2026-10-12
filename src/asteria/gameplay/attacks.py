"""Attack definitions: what one hit does (ASTERIA_SPEC §20 hitbox/hurtbox, knockback, stagger/poise, hitstop,
super armor, knockdown).

An ``AttackDefinition`` is plain authored data. A hitbox whose ``hit_tag`` is the attack id (usually set by an action
timeline ``hitbox`` cue) applies it to every target it hits; ``runtime.combat.CombatSystem`` does the resolving.
Nothing here names a game, a class or a stat: the damage is a ``ValueFormula`` over whatever stats the project
defines, it lowers whichever resource the author picks (a negative amount restores it), and every reaction is an
option with a neutral default.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .formulas import ValueFormula
from .tags import normalize_tag

KNOCKBACK_DIRECTIONS = ("away", "attacker_facing", "fixed")
HITSTOP_SCOPES = ("participants", "global")


def _number(value, name, *, minimum=None, maximum=None):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class AttackDefinition:
    attack_id: str
    display_name: str = ""
    damage: ValueFormula | None = None  # inline formula; ignored when damage_formula_id is set
    damage_formula_id: str = ""  # a shared formula in the gameplay library
    damage_resource: str = "hp"
    tags: tuple[str, ...] = ()  # added to the attacker's tags while the formula runs (e.g. Element.Fire)
    poise_damage: float = 0.0
    hitstun: float = 0.0  # seconds the target cannot act
    knockback: float = 0.0  # push speed, world units / s
    knockback_direction: str = "away"
    knockback_angle: float = 0.0  # degrees; "fixed" = world angle (0 right, 90 down), else turns the push
    knockback_lift: float = 0.0  # side view: upward launch speed
    hitstop: float = 0.0
    hitstop_scope: str = "participants"
    target_iframes: float = 0.0
    max_targets: int = 0  # 0 = every target the hitbox touches
    critical_chance: float = 0.0  # 0..1, plus critical_chance_stat / 100 of the attacker
    critical_chance_stat: str = ""
    critical_multiplier: float = 1.5
    on_hit_event: str = ""  # gameplay event reported for every landed hit
    armor_break: int = 0  # super armor holds while the target's armor level is above this
    knockdown: bool = False
    knockdown_time: float = 0.0  # 0 = the target's own knockdown_time

    def __init__(
        self,
        attack_id,
        display_name="",
        *,
        damage=None,
        damage_formula_id="",
        damage_resource="hp",
        tags=(),
        poise_damage=0.0,
        hitstun=0.0,
        knockback=0.0,
        knockback_direction="away",
        knockback_angle=0.0,
        knockback_lift=0.0,
        hitstop=0.0,
        hitstop_scope="participants",
        target_iframes=0.0,
        max_targets=0,
        critical_chance=0.0,
        critical_chance_stat="",
        critical_multiplier=1.5,
        on_hit_event="",
        armor_break=0,
        knockdown=False,
        knockdown_time=0.0,
    ):
        attack_id = str(attack_id).strip()
        if not attack_id:
            raise ValueError("attack_id is required")
        if damage is not None and not isinstance(damage, ValueFormula):
            raise TypeError("damage must be ValueFormula")
        if knockback_direction not in KNOCKBACK_DIRECTIONS:
            raise ValueError(f"knockback_direction must be one of {KNOCKBACK_DIRECTIONS}")
        if hitstop_scope not in HITSTOP_SCOPES:
            raise ValueError(f"hitstop_scope must be one of {HITSTOP_SCOPES}")
        resource = str(damage_resource).strip()
        if not resource:
            raise ValueError("damage_resource is required")
        if int(max_targets) < 0:
            raise ValueError("max_targets must be >= 0")
        set_ = object.__setattr__
        set_(self, "attack_id", attack_id)
        set_(self, "display_name", str(display_name or attack_id))
        set_(self, "damage", damage)
        set_(self, "damage_formula_id", str(damage_formula_id).strip())
        set_(self, "damage_resource", resource)
        set_(self, "tags", tuple(sorted({normalize_tag(t) for t in tags})))
        set_(self, "poise_damage", _number(poise_damage, "poise_damage", minimum=0.0))
        set_(self, "hitstun", _number(hitstun, "hitstun", minimum=0.0))
        set_(self, "knockback", _number(knockback, "knockback"))
        set_(self, "knockback_direction", knockback_direction)
        set_(self, "knockback_angle", _number(knockback_angle, "knockback_angle"))
        set_(self, "knockback_lift", _number(knockback_lift, "knockback_lift"))
        set_(self, "hitstop", _number(hitstop, "hitstop", minimum=0.0))
        set_(self, "hitstop_scope", hitstop_scope)
        set_(self, "target_iframes", _number(target_iframes, "target_iframes", minimum=0.0))
        set_(self, "max_targets", int(max_targets))
        set_(self, "critical_chance", _number(critical_chance, "critical_chance", minimum=0.0, maximum=1.0))
        set_(self, "critical_chance_stat", str(critical_chance_stat).strip())
        set_(self, "critical_multiplier", _number(critical_multiplier, "critical_multiplier", minimum=0.0))
        set_(self, "on_hit_event", str(on_hit_event).strip())
        if int(armor_break) < 0:
            raise ValueError("armor_break must be >= 0")
        set_(self, "armor_break", int(armor_break))
        set_(self, "knockdown", bool(knockdown))
        set_(self, "knockdown_time", _number(knockdown_time, "knockdown_time", minimum=0.0))

    def to_data(self):
        return {
            "schema": "asteria.attack",
            "version": 1,
            "attack_id": self.attack_id,
            "display_name": self.display_name,
            "damage": None if self.damage is None else self.damage.to_data(),
            "damage_formula_id": self.damage_formula_id,
            "damage_resource": self.damage_resource,
            "tags": list(self.tags),
            "poise_damage": self.poise_damage,
            "hitstun": self.hitstun,
            "knockback": self.knockback,
            "knockback_direction": self.knockback_direction,
            "knockback_angle": self.knockback_angle,
            "knockback_lift": self.knockback_lift,
            "hitstop": self.hitstop,
            "hitstop_scope": self.hitstop_scope,
            "target_iframes": self.target_iframes,
            "max_targets": self.max_targets,
            "critical_chance": self.critical_chance,
            "critical_chance_stat": self.critical_chance_stat,
            "critical_multiplier": self.critical_multiplier,
            "on_hit_event": self.on_hit_event,
            "armor_break": self.armor_break,
            "knockdown": self.knockdown,
            "knockdown_time": self.knockdown_time,
        }

    @classmethod
    def from_data(cls, data):
        data = dict(data)
        if data.pop("schema", None) != "asteria.attack" or data.pop("version", None) != 1:
            raise ValueError("unsupported attack definition")
        damage = data.pop("damage", None)
        known = set(cls.__dataclass_fields__)
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown attack fields: {sorted(unknown)}")
        return cls(damage=None if damage is None else ValueFormula.from_data(damage), **data)


__all__ = ["HITSTOP_SCOPES", "KNOCKBACK_DIRECTIONS", "AttackDefinition"]
