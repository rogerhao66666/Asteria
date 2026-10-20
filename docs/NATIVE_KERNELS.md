# Native (C++) kernels

The engine's hot loops (broad-phase collision, projectiles, particles, weather, character
movement, field AI steps) run as **kernels**: small functions over column buffers, in three
interchangeable sets:

| Set | What it is | When |
| --- | --- | --- |
| `python` | the reference; always available | the rule every other set must match, bit for bit |
| `numpy` | the same arithmetic on whole arrays | when numpy is installed |
| `native` | the same arithmetic in C++ | when the library is built (numpy optional) |

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

On macOS the library is **universal** (`-arch arm64 -arch x86_64`) when the compiler can build
both, so a game built on an Apple silicon Mac also runs natively on an Intel one; otherwise it is
built for this machine only. `lipo -info` on the library shows which.

Without the library nothing breaks: `auto` falls back to numpy (or python). Each native function
also checks the buffer types it reads and falls back for anything else.

**Exports** (`asteria-export`, the editor's Export Game) check the library first: missing, not
loadable, another ABI (`ABI_VERSION` in `build_native.py`, `ak_abi_version` in the C++) or older
than its source means it is built again. Only a library that passed the check is copied into the
game. When no compiler can build it the export still finishes, with a warning in its report, the
CLI output and the editor's export message; that game runs on numpy or python.

## Without numpy

The native set does not need numpy: the C++ reads and writes `array.array` buffers through
ctypes, so a game exported to a player's plain Python (no numpy) still runs the C++ kernels.
What changes without numpy:

- functions not ported to C++ (and unexpected column types) fall back to the **python** reference
  instead of numpy;
- the particle, weather and projectile stores keep their rows in one flat `array("d")` (field `k`
  of row `i` at `k * n + i`, the layout the C++ steps read); with numpy they stay numpy arrays,
  whose views and weather drawing are vectorised.

## Exported games

`asteria-export` copies the whole `asteria` package, so the built library travels with the game
(the folder build and the `.pyz`, which unpacks into the user cache on first run and loads it from
there). Build the library before exporting; a game exported without it runs on numpy or python.

## Checking it

```bash
python -m pytest tests/test_native_kernels.py     # every function against the reference
ASTERIA_KERNELS=native python -m pytest           # the whole suite on the native set
python scripts/arpg_stress.py out.json --kernels python numpy native
lipo -info src/asteria/kernels/native/libasteria_kernels.dylib    # macOS: arm64 and x86_64
```

`tests/test_native_kernels.py` also runs itself again with numpy hidden, checks the macOS library
is universal, and unpacks an exported `.pyz` to check it loads the library.

## Adding a kernel

1. Write the python reference in `kernels/_python.py` and the numpy version in `_numpy.py`.
2. Add a C function to `native/asteria_kernels.cpp` (a plain `extern "C"` function over raw
   buffers; variable-size results use a caller-owned buffer and return the count needed).
3. Declare it and wrap it in `kernels/_native.py` (hold references to temporary arrays until the
   call returns).
4. Add a comparison to `tests/test_native_kernels.py`, including the columns it writes in place.

## What it buys

On the ARPG stress scene (300 enemies, 500 projectiles, 300 frames, MacBook Air, no heap
tracing) a frame takes about 3.2 ms on python, 2.4 ms on numpy, 1.85 ms on native and 1.95 ms on
native without numpy - every set with the same final state digest. The rest of the frame is Python object loops (the collision
world is rebuilt from the scene every frame, field AI per entity, combat resolution); see
`docs/audits/DECISION_LOG.md` D23.
