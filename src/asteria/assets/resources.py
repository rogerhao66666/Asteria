from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextureResource:
    asset_id: str
    width: int
    height: int
    backend_handle: object


class TextureResourceCache:
    def __init__(self, loader):
        self._loader = loader
        self._items = {}

    def get(self, asset_id, source_path):
        if asset_id in self._items:
            return self._items[asset_id]
        resource = self._loader(asset_id, source_path)
        if resource.asset_id != asset_id:
            raise ValueError("loader returned mismatched asset id")
        self._items[asset_id] = resource
        return resource

    def contains(self, asset_id):
        return asset_id in self._items

    def remove(self, asset_id):
        return self._items.pop(asset_id, None)

    def clear(self):
        self._items.clear()

    def __len__(self):
        return len(self._items)


# Canonical non-image resources (Asset System branch)
from typing import Any
from .canonical import CanonicalAsset, AssetSource, ValidationIssue, ValidationReport


@dataclass(frozen=True, slots=True)
class AudioAsset:
    canonical: CanonicalAsset
    uri: str
    duration_ms: float | None = None
    channels: int | None = None
    sample_rate: int | None = None
    loop_region_ms: tuple[float, float] | None = None
    properties: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self):
        if self.canonical.kind != "audio" or not self.uri:
            raise ValueError("audio")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("duration")
        if self.channels is not None and self.channels <= 0:
            raise ValueError("channels")
        if self.sample_rate is not None and self.sample_rate <= 0:
            raise ValueError("sample_rate")
        if self.loop_region_ms and not (0 <= self.loop_region_ms[0] < self.loop_region_ms[1]):
            raise ValueError("loop")


@dataclass(frozen=True, slots=True)
class FontAsset:
    canonical: CanonicalAsset
    uri: str
    family_hint: str | None = None
    fallback_refs: tuple[str, ...] = ()
    properties: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self):
        if self.canonical.kind != "font" or not self.uri:
            raise ValueError("font")


@dataclass(frozen=True, slots=True)
class MaterialAsset:
    canonical: CanonicalAsset
    shader_ref: str
    parameters: tuple[tuple[str, Any], ...] = ()
    texture_refs: tuple[tuple[str, str], ...] = ()
    properties: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self):
        if self.canonical.kind != "material" or not self.shader_ref:
            raise ValueError("material")
        if len({k for k, _ in self.parameters}) != len(self.parameters):
            raise ValueError("duplicate parameter")
        if len({k for k, _ in self.texture_refs}) != len(self.texture_refs):
            raise ValueError("duplicate texture slot")


class ResourceValidator:
    def validate(self, a):
        issues = []
        if (
            isinstance(a, AudioAsset)
            and a.loop_region_ms
            and a.duration_ms is not None
            and a.loop_region_ms[1] > a.duration_ms
        ):
            issues.append(ValidationIssue("audio.loop.out_of_range", "loop end exceeds duration"))
        if isinstance(a, FontAsset) and a.canonical.asset_id in a.fallback_refs:
            issues.append(ValidationIssue("font.fallback.self", "font cannot fallback to itself"))
        return ValidationReport(a.canonical.asset_id, tuple(issues))


def _base(i, k, u):
    return CanonicalAsset(i, k, AssetSource(u))


def audio_asset(i, u, **kw):
    return AudioAsset(_base(i, "audio", u), u, **kw)


def font_asset(i, u, **kw):
    return FontAsset(_base(i, "font", u), u, **kw)


def material_asset(i, shader_ref, source_uri="", **kw):
    return MaterialAsset(_base(i, "material", source_uri or shader_ref), shader_ref, **kw)
