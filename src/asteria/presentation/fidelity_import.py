"""Loss-aware source-to-canonical fidelity contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from .fidelity import FrameTiming, HighFidelityClip, VisualLayer


@dataclass(frozen=True, slots=True)
class SourceFrame:
    asset_id: str
    width: int
    height: int
    duration_ms: float
    alpha: bool = True
    pivot: tuple[float, float] = (0, 0)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0 or self.duration_ms <= 0:
            raise ValueError("invalid source frame")


@dataclass(frozen=True, slots=True)
class SourceLayer:
    asset_id: str
    z: int = 0
    blend_mode: str = "alpha"
    opacity: float = 1
    material: str | None = None


@dataclass(frozen=True, slots=True)
class FidelitySource:
    id: str
    frames: tuple[SourceFrame, ...]
    layers: tuple[SourceLayer, ...] = ()
    detached_candidates: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id or not self.frames:
            raise ValueError("source requires id and frames")


@dataclass(frozen=True, slots=True)
class FidelityImportReport:
    clip: HighFidelityClip
    alpha_preserved: bool
    timing_preserved: bool
    resolution_preserved: bool
    layers_preserved: bool
    review_required: tuple[str, ...]
    source_metadata: Mapping[str, object]


class FidelityImporter:
    """Canonicalizes without silently flattening/dropping source information."""

    def import_source(self, src: FidelitySource) -> FidelityImportReport:
        sizes = {(f.width, f.height) for f in src.frames}
        review = []
        # Variable source dimensions are not silently resampled: preserve maximum canvas
        # and require placement review.
        if len(sizes) > 1:
            review.append("variable_frame_dimensions")
        if src.detached_candidates:
            review.append("detached_candidates")
        size = (max(f.width for f in src.frames), max(f.height for f in src.frames))
        pivots = {f.pivot for f in src.frames}
        if len(pivots) > 1:
            review.append("per_frame_pivot_variation")
        layers = tuple(VisualLayer(x.asset_id, x.z, x.blend_mode, x.opacity, x.material) for x in src.layers)
        clip = HighFidelityClip(
            src.id,
            size,
            tuple(f.asset_id for f in src.frames),
            tuple(FrameTiming(f.duration_ms) for f in src.frames),
            src.frames[0].pivot,
            layers,
        )
        return FidelityImportReport(
            clip=clip,
            alpha_preserved=all(f.alpha for f in src.frames),
            timing_preserved=True,
            resolution_preserved=len(sizes) == 1,
            layers_preserved=True,
            review_required=tuple(review),
            source_metadata=dict(src.metadata),
        )
