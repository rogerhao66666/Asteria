"""Build the native kernel library (D23): ``python -m asteria.kernels.build_native``.

Compiles ``native/asteria_kernels.cpp`` with the system C++ compiler (clang++, g++ or c++) into a
shared library next to it. No other dependency. Floating point is built strictly (no fast-math, no
fused multiply-add) so results match the python reference kernel set. Without the library the
engine simply keeps using the numpy kernels.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "native" / "asteria_kernels.cpp"


def library_name():
    suffix = {"darwin": ".dylib", "win32": ".dll"}.get(sys.platform, ".so")
    return HERE / "native" / f"libasteria_kernels{suffix}"


def build(*, verbose=True):
    """Compile the library; returns its path, or raises ``RuntimeError`` (the compiler output)."""
    compiler = next((c for c in ("clang++", "g++", "c++") if shutil.which(c)), None)
    if compiler is None:
        raise RuntimeError("no C++ compiler found (install clang++ or g++)")
    target = library_name()
    command = [
        compiler,
        "-std=c++17",
        "-O3",
        "-fPIC",
        "-shared",
        "-ffp-contract=off",  # no fused multiply-add: same rounding as the python kernels
        "-fno-fast-math",
        "-Wall",
        "-Wextra",
        str(SOURCE),
        "-o",
        str(target),
    ]
    if verbose:
        print(" ".join(command))
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    if verbose and result.stderr:
        print(result.stderr)
    return target


if __name__ == "__main__":
    print(f"built {build()}")
