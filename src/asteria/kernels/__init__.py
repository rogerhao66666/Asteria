"""Compute kernels: the engine's hot inner loops behind a small, array-shaped interface (D21).

A kernel set is a module with the same names in every implementation:

- ``ParticleStore`` - particle columns (position, velocity, life, size, angle, spin) with ``add``, ``step``,
  ``shift`` and ``views``.
- ``WeatherStore`` - screen-space weather particles with ``step`` (fall, wind, sway, camera shift) and ``draw``
  (pixels identical to the reference).
- ``aabb_pairs(x0, y0, x1, y1, cell_size)`` - every pair ``(i, j)``, ``i < j``, whose boxes overlap or touch,
  sorted.
- ``aabb_cross_pairs(a, b, cell_size)`` - every pair ``(i, j)`` where box ``a[i]`` overlaps box ``b[j]`` (strictly),
  sorted; ``a`` / ``b`` are ``(x0, y0, x1, y1)`` columns (hitboxes x hurtboxes, projectiles x targets).
- ``ProjectileStore`` - projectile columns (position, velocity, gravity, age, life, box, homing turn, uid) with
  ``add``, ``step`` (homing toward per-row targets, gravity, motion, ageing), ``boxes``, ``expired``, ``keep``.

``python`` is the reference and is always available. ``numpy`` runs the same arithmetic on arrays when numpy is
installed; a native module can be added the same way later. Implementations must give the same results as
``python`` (tests compare them). ``ASTERIA_KERNELS`` = ``auto`` (default: the fastest installed), ``python`` or
``numpy`` picks the set; ``use()`` switches it in code.
"""

from __future__ import annotations

import importlib
import os

_MODULES = {"python": "asteria.kernels._python", "numpy": "asteria.kernels._numpy"}
_PREFERENCE = ("numpy", "python")
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


def use(name="auto"):
    """Switch the active kernel set (``auto`` = the fastest available); returns the previous name."""
    global _active
    previous = None if _active is None else _active.NAME
    _active = _load(available()[0] if name == "auto" else name)
    return previous


def active():
    """The active kernel set (chosen from ``ASTERIA_KERNELS`` on first use)."""
    if _active is None:
        use(os.environ.get("ASTERIA_KERNELS", "auto").strip().lower() or "auto")
    return _active
