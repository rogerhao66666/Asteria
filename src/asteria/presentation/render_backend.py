"""Concrete renderer-backend execution boundary for presentation packets.

The engine owns ordering/lifetime/reference semantics; graphics implementations
provide the small RendererBackend protocol (ModernGL/Pygame/etc.).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol, Sequence
from .render_integration import DrawPacket
from .text_render_integration import TextRenderPacket


class RendererBackend(Protocol):
    def begin_frame(self, frame_id: int) -> None: ...
    def resolve_visual(self, asset_id: str) -> Any: ...
    def draw_visual(self, resource: Any, packet: DrawPacket) -> None: ...
    def resolve_font(self, asset_id: str | None) -> Any: ...
    def draw_text(self, font: Any, packet: TextRenderPacket) -> None: ...
    def end_frame(self) -> None: ...


@dataclass(frozen=True, slots=True)
class BackendFrameStats:
    frame_id: int
    visual_packets: int
    text_packets: int
    visual_resolves: int
    font_resolves: int


class PresentationBackendExecutor:
    """Executes canonical packets against a concrete backend.

    Resolution is cached by stable asset id across frames. Invalidation is
    explicit so AssetStore reconciliation/hot reload can release stale handles.
    """

    def __init__(self, backend: RendererBackend):
        self.backend = backend
        self._visuals = {}
        self._fonts = {}

    def invalidate(self, asset_id: str) -> None:
        self._visuals.pop(asset_id, None)
        self._fonts.pop(asset_id, None)

    def clear_resources(self) -> None:
        self._visuals.clear()
        self._fonts.clear()

    def execute(
        self, frame_id: int, visuals: Sequence[DrawPacket] = (), texts: Sequence[TextRenderPacket] = ()
    ) -> BackendFrameStats:
        vr = fr = 0
        self.backend.begin_frame(frame_id)
        try:
            for p in sorted(visuals, key=lambda q: (q.z, q.owner_id or "", q.component_id or "", q.asset_id)):
                if not p.transform.visible or p.transform.opacity <= 0:
                    continue
                if p.asset_id not in self._visuals:
                    self._visuals[p.asset_id] = self.backend.resolve_visual(p.asset_id)
                    vr += 1
                self.backend.draw_visual(self._visuals[p.asset_id], p)
            for p in sorted(texts, key=lambda q: (q.z, q.instance_id)):
                if p.opacity <= 0:
                    continue
                key = p.font_asset_id
                if key not in self._fonts:
                    self._fonts[key] = self.backend.resolve_font(key)
                    fr += 1
                self.backend.draw_text(self._fonts[key], p)
        finally:
            self.backend.end_frame()
        return BackendFrameStats(frame_id, len(visuals), len(texts), vr, fr)
