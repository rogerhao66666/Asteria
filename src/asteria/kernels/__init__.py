"""Compute kernels: the engine's hot inner loops behind a small, array-shaped interface (D21).

A kernel set is a module with the same names in every implementation:

- ``ParticleStore`` - particle columns (position, velocity, life, size, angle, spin) with ``add``,
  ``step``,
  ``shift`` and ``views``.
- ``WeatherStore`` - screen-space weather particles with ``step`` (fall, wind, sway, camera shift)
  and ``draw``
  (pixels identical to the reference).
- ``aabb_pairs(x0, y0, x1, y1, cell_size)`` - every pair ``(i, j)``, ``i < j``, whose boxes
  overlap or touch,
  sorted.
- ``aabb_cross_pairs(a, b, cell_size, touching=False)`` - every pair ``(i, j)`` where box ``a[i]``
  overlaps box
  ``b[j]`` (touching edges count only with ``touching``), sorted; ``a`` / ``b`` are ``(x0, y0, x1,
  y1)`` columns
  (hitboxes x hurtboxes, projectiles x targets, characters x walls).
- ``ProjectileStore`` - projectile columns (position, velocity, gravity, age, life, box, homing
  turn, uid) with
  ``add``, ``step`` (homing toward per-row targets, gravity, motion, ageing), ``boxes``,
  ``expired``, ``keep``.

``python`` is the reference and is always available. ``numpy`` runs the same arithmetic on arrays
when numpy is installed. ``native`` runs the hot loops in C++ (build it with
``python -m asteria.kernels.build_native``; it is skipped when not built) and needs no numpy: the
rest comes from numpy when installed, else from python. Implementations must
give the same results as
``python`` (tests compare them). ``ASTERIA_KERNELS`` = ``auto`` (default: the fastest installed),
``python``,
``numpy`` or ``native`` picks the set; ``use()`` switches it in code.
"""

from __future__ import annotations

import importlib
import os

_MODULES = {
    "python": "asteria.kernels._python",
    "numpy": "asteria.kernels._numpy",
    "native": "asteria.kernels._native",
}
_PREFERENCE = ("native", "numpy", "python")
_active = None


def _load(name):
    if name not in _MODULES:
        raise ValueError(f"unknown kernel set {name!r}; choose from {', '.join(_MODULES)} or auto")
    return importlib.import_module(_MODULES[name])


def available():
    """Names of the kernel sets that can be loaded here, fastest first."""
    names = []
    for name in _PREFERENCE:
        try:
            _load(name)
        except ImportError:
            continue
        names.append(name)
    return tuple(names)


def _resolve(name):
    name = (name or "auto").strip().lower() or "auto"
    return available()[0] if name == "auto" else name


def use(name="auto"):
    """Switch the active kernel set (``auto`` = the fastest available); returns the previous name
    (the set that
    ``ASTERIA_KERNELS`` would have chosen when none was chosen yet)."""
    global _active
    previous = (
        _active.NAME
        if _active is not None
        else _resolve(os.environ.get("ASTERIA_KERNELS", "auto"))
    )
    _active = _load(_resolve(name))
    return previous


def active():
    """The active kernel set (chosen from ``ASTERIA_KERNELS`` on first use)."""
    global _active
    if _active is None:
        _active = _load(_resolve(os.environ.get("ASTERIA_KERNELS", "auto")))
    return _active
