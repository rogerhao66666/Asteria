"""Deterministic canonical tileset model; tile size is declared, never engine-fixed."""

from dataclasses import dataclass
from typing import Any

from .canonical import AssetSource, CanonicalAsset, ValidationIssue, ValidationReport


@dataclass(frozen=True, slots=True)
class TileCollision:
    kind: str = "none"
    points: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True, slots=True)
class TileDef:
    tile_id: int
    terrain: str | None = None
    collision: TileCollision = TileCollision()
    properties: tuple[tuple[str, Any], ...] = ()
    animation: tuple[int, ...] = ()
    frame_ms: float | None = None

    def __post_init__(self):
        if self.tile_id < 0:
            raise ValueError("tile id")
        if self.animation and (self.frame_ms is None or self.frame_ms <= 0):
            raise ValueError("animated tile needs positive frame_ms")


@dataclass(frozen=True, slots=True)
class TilesetAsset:
    canonical: CanonicalAsset
    image_size: tuple[int, int]
    tile_size: tuple[int, int]
    columns: int
    rows: int
    tiles: tuple[TileDef, ...] = ()
    margin: int = 0
    spacing: int = 0

    def __post_init__(self):
        if self.canonical.kind != "tileset":
            raise ValueError("kind")
        if min(*self.image_size, *self.tile_size, self.columns, self.rows) <= 0:
            raise ValueError("dimensions")
        if self.margin < 0 or self.spacing < 0:
            raise ValueError("layout")
        expected_w = self.margin * 2 + self.columns * self.tile_size[0] + max(0, self.columns - 1) * self.spacing
        expected_h = self.margin * 2 + self.rows * self.tile_size[1] + max(0, self.rows - 1) * self.spacing
        if (expected_w, expected_h) != self.image_size:
            raise ValueError("image/grid mismatch")
        ids = [x.tile_id for x in self.tiles]
        if len(ids) != len(set(ids)) or any(i >= self.columns * self.rows for i in ids):
            raise ValueError("tile definitions")

    def tile(self, tile_id):
        return next((x for x in self.tiles if x.tile_id == tile_id), TileDef(tile_id))


class TilesetValidator:
    def validate(self, a):
        issues = []
        for t in a.tiles:
            if t.collision.kind == "polygon" and len(t.collision.points) < 3:
                issues.append(ValidationIssue("tile.collision.polygon", str(t.tile_id)))
            for f in t.animation:
                if f < 0 or f >= a.columns * a.rows:
                    issues.append(ValidationIssue("tile.animation.frame", str(t.tile_id)))
        return ValidationReport(a.canonical.asset_id, tuple(issues))


def tileset_asset(asset_id, uri, image_size, tile_size, columns, rows, **kw):
    return TilesetAsset(
        CanonicalAsset(asset_id, "tileset", AssetSource(uri)), image_size, tile_size, columns, rows, **kw
    )
