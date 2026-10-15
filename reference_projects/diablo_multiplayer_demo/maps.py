"""Tile maps of the ARPG demo, laid out by code (deterministic): the town, the top-down field and
the side-view dungeon. Each returns the canonical tile map data plus the places the content needs
(spawn points, doors, enemies, platforms) in world units.
"""

from __future__ import annotations

import random

from asteria.assets.types import AssetRef
from asteria.graphics import EMPTY_TILE, TileChunk, TileLayer, TileMap
from asteria.graphics.serialization import tilemap_to_data

CHUNK = 16
# draw order: ground and decoration below characters, tree tops and roofs above (>= 100);
# the hidden collision layer only blocks
ORDERS = {"ground": 0, "decor": 10, "objects": 50, "above": 150, "collision": 500}


class Grid:
    """Layers of tile ids being painted; ``data(tileset_id)`` gives the TileMap data."""

    def __init__(self, atlas, width, height, seed):
        self.atlas, self.width, self.height = atlas, width, height
        self.rng = random.Random(seed)
        self.layers = {name: {} for name in ORDERS}
        self.reserved = set()  # roads and plazas: nothing is planted on them

    def put(self, layer, x, y, name):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.layers[layer][(x, y)] = self.atlas.ids[name]

    def solid(self, x, y):
        self.put("collision", x, y, "block")

    def clear_solid(self, x, y):
        self.layers["collision"].pop((x, y), None)

    def is_free(self, x, y, w=1, h=1):
        return all(
            (x + dx, y + dy) not in self.reserved
            and (x + dx, y + dy) not in self.layers["collision"]
            and (x + dx, y + dy) not in self.layers["objects"]
            and 0 <= x + dx < self.width
            and 0 <= y + dy < self.height
            for dx in range(w)
            for dy in range(h)
        )

    def fill(self, layer, x0, y0, x1, y1, names, weights=None):
        for y in range(y0, y1):
            for x in range(x0, x1):
                self.put(layer, x, y, self.rng.choices(names, weights)[0])

    def patch(self, name, x0, y0, x1, y1):
        """A 9-slice patch (``name.<dx>.<dy>`` cells, 3 x 3) over ``[x0, x1) x [y0, y1)``."""
        for y in range(y0, y1):
            for x in range(x0, x1):
                dx = 0 if x == x0 else 2 if x == x1 - 1 else 1
                dy = 0 if y == y0 else 2 if y == y1 - 1 else 1
                self.put("ground", x, y, f"{name}.{dx}.{dy}")
                self.reserved.add((x, y))

    def block(self, name, x, y, w, h, *, solid_rows=None, above_rows=0):
        """A multi-cell object: its top ``above_rows`` draw over characters; ``solid_rows`` (from
        the bottom, default all) block."""
        solid_rows = h if solid_rows is None else solid_rows
        for dy in range(h):
            for dx in range(w):
                layer = "above" if dy < above_rows else "objects"
                self.put(layer, x + dx, y + dy, f"{name}.{dx}.{dy}")
                if dy >= h - solid_rows:
                    self.solid(x + dx, y + dy)

    def data(self, tileset_id, size):
        layers = []
        for name, order in ORDERS.items():
            cells = self.layers[name]
            layer = TileLayer(
                name.capitalize(),
                order,
                name != "collision",
                1.0,
                name == "collision",
            )
            for (x, y), tile_id in cells.items():
                if tile_id == EMPTY_TILE:
                    continue
                key = (x // CHUNK, y // CHUNK)
                chunk = layer.chunks.get(key)
                if chunk is None:
                    chunk = layer.chunks[key] = TileChunk.empty(key[0], key[1], CHUNK, CHUNK)
                chunk.set(x % CHUNK, y % CHUNK, tile_id)
            layers.append(layer)
        tilemap = TileMap(AssetRef(tileset_id, "tileset"), size, size, CHUNK, CHUNK, layers)
        tilemap.validate()
        return tilemap_to_data(tilemap)


def _grass(g, dark=False):
    base = "grass_dark" if dark else "grass"
    g.fill(
        "ground",
        0,
        0,
        g.width,
        g.height,
        [base, f"{base}1", f"{base}2", f"{base}3"],
        [80, 7, 7, 6],
    )


def _tree_border(g, gaps=()):
    """Two rows of trees around the edge, leaving the ``gaps`` (sets of (x, y)) open."""
    for y in range(-1, g.height, 2):
        for x in range(-1, g.width, 2):
            edge = x <= 1 or y <= 1 or x >= g.width - 3 or y >= g.height - 3
            cells = [(x + dx, y + dy) for dx in (0, 1) for dy in (0, 1)]
            if not edge or any(c in gaps or c in g.reserved for c in cells):
                continue
            kind = g.rng.choice(("tree", "tree", "pine"))
            g.block(kind, x, y, 2, 2, solid_rows=1, above_rows=1)


def _scatter(g, names, count, area, *, solid=False):
    x0, y0, x1, y1 = area
    for _ in range(count):
        x, y = g.rng.randrange(x0, x1), g.rng.randrange(y0, y1)
        if g.is_free(x, y):
            g.put("decor" if not solid else "objects", x, y, g.rng.choice(names))
            if solid:
                g.solid(x, y)


def town(atlas):
    """A small walled town: a plaza, the merchant's shop, the smith's forge, homes, the class
    trainers' square, and a road east to the field."""
    w, h, s = 40, 26, 16
    g = Grid(atlas, w, h, "town")
    _grass(g)
    road = {(x, y) for x in range(w - 4, w) for y in range(11, 15)}
    _tree_border(g, road)
    g.patch("dirt", 10, 8, 30, 19)  # the plaza
    g.patch("dirt", 29, 11, w, 15)  # the road east
    g.block("shop", 13, 4, 3, 3, above_rows=1)
    g.block("forge", 22, 4, 3, 3, above_rows=1)
    g.block("house", 4, 8, 3, 3, above_rows=1)
    g.block("house2", 4, 15, 3, 3, above_rows=1)
    g.block("house", 32, 4, 3, 3, above_rows=1)
    g.block("torii", 18, 19, 3, 2, solid_rows=0, above_rows=1)
    for x, y, name in ((12, 6, "barrel"), (16, 6, "crate"), (21, 6, "pot"), (25, 6, "barrel")):
        g.put("objects", x, y, name)
        g.solid(x, y)
    _scatter(
        g,
        ["flower_y", "flower_s", "flower_r", "flower_w", "bush", "fern"],
        70,
        (2, 2, w - 2, h - 2),
    )
    tile = lambda x, y: ((x + 0.5) * s, (y + 0.5) * s)  # noqa: E731
    return {
        "grid": g,
        "size": s,
        "start": tile(19, 12),
        "from_field": tile(w - 3, 12.5),
        "to_field": tile(w - 1, 12.5),
        "merchant": tile(14, 7.4),
        "smith": tile(23, 7.4),
        "trainers": [tile(15, 16), tile(19.5, 16), tile(24, 16)],
        "elder": tile(19.5, 21.5),
        "villagers": [tile(8, 12), tile(30, 9), tile(27, 17)],
    }


def field(atlas):
    """Open grassland: tree groves, boulders and dirt roads; the town to the west, the dungeon
    gate to the east, a boss clearing in the north-east."""
    w, h, s = 72, 48, 16
    g = Grid(atlas, w, h, "field")
    _grass(g)
    west = {(x, y) for x in range(0, 4) for y in range(22, 26)}
    east = {(x, y) for x in range(w - 4, w) for y in range(30, 34)}
    _tree_border(g, west | east)
    g.patch("dirt", 0, 22, 30, 26)
    g.patch("dirt", 27, 22, 31, 34)
    g.patch("dirt", 27, 30, w, 34)
    g.patch("dirt", 50, 8, 64, 18)  # the boss clearing
    g.block("torii", w - 6, 29, 3, 2, solid_rows=0, above_rows=1)  # the dungeon gate
    groves = [(10, 6), (22, 10), (36, 6), (12, 34), (40, 38), (58, 38), (44, 18), (18, 16)]
    for gx, gy in groves:
        for _ in range(7):
            x, y = gx + g.rng.randrange(-4, 5), gy + g.rng.randrange(-3, 4)
            if g.is_free(x, y, 2, 2):
                g.block(
                    g.rng.choice(("tree", "pine", "autumn")),
                    x,
                    y,
                    2,
                    2,
                    solid_rows=1,
                    above_rows=1,
                )
    # the boss clearing is ringed by trees with an opening to the south
    for x in range(48, 66, 2):
        for y in (5, 18):
            if y == 18 and 54 <= x <= 58:
                continue
            if g.is_free(x, y, 2, 2):
                g.block("pine", x, y, 2, 2, solid_rows=1, above_rows=1)
    for y in range(7, 18, 2):
        for x in (47, 65):
            if g.is_free(x, y, 2, 2):
                g.block("pine", x, y, 2, 2, solid_rows=1, above_rows=1)
    for x, y in ((20, 28), (34, 14), (48, 26), (60, 24), (8, 40), (30, 42)):
        if g.is_free(x, y, 2, 2):
            g.block("boulder", x, y, 2, 2)
    _scatter(g, ["rock", "rock2", "stump"], 30, (3, 3, w - 3, h - 3), solid=True)
    _scatter(
        g, ["flower_y", "flower_s", "flower_r", "bush", "bush2", "fern"], 160, (2, 2, w - 2, h - 2)
    )
    tile = lambda x, y: ((x + 0.5) * s, (y + 0.5) * s)  # noqa: E731
    return {
        "grid": g,
        "size": s,
        "from_town": tile(3, 23.5),
        "to_town": tile(0, 23.5),
        "from_dungeon": tile(w - 7, 31.5),
        "to_dungeon": tile(w - 4.5, 31.5),
        "boss": tile(56.5, 11.5),
        "slimes": [
            tile(x, y)
            for x, y in (
                (14, 20),
                (17, 27),
                (24, 18),
                (33, 27),
                (38, 30),
                (22, 38),
                (26, 41),
                (44, 30),
                (52, 34),
                (58, 30),
            )
        ],
        "eyes": [tile(x, y) for x, y in ((30, 12), (40, 22), (50, 22), (36, 40), (62, 34))],
        "elite": tile(46, 40),
        "skulls": [tile(x, y) for x, y in ((42, 40), (49, 41), (45, 36))],
    }


def dungeon(atlas):
    """A side-view cave: rolling ground, wooden platforms, one-way ledges, a ladder up to a high
    walkway, and the boss hall at the far end."""
    w, h, s = 96, 20, 18
    g = Grid(atlas, w, h, "dungeon")
    heights = []
    level = 15
    for x in range(w):
        if x in (14, 30, 46, 60) and x < 78:
            level = max(12, min(16, level + g.rng.choice((-2, -1, 1, 2))))
        if x >= 78:
            level = 16
        heights.append(level)

    def column(x, top):
        for y in range(top, h):
            if y == top:
                left = x > 0 and heights[x - 1] > top
                right = x < w - 1 and heights[x + 1] > top
                name = "top_l" if left else "top_r" if right else "top"
            else:
                name = g.rng.choice(("dirt", "dirt2", "dirt3", "dirt4"))
            g.put("objects", x, y, name)
            g.solid(x, y)

    for x, top in enumerate(heights):
        column(x, top)
    # cave walls: the first and last columns go to the ceiling
    for y in range(h):
        for x in (0, w - 1):
            g.put("objects", x, y, "dirt")
            g.solid(x, y)
    platforms, ladders = [], []

    def platform(x0, x1, y):  # a one-way ledge: art here, a one-way collider in the content
        for x in range(x0, x1):
            g.put("objects", x, y, "slab")
        platforms.append(((x0 + x1) / 2 * s, y * s + 2, (x1 - x0) * s, 4))

    def wood(x0, x1, y):  # a solid wooden bridge
        for x in range(x0, x1):
            name = "plank_l" if x == x0 else "plank_r" if x == x1 - 1 else "plank"
            g.put("objects", x, y, name)
            g.solid(x, y)

    platform(8, 12, heights[10] - 3)
    platform(20, 25, heights[22] - 4)
    wood(33, 40, heights[36] - 4)
    platform(50, 54, heights[52] - 3)
    platform(56, 60, heights[58] - 6)
    # a ladder up to the high walkway
    top = heights[66] - 8
    for y in range(top, heights[66]):
        g.put("decor", 66, y, "ladder_top" if y == top else "ladder")
    ladders.append((66.5 * s, (top + heights[66]) / 2 * s, 10, (heights[66] - top) * s))
    wood(67, 76, top)
    for x, name in (
        (5, "sign"),
        (12, "plant"),
        (26, "mushroom"),
        (41, "sprout"),
        (55, "plant"),
        (70, "crate"),
        (73, "crate2"),
        (84, "mushroom"),
    ):
        g.put("decor", x, heights[x] - 1, name)
    g.put("decor", 2, heights[2] - 2, "door_top")
    g.put("decor", 2, heights[2] - 1, "door")
    on = lambda x, half=8: ((x + 0.5) * s, heights[int(x)] * s - half)  # noqa: E731
    return {
        "grid": g,
        "size": s,
        "from_field": on(4),
        "to_field": on(2),
        "platforms": platforms,
        "ladders": ladders,
        "walkers": [on(x) for x in (18, 27, 38, 49, 62)],
        "bats": [((x + 0.5) * s, (heights[x] - 5) * s) for x in (24, 44, 58)],
        "drills": [on(x) for x in (35, 72)],
        "drill_high": ((71.5) * s, top * s - 12),
        "boss": on(88, 24),
    }


__all__ = ["dungeon", "field", "town"]
