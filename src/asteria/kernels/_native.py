"""Native kernel set (D23): the engine's hot loops in C++, loaded with ctypes.

Imports like any kernel set; raises ``ImportError`` (so ``available()`` skips it) when the compiled
library is missing - build it with ``python -m asteria.kernels.build_native``. numpy is optional:
the C++ reads and writes ``array.array`` buffers, so a game exported to a plain Python (no numpy)
still runs it. Anything not ported is the numpy kernel when numpy is installed and the python
reference otherwise, so the interface is always complete. Results are bit-identical to the python
reference set (the C++ does the same arithmetic in the same order).

Slot-indexed columns are ``array.array`` buffers read and written in place; each function checks
the buffer types it expects and falls back for anything else. The stores keep numpy arrays when
numpy is installed (its drawing and views are vectorised) and one flat ``array("d")`` otherwise.
"""

from __future__ import annotations

import ctypes
from array import array
from itertools import chain, compress, repeat

from . import _python
from ._python import FIELDS, PROJECTILE_FIELDS, WEATHER_FIELDS, _turn_cosines
from .build_native import ABI_VERSION, library_name

NAME = "native"

_path = library_name()
if not _path.is_file():
    raise ImportError(
        f"native kernels not built: {_path.name} (python -m asteria.kernels.build_native)"
    )
try:
    _lib = ctypes.CDLL(str(_path))
except OSError as exc:  # a library built for another platform or Python
    raise ImportError(f"native kernels cannot be loaded: {exc}") from exc
_lib.ak_abi_version.restype = ctypes.c_int32
if _lib.ak_abi_version() != ABI_VERSION:
    raise ImportError("native kernels are out of date: rebuild with build_native")

try:
    import numpy as np
except ImportError:  # a plain Python: the python reference fills in, the stores are flat
    np = None

if np is not None:
    from . import _numpy as _fallback
else:
    _fallback = _python

# everything not ported below is the fallback kernel (same names, same behaviour)
globals().update({k: v for k, v in vars(_fallback).items() if not k.startswith("__")})
NAME = "native"

_V = ctypes.c_void_p
_F, _I, _L = ctypes.c_double, ctypes.c_int32, ctypes.c_int64


def _sig(name, restype, *argtypes):
    function = getattr(_lib, name)
    function.restype = restype
    function.argtypes = argtypes
    return function


_aabb_pairs = _sig("ak_aabb_pairs", _L, _V, _V, _V, _V, _L, _F, _V, _L)
_cross_pairs = _sig("ak_aabb_cross_pairs", _L, *([_V] * 4), _L, *([_V] * 4), _L, _F, _I, _V, _L)
_particle_step = _sig("ak_particle_step", None, _V, _L, _F, _F, _F, _F, _V)
_weather_step = _sig("ak_weather_step", _L, _V, _L, _F, _F, _F, _I, _F, _F, _F, _F, _V, _V)
_projectile_step = _sig("ak_projectile_step", None, _V, _L, _F, _V, _V, _V, _V)
_take_rows = _sig("ak_take_rows", _I, _V, _L, _L, _V, _L, _V)
_offset = _sig("ak_offset", None, _V, _L, _F)
_collider_columns = _sig("ak_collider_columns", None, *([_V] * 9), _L, *([_V] * 4))
_topdown_prepare = _sig("ak_topdown_prepare", None, *([_V] * 9), _L, _F, *([_V] * 5))
_moved_boxes = _sig("ak_moved_boxes", None, *([_V] * 5), _V, _V, _L, *([_V] * 4))
_add_to_column = _sig("ak_add_to_column", None, _V, _V, _V, _L)
_decay_push = _sig("ak_decay_push", None, _V, _V, _V, _V, _L, _F, _F)
_box_columns = _sig("ak_box_columns", None, *([_V] * 9), _L, *([_V] * 4))
_blocked_rows = _sig("ak_blocked_rows", None, *([_V] * 8), _L, *([_V] * 6))
_blocked_boxes = _sig("ak_blocked_boxes", None, *([_V] * 4), _L, *([_V] * 4), _L, _F, *([_V] * 9))
_facing_codes = _sig("ak_facing_codes", None, _V, _V, _V, _V, _L, _V)
_fieldai_step = _sig("ak_fieldai_step", None, *([_V] * 12), _L, *([_V] * 4), _F, _V)
_fieldai_free_step = _sig(
    "ak_fieldai_free_step", None, *([_V] * 10), _L, *([_V] * 7), _F, *([_V] * 3)
)
_points_blocked = _sig("ak_points_blocked", None, _V, _V, _L, *([_V] * 9), _L, _F, *([_V] * 4))


# -- buffers --------------------------------------------------------------------------------
# A buffer's address is only good while the buffer lives: every temporary passed to C++ is
# bound to a name until the call returns.
def _ptr(buffer):
    return buffer.buffer_info()[0]


_SIZES = {code: array(code).itemsize for code in "dqbB"}


def _zeros(typecode, n):
    return array(typecode, bytes(n * _SIZES[typecode]))


def _f(values):
    """float64 buffer of ``values`` (an ``array("d")`` is used as it is)."""
    if type(values) is array and values.typecode == "d":
        return values
    if not isinstance(values, (list, tuple)):
        try:
            view = memoryview(values)  # e.g. a numpy column: copied at memcpy speed
        except TypeError:
            pass
        else:
            if view.format == "d" and view.ndim == 1 and view.c_contiguous:
                out = array("d")
                out.frombytes(view.cast("B"))
                return out
    return array("d", values)


def _i(values):
    """int64 buffer of ``values``."""
    if type(values) is array and values.typecode == "q":
        return values
    if not hasattr(values, "__len__"):
        values = list(values)  # an iterator: read once, maybe twice below
    try:
        return array("q", values)
    except TypeError:  # floats: truncated, as an int64 cast does
        return array("q", map(int, values))


def _flags(values):
    """uint8 buffer of the truth of each value."""
    if not hasattr(values, "__len__"):
        values = list(values)
    try:
        return array("B", values)
    except (TypeError, OverflowError):
        return array("B", map(bool, values))


class _Mismatch(Exception):
    """A column does not have the buffer type the C++ kernel reads."""


def _col(column, typecode):
    """Address of an ``array.array`` column of the expected type (read and written in place)."""
    if not isinstance(column, array) or column.typecode != typecode:
        raise _Mismatch
    return _ptr(column)


def _columns(values):
    return [_f(v) for v in values]


def _rows(flags):
    """Indexes of the set flags, ascending."""
    return list(compress(range(len(flags)), flags))


def _pairs_result(code, n):
    return list(map(divmod, code, repeat(n)))


def _call_pairs(count_of, n):
    cap = max(64, 4 * n)
    while True:
        out = _zeros("q", cap)
        count = count_of(_ptr(out), cap)
        if count <= cap:
            del out[count:]
            return out
        cap = int(count)


# -- broad phase ----------------------------------------------------------------------------
def aabb_pairs(x0, y0, x1, y1, cell_size=64.0):
    if cell_size <= 0:
        raise ValueError("cell_size must be positive")
    cols = _columns((x0, y0, x1, y1))
    n = len(cols[0])
    if n < 2:
        return []
    ptrs = [_ptr(c) for c in cols]
    code = _call_pairs(lambda out, cap: _aabb_pairs(*ptrs, n, float(cell_size), out, cap), n)
    return _pairs_result(code, n)


def aabb_cross_pairs(a, b, cell_size=64.0, touching=False):
    if cell_size <= 0:
        raise ValueError("cell_size must be positive")
    ca, cb = _columns(a), _columns(b)
    na, nb = len(ca[0]), len(cb[0])
    if not na or not nb:
        return []
    pa, pb = [_ptr(c) for c in ca], [_ptr(c) for c in cb]
    code = _call_pairs(
        lambda out, cap: _cross_pairs(
            *pa, na, *pb, nb, float(cell_size), 1 if touching else 0, out, cap
        ),
        na,
    )
    return _pairs_result(code, nb)


def _targets(n, target_x, target_y):
    tx, ty = _f(target_x), _f(target_y)
    if len(tx) != n or len(ty) != n:
        raise ValueError("step needs one target (or nan) per projectile")
    return tx, ty


# -- stores ---------------------------------------------------------------------------------
if np is not None:

    def _contiguous(store):
        if not store._data.flags.c_contiguous:
            store._data = np.ascontiguousarray(store._data)
        return store._data

    class ParticleStore(_fallback.ParticleStore):
        def step(self, dt, gx, gy, keep):
            data = _contiguous(self)
            n = data.shape[1]
            if not n:
                return
            alive = np.empty(n, dtype=np.uint8)
            _particle_step(data.ctypes.data, n, dt, gx, gy, keep, alive.ctypes.data)
            if not alive.all():
                self._data = self._data[:, alive.astype(bool)]

    class WeatherStore(_fallback.WeatherStore):
        def step(self, dt, wind, time, sway, shift_x, shift_y, width, height):
            data = _contiguous(self)
            n = data.shape[1]
            if not n:
                return []
            rows = np.empty(n, dtype=np.int64)
            fell = np.empty(n, dtype=np.uint8)
            count = _weather_step(
                data.ctypes.data,
                n,
                dt,
                wind,
                time,
                1 if sway else 0,
                shift_x,
                shift_y,
                width,
                height,
                rows.ctypes.data,
                fell.ctypes.data,
            )
            fell = fell[:count].astype(bool).tolist()
            return list(zip(rows[:count].tolist(), fell, strict=True))

    class ProjectileStore(_fallback.ProjectileStore):
        def step(self, dt, target_x=None, target_y=None):
            data = _contiguous(self)
            n = data.shape[1]
            if not n:
                return
            if target_x is None:
                _projectile_step(data.ctypes.data, n, dt, None, None, None, None)
                return
            turn = data[9]
            rot = _turn_cosines(turn.tolist(), dt)
            c = np.ones(n)
            s = np.zeros(n)
            for t, (ct, st) in rot.items():
                where = turn == t
                c[where], s[where] = ct, st
            tx, ty = _targets(n, target_x, target_y)
            _projectile_step(
                data.ctypes.data, n, dt, _ptr(tx), _ptr(ty), c.ctypes.data, s.ctypes.data
            )

else:
    _NO_TURN = (1.0, 0.0)

    class _FlatStore:
        """Rows in one ``array("d")``: field ``k`` of row ``i`` at ``k * n + i`` (the layout the
        C++ steps read)."""

        _FIELDS = ()

        def __init__(self):
            self._data = array("d")
            self._n = 0

        def __len__(self):
            return self._n

        def _field(self, k):
            n = self._n
            return self._data[k * n : (k + 1) * n]

        def column(self, name):
            return self._field(self._FIELDS.index(name)).tolist()

        def add(self, rows):
            rows = [tuple(row) for row in rows]
            if not rows:
                return
            width = len(self._FIELDS)
            if any(len(row) != width for row in rows):
                raise ValueError(f"each row holds {width} values: {', '.join(self._FIELDS)}")
            grown = array("d")
            for k, values in enumerate(zip(*rows, strict=True)):
                grown.extend(self._field(k))
                grown.extend(values)
            self._data, self._n = grown, self._n + len(rows)

        def _take(self, rows):
            """Keep the rows ``rows`` (any order; negative = from the end)."""
            idx = _i(rows)
            m = len(idx)
            out = _zeros("d", len(self._FIELDS) * m)
            src, fields = self._data, len(self._FIELDS)
            if m and _take_rows(_ptr(src), fields, self._n, _ptr(idx), m, _ptr(out)):
                raise IndexError("row index out of range")
            self._data, self._n = out, m

        def _set(self, index, values):
            row = range(self._n)[index]  # IndexError like a list's, negative from the end
            for k, value in values:
                self._data[k * self._n + row] = value

    class ParticleStore(_FlatStore):
        _FIELDS = FIELDS

        def step(self, dt, gx, gy, keep):
            n = self._n
            if not n:
                return
            alive = _zeros("B", n)
            _particle_step(_ptr(self._data), n, dt, gx, gy, keep, _ptr(alive))
            if alive.count(0):
                self._take(_rows(alive))

        def shift(self, dx, dy):
            n, start = self._n, _ptr(self._data)
            if n:
                _offset(start, n, dx)
                _offset(start + 8 * n, n, dy)

        def views(self, size_from, size_to, color_from, color_to, scale):
            s0, s1, c0, c1 = size_from, size_to, color_from, color_to
            px, py, _vx, _vy, life, max_life, size_k, angle, _spin = (
                self._field(k).tolist() for k in range(len(FIELDS))
            )
            out = []
            for x, y, lived, span, k, a in zip(px, py, life, max_life, size_k, angle, strict=True):
                t = lived / span
                size = (s0 + (s1 - s0) * t) * k * scale
                color = tuple(int(c0[c] + (c1[c] - c0[c]) * t) for c in range(4))
                out.append((x, y, max(0.0, size), color, a))
            return out

    class WeatherStore(_FlatStore):
        _FIELDS = WEATHER_FIELDS
        # the reference drawing reads these columns once per call
        x = property(lambda self: self._field(0).tolist())
        y = property(lambda self: self._field(1).tolist())
        vy = property(lambda self: self._field(2).tolist())
        size = property(lambda self: self._field(3).tolist())
        phase = property(lambda self: self._field(4).tolist())
        draw = _python.WeatherStore.draw

        def set_row(self, index, row):
            values = tuple(row)
            if len(values) != len(WEATHER_FIELDS):
                raise ValueError(f"a row holds {len(WEATHER_FIELDS)} values")
            self._set(index, enumerate(values))

        def truncate(self, count):
            self._take(range(self._n)[:count])

        def step(self, dt, wind, time, sway, shift_x, shift_y, width, height):
            n = self._n
            if not n:
                return []
            rows, fell = _zeros("q", n), _zeros("B", n)
            count = _weather_step(
                _ptr(self._data),
                n,
                dt,
                wind,
                time,
                1 if sway else 0,
                shift_x,
                shift_y,
                width,
                height,
                _ptr(rows),
                _ptr(fell),
            )
            return list(zip(rows[:count].tolist(), map(bool, fell[:count]), strict=True))

    class ProjectileStore(_FlatStore):
        _FIELDS = PROJECTILE_FIELDS
        _INDEX = {name: k for k, name in enumerate(PROJECTILE_FIELDS)}

        def column(self, name):
            return self._field(self._INDEX[name]).tolist()

        def add(self, rows):
            super().add([tuple(map(float, row)) for row in rows])

        def set_velocity(self, index, vx, vy):
            self._set(index, ((2, float(vx)), (3, float(vy))))

        def set_values(self, index, **values):
            self._set(index, [(self._INDEX[k], float(v)) for k, v in values.items()])

        def keep(self, indices):
            self._take(indices)

        def step(self, dt, target_x=None, target_y=None):
            n = self._n
            if not n:
                return
            if target_x is None:
                _projectile_step(_ptr(self._data), n, dt, None, None, None, None)
                return
            turn = self._field(9).tolist()
            rot = _turn_cosines(turn, dt)
            cos_sin = [rot.get(t, _NO_TURN) for t in turn]
            c = array("d", [v[0] for v in cos_sin])
            s = array("d", [v[1] for v in cos_sin])
            tx, ty = _targets(n, target_x, target_y)
            _projectile_step(_ptr(self._data), n, dt, _ptr(tx), _ptr(ty), _ptr(c), _ptr(s))

        def boxes(self):
            x, y, hw, hh = (self._field(k).tolist() for k in (0, 1, 7, 8))
            return (
                [a - w for a, w in zip(x, hw, strict=True)],
                [a - h for a, h in zip(y, hh, strict=True)],
                [a + w for a, w in zip(x, hw, strict=True)],
                [a + h for a, h in zip(y, hh, strict=True)],
            )

        def expired(self):
            age, life = self._field(5), self._field(6)
            return [i for i, (a, end) in enumerate(zip(age, life, strict=True)) if a >= end]


# -- columns by slot ------------------------------------------------------------------------
def collider_columns(transform, collider, slots, circle):
    n = len(slots)
    if not n:
        return [], [], [], []
    try:
        cols = [
            _col(transform["x"], "d"),
            _col(transform["y"], "d"),
            _col(collider["offset_x"], "d"),
            _col(collider["offset_y"], "d"),
            _col(collider["width"], "d"),
            _col(collider["height"], "d"),
            _col(collider["radius"], "d"),
        ]
    except _Mismatch:
        return _fallback.collider_columns(transform, collider, slots, circle)
    idx, flag = _i(slots), _flags(circle)
    out = [_zeros("d", n) for _ in range(4)]
    _collider_columns(*cols, _ptr(idx), _ptr(flag), n, *[_ptr(o) for o in out])
    return tuple(o.tolist() for o in out)


def topdown_prepare(c, slots, dt):
    n = len(slots)
    if not n:
        return [], [], [], [], []
    try:
        cols = [
            _col(c["intent_x"], "d"),
            _col(c["intent_y"], "d"),
            _col(c["control_lock"], "d"),
            _col(c["jump"], "b"),
            _col(c["speed"], "d"),
            _col(c["speed_override"], "d"),
            _col(c["push_x"], "d"),
            _col(c["push_y"], "d"),
        ]
    except _Mismatch:
        return _fallback.topdown_prepare(c, slots, dt)
    idx = _i(slots)
    out = [_zeros("d", n) for _ in range(4)]
    locked = _zeros("B", n)
    _topdown_prepare(*cols, _ptr(idx), n, dt, *[_ptr(o) for o in out], _ptr(locked))
    return (*[o.tolist() for o in out], list(map(bool, locked)))


def moved_boxes(c, t, slots, move_x, move_y):
    """The four box columns as ``array("d")`` buffers (passed on to the next kernel as they
    are)."""
    n = len(slots)
    try:
        cols = [
            _col(t["x"], "d"),
            _col(t["y"], "d"),
            _col(c["half_width"], "d"),
            _col(c["half_height"], "d"),
        ]
    except _Mismatch:
        return _fallback.moved_boxes(c, t, slots, move_x, move_y)
    idx, mx, my = _i(slots), _f(move_x), _f(move_y)
    out = [_zeros("d", n) for _ in range(4)]
    if n:
        _moved_boxes(*cols, _ptr(idx), _ptr(mx), _ptr(my), n, *[_ptr(o) for o in out])
    return tuple(out)


def add_to_column(column, slots, values):
    n = len(slots)
    if not n:
        return
    try:
        target = _col(column, "d")
    except _Mismatch:
        return _fallback.add_to_column(column, slots, values)
    idx, vals = _i(slots), _f(values)
    _add_to_column(target, _ptr(idx), _ptr(vals), n)


def decay_push(c, slots, dt, epsilon):
    n = len(slots)
    if not n:
        return
    try:
        cols = [_col(c["push_x"], "d"), _col(c["push_y"], "d"), _col(c["knockback_decay"], "d")]
    except _Mismatch:
        return _fallback.decay_push(c, slots, dt, epsilon)
    idx = _i(slots)
    _decay_push(*cols, _ptr(idx), n, dt, epsilon)


def box_columns(t, b, slots, codes):
    n = len(slots)
    if not n:
        return [], [], [], []
    try:
        cols = [
            _col(t["x"], "d"),
            _col(t["y"], "d"),
            _col(b["offset_x"], "d"),
            _col(b["offset_y"], "d"),
            _col(b["width"], "d"),
            _col(b["height"], "d"),
            _col(b["follow_facing"], "b"),
        ]
    except _Mismatch:
        return _fallback.box_columns(t, b, slots, codes)
    idx, code = _i(slots), _i(codes)
    out = [_zeros("d", n) for _ in range(4)]
    _box_columns(*cols, _ptr(idx), _ptr(code), n, *[_ptr(o) for o in out])
    return tuple(o.tolist() for o in out)


def blocked_rows(boxes, walls, pairs, mover_mask, mover_row, wall_bit, wall_one_way, wall_circle):
    if not len(pairs):
        return []
    cols = _columns(boxes) + _columns(walls)
    pair_array = _i(chain.from_iterable(pairs))
    mask, row, bit = _i(mover_mask), _i(mover_row), _i(wall_bit)
    one_way, circle = _flags(wall_one_way), _flags(wall_circle)
    blocked = _zeros("B", len(cols[0]))
    _blocked_rows(
        *[_ptr(a) for a in cols],
        _ptr(pair_array),
        len(pair_array) // 2,
        *[_ptr(a) for a in (mask, row, bit, one_way, circle)],
        _ptr(blocked),
    )
    return _rows(blocked)


def blocked_boxes(
    boxes, solids, walls, cell_size, mover_mask, mover_row, wall_bit, wall_one_way, wall_circle
):
    if cell_size <= 0:
        raise ValueError("cell_size must be positive")
    a, b = _columns(boxes), _columns(solids)
    na, nb = len(a[0]), len(b[0])
    if not na or not nb:
        return []
    cx, cy, radius = _columns(walls)
    mask, row, bit = _i(mover_mask), _i(mover_row), _i(wall_bit)
    one_way, circle = _flags(wall_one_way), _flags(wall_circle)
    blocked = _zeros("B", na)
    _blocked_boxes(
        *[_ptr(c) for c in a],
        na,
        *[_ptr(c) for c in b],
        nb,
        float(cell_size),
        *[_ptr(c) for c in (cx, cy, radius, mask, row, bit, one_way, circle)],
        _ptr(blocked),
    )
    return _rows(blocked)


def facing_codes(dx, dy, current, locked):
    n = len(dx)
    if not n:
        return []
    ax, ay, cur, held = _f(dx), _f(dy), _i(current), _flags(locked)
    out = _zeros("q", n)
    _facing_codes(_ptr(ax), _ptr(ay), _ptr(cur), _ptr(held), n, _ptr(out))
    return out.tolist()


def fieldai_step(f, t, c, slots, behaviour, target_x, target_y, has_target, dt):
    n = len(slots)
    if not n:
        return []
    try:
        cols = [
            _col(f["mode_code"], "q"),
            _col(f["home_x"], "d"),
            _col(f["home_y"], "d"),
            _col(f["detect_radius"], "d"),
            _col(f["lose_radius"], "d"),
            _col(f["arrive_distance"], "d"),
            _col(t["x"], "d"),
            _col(t["y"], "d"),
            _col(c["intent_x"], "d"),
            _col(c["intent_y"], "d"),
            _col(c["speed"], "d"),
        ]
    except _Mismatch:
        return _fallback.fieldai_step(
            f, t, c, slots, behaviour, target_x, target_y, has_target, dt
        )
    idx, b = _i(slots), _i(behaviour)
    tx, ty, has = _f(target_x), _f(target_y), _flags(has_target)
    rest = _zeros("B", n)
    _fieldai_step(*cols, _ptr(idx), n, _ptr(b), _ptr(tx), _ptr(ty), _ptr(has), dt, _ptr(rest))
    return _rows(rest)


def fieldai_free_step(
    f, t, slots, behaviour, target_x, target_y, has_target, goal_x, goal_y, has_goal, dt
):
    n = len(slots)
    if not n:
        return [], [], []
    args = (f, t, slots, behaviour, target_x, target_y, has_target, goal_x, goal_y, has_goal, dt)
    try:
        cols = [
            _col(f["mode_code"], "q"),
            *[
                _col(f[name], "d")
                for name in (
                    "home_x",
                    "home_y",
                    "detect_radius",
                    "lose_radius",
                    "arrive_distance",
                    "speed",
                )
            ],
            _col(t["x"], "d"),
            _col(t["y"], "d"),
        ]
    except _Mismatch:
        return _fallback.fieldai_free_step(*args)
    idx, b = _i(slots), _i(behaviour)
    tx, ty, has = _f(target_x), _f(target_y), _flags(has_target)
    gx, gy, goal = _f(goal_x), _f(goal_y), _flags(has_goal)
    status, mx, my = _zeros("b", n), _zeros("d", n), _zeros("d", n)
    _fieldai_free_step(
        *cols,
        _ptr(idx),
        n,
        *[_ptr(a) for a in (b, tx, ty, has, gx, gy, goal)],
        dt,
        *[_ptr(a) for a in (status, mx, my)],
    )
    return status.tolist(), mx.tolist(), my.tolist()


def points_blocked(px, py, solids, walls, shapes, wall_bit, cell_size, mask, skip_start, skip):
    if cell_size <= 0:
        raise ValueError("cell_size must be positive")
    n, nw = len(px), len(solids[0])
    if not n or not nw:
        return []
    x, y = _f(px), _f(py)
    cols = _columns(solids) + _columns(walls)
    kind, bit, masks = _i(shapes), _i(wall_bit), _i(mask)
    starts, skipped = _i(skip_start), _i(skip)
    if not len(skipped):
        skipped = _zeros("q", 1)  # a valid address; nothing is read from it
    blocked = _zeros("B", n)
    _points_blocked(
        _ptr(x),
        _ptr(y),
        n,
        *[_ptr(c) for c in cols],
        _ptr(kind),
        _ptr(bit),
        nw,
        float(cell_size),
        *[_ptr(a) for a in (masks, starts, skipped, blocked)],
    )
    return _rows(blocked)
