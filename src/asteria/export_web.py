"""Export an Asteria project as a game that runs in the browser (pygbag: CPython + pygame-ce
compiled to WebAssembly).

    python -m asteria.export_web path/to/project.asteria.json OUT_DIR
    python -m asteria.export_web ... OUT_DIR --serve        # build, then serve on 127.0.0.1:8000
    asteria-export-web ...                                  # the same, installed as a command

The export writes ``OUT_DIR/<game>/``: the project and every file it references (with the packs'
credits and licences), a slim copy of the engine (no editor, multiplayer, validation or template
code, no native library), the bundled Chinese font (``fonts/``) and a ``main.py`` that pygbag
runs. ``pygbag --build`` then packs that folder into ``OUT_DIR/<game>/build/web/``
(``index.html``, the icon and the game as an archive): copy that folder to any static web host
(or itch.io). The page loads the Python runtime from the pygame-web CDN when the player opens it
(``--cdn`` points it at a copy you host yourself).

On the web the game runs on the pure Python kernels, has no threads (battle pictures are
decoded one per frame instead of on a worker), no multiplayer, no ModernGL back end, and keeps
its saves and settings in the browser's ``localStorage`` (``runtime/web_persistence.py``).
Music and sounds must be ``.ogg`` or ``.wav``: the browser build has no mp3 decoder.
"""

from __future__ import annotations

import argparse
import http.server
import mimetypes
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from asteria import project_tools

WEB_DIR = Path("build") / "web"
DEFAULT_WIDTH, DEFAULT_HEIGHT = 1280, 720
DEFAULT_PORT = 8000
DEFAULT_CDN = "https://pygame-web.github.io/cdn/0.9.3/"
TEMPLATE_NAME = "default.tmpl"
ICON_NAME = "favicon.png"
CACHE_DIR = ".pygbag-cache"
# engine folders a browser build never imports (the editor needs PySide6, the rest needs sockets,
# threads or a compiler); the native kernel library is a desktop binary
ENGINE_SKIP_DIRS = ("editor", "multiplayer", "validation", "templates")
ENGINE_SKIP_PATTERNS = ("__pycache__", "*.pyc", "libasteria_kernels.*", ".*.tmp", "native")
UNSUPPORTED_AUDIO = {".mp3", ".flac", ".mid", ".midi", ".xm", ".mod"}
FONT_DIR = "fonts"


def default_cjk_font():
    """The Chinese font shipped with the engine's asset library (Noto Sans TC, SIL OFL 1.1),
    when this is a source checkout; None otherwise."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "asset_library" / "fonts" / "noto_sans_tc" / "NotoSansTC-Regular.otf"
        if candidate.is_file():
            return candidate
    return None


MAIN_PY = '''"""{title}: the browser entry point written by asteria.export_web (pygbag runs it).

The same file runs on the desktop (``python main.py``) with the same loop, which is how the
export is tested without a browser: ``ASTERIA_WEB_MAX_FRAMES`` stops it after that many frames.
"""

import asyncio
import os
import sys
import time
from pathlib import Path

import pygame  # noqa: F401 - pygbag reads this file's imports to know which packages to load

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.chdir(HERE)
os.environ["ASTERIA_KERNELS"] = "python"  # no numpy, no native library in the browser
if {cjk_font!r}:
    os.environ.setdefault("ASTERIA_CJK_FONT", str(HERE / {cjk_font!r}))
if sys.platform == "emscripten":  # ?mute=1 in the page address: a silent run (automated checks)
    try:
        import platform

        if "mute" in str(platform.window.location.search):
            os.environ["ASTERIA_MUTE"] = "1"
    except Exception:  # noqa: BLE001 - no page bridge: play with sound
        pass

PROJECT = {project!r}
WIDTH, HEIGHT = {width}, {height}
SYNC_EVERY = 30  # frames between looks at the saves folder
REPORT_EVERY = 600  # frames between frame-time lines on the console
RUNTIME = None  # the running game, for the page's Python console (pygbag's terminal)


def build_runtime():
    from asteria.project import Project
    from asteria.runtime.component_registry import default_component_registry
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = Project.load_json(HERE / PROJECT, default_component_registry())
    save = project.game_start.instantiate(project)
    runtime = PlayableTestRuntime(project, save, HERE, width=WIDTH, height=HEIGHT)
    runtime.preload_battle_images = sys.platform == "emscripten" or None
    return runtime


def saves_mirror():
    from asteria.runtime.web_persistence import DictStorage, FolderMirror, browser_storage

    storage = browser_storage()
    if storage is None and os.environ.get("ASTERIA_WEB_FAKE_STORAGE"):
        storage = DictStorage()
    return None if storage is None else FolderMirror(HERE / "saves", storage)


async def main():
    global RUNTIME
    mirror = saves_mirror()
    if mirror is not None:
        mirror.restore()
    runtime = RUNTIME = build_runtime()
    runtime.open()
    max_frames = int(os.environ.get("ASTERIA_WEB_MAX_FRAMES", "0") or 0)
    frames, last, spent = 0, time.perf_counter(), 0.0
    try:
        while runtime.running:
            now = time.perf_counter()
            dt, last = min(now - last, 0.05), now
            runtime.step(dt)
            spent += time.perf_counter() - now
            frames += 1
            if mirror is not None and frames % SYNC_EVERY == 0:
                mirror.sync()
            if frames % REPORT_EVERY == 0:
                print(f"asteria: {{frames}} frames, {{spent / REPORT_EVERY * 1000:.1f}} ms each")
                spent = 0.0
            if max_frames and frames >= max_frames:
                break
            await asyncio.sleep(0)
    finally:
        if mirror is not None:
            mirror.sync()
        runtime.close()
    return 0


if __name__ == "__main__":
    asyncio.run(main())
'''


@dataclass
class WebExportReport:
    output: Path
    app: Path
    web: Path | None = None
    files: list[Path] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class WebExportError(RuntimeError):
    pass


def _copy_engine(target):
    """The ``asteria`` package without the parts a browser cannot run."""
    import asteria

    source = Path(asteria.__file__).resolve().parent
    shutil.rmtree(target, ignore_errors=True)
    skip = shutil.ignore_patterns(*ENGINE_SKIP_PATTERNS)

    def ignore(directory, names):
        ignored = set(skip(directory, names))
        if Path(directory) == source:
            ignored.update(n for n in names if n in ENGINE_SKIP_DIRS)
        return ignored

    shutil.copytree(source, target, ignore=ignore)
    return sorted(p for p in target.rglob("*") if p.is_file())


def _audio_check(files, report, *, allow_unsupported):
    bad = sorted(str(p) for p in files if p.suffix.lower() in UNSUPPORTED_AUDIO)
    if bad:
        message = "audio the browser cannot play (convert to .ogg): " + ", ".join(bad)
        if not allow_unsupported:
            raise WebExportError(message)
        report.warnings.append(message)
    wavs = [p for p in files if p.suffix.lower() == ".wav" and p.stat().st_size > 1 << 20]
    if wavs:
        report.warnings.append(
            f"{len(wavs)} .wav file(s) over 1 MB: .ogg would load faster in the browser"
        )


def _slug(name):
    return project_tools._slug(name).lower()


def _fetch(url, target):
    """Download ``url`` to ``target``: urllib, then urllib with certifi's bundle, then curl (a
    python.org Python on macOS has no certificates until its own script installs them)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    errors = []
    contexts = [None]
    try:
        import ssl

        import certifi

        contexts.append(ssl.create_default_context(cafile=certifi.where()))
    except ImportError:
        pass
    for context in contexts:
        try:
            with urllib.request.urlopen(url, timeout=30, context=context) as response:
                target.write_bytes(response.read())
            return target
        except Exception as exc:  # noqa: BLE001 - try the next way
            errors.append(f"{type(exc).__name__}: {exc}")
    curl = shutil.which("curl")
    if curl:
        done = subprocess.run(
            [curl, "-fsSL", "--max-time", "60", "-o", str(target), url],
            check=False,
            capture_output=True,
            text=True,
        )
        if done.returncode == 0 and target.is_file():
            return target
        errors.append(f"curl: {done.stderr.strip() or done.returncode}")
    raise WebExportError(f"could not download {url} ({'; '.join(errors)})")


def pygbag_files(output, cdn=None, icon=None):
    """The page template and icon pygbag needs, fetched once into ``OUT_DIR/.pygbag-cache``
    (pygbag's own download has no way around a Python without certificates). ``icon``: the
    game's own 32x32+ PNG; without one the CDN's, and failing that a plain generated one."""
    cache = Path(output) / CACHE_DIR
    base = (cdn or DEFAULT_CDN).rstrip("/") + "/"
    template = cache / TEMPLATE_NAME
    if not template.is_file():
        _fetch(base + TEMPLATE_NAME, template)
    if icon:
        icon = Path(icon)
        if not icon.is_file():
            raise WebExportError(f"icon not found: {icon}")
        return template, icon
    icon = cache / ICON_NAME
    if not icon.is_file():
        try:
            _fetch(base + ICON_NAME, icon)
        except WebExportError:
            _plain_icon(icon)
    return template, icon


def _plain_icon(target):
    import pygame

    image = pygame.Surface((32, 32), pygame.SRCALPHA)
    pygame.draw.circle(image, (60, 120, 220, 255), (16, 16), 15)
    pygame.draw.circle(image, (240, 240, 255, 255), (16, 16), 7)
    pygame.image.save(image, str(target))
    return target


def pygbag_command(
    app,
    *,
    title,
    cdn=None,
    width=DEFAULT_WIDTH,
    height=DEFAULT_HEIGHT,
    template=None,
    icon=None,
):
    """The ``pygbag --build`` command line for ``app``.

    ``--no_opt`` keeps pygbag's optimizer off: it would requantize the PNGs (lossy, wrong for
    pixel art) and re-encode the audio. ``--ume_block 1`` waits for the player's first click
    before starting (browsers allow audio only after a gesture)."""
    command = [sys.executable, "-m", "pygbag", "--build"]
    command += [
        "--no_opt",
        "--disable-sound-format-error",  # .wav plays in the browser; pygbag only prefers .ogg
        "--app_name",
        _slug(title),
        "--title",
        str(title),
        "--ume_block",
        "1",
        "--can_close",
        "1",
        "--width",
        str(int(width)),
        "--height",
        str(int(height)),
    ]
    if cdn:
        command += ["--cdn", str(cdn).rstrip("/") + "/"]
    if template:
        command += ["--template", str(template)]
    if icon:
        command += ["--icon", str(icon)]
    command.append(str(app))
    return command


class _WebHandler(http.server.SimpleHTTPRequestHandler):
    """Static files with the wasm media type and permissive cross-origin headers. No
    ``cross-origin-embedder-policy``: the page loads its runtime from the CDN, which that
    header would block (pygbag's own test server can set it only because it proxies the CDN)."""

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".apk": "application/octet-stream",
    }

    def end_headers(self):
        self.send_header("access-control-allow-origin", "*")
        self.send_header("cross-origin-resource-policy", "cross-origin")
        self.send_header("cache-control", "no-store")
        super().end_headers()

    def log_message(self, format, *args):  # noqa: A002 - the base class's name
        sys.stderr.write(f"{self.address_string()} - {format % args}\n")

    def do_POST(self):  # noqa: N802 - the base class's name
        """``POST /shot?name=X`` with a PNG body saves ``shots/X.png`` beside the build: how a
        page's picture reaches the disk (from the browser console:
        ``canvas.toBlob(b => fetch('/shot?name=title', {method: 'POST', body: b}))``)."""
        from urllib.parse import parse_qs, urlsplit

        parts = urlsplit(self.path)
        name = parse_qs(parts.query).get("name", ["shot"])[0]
        name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name) or "shot"
        length = int(self.headers.get("content-length", 0))
        body = self.rfile.read(length) if length else b""
        if parts.path != "/shot" or not body.startswith(b"\x89PNG"):
            self.send_error(400, "POST /shot?name=X with a PNG body")
            return
        target = Path(self.directory).parent / "shots" / f"{name}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        self.send_response(200)
        self.send_header("content-type", "text/plain")
        self.end_headers()
        self.wfile.write(str(target).encode())


def serve_web(web, port=DEFAULT_PORT, *, bind="127.0.0.1", ready=None):
    """Serve a built ``build/web`` folder on ``http://127.0.0.1:PORT/`` until interrupted.
    Open it by that address, not ``localhost``: pygbag's runtime takes ``localhost:8xxx`` for
    its own development server and then looks for the Python packages at ``localhost:8000``.
    ``ready(server)`` runs on its own thread once the server listens (tests talk to the server
    and stop it from there)."""
    import threading

    mimetypes.add_type("application/wasm", ".wasm")
    web = Path(web)

    def handler(*args, **kwargs):
        return _WebHandler(*args, directory=str(web), **kwargs)

    with http.server.ThreadingHTTPServer((bind, int(port)), handler) as server:
        print(
            f"Serving {web} on http://127.0.0.1:{server.server_address[1]}/ (open that address,"
            " not localhost; Ctrl+C stops)"
        )
        if ready is not None:
            threading.Thread(target=ready, args=(server,), daemon=True).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


def export_web(
    project_path,
    output,
    *,
    title=None,
    cjk_font="default",
    cdn=None,
    icon=None,
    width=DEFAULT_WIDTH,
    height=DEFAULT_HEIGHT,
    allow_missing=False,
    allow_unsupported_audio=False,
    build=True,
    serve=False,
    port=DEFAULT_PORT,
    run=subprocess.run,
):
    """Write ``OUT_DIR/app`` and (with ``build``) run pygbag on it; returns a WebExportReport.

    ``cjk_font``: a font file to ship for Chinese, Japanese and Korean text; ``"default"`` is the
    asset library's Noto Sans TC, None ships none (such text then draws as boxes in the browser).
    ``allow_unsupported_audio`` exports mp3 and other formats the browser cannot decode with a
    warning instead of refusing. ``serve`` also serves the built page on ``port`` (blocks until
    stopped) the way any static host would: the page loads the runtime from the CDN.
    """
    project_path = Path(project_path)
    output = Path(output)
    project = project_tools.load_project(project_path)
    title = title or project.name or "Asteria Game"
    app = output / _slug(title)  # pygbag names the archive after this folder
    base = project_tools.export_game(
        project_path, app, allow_missing=allow_missing, bundle_engine=False
    )
    report = WebExportReport(output, app, files=list(base.files), missing=list(base.missing))
    report.warnings.extend(base.warnings)
    launcher = app / "run_game.py"  # the desktop launcher: not part of a web game
    if launcher.exists():
        launcher.unlink()
        report.files = [p for p in report.files if p != launcher]
    report.files.extend(_copy_engine(app / "asteria"))
    font_rel = None
    if cjk_font == "default":
        cjk_font = default_cjk_font()
        if cjk_font is None:
            report.warnings.append(
                "no Chinese font found in asset_library/fonts: CJK text draws as boxes"
            )
    if cjk_font:
        source = Path(cjk_font)
        if not source.is_file():
            raise WebExportError(f"CJK font not found: {source}")
        target = app / FONT_DIR / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        report.files.append(target)
        for name in project_tools.NOTICE_NAMES:  # the font's licence travels with it
            notice = source.parent / name
            if notice.is_file():
                shutil.copy2(notice, target.parent / name)
                report.files.append(target.parent / name)
        font_rel = f"{FONT_DIR}/{source.name}"
    _audio_check(report.files, report, allow_unsupported=allow_unsupported_audio)
    main_py = app / "main.py"
    main_py.write_text(
        MAIN_PY.format(
            title=title,
            cjk_font=font_rel,
            project=project_tools.PROJECT_FILE,
            width=int(width),
            height=int(height),
        ),
        encoding="utf-8",
    )
    report.files.append(main_py)
    if build or serve:
        try:
            import pygbag  # noqa: F401
        except ImportError as exc:
            raise WebExportError(
                "pygbag is not installed: pip install 'asteria[web]' (or pip install pygbag)"
            ) from exc
        template, icon = pygbag_files(output, cdn, icon)
        command = pygbag_command(
            app, title=title, cdn=cdn, width=width, height=height, template=template, icon=icon
        )
        completed = run(command, cwd=str(output), check=False)
        if getattr(completed, "returncode", 0):
            raise WebExportError(f"pygbag failed with exit code {completed.returncode}")
        web = app / WEB_DIR
        if not (web / "index.html").is_file():
            raise WebExportError(f"pygbag produced no {web / 'index.html'}")
        report.web = web  # index.html, favicon.png, the game as .apk and .tar.gz (the page
        if serve:  # fetches the .tar.gz; the .apk is the same files for other front ends)
            serve_web(web, port)
    elif serve:  # --no-build --serve: the page built last time
        web = app / WEB_DIR
        if not (web / "index.html").is_file():
            raise WebExportError(f"nothing built yet at {web}: run without --no-build first")
        report.web = web
        serve_web(web, port)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Export an Asteria project as a browser game (pygbag)"
    )
    parser.add_argument("project")
    parser.add_argument("output")
    parser.add_argument("--title", help="game name (default: the project name)")
    parser.add_argument(
        "--cjk-font",
        default="default",
        help="font file for Chinese/Japanese/Korean text (default: the asset library's Noto "
        "Sans TC; 'none' ships no font)",
    )
    parser.add_argument("--cdn", help="where the page loads the Python runtime from")
    parser.add_argument("--icon", help="the page's icon, a PNG of 32x32 or more")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument(
        "--allow-unsupported-audio",
        action="store_true",
        help="export mp3 and other audio the browser cannot play (silent there) with a warning",
    )
    parser.add_argument(
        "--no-build", action="store_true", help="write the app folder only, do not run pygbag"
    )
    parser.add_argument(
        "--serve", action="store_true", help="after building, serve it on http://127.0.0.1:PORT"
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    font = None if str(args.cjk_font).lower() == "none" else args.cjk_font
    try:
        report = export_web(
            args.project,
            args.output,
            title=args.title,
            cjk_font=font,
            cdn=args.cdn,
            icon=args.icon,
            width=args.width,
            height=args.height,
            allow_missing=args.allow_missing,
            allow_unsupported_audio=args.allow_unsupported_audio,
            build=not args.no_build,
            serve=args.serve,
            port=args.port,
        )
    except (WebExportError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"App folder: {report.app}  ({len(report.files)} files)")
    for missing in report.missing:
        print(f"  missing: {missing}")
    for warning in report.warnings:
        print(f"  warning: {warning}")
    if report.web is not None:
        print(f"Web build:  {report.web}  (copy index.html and the .apk to a static host)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
