"""Tile art for the Astral Gate field, built on the editor's starter tileset."""
from __future__ import annotations

from asteria.editor.starter_project import (
    BUSH,
    CRATE,
    DEEP_WATER,
    FLOWERS,
    GRASS,
    LAMP,
    PATH,
    WATER,
    add_tilemap,
    build_layer,
    install_starter_tileset,
)

TILE_DIR = "field_tiles"
MAP_WIDTH = 24
MAP_HEIGHT = 14
# Centres the map on the Player (0, 0) and Astral Tyrant (48, 0).
ORIGIN = (-168.0, -112.0)
PATH_ROW = 7


def _ground_tile(x, y):
    if y == PATH_ROW:
        return PATH
    if x <= 4 and y >= 10:
        return DEEP_WATER if (x <= 2 and y >= 12) else WATER
    # Deterministic sprinkle of flowers so the field doesn't read as one flat fill.
    return FLOWERS if (x * 7 + y * 13) % 11 == 0 else GRASS


def _decor_tile(x, y):
    if y == 0 or y == MAP_HEIGHT - 1 or x == 0 or x == MAP_WIDTH - 1:
        # Bush border, left open where the path runs off the map.
        return -1 if y == PATH_ROW else BUSH
    if (x, y) in {(18, 4), (19, 4), (18, 10)}:
        return CRATE
    if (x, y) in {(9, 6), (17, 6)}:
        return LAMP
    return -1


def install_field_tilemap(project, scene, output_dir):
    tileset_id = install_starter_tileset(project, output_dir, asset_dir=TILE_DIR)
    return add_tilemap(
        project, scene, output_dir, tileset_id,
        [
            build_layer("Ground", 0, MAP_WIDTH, MAP_HEIGHT, _ground_tile),
            build_layer("Decor", 1, MAP_WIDTH, MAP_HEIGHT, _decor_tile, collision=True),
        ],
        "astral_gate.tilemap.json",
        entity_name="Field Map",
        origin=ORIGIN,
        asset_dir=TILE_DIR,
    )
