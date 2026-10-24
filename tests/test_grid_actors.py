"""Grid movers (GridMover2D): townspeople who stand, look around or wander a cell at a time."""

import random

from asteria.core import Entity, Scene, Transform, deserialize_scene, serialize_scene
from asteria.runtime.component_registry import default_component_registry
from asteria.runtime.grid_actors import GridMover2DComponent, GridMoverSystem, parse_pauses


def _scene(behaviour, *, cell=(5, 5), **fields):
    scene = Scene("Town")
    person = Entity("Person")
    person.add_component(Transform(cell[0] * 16 + 8, cell[1] * 16 + 8))
    mover = person.add_component(GridMover2DComponent())
    mover.behaviour = behaviour
    mover.pauses = "0.1"
    for key, value in fields.items():
        setattr(mover, key, value)
    scene.add_entity(person)
    return scene, person


def _run(system, scene, seconds, walls=None, reserved=(), watch=None):
    for _ in range(round(seconds * 60)):
        system.update(scene, 1 / 60, walls, reserved)
        if watch is not None:
            watch()


def test_a_wanderer_stays_inside_its_range_and_rests_on_cell_centres():
    scene, person = _scene("wander", range_x=1, range_y=2)
    system = GridMoverSystem(random.Random(3))
    seen = set()

    def watch():
        t = person.get(Transform)
        if system.state[person.id].target is None:
            assert (t.x - 8) % 16 == 0 and (t.y - 8) % 16 == 0
            seen.add((int(t.x // 16), int(t.y // 16)))

    _run(system, scene, 30, watch=watch)
    assert len(seen) > 3  # it walked about
    assert all(abs(x - 5) <= 1 and abs(y - 5) <= 2 for x, y in seen)


def test_walls_and_reserved_cells_are_never_entered():
    scene, person = _scene("wander", range_x=0, range_y=0)  # no range limit
    system = GridMoverSystem(random.Random(1))

    def walls(x, y):  # a box: only the start cell and the one to its right are open
        return (int(x // 16), int(y // 16)) not in {(5, 5), (6, 5)}

    seen = set()
    _run(system, scene, 20, walls, watch=lambda: seen.add(system.state[person.id].cell))
    assert seen <= {(5, 5), (6, 5)} and (6, 5) in seen
    scene, person = _scene("wander", range_x=0, range_y=0)
    system = GridMoverSystem(random.Random(1))
    reserved = {(6, 5)}  # e.g. the player stands there
    _run(system, scene, 20, walls, reserved, watch=lambda: seen.add(system.state[person.id].cell))
    assert system.state[person.id].cell == (5, 5)


def test_one_axis_wanderers_and_lookers():
    scene, person = _scene("wander_horizontal", range_x=2, range_y=2)
    system = GridMoverSystem(random.Random(5))
    rows = set()
    _run(system, scene, 20, watch=lambda: rows.add(system.state[person.id].cell[1]))
    assert rows == {5}
    scene, person = _scene("look_around")
    system = GridMoverSystem(random.Random(2))
    facings = set()
    _run(system, scene, 10, watch=lambda: facings.add(person.get(GridMover2DComponent).facing))
    assert len(facings) > 1 and system.state[person.id].cell == (5, 5)


def test_still_people_never_move_and_turn_to_the_player_who_talks():
    scene, person = _scene("still", facing="left")
    system = GridMoverSystem(random.Random(0))
    _run(system, scene, 5)
    assert system.state[person.id].cell == (5, 5)
    system.face_toward(person, 5 * 16 + 8, 7 * 16 + 8)  # the player below
    assert person.get(GridMover2DComponent).facing == "down"
    person.get(GridMover2DComponent).face_player = False
    system.face_toward(person, 9 * 16, 5 * 16 + 8)
    assert person.get(GridMover2DComponent).facing == "down"


def test_two_movers_never_share_a_cell_and_held_cells_cover_both_ends_of_a_step():
    scene, first = _scene("wander", range_x=0, range_y=0)
    second = Entity("Other")
    second.add_component(Transform(6 * 16 + 8, 5 * 16 + 8))
    other = second.add_component(GridMover2DComponent())
    other.behaviour, other.pauses = "wander", "0.1"
    scene.add_entity(second)
    system = GridMoverSystem(random.Random(9))

    def walls(x, y):  # a corridor of three cells
        return (int(x // 16), int(y // 16)) not in {(5, 5), (6, 5), (7, 5)}

    def watch():
        a, b = system.state[first.id], system.state[second.id]
        cells_a = {a.cell, a.target} - {None}
        cells_b = {b.cell, b.target} - {None}
        assert not cells_a & cells_b

    _run(system, scene, 20, walls, watch=watch)


def test_the_component_round_trips_and_pauses_parse():
    scene, person = _scene("wander_vertical", range_y=3, pauses="0.5, 1.5")
    registry = default_component_registry()
    copy = deserialize_scene(serialize_scene(scene), registry)
    mover = next(iter(copy.entities())).get(GridMover2DComponent)
    assert (mover.behaviour, mover.range_y, mover.pauses) == ("wander_vertical", 3, "0.5, 1.5")
    assert parse_pauses("0.5; 1, x, -2") == (0.5, 1.0) and parse_pauses("") == (1.0,)
