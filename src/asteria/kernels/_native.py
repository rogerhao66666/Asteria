"""Native kernel set (D23): the numpy set with every hot loop replaced by C++.

Imports like any kernel set; raises ``ImportError`` (so ``available()`` skips it) when numpy or the
compiled library is missing - build it with ``python -m asteria.kernels.build_native``.
Anything not ported is the numpy implementation, so the interface is always complete.
Results are bit-identical to the python reference set (the C++ does the same arithmetic in the
same order).

Columns are ``array.array`` buffers read and written in place; each function checks the buffer
types it expects and falls back to the numpy kernel for anything else.
"""

from __future__ import annotations

import ctypes

import numpy as np

from . import _numpy
from ._python import _turn_cosines
from .build_native import library_name

NAME = "native"
ABI_VERSION = 3

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

# everything not ported below is the numpy kernel (same names, same behaviour)
globals().update({k: v for k, v in vars(_numpy).items() if not k.startswith("__")})
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

_TYPES = {"d": np.float64, "q": np.int64, "b": np.int8}


def _ptr(array):
    return array.ctypes.data


def _f(values):
    return np.ascontiguousarray(values, dtype=np.float64)


def _i(values):
    return np.ascontiguousarray(values, dtype=np.int64)


def _flags(values):
    return np.ascontiguousarray(values, dtype=np.uint8)


class _Mismatch(Exception):
    """A column does not have the buffer type the C++ kernel reads."""


def _col(column, typecode):
    """Writable zero-copy view of an ``array.array`` column of the expected type."""
    if getattr(column, "typecode", None) != typecode:
        raise _Mismatch
    return np.frombuffer(column, dtype=_TYPES[typecode])


def _columns(values):
    return [_f(v) for v in values]


def _pairs_result(code, n):
    return list(zip((code // n).tolist(), (code % n).tolist(), strict=True))


def _call_pairs(count_of, n):
    cap = max(64, 4 * n)
    while True:
        out = np.empty(cap, dtype=np.int64)
        count = count_of(_ptr(out), cap)
        if count <= cap:
            return out[:count]
        cap = int(count)


# -- broad phase ----------------------------------------------------------------------------
def aabb_pairs(x0, y0, x1, y1, cell_size=64.0):
    if cell_size <= 0:
        raise ValueError("cell_size must be positive")
    cols = _columns((x0, y0, x1, y1))
    n = len(cols[0])
    if n < 2:
        return []
    code = _call_pairs(
        lambda out, cap: _aabb_pairs(*[_ptr(c) for c in cols], n, float(cell_size), out, cap), n
    )
    return _pairs_result(code, n)


def aabb_cross_pairs(a, b, cell_size=64.0, touching=False):
    if cell_size <= 0:
        raise ValueError("cell_size must be positive")
    ca, cb = _columns(a), _columns(b)
    na, nb = len(ca[0]), len(cb[0])
    if not na or not nb:
        return []
    code = _call_pairs(
        lambda out, cap: _cross_pairs(
            *[_ptr(c) for c in ca],
            na,
            *[_ptr(c) for c in cb],
            nb,
            float(cell_size),
            1 if touching else 0,
            out,
            cap,
        ),
        na,
    )
    return _pairs_result(code, nb)


# -- stores ---------------------------------------------------------------------------------
def _contiguous(store):
    if not store._data.flags.c_contiguous:
        store._data = np.ascontiguousarray(store._data)
    return store._data


class ParticleStore(_numpy.ParticleStore):
    def step(self, dt, gx, gy, keep):
        data = _contiguous(self)
        n = data.shape[1]
        if not n:
            return
        alive = np.empty(n, dtype=np.uint8)
        _particle_step(_ptr(data), n, dt, gx, gy, keep, _ptr(alive))
        if not alive.all():
            self._data = self._data[:, alive.astype(bool)]


class WeatherStore(_numpy.WeatherStore):
    def step(self, dt, wind, time, sway, shift_x, shift_y, width, height):
        data = _contiguous(self)
        n = data.shape[1]
        if not n:
            return []
        rows = np.empty(n, dtype=np.int64)
        fell = np.empty(n, dtype=np.uint8)
        count = _weather_step(
            _ptr(data),
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
        return list(zip(rows[:count].tolist(), fell[:count].astype(bool).tolist(), strict=True))


class ProjectileStore(_numpy.ProjectileStore):
    def step(self, dt, target_x=None, target_y=None):
        data = _contiguous(self)
        n = data.shape[1]
        if not n:
            return
        if target_x is None:
            _projectile_step(_ptr(data), n, dt, None, None, None, None)
            return
        turn = data[9]
        rot = _turn_cosines(turn.tolist(), dt)
        c = np.ones(n)
        s = np.zeros(n)
        for t, (ct, st) in rot.items():
            where = turn == t
            c[where], s[where] = ct, st
        tx, ty = _f(target_x), _f(target_y)
        _projectile_step(_ptr(data), n, dt, _ptr(tx), _ptr(ty), _ptr(c), _ptr(s))


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
        return _numpy.collider_columns(transform, collider, slots, circle)
    idx, flag = _i(slots), _flags(circle)
    out = [np.empty(n) for _ in range(4)]
    _collider_columns(*[_ptr(c) for c in cols], _ptr(idx), _ptr(flag), n, *[_ptr(o) for o in out])
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
        return _numpy.topdown_prepare(c, slots, dt)
    idx = _i(slots)
    out = [np.empty(n) for _ in range(4)]
    locked = np.empty(n, dtype=np.uint8)
    _topdown_prepare(
        *[_ptr(x) for x in cols], _ptr(idx), n, dt, *[_ptr(o) for o in out], _ptr(locked)
    )
    return (*[o.tolist() for o in out], locked.astype(bool).tolist())


def moved_boxes(c, t, slots, move_x, move_y):
    n = len(slots)
    try:
        cols = [
            _col(t["x"], "d"),
            _col(t["y"], "d"),
            _col(c["half_width"], "d"),
            _col(c["half_height"], "d"),
        ]
    except _Mismatch:
        return _numpy.moved_boxes(c, t, slots, move_x, move_y)
    idx, mx, my = _i(slots), _f(move_x), _f(move_y)
    out = [np.empty(n) for _ in range(4)]
    if n:
        _moved_boxes(
            *[_ptr(x) for x in cols], _ptr(idx), _ptr(mx), _ptr(my), n, *[_ptr(o) for o in out]
        )
    return tuple(out)


def add_to_column(column, slots, values):
    n = len(slots)
    if not n:
        return
    try:
        view = _col(column, "d")
    except _Mismatch:
        return _numpy.add_to_column(column, slots, values)
    idx, vals = _i(slots), _f(values)
    _add_to_column(_ptr(view), _ptr(idx), _ptr(vals), n)


def decay_push(c, slots, dt, epsilon):
    n = len(slots)
    if not n:
        return
    try:
        px, py, decay = (
            _col(c["push_x"], "d"),
            _col(c["push_y"], "d"),
            _col(c["knockback_decay"], "d"),
        )
    except _Mismatch:
        return _numpy.decay_push(c, slots, dt, epsilon)
    idx = _i(slots)  # named: the temporary must outlive the call
    _decay_push(_ptr(px), _ptr(py), _ptr(decay), _ptr(idx), n, dt, epsilon)


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
        return _numpy.box_columns(t, b, slots, codes)
    idx, code = _i(slots), _i(codes)
    out = [np.empty(n) for _ in range(4)]
    _box_columns(*[_ptr(x) for x in cols], _ptr(idx), _ptr(code), n, *[_ptr(o) for o in out])
    return tuple(o.tolist() for o in out)


def blocked_rows(boxes, walls, pairs, mover_mask, mover_row, wall_bit, wall_one_way, wall_circle):
    if not len(pairs):
        return []
    x0, y0, x1, y1 = _columns(boxes)
    cx, cy, radius = _columns(walls)
    pair_array = np.ascontiguousarray(pairs, dtype=np.int64).reshape(-1, 2)
    mask, row, bit = _i(mover_mask), _i(mover_row), _i(wall_bit)
    one_way, circle = _flags(wall_one_way), _flags(wall_circle)
    blocked = np.zeros(len(x0), dtype=np.uint8)
    _blocked_rows(
        *[_ptr(a) for a in (x0, y0, x1, y1, cx, cy, radius)],
        _ptr(pair_array),
        len(pair_array),
        *[_ptr(a) for a in (mask, row, bit, one_way, circle)],
        _ptr(blocked),
    )
    return np.flatnonzero(blocked).tolist()


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
    blocked = np.zeros(na, dtype=np.uint8)
    _blocked_boxes(
        *[_ptr(c) for c in a],
        na,
        *[_ptr(c) for c in b],
        nb,
        float(cell_size),
        *[_ptr(c) for c in (cx, cy, radius, mask, row, bit, one_way, circle)],
        _ptr(blocked),
    )
    return np.flatnonzero(blocked).tolist()


def facing_codes(dx, dy, current, locked):
    n = len(dx)
    if not n:
        return []
    ax, ay, cur, held = _f(dx), _f(dy), _i(current), _flags(locked)  # keep them alive
    out = np.empty(n, dtype=np.int64)
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
        return _numpy.fieldai_step(f, t, c, slots, behaviour, target_x, target_y, has_target, dt)
    idx, b = _i(slots), _i(behaviour)
    tx, ty, has = _f(target_x), _f(target_y), _flags(has_target)
    rest = np.zeros(n, dtype=np.uint8)
    _fieldai_step(
        *[_ptr(x) for x in cols],
        _ptr(idx),
        n,
        _ptr(b),
        _ptr(tx),
        _ptr(ty),
        _ptr(has),
        dt,
        _ptr(rest),
    )
    return np.flatnonzero(rest).tolist()
