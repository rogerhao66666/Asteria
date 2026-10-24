"""Grid walking (field.movement: "grid"): whole cells, a tap turns, walls stop."""

from types import SimpleNamespace

from asteria.runtime.grid_walk import GridWalker


def _walk(walker, transform, facing, dx, dy, seconds, blocked=lambda x, y: False, dt=1 / 60):
    moving = False
    for _ in range(round(seconds / dt)):
        facing, moving = walker.step(transform, facing, dx, dy, dt, blocked)
    return facing, moving


def test_holding_a_direction_walks_whole_cells_and_stops_on_a_centre():
    walker = GridWalker({"grid_size": 16, "walk_speed": 60})
    at = SimpleNamespace(x=8.0, y=8.0)
    facing, _ = _walk(walker, at, "down", 0, 1, 0.5)  # 30 frames: a turn wait + 1.x cells
    facing, moving = _walk(walker, at, facing, 0, 0, 1.0)  # let go: the step finishes
    assert facing == "down" and not moving
    assert (at.y - 8) % 16 == 0 and at.y > 8 and at.x == 8


def test_a_tap_away_from_the_facing_only_turns():
    walker = GridWalker()
    at = SimpleNamespace(x=8.0, y=8.0)
    facing, moving = _walk(walker, at, "down", -1, 0, 0.05)
    facing, moving = _walk(walker, at, facing, 0, 0, 0.5)
    assert facing == "left" and (at.x, at.y) == (8.0, 8.0) and not moving


def test_a_press_toward_the_facing_walks_at_once_and_walls_stop_it():
    walker = GridWalker()
    at = SimpleNamespace(x=8.0, y=8.0)
    _walk(walker, at, "right", 1, 0, 0.05)
    assert at.x > 8.0  # already facing right: no turn wait
    _walk(walker, at, "right", 0, 0, 1.0)
    assert at.x == 24.0
    wall = lambda x, y: x > 30  # noqa: E731 - the next cell to the right is a wall
    facing, moving = _walk(walker, at, "right", 1, 0, 0.5, wall)
    assert at.x == 24.0 and facing == "right" and not moving


def test_running_takes_half_the_time():
    walk, run = GridWalker(), GridWalker()
    a, b = SimpleNamespace(x=8.0, y=8.0), SimpleNamespace(x=8.0, y=8.0)
    for _ in range(8):
        walk.step(a, "down", 0, 1, 1 / 60, lambda x, y: False)
        run.step(b, "down", 0, 1, 1 / 60, lambda x, y: False, running=True)
    assert b.y - 8 == 2 * (a.y - 8)


def _ledge_world():
    """Row 1 is a ledge that may be jumped going down; everything else is open."""

    def blocked(x, y):
        return int(y // 16) == 1

    def ledge(x, y, facing):
        return int(y // 16) == 1 and facing == "down"

    return blocked, ledge


def test_a_ledge_is_hopped_to_the_cell_beyond_with_the_player_raised():
    walker = GridWalker({"grid_size": 16, "jump_height": 12})
    t = SimpleNamespace(x=8.0, y=8.0)
    blocked, ledge = _ledge_world()
    facing, lifts = "down", []
    for _ in range(round(0.2 * 60)):  # a short hold starts the hop
        facing, _moving = walker.step(t, facing, 0, 1, 1 / 60, blocked, ledge=ledge)
        lifts.append(walker.lift)
    for _ in range(60):  # let go: the hop still ends on its cell
        facing, _moving = walker.step(t, facing, 0, 0, 1 / 60, blocked, ledge=ledge)
        lifts.append(walker.lift)
    assert (t.x, t.y) == (8.0, 40.0)  # two cells down, over the ledge row
    assert 11.0 < max(lifts) <= 12.0 and walker.lift == 0.0 and walker.jump is None


def test_a_ledge_only_lets_the_player_jump_its_own_way():
    walker = GridWalker({"grid_size": 16})
    t = SimpleNamespace(x=8.0, y=40.0)  # below the ledge, walking up into it
    blocked, ledge = _ledge_world()
    facing = "up"
    for _ in range(60):
        facing, moving = walker.step(t, facing, 0, -1, 1 / 60, blocked, ledge=ledge)
    assert (t.x, t.y) == (8.0, 40.0) and not moving and walker.lift == 0.0


def test_a_hop_needs_the_cell_beyond_free():
    walker = GridWalker({"grid_size": 16})
    t = SimpleNamespace(x=8.0, y=8.0)
    _blocked, ledge = _ledge_world()

    def blocked(x, y):  # the ledge row and the landing row are both closed
        return int(y // 16) in (1, 2)

    facing = "down"
    for _ in range(60):
        facing, _moving = walker.step(t, facing, 0, 1, 1 / 60, blocked, ledge=ledge)
    assert (t.x, t.y) == (8.0, 8.0)
