"""Monster asset contract: animated, arbitrary dimensions/counts/directions."""

from dataclasses import dataclass
from .canonical import CanonicalAsset, AssetSource, ValidationIssue, ValidationReport
from asteria.presentation.fidelity import HighFidelityClip


@dataclass(frozen=True, slots=True)
class MonsterAnimation:
    name: str
    clip: HighFidelityClip
    directions: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.name:
            raise ValueError("animation name")
        if self.directions and len(set(self.directions)) != len(self.directions):
            raise ValueError("duplicate directions")


@dataclass(frozen=True, slots=True)
class MonsterAsset:
    canonical: CanonicalAsset
    animations: tuple[MonsterAnimation, ...]
    default_animation: str | None = None
    collision_bounds: tuple[float, float, float, float] | None = None
    anchor: tuple[float, float] | None = None

    def __post_init__(self):
        if self.canonical.kind != "monster":
            raise ValueError("kind must be monster")
        names = [x.name for x in self.animations]
        if len(names) != len(set(names)):
            raise ValueError("duplicate animation names")
        if self.default_animation is not None and self.default_animation not in names:
            raise ValueError("missing default animation")

    def animation(self, name):
        return next(x for x in self.animations if x.name == name)


class MonsterValidator:
    def validate(self, a: MonsterAsset):
        issues = []
        if not a.animations:
            issues.append(ValidationIssue("monster.animation.missing", "monster has no animation", "warning"))
        for x in a.animations:
            if not x.clip.frames:
                issues.append(ValidationIssue("monster.frames.missing", f"{x.name} has no frames"))
            if x.clip.frame_size[0] <= 0 or x.clip.frame_size[1] <= 0:
                issues.append(ValidationIssue("monster.frame_size.invalid", x.name))
        return ValidationReport(a.canonical.asset_id, tuple(issues))


def monster_asset(asset_id, source_uri, animations, **kw):
    return MonsterAsset(CanonicalAsset(asset_id, "monster", AssetSource(source_uri)), tuple(animations), **kw)
