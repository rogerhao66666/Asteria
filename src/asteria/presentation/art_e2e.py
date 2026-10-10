"""Full production Art/Presentation frame coordinator.

Composes existing actor/attachment/property, camera/material/light/VFX/audio/text
and renderer contracts. It intentionally adds no gameplay vocabulary.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Sequence
from .e2e_pipeline import PresentationE2EPipeline
from .production_preview import ProductionPreviewSession
from .material_runtime import LightingRuntime, MaterialState
from .vfx_runtime import VFXRuntime
from .render_integration import DrawPacket, RenderTransform
from .text_render_integration import TextRenderPacket
from .render_backend import PresentationBackendExecutor, BackendFrameStats


def apply_light_channels(lighting: LightingRuntime, values: Mapping[str, float]) -> None:
    """Route `light.<id>.<property>` without predefined light semantics."""
    grouped = {}
    for path, value in values.items():
        parts = path.split(".", 2)
        if len(parts) == 3 and parts[0] == "light":
            grouped.setdefault(parts[1], {})[parts[2]] = value
    for light_id, props in grouped.items():
        lighting.apply(light_id, props)


def vfx_draw_packets(vfx: VFXRuntime, z: float = 0) -> tuple[DrawPacket, ...]:
    """Submit visual particles through the ordinary renderer path."""
    out = []
    for p in vfx.frame().particles:
        if p.asset_id and p.alive:
            out.append(
                DrawPacket(
                    p.asset_id,
                    RenderTransform(p.x, p.y, p.rotation_deg, p.scale, p.scale, p.opacity, True),
                    z,
                    None,
                    p.id,
                )
            )
    return tuple(out)


@dataclass(frozen=True, slots=True)
class ArtFrame:
    time_ms: float
    visuals: tuple[DrawPacket, ...]
    texts: tuple[TextRenderPacket, ...]
    material: MaterialState
    lights: tuple
    audio: tuple
    backend_stats: BackendFrameStats


class ArtPresentationRuntime:
    def __init__(
        self,
        pipeline: PresentationE2EPipeline,
        preview: ProductionPreviewSession,
        lighting: LightingRuntime,
        renderer: PresentationBackendExecutor,
    ):
        self.pipeline = pipeline
        self.preview = preview
        self.lighting = lighting
        self.renderer = renderer

    def render(self, frame_id: int, time_ms: float, texts: Sequence[TextRenderPacket] = ()) -> ArtFrame:
        pf = self.pipeline.sample(time_ms)
        pp = self.preview.sample(time_ms)
        # Pipeline keeps unknown/custom paths; light routing is generic and project-defined.
        apply_light_channels(self.lighting, pf.channels.custom)
        visuals = tuple(pf.draw_packets) + vfx_draw_packets(self.preview.vfx)
        stats = self.renderer.execute(frame_id, visuals, tuple(texts))
        return ArtFrame(time_ms, visuals, tuple(texts), pp.material, self.lighting.snapshot(), pp.audio, stats)
