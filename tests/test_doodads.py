"""Doodads: definitions, placement as entities with undo, scattering and storage."""

import random

import pytest

from asteria.core import Scene, Transform
from asteria.editor.commands import CommandStack
from asteria.editor.doodads import build_place_doodads_command, doodad_of, make_doodad_entity
from asteria.rpg.actors import RpgDatabase
from asteria.rpg.doodads import DoodadDefinition, scatter_positions, snap_position
from asteria.runtime.collision import Collider2DComponent
from asteria.runtime.components2d import SpriteRenderer2D

SHEET = "11111111-1111-4111-8111-111111111111"
TREE = DoodadDefinition(
    "tree",
    SHEET,
    frame=3,
    solid_width=10,
    solid_height=6,
    solid_offset_y=-3,
    layer=2,
    depth=1.5,
    snap=8,
    tags=("nature", "tall"),
)
FLOWER = DoodadDefinition("flower", SHEET)


def test_an_entity_carries_the_sprite_and_a_foot_collider():
    entity = make_doodad_entity(TREE, 21, 13)
    transform, sprite = entity.get(Transform), entity.get(SpriteRenderer2D)
    assert (transform.x, transform.y) == (24.0, 16.0)  # snapped to the 8-grid
    assert (sprite.sprite_sheet_asset_id, sprite.frame_index, sprite.layer) == (SHEET, 3, 2)
    assert sprite.depth == 1.5
    collider = entity.get(Collider2DComponent)
    assert (collider.width, collider.height, collider.offset_y) == (10.0, 6.0, -3.0)
    assert doodad_of(entity) == "tree"


def test_a_decoration_without_a_footprint_has_no_collider_and_can_be_flipped():
    entity = make_doodad_entity(FLOWER, 5.5, 6.5, flip=True)
    assert not entity.has(Collider2DComponent)
    assert (entity.get(Transform).x, entity.get(Transform).y) == (5.5, 6.5)  # snap 0: free
    assert entity.get(Transform).scale_x == -1.0 and entity.get(SpriteRenderer2D).flip_x


def test_placing_several_is_one_undo_step():
    scene = Scene("map")
    stack = CommandStack()
    stack.execute(build_place_doodads_command(scene, TREE, [(0, 0), (40, 8), (80, 16)]))
    assert [doodad_of(e) for e in scene.entities()] == ["tree"] * 3
    assert len({e.id for e in scene.entities()}) == 3
    stack.undo()
    assert scene.entities() == ()
    stack.redo()
    assert len(scene.entities()) == 3
    with pytest.raises(ValueError):
        build_place_doodads_command(scene, TREE, [])


def test_snap_position():
    assert snap_position(13, 29, 16) == (16.0, 32.0)
    assert snap_position(13.4, 2.2, 0) == (13.4, 2.2)


def test_scatter_keeps_its_distance_stays_inside_and_is_deterministic():
    area = (0, 0, 200, 200)
    first = scatter_positions(area, 25, random.Random(1), min_distance=30)
    assert first == scatter_positions(area, 25, random.Random(1), min_distance=30)
    assert 5 < len(first) <= 25
    for i, (x, y) in enumerate(first):
        assert 0 <= x <= 200 and 0 <= y <= 200
        assert all((x - px) ** 2 + (y - py) ** 2 >= 900 for px, py in first[:i])
    avoided = scatter_positions(area, 40, random.Random(2), avoid=lambda x, y: x < 100)
    assert avoided and all(x >= 100 for x, _ in avoided)
    with pytest.raises(ValueError):
        scatter_positions((0, 0, 0, 5), 3, random.Random(0))


def test_definitions_round_trip_and_stay_in_the_database():
    assert DoodadDefinition.from_data(TREE.to_data()) == TREE
    assert FLOWER.to_data() == {"doodad_id": "flower", "sprite_sheet_asset_id": SHEET}
    database = RpgDatabase()
    database.add_doodad(TREE)
    restored = RpgDatabase.from_data(database.to_data())
    assert restored.doodads["tree"] == TREE
    with pytest.raises(ValueError):
        database.add_doodad(TREE)  # duplicate id


def test_validation():
    for args in (("", SHEET), ("x", "")):
        with pytest.raises(ValueError):
            DoodadDefinition(*args)
    with pytest.raises(ValueError):
        DoodadDefinition("x", SHEET, frame=-1)
    with pytest.raises(ValueError):
        DoodadDefinition("x", SHEET, snap=-2)
    with pytest.raises(TypeError):
        make_doodad_entity("tree", 0, 0)
