"""Backend-neutral Animated Text -> font/renderer integration contract."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .animated_text import ResolvedText


@dataclass(frozen=True, slots=True)
class TextRenderPacket:
    instance_id: str
    text: str
    space: str
    x: float
    y: float
    scale: float
    rotation_deg: float
    opacity: float
    z: int
    font_asset_id: str | None = None
    material_asset_id: str | None = None
    style_id: str | None = None
    anchor_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class AnimatedTextRenderComposer:
    """Converts resolved runtime text to renderer packets without gameplay semantics.

    anchor_resolver(anchor_id) -> (x,y) is supplied by Scene/Actor integration.
    Screen-space text ignores world-anchor resolution by design.
    """

    def __init__(
        self,
        anchor_resolver: Callable[[str], tuple[float, float] | None] | None = None,
        font_exists: Callable[[str], bool] | None = None,
        material_exists: Callable[[str], bool] | None = None,
    ):
        self.anchor_resolver = anchor_resolver
        self.font_exists = font_exists
        self.material_exists = material_exists

    def compose_one(self, r: ResolvedText) -> TextRenderPacket:
        if r.font_asset_id and self.font_exists and not self.font_exists(r.font_asset_id):
            raise ValueError("unknown font asset")
        if (
            r.material_asset_id
            and self.material_exists
            and not self.material_exists(r.material_asset_id)
        ):
            raise ValueError("unknown material asset")
        x, y = r.transform.x, r.transform.y
        if r.space == "world" and r.anchor_id:
            if self.anchor_resolver is None:
                raise ValueError("world anchor resolver required")
            anchor = self.anchor_resolver(r.anchor_id)
            if anchor is None:
                raise ValueError("unknown world anchor")
            x += anchor[0]
            y += anchor[1]
        return TextRenderPacket(
            r.instance_id,
            r.text,
            r.space,
            x,
            y,
            r.transform.scale,
            r.transform.rotation_deg,
            r.transform.opacity,
            r.z_order,
            r.font_asset_id,
            r.material_asset_id,
            r.style_id,
            r.anchor_id,
            dict(r.metadata),
        )

    def compose(self, resolved) -> tuple[TextRenderPacket, ...]:
        packets = (self.compose_one(r) for r in resolved if r.transform.opacity > 0)
        return tuple(sorted(packets, key=lambda p: (p.z, p.instance_id)))
