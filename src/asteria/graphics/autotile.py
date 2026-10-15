"""Terrain autotiling (Godot-style terrain painting): the tile shown follows its neighbours.

A terrain's tiles are told apart by a neighbour bitmask. ``edge4`` looks at the four sides
(N=1, E=2, S=4, W=8; 16 tiles) and ``blob8`` also at the corners, counted only when both sides
next to them are filled (the usual 47-tile blob). The tileset says which tile has which mask with
the tile's ``terrain`` field (the terrain id) and a ``mask:<n>`` tag. A missing mask falls back to
the closest tile asking for fewer neighbours, so a half-drawn set still paints.
"""

from __future__ import annotations

from dataclasses import dataclass

from .tilemap import EMPTY_TILE

N, E, S, W = 1, 2, 4, 8
NE, SE, SW, NW = 16, 32, 64, 128
MODES = ("edge4", "blob8")
_SIDES = ((0, -1, N), (1, 0, E), (0, 1, S), (-1, 0, W))
_CORNERS = ((1, -1, NE, N | E), (1, 1, SE, S | E), (-1, 1, SW, S | W), (-1, -1, NW, N | W))


@dataclass(frozen=True, slots=True)
class AutotileSet:
    terrain_id: str
    mode: str
    masks: tuple[tuple[int, int], ...]  # (mask, tile id)

    def __init__(self, terrain_id, masks, mode="edge4"):
        terrain_id = str(terrain_id).strip()
        if not terrain_id:
            raise ValueError("terrain_id is required")
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        pairs = tuple(sorted((int(m), int(t)) for m, t in dict(masks).items()))
        if not pairs:
            raise ValueError("an autotile set needs at least one tile")
        limit = 16 if mode == "edge4" else 256
        if any(not 0 <= m < limit for m, _ in pairs):
            raise ValueError("a mask is out of range for the mode")
        object.__setattr__(self, "terrain_id", terrain_id)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "masks", pairs)

    def tile_for(self, mask):
        """The tile for ``mask``; else the tile whose mask is a subset sharing the most bits."""
        table = dict(self.masks)
        if mask in table:
            return table[mask]
        best, best_bits = None, -1
        for candidate, tile in self.masks:
            if candidate & ~mask:
                continue  # it asks for a neighbour that is not there
            bits = bin(candidate).count("1")
            if bits > best_bits:
                best, best_bits = tile, bits
        return best if best is not None else self.masks[0][1]


def build_autotile_set(tileset, terrain_id, mode="edge4"):
    """Gather the tiles of ``terrain_id`` from a tileset: those whose ``terrain`` is the id and
    that carry a ``mask:<n>`` tag."""
    masks = {}
    for tile_id, definition in tileset.tiles.items():
        if definition.terrain != terrain_id:
            continue
        for tag in definition.tags:
            if tag.startswith("mask:") and tag[5:].isdigit():
                masks[int(tag[5:])] = tile_id
    return AutotileSet(terrain_id, masks, mode)


def neighbour_mask(filled, x, y, mode="edge4"):
    """Bitmask of the filled neighbours of ``(x, y)``; ``filled(x, y)`` says if a cell is."""
    mask = 0
    for dx, dy, bit in _SIDES:
        if filled(x + dx, y + dy):
            mask |= bit
    if mode == "blob8":
        for dx, dy, bit, sides in _CORNERS:
            if mask & sides == sides and filled(x + dx, y + dy):
                mask |= bit
    return mask


def _tile_at(tilemap, layer, x, y):
    cx, cy = x // tilemap.chunk_width, y // tilemap.chunk_height
    chunk = layer.chunks.get((cx, cy))
    if chunk is None:
        return EMPTY_TILE
    return chunk.get(x - cx * tilemap.chunk_width, y - cy * tilemap.chunk_height)


def terrain_updates(tilemap, layer, tileset, autotiles, cells, *, erase=False):
    """New tile ids after painting (or erasing) ``cells`` with a terrain.

    ``autotiles``: ``{terrain id: AutotileSet}``. A cell is "filled" for a terrain when its tile's
    terrain is that terrain (cells being painted count as filled, cells being erased as empty).
    Returns ``{(x, y): tile id}`` for the painted cells and every neighbour that must change.
    """
    if len(autotiles) != 1:
        raise ValueError("paint one terrain at a time")
    ((terrain_id, auto),) = autotiles.items()
    painted = {(int(x), int(y)) for x, y in cells}

    def filled(x, y):
        if (x, y) in painted:
            return not erase
        tile = _tile_at(tilemap, layer, x, y)
        if tile == EMPTY_TILE:
            return False
        definition = tileset.tiles.get(tile)
        return definition is not None and definition.terrain == terrain_id

    touched = set(painted)
    for x, y in painted:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                touched.add((x + dx, y + dy))
    updates = {}
    for x, y in sorted(touched):
        if (x, y) in painted and erase:
            updates[(x, y)] = EMPTY_TILE
        elif filled(x, y):
            updates[(x, y)] = auto.tile_for(neighbour_mask(filled, x, y, auto.mode))
    return updates
