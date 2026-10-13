"""Canonical icon assets. Semantic usage is project-defined, not engine-enumerated."""

from dataclasses import dataclass
from typing import Any

from .canonical import AssetSource, CanonicalAsset, ValidationIssue, ValidationReport


@dataclass(frozen=True, slots=True)
class AtlasRegion:
    image_uri: str
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self):
        if not self.image_uri:
            raise ValueError("image_uri")
        if min(self.x, self.y) < 0 or self.width <= 0 or self.height <= 0:
            raise ValueError("atlas region")


@dataclass(frozen=True, slots=True)
class IconVariant:
    name: str
    image_uri: str | None = None
    atlas: AtlasRegion | None = None
    size: tuple[int, int] | None = None
    metadata: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self):
        if not self.name:
            raise ValueError("name")
        if (self.image_uri is None) == (self.atlas is None):
            raise ValueError("variant requires exactly one image source")
        if self.size is not None and (self.size[0] <= 0 or self.size[1] <= 0):
            raise ValueError("size")


@dataclass(frozen=True, slots=True)
class IconAsset:
    canonical: CanonicalAsset
    variants: tuple[IconVariant, ...]
    default_variant: str
    usages: frozenset[str] = frozenset()
    properties: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self):
        if self.canonical.kind != "icon":
            raise ValueError("kind")
        names = [v.name for v in self.variants]
        if not names:
            raise ValueError("variants")
        if len(names) != len(set(names)):
            raise ValueError("duplicate variants")
        if self.default_variant not in names:
            raise ValueError("default variant")
        if len(set(k for k, _ in self.properties)) != len(self.properties):
            raise ValueError("duplicate properties")

    def variant(self, name=None):
        target = name or self.default_variant
        return next(v for v in self.variants if v.name == target)


class IconValidator:
    def validate(self, a: IconAsset):
        issues = []
        for v in a.variants:
            if v.atlas and v.size and v.size != (v.atlas.width, v.atlas.height):
                issues.append(ValidationIssue("icon.atlas.size_mismatch", v.name))
        return ValidationReport(a.canonical.asset_id, tuple(issues))


def icon_asset(asset_id, source_uri, variants, default_variant="default", **kw):
    return IconAsset(
        CanonicalAsset(asset_id, "icon", AssetSource(source_uri)),
        tuple(variants),
        default_variant,
        **kw,
    )
