from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from asteria.assets.types import AssetRef

EMPTY_TILE = -1


@dataclass(slots=True)
class TileChunk:
    chunk_x: int
    chunk_y: int
    width: int
    height: int
    tiles: list[int]

    @classmethod
    def empty(cls, chunk_x, chunk_y, width, height):
        if width <= 0 or height <= 0:
            raise ValueError("chunk dimensions")
        return cls(chunk_x, chunk_y, width, height, [EMPTY_TILE] * (width * height))

    def validate(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError("chunk dimensions")
        if len(self.tiles) != self.width * self.height:
            raise ValueError("chunk tile count mismatch")
        if any(not isinstance(t, int) or t < EMPTY_TILE for t in self.tiles):
            raise ValueError("invalid tile id")

    def _index(self, x, y):
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            raise IndexError("tile coordinate")
        return y * self.width + x

    def get(self, x, y):
        return self.tiles[self._index(x, y)]

    def set(self, x, y, tile_id):
        if not isinstance(tile_id, int) or tile_id < EMPTY_TILE:
            raise ValueError("invalid tile id")
        self.tiles[self._index(x, y)] = tile_id


@dataclass(slots=True)
class TileLayer:
    name: str
    order: int = 0
    visible: bool = True
    opacity: float = 1.0
    collision_enabled: bool = False
    chunks: dict[tuple[int, int], TileChunk] = field(default_factory=dict)

    def validate(self):
        if not self.name:
            raise ValueError("layer name required")
        if not 0.0 <= self.opacity <= 1.0:
            raise ValueError("opacity 0..1")
        for key, chunk in self.chunks.items():
            if key != (chunk.chunk_x, chunk.chunk_y):
                raise ValueError("chunk key mismatch")
            chunk.validate()


@dataclass(slots=True)
class TileMap:
    tileset: AssetRef
    tile_width: int
    tile_height: int
    chunk_width: int = 32
    chunk_height: int = 32
    layers: list[TileLayer] = field(default_factory=list)

    def validate(self):
        if self.tileset.expected_kind not in (None, "tileset"):
            raise TypeError("tileset ref")
        if min(self.tile_width, self.tile_height, self.chunk_width, self.chunk_height) <= 0:
            raise ValueError("dimensions")
        if len({l.name for l in self.layers}) != len(self.layers):
            raise ValueError("duplicate layer name")
        for layer in self.layers:
            layer.validate()

    def ordered_layers(self):
        return tuple(sorted(self.layers, key=lambda l: l.order))
