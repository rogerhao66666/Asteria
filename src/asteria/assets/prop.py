"""Canonical props/environment assets: visual geometry plus optional gameplay-facing metadata."""

from dataclasses import dataclass
from typing import Any

from .canonical import AssetSource, CanonicalAsset, ValidationIssue, ValidationReport


@dataclass(frozen=True, slots=True)
class CollisionShape:
    kind: str
    points: tuple[tuple[float, float], ...] = ()
    size: tuple[float, float] | None = None
    offset: tuple[float, float] = (0.0, 0.0)


@dataclass(frozen=True, slots=True)
class InteractionPoint:
    name: str
    position: tuple[float, float]
    tags: frozenset[str] = frozenset()
    metadata: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class PropVisual:
    image_uri: str
    size: tuple[int, int]
    pivot: tuple[float, float]
    z_offset: float = 0.0
    opacity: float = 1.0
    material: str | None = None

    def __post_init__(self):
        if not self.image_uri:
            raise ValueError("image_uri")
        if self.size[0] <= 0 or self.size[1] <= 0:
            raise ValueError("size")
        if not 0 <= self.opacity <= 1:
            raise ValueError("opacity")


@dataclass(frozen=True, slots=True)
class PropAsset:
    canonical: CanonicalAsset
    visuals: tuple[PropVisual, ...]
    collisions: tuple[CollisionShape, ...] = ()
    interactions: tuple[InteractionPoint, ...] = ()
    properties: tuple[tuple[str, Any], ...] = ()
    animation_ref: str | None = None
    presentation_ref: str | None = None

    def __post_init__(self):
        if self.canonical.kind != "prop":
            raise ValueError("kind")
        names = [x.name for x in self.interactions]
        if len(names) != len(set(names)):
            raise ValueError("duplicate interaction names")
        if len(set(k for k, _ in self.properties)) != len(self.properties):
            raise ValueError("duplicate properties")


class PropValidator:
    def validate(self, a: PropAsset):
        issues = []
        if not a.visuals:
            issues.append(ValidationIssue("prop.visual.missing", "prop has no visual", "warning"))
        for c in a.collisions:
            if c.kind == "polygon" and len(c.points) < 3:
                issues.append(
                    ValidationIssue("prop.collision.polygon", "polygon needs >=3 points")
                )
            if c.kind in ("rect", "ellipse") and (
                c.size is None or c.size[0] <= 0 or c.size[1] <= 0
            ):
                issues.append(ValidationIssue("prop.collision.size", "shape needs positive size"))
        return ValidationReport(a.canonical.asset_id, tuple(issues))


def prop_asset(asset_id, source_uri, visuals, **kw):
    return PropAsset(
        CanonicalAsset(asset_id, "prop", AssetSource(source_uri)), tuple(visuals), **kw
    )
