"""Build the native kernel library (D23): ``python -m asteria.kernels.build_native``.

Compiles ``native/asteria_kernels.cpp`` with the system C++ compiler (clang++, g++ or c++) into a
shared library next to it. No other dependency. Floating point is built strictly (no fast-math, no
fused multiply-add) so results match the python reference kernel set. On macOS the library is
universal (arm64 and x86_64) when the compiler can build both, so a game exported from an Apple
silicon Mac also runs natively on an Intel one; otherwise it is built for this machine only.
Without the library the engine simply keeps using the numpy (or python) kernels.

``problem()`` says why the library cannot be used as it is (missing, will not load, another ABI,
older than its source) and ``ensure()`` builds it when it can; exports call it before copying
the engine.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "native" / "asteria_kernels.cpp"
# the library and the ctypes declarations in _native.py must agree; bump both together
ABI_VERSION = 5
STALE = "older than its source"
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


def find_compiler():
    return next((c for c in ("clang++", "g++", "c++") if shutil.which(c)), None)


def _run(command, verbose):
    if verbose:
        print(" ".join(command))
    return subprocess.run(command, capture_output=True, text=True, check=False)


def build(*, verbose=True, universal=None):
    """Compile the library; returns its path, or raises ``RuntimeError`` (the compiler output).

    ``universal`` (default: on macOS) builds arm64 + x86_64 in one file, falling back to this
    machine's architecture when the compiler cannot."""
    compiler = find_compiler()
    if compiler is None:
        raise RuntimeError("no C++ compiler found (install clang++ or g++)")
    target = library_name()
    # built beside the library, then swapped in: a process that has the old library loaded
    # keeps its copy (writing over a loaded library in place can crash it)
    built = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    if universal is None:
        universal = sys.platform == "darwin"
    result = None
    try:
        if universal:
            result = _run(_command(compiler, built, UNIVERSAL), verbose)
            if result.returncode != 0 and verbose:
                print("universal build failed; building for this machine only")
        if result is None or result.returncode != 0:
            result = _run(_command(compiler, built), verbose)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or "the compiler failed")
        if not built.is_file():
            raise RuntimeError(f"the compiler wrote no {built.name}")
        os.replace(built, target)
    finally:
        built.unlink(missing_ok=True)
    if verbose and result.stderr:
        print(result.stderr)
    return target


_PROBE = (
    "import ctypes, sys\n"
    "lib = ctypes.CDLL(sys.argv[1])\n"
    "lib.ak_abi_version.restype = ctypes.c_int32\n"
    "print(lib.ak_abi_version())\n"
)


def _abi_of(path):
    """The library's ABI version, read in a fresh process: this one may hold an older copy (the
    loader hands back the library it already loaded from that path). Raises ``OSError`` when the
    library does not load."""
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-c", _PROBE, str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise OSError("loading it timed out") from exc
    lines = result.stderr.strip().splitlines()
    if result.returncode != 0:
        raise OSError(lines[-1] if lines else f"exit code {result.returncode}")
    try:
        return int(result.stdout.strip())
    except ValueError as exc:
        raise OSError(f"unexpected answer {result.stdout.strip()!r}") from exc


def problem(path=None):
    """Why the library cannot be used as it is, or ``None`` when it is built, loads, has this
    engine's ABI and is newer than its source."""
    path = Path(path) if path is not None else library_name()
    if not path.is_file():
        return "not built"
    try:
        abi = _abi_of(path)
    except OSError as exc:
        return f"not loadable ({exc})"
    if abi != ABI_VERSION:
        return f"out of date (ABI {abi}, this engine needs {ABI_VERSION})"
    if SOURCE.is_file() and SOURCE.stat().st_mtime > path.stat().st_mtime:
        return STALE
    return None


def _first_line(exc):
    lines = str(exc).strip().splitlines()
    return lines[0] if lines else type(exc).__name__


def ensure():
    """Build the library when ``problem()`` finds one. Returns ``(usable, reason)``: whether a
    library this engine loads is in place now (an older build of the same ABI still is), and
    what is still wrong (``None`` when nothing is)."""
    reason = problem()
    if reason is None:
        return True, None
    failure = None
    try:
        build(verbose=False)
    except (RuntimeError, OSError) as exc:
        failure = _first_line(exc)
    after = problem()
    if after is None:
        return True, None
    failure = failure or f"the new build is {after}"
    return after == STALE, f"{reason}; building it failed: {failure}"


if __name__ == "__main__":
    print(f"built {build()}")
