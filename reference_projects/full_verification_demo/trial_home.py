"""Aldric's house in Hearthfold: a house on the town map the player walks into, a room with a
bed, and sleeping in the bed rests the whole party (fade out, REST_PARTY, fade in).

The pictures are Ninja Adventure's (CC0, Pixel-boy): the house from TilesetHouse, the walls and
floor from TilesetInteriorFloor, the bed from tileset_bed.
"""

from __future__ import annotations

import trial_maps as maps
import trial_people as people

TILES = people.NINJA / "Backgrounds" / "Tilesets"
LOT = maps.HOME_LOT  # the house's tiles on the town map (no prop is scattered on it)
ROOM = (12, 9)  # the room's size in tiles
FLOOR = [(1, 13), (2, 13), (6, 13)]  # TilesetInteriorFloor: warm stone
WALL = [(12, 13), (13, 13), (16, 13)]  # TilesetInteriorFloor: dark brick
DOOR_X = 6  # the room's doorway column (bottom wall)


def front_door():
    """Where the game starts: on the path just below Aldric's front door."""
    x0, _y0, x1, y1 = LOT
    return ((x0 + x1) * 8.0, (y1 + 2) * 16.0 + 8.0)


def clear_lot(grid):
    """The house's walls block and a path leads to the road (the town keeps the lot free of
    trees and rocks when it scatters them, so nothing is cut in half here)."""
    x0, y0, x1, y1 = LOT
    grid.block(x0, y0, x1, y1 - 1)  # the roof and the upper wall
    grid.block(x0, y1 - 1, x0 + 1, y1)  # the lower wall left and right of the door
    grid.block(x1 - 1, y1 - 1, x1, y1)
    maps.paint_ground(grid, maps.EXTERIOR["path"], x0 + 1, y1, x0 + 3, 11)  # to the road


def tileset(assets):
    """The room's tiles: floor, wall, and the invisible blocking tile."""
    from PIL import Image

    sheet = Image.open(TILES / "Interior" / "TilesetInteriorFloor.png").convert("RGBA")
    cells = [*FLOOR, *WALL]
    image = Image.new("RGBA", (16 * (len(cells) + 1), 16), (0, 0, 0, 0))
    for index, (col, row) in enumerate(cells):
        tile = sheet.crop((col * 16, row * 16, col * 16 + 16, row * 16 + 16))
        image.alpha_composite(tile, (index * 16, 0))
    block = len(cells)
    walls = tuple(range(len(FLOOR), len(cells)))
    tileset_id, _ = assets.tileset("home", image, 16, "Aldric's House", solid=(*walls, block))
    floor = list(range(len(FLOOR)))
    return tileset_id, len(cells) + 1, floor, list(walls)


def room(grid, floor, walls):
    """Walls round a warm floor, a doorway in the bottom wall."""
    w, h = ROOM
    grid.fill("ground", 0, 0, w, h, walls)
    grid.block(0, 0, w, h)
    grid.fill("ground", 1, 2, w - 1, h - 1, floor)
    for y in range(2, h - 1):
        for x in range(1, w - 1):
            grid.layers["collision"].pop((x, y), None)
    for x in (DOOR_X - 1, DOOR_X):  # the doorway
        grid.put("ground", x, h - 1, floor[0])
        grid.layers["collision"].pop((x, h - 1), None)
    return {
        "inside": (DOOR_X * 16.0, (h - 2) * 16.0 + 8.0),
        "exit": (DOOR_X * 16.0, (h - 1) * 16.0 + 8.0),
    }


def picture(assets, key, file, box, name):
    """A still picture (the house, the bed) as an entity look: one frame, every facing."""
    from PIL import Image

    image = Image.open(TILES / file).convert("RGBA").crop(box)
    sheet = assets.sheet(key, image, [(0, 0, image.width, image.height)], name)
    clips = {
        f"{kind}_{facing}": ([0], 1.0, True)
        for kind in ("idle", "walk")
        for facing in people.DIRECTIONS
    }
    return sheet, assets.clips(key, clips, name)


def furnish(assets, town, home, home_places):
    """The house on the town map with its door, the room's way out, and the bed."""
    from asteria.runtime.collision import Collider2DComponent

    x0, y0, x1, y1 = LOT
    house = town.entity("Aldric's House", (x0 + x1) * 8.0, y1 * 16.0)  # stands on its lot
    town.look(house, *picture(assets, "home_outside", "TilesetHouse.png", (0, 0, 64, 48), "House"))
    door_x = (x0 + x1) * 8.0
    town.door(
        "House Door",
        (door_x, (y1 - 1) * 16.0 + 8.0),
        home.scene.id,
        home_places["inside"],
        "up",
    )
    home.door("Front Door", home_places["exit"], town.scene.id, (door_x, y1 * 16.0 + 10.0), "down")
    import trial_brave

    trial_brave.family_chest(assets, home, maps)  # the Demon Ring and the charms
    bed = home.entity("Bed", 3 * 16.0, 5 * 16.0)
    home.look(bed, *picture(assets, "home_bed", "tileset_bed.png", (0, 48, 32, 96), "Bed"))
    bed.add_component(maps._set(Collider2DComponent(), width=28, height=40, offset_y=-20))
    home.program(
        bed,
        "home.bed",
        maps.menu(
            "Bed",
            "A warm bed. Sleep until morning?",
            [
                (
                    "Sleep",
                    [
                        maps.world("SCREEN_FADE", to=1.0, duration=0.5, color=[0, 0, 0]),
                        maps.world("REST_PARTY"),  # everyone wakes up whole
                        maps.world("SCREEN_FADE", to=0.0, duration=0.5, color=[0, 0, 0]),
                        maps.world("SHOW_POPUP", text="You feel rested.", kind="item"),
                    ],
                ),
                ("Not now", []),
            ],
        ),
        radius=30.0,
    )
