"""Backend-neutral texture draw command values."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextureDraw:
    texture_asset_id: str
    source: tuple[int, int, int, int]
    screen_x: float
    screen_y: float
    width: float
    height: float
    layer: int = 0
    depth: float = 0.0
    opacity: float = 1.0
    flip_x: bool = False
    rotation_deg: float = 0.0
    tint: tuple | None = None
