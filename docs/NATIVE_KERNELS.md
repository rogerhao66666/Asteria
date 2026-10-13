# Native (C++) kernels

The engine's hot loops (broad-phase collision, projectiles, particles, weather, character
movement, field AI steps) run as **kernels**: small functions over column buffers, in three
interchangeable sets:

| Set | What it is | When |
| --- | --- | --- |
| `python` | the reference; always available | the rule every other set must match, bit for bit |
| `numpy` | the same arithmetic on whole arrays | when numpy is installed |
| `native` | the same arithmetic in C++ | when the library is built |

`ASTERIA_KERNELS=native|numpy|python` picks one; the default (`auto`) takes the fastest
available. Everything else - events, RPG data, the editor, your own game code - stays Python.

## Build

```bash
python -m asteria.kernels.build_native
```

It needs only a C++17 compiler (`clang++`, `g++` or `c++`); no cmake, no pybind11. The library is
written next to the source (`src/asteria/kernels/native/libasteria_kernels.{dylib,so,dll}`) and is
**not** committed. Floating point is built strictly (`-ffp-contract=off -fno-fast-math`) so the
results are identical to the python set.

Without the library nothing breaks: `auto` falls back to numpy (or python). Each native function
also checks the buffer types it reads and falls back to the numpy version for anything else.

## Checking it

```bash
python -m pytest tests/test_native_kernels.py     # every function against the reference
ASTERIA_KERNELS=native python -m pytest           # the whole suite on the native set
python scripts/arpg_stress.py out.json --kernels python numpy native
```

## Adding a kernel

1. Write the python reference in `kernels/_python.py` and the numpy version in `_numpy.py`.
2. Add a C function to `native/asteria_kernels.cpp` (a plain `extern "C"` function over raw
   buffers; variable-size results use a caller-owned buffer and return the count needed).
3. Declare it and wrap it in `kernels/_native.py` (hold references to temporary arrays until the
   call returns).
4. Add a comparison to `tests/test_native_kernels.py`, including the columns it writes in place.

## What it buys

On the ARPG stress scene (300 enemies, 500 projectiles) native is about 20% faster than numpy
and more than twice as fast as python. The rest of the frame is Python object loops (the collision
world is rebuilt from the scene every frame, field AI per entity, combat resolution); see
`docs/audits/DECISION_LOG.md` D23.
