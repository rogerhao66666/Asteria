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
    # filled (non-empty) cells, kept by ``set`` so an erase need not rescan the chunk; only a
    # hint (``is_empty`` checks the cells before saying yes), as ``tiles`` is a plain list
    _filled: int = field(default=0, init=False, repr=False, compare=False)

    def __post_init__(self):
        tiles = self.tiles
        self._filled = len(tiles) - tiles.count(EMPTY_TILE) if hasattr(tiles, "count") else 0

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
        index = self._index(x, y)
        old = self.tiles[index]
        self.tiles[index] = tile_id
        if old == EMPTY_TILE:
            if tile_id != EMPTY_TILE:
                self._filled += 1
        elif tile_id == EMPTY_TILE:
            self._filled -= 1

    def is_empty(self):
        """True when every cell is empty: O(1) while the cells change through ``set``."""
        if self._filled > 0:
            return False
        if all(t == EMPTY_TILE for t in self.tiles):
            return True
        self._filled = len(self.tiles) - self.tiles.count(EMPTY_TILE)  # changed behind set
        return False


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
