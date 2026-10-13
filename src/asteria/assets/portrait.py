"""Canonical portrait art; UI/dialogue chrome remains presentation-owned."""

from dataclasses import dataclass
from typing import Any

from .canonical import AssetSource, CanonicalAsset, ValidationIssue, ValidationReport


@dataclass(frozen=True, slots=True)
class NormalizedRect:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self):
        if (
            self.width <= 0
            or self.height <= 0
            or min(self.x, self.y) < 0
            or self.x + self.width > 1
            or self.y + self.height > 1
        ):
            raise ValueError("normalized rect")


@dataclass(frozen=True, slots=True)
class PortraitVariant:
    name: str
    image_uri: str
    size: tuple[int, int]
    focal_point: tuple[float, float] = (0.5, 0.5)
    safe_crop: NormalizedRect | None = None
    metadata: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self):
        if not self.name or not self.image_uri:
            raise ValueError("name/image")
        if self.size[0] <= 0 or self.size[1] <= 0:
            raise ValueError("size")
        if not (0 <= self.focal_point[0] <= 1 and 0 <= self.focal_point[1] <= 1):
            raise ValueError("focal point")


@dataclass(frozen=True, slots=True)
class PortraitAsset:
    canonical: CanonicalAsset
    variants: tuple[PortraitVariant, ...]
    default_variant: str
    subject_ref: str | None = None
    properties: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self):
        if self.canonical.kind != "portrait":
            raise ValueError("kind")
        names = [v.name for v in self.variants]
        if not names or len(names) != len(set(names)):
            raise ValueError("variants")
        if self.default_variant not in names:
            raise ValueError("default")

    def variant(self, name=None):
        return next(v for v in self.variants if v.name == (name or self.default_variant))


class PortraitValidator:
    def validate(self, a):
        issues = []
        for v in a.variants:
            md = dict(v.metadata)
            if any(k in md for k in ("dialogue_box_baked", "ui_chrome_baked", "nameplate_baked")):
                issues.append(
                    ValidationIssue(
                        "portrait.baked_ui", f"{v.name}: UI chrome must remain presentation-owned"
                    )
                )
        return ValidationReport(a.canonical.asset_id, tuple(issues))


def portrait_asset(asset_id, uri, variants, default_variant="default", **kw):
    return PortraitAsset(
        CanonicalAsset(asset_id, "portrait", AssetSource(uri)),
        tuple(variants),
        default_variant,
        **kw,
    )
