"""Canonical VFX assets. Visual capability is independent from gameplay meaning."""

from dataclasses import dataclass
from typing import Any

from asteria.presentation.fidelity import HighFidelityClip

from .canonical import AssetSource, CanonicalAsset, ValidationIssue, ValidationReport


@dataclass(frozen=True, slots=True)
class VFXAnchor:
    mode: str = "local"
    offset: tuple[float, float] = (0.0, 0.0)
    bone_or_socket: str | None = None


@dataclass(frozen=True, slots=True)
class VFXVariant:
    name: str
    clip: HighFidelityClip
    anchor: VFXAnchor = VFXAnchor()
    scale: tuple[float, float] = (1.0, 1.0)
    rotation_deg: float = 0.0
    properties: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self):
        if not self.name:
            raise ValueError("name")
        if self.scale[0] == 0 or self.scale[1] == 0:
            raise ValueError("scale")


@dataclass(frozen=True, slots=True)
class VFXAsset:
    canonical: CanonicalAsset
    variants: tuple[VFXVariant, ...]
    default_variant: str
    presentation_tags: frozenset[str] = frozenset()
    properties: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self):
        if self.canonical.kind != "vfx":
            raise ValueError("kind")
        names = [v.name for v in self.variants]
        if not names or len(names) != len(set(names)):
            raise ValueError("variants")
        if self.default_variant not in names:
            raise ValueError("default")

    def variant(self, name=None):
        return next(v for v in self.variants if v.name == (name or self.default_variant))


class VFXValidator:
    def validate(self, a):
        issues = []
        for v in a.variants:
            if not v.clip.frames:
                issues.append(ValidationIssue("vfx.frames.missing", v.name))
            if v.anchor.mode == "socket" and not v.anchor.bone_or_socket:
                issues.append(ValidationIssue("vfx.anchor.socket_missing", v.name))
        return ValidationReport(a.canonical.asset_id, tuple(issues))


def vfx_asset(asset_id, uri, variants, default_variant="default", **kw):
    return VFXAsset(CanonicalAsset(asset_id, "vfx", AssetSource(uri)), tuple(variants), default_variant, **kw)
