"""Build the native kernel library (D23): ``python -m asteria.kernels.build_native``.

Compiles ``native/asteria_kernels.cpp`` with the system C++ compiler (clang++, g++ or c++) into a
shared library next to it. No other dependency. Floating point is built strictly (no fast-math, no
fused multiply-add) so results match the python reference kernel set. On macOS the library is
universal (arm64 and x86_64) when the compiler can build both, so a game exported from an Apple
silicon Mac also runs natively on an Intel one; otherwise it is built for this machine only.
Without the library the engine simply keeps using the numpy (or python) kernels.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "native" / "asteria_kernels.cpp"
UNIVERSAL = ("-arch", "arm64", "-arch", "x86_64")
# oldest macOS the library loads on (11 = the first with arm64); without it clang stamps the
# build machine's version and an older Mac refuses the library. MACOSX_DEPLOYMENT_TARGET wins.
MACOS_MIN = "11.0"


def library_name():
    suffix = {"darwin": ".dylib", "win32": ".dll"}.get(sys.platform, ".so")
    return HERE / "native" / f"libasteria_kernels{suffix}"


def _platform_flags():
    if sys.platform != "darwin" or os.environ.get("MACOSX_DEPLOYMENT_TARGET"):
        return []
    return [f"-mmacosx-version-min={MACOS_MIN}"]


def _command(compiler, target, arch=()):
    return [
        compiler,
        "-std=c++17",
        "-O3",
        "-fPIC",
        "-shared",
        *arch,
        *_platform_flags(),
        "-ffp-contract=off",  # no fused multiply-add: same rounding as the python kernels
        "-fno-fast-math",
        "-Wall",
        "-Wextra",
        str(SOURCE),
        "-o",
        str(target),
    ]


def _run(command, verbose):
    if verbose:
        print(" ".join(command))
    return subprocess.run(command, capture_output=True, text=True, check=False)


def build(*, verbose=True, universal=None):
    """Compile the library; returns its path, or raises ``RuntimeError`` (the compiler output).

    ``universal`` (default: on macOS) builds arm64 + x86_64 in one file, falling back to this
    machine's architecture when the compiler cannot."""
    compiler = next((c for c in ("clang++", "g++", "c++") if shutil.which(c)), None)
    if compiler is None:
        raise RuntimeError("no C++ compiler found (install clang++ or g++)")
    target = library_name()
    if universal is None:
        universal = sys.platform == "darwin"
    result = None
    if universal:
        result = _run(_command(compiler, target, UNIVERSAL), verbose)
        if result.returncode != 0 and verbose:
            print("universal build failed; building for this machine only")
    if result is None or result.returncode != 0:
        result = _run(_command(compiler, target), verbose)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    if verbose and result.stderr:
        print(result.stderr)
    return target


if __name__ == "__main__":
    print(f"built {build()}")
