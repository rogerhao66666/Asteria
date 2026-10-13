"""Native kernel set (D23): the numpy set with the hot loops replaced by C++.

Imports like any kernel set; raises ``ImportError`` (so ``available()`` skips it) when numpy or
the compiled library is missing - build it with ``python -m asteria.kernels.build_native``. Names
not yet ported are the numpy implementations, so the interface is always complete.
"""

from __future__ import annotations

import ctypes

import numpy as np

from . import _numpy
from .build_native import library_name

NAME = "native"
ABI_VERSION = 1

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

_D = ctypes.POINTER(ctypes.c_double)
_I64 = ctypes.POINTER(ctypes.c_int64)
_lib.ak_aabb_cross_pairs.restype = ctypes.c_int64
_lib.ak_aabb_cross_pairs.argtypes = (
    [_D] * 4
    + [ctypes.c_int64]
    + [_D] * 4
    + [ctypes.c_int64]
    + [
        ctypes.c_double,
        ctypes.c_int32,
        _I64,
        ctypes.c_int64,
    ]
)


def _columns(values):
    """Four contiguous float64 columns (no copy when they already are)."""
    return [np.ascontiguousarray(v, dtype=np.float64) for v in values]


def _ptr(array):
    return array.ctypes.data_as(_D)


def aabb_cross_pairs(a, b, cell_size=64.0, touching=False):
    """Same pairs as the reference kernel, found by a sorted cell grid in C++."""
    if cell_size <= 0:
        raise ValueError("cell_size must be positive")
    ca, cb = _columns(a), _columns(b)
    na, nb = len(ca[0]), len(cb[0])
    if not na or not nb:
        return []
    cap = max(64, 4 * na)
    while True:
        out = np.empty(cap, dtype=np.int64)
        count = _lib.ak_aabb_cross_pairs(
            *[_ptr(c) for c in ca],
            na,
            *[_ptr(c) for c in cb],
            nb,
            float(cell_size),
            1 if touching else 0,
            out.ctypes.data_as(_I64),
            cap,
        )
        if count <= cap:
            break
        cap = int(count)
    code = out[:count]
    return list(zip((code // nb).tolist(), (code % nb).tolist(), strict=True))
