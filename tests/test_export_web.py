"""The browser export (asteria/export_web.py) and what makes the engine run there: the app
folder it writes, its main.py running the same loop on the desktop, saves mirrored into Web
Storage, battle pictures decoded without threads, a bundled Chinese font."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

pygame = pytest.importorskip("pygame")

from asteria import export_web  # noqa: E402
from asteria.runtime.image_preloader import ImagePreloader  # noqa: E402
from asteria.runtime.web_persistence import DictStorage, FolderMirror  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "reference_projects" / "party_rpg_demo" / "project.asteria.json"
HEADLESS = {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    out = tmp_path_factory.mktemp("web")
    report = export_web.export_web(DEMO, out, build=False)
    return report


def test_the_app_folder_holds_the_game_a_slim_engine_the_font_and_main_py(exported):
    app = exported.app
    assert app.name == "party_rpg_demo" or app.name.endswith("demo")
    assert (app / "project.asteria.json").is_file()
    assert (app / "playable_test_manifest.json").is_file()
    assert (app / "main.py").is_file()
    assert not (app / "run_game.py").exists()  # the desktop launcher stays home
    engine = app / "asteria"
    assert (engine / "runtime" / "playable_test_runtime.py").is_file()
    assert (engine / "runtime" / "web_persistence.py").is_file()
    for skipped in export_web.ENGINE_SKIP_DIRS:
        assert not (engine / skipped).exists(), skipped
    assert not (engine / "kernels" / "native").exists()
    assert not list(engine.rglob("__pycache__"))
    font = app / export_web.FONT_DIR / "NotoSansTC-Regular.otf"
    assert font.is_file() and (font.parent / "LICENSE.txt").is_file()
    assert exported.web is None and not exported.missing
    # every picture the project draws came along, nothing outside the project did
    pictures = [p for p in app.rglob("*.png")]
    assert pictures and all(app in p.parents for p in pictures)


def test_main_py_runs_the_exported_game_on_the_desktop_with_the_web_loop(exported):
    env = dict(os.environ, **HEADLESS)
    env.update(ASTERIA_WEB_MAX_FRAMES="40", ASTERIA_WEB_FAKE_STORAGE="1")
    env.pop("ASTERIA_KERNELS", None)
    done = subprocess.run(
        [sys.executable, "-I", "main.py"],
        cwd=exported.app,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    assert "Traceback" not in done.stderr


def test_main_py_pins_the_pure_python_kernels_and_the_bundled_font(exported):
    text = (exported.app / "main.py").read_text(encoding="utf-8")
    assert 'os.environ["ASTERIA_KERNELS"] = "python"' in text
    assert "fonts/NotoSansTC-Regular.otf" in text
    assert "await asyncio.sleep(0)" in text and "runtime.step(dt)" in text


def test_mute_gives_the_silent_audio_device(monkeypatch, exported):
    from asteria.platform.pygame_audio import open_audio_device
    from asteria.runtime.audio_mixer import RecordingAudioDevice

    monkeypatch.setenv("ASTERIA_MUTE", "1")
    assert isinstance(open_audio_device(pygame), RecordingAudioDevice)
    assert "?mute=1" in (exported.app / "main.py").read_text(encoding="utf-8")


def test_unsupported_audio_is_refused_unless_allowed(tmp_path):
    demo = tmp_path / "demo"
    demo.mkdir()
    for name in ("project.asteria.json", "playable_test_manifest.json"):
        (demo / name).write_bytes((DEMO.parent / name).read_bytes())
    manifest = json.loads((demo / "playable_test_manifest.json").read_text())
    manifest.setdefault("audio", {})["mp3_test"] = "playable_assets/song.mp3"
    (demo / "playable_test_manifest.json").write_text(json.dumps(manifest))
    (demo / "playable_assets").mkdir()
    (demo / "playable_assets" / "song.mp3").write_bytes(b"ID3")
    with pytest.raises(export_web.WebExportError, match="song.mp3"):
        export_web.export_web(
            demo / "project.asteria.json", tmp_path / "out", build=False, allow_missing=True
        )
    report = export_web.export_web(
        demo / "project.asteria.json",
        tmp_path / "out2",
        build=False,
        allow_missing=True,
        allow_unsupported_audio=True,
        cjk_font=None,
    )
    assert any("song.mp3" in w for w in report.warnings)


def test_the_pygbag_command_keeps_pixels_and_wav_and_names_the_page(tmp_path):
    command = export_web.pygbag_command(
        tmp_path / "game",
        title="My Game",
        cdn="https://example.test/cdn/0.9.3",
        template=tmp_path / "default.tmpl",
        icon=tmp_path / "favicon.png",
    )
    assert command[:3] == [sys.executable, "-m", "pygbag"]
    assert "--build" in command and "--no_opt" in command
    assert "--disable-sound-format-error" in command
    assert command[command.index("--cdn") + 1] == "https://example.test/cdn/0.9.3/"
    assert command[command.index("--title") + 1] == "My Game"
    assert command[-1] == str(tmp_path / "game")
    assert command[command.index("--template") + 1] == str(tmp_path / "default.tmpl")


def test_serve_web_answers_with_the_page_and_wasm_headers(tmp_path):
    import threading
    import urllib.request

    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<html>hi</html>")
    (web / "a.wasm").write_bytes(b"\0asm")
    got = {}

    def ready(server):
        port = server.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/index.html") as r:
            got["html"] = (r.status, r.read(), r.headers.get("cross-origin-resource-policy"))
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/a.wasm") as r:
            got["wasm"] = r.headers.get("content-type")
        threading.Thread(target=server.shutdown).start()

    assert export_web.serve_web(web, 0, ready=ready) == 0
    assert got["html"] == (200, b"<html>hi</html>", "cross-origin")
    assert got["wasm"] == "application/wasm"


def test_building_runs_pygbag_and_reports_its_page(tmp_path, monkeypatch):
    pytest.importorskip("pygbag")
    calls = []

    def fake_run(command, cwd, check):
        calls.append(command)
        app = Path(command[-1])
        web = app / export_web.WEB_DIR
        web.mkdir(parents=True)
        (web / "index.html").write_text("<html></html>")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(
        export_web, "pygbag_files", lambda out, cdn, icon: (tmp_path / "t.tmpl", tmp_path / "i")
    )
    report = export_web.export_web(DEMO, tmp_path / "out", run=fake_run, cjk_font=None)
    assert report.web == report.app / export_web.WEB_DIR
    assert calls and calls[0][-1] == str(report.app)


# -- saves in the browser --------------------------------------------------------------------


def test_folder_mirror_restores_stores_and_forgets(tmp_path):
    storage = DictStorage()
    saves = tmp_path / "saves"
    mirror = FolderMirror(saves, storage)
    assert mirror.restore() == 0 and saves.is_dir()
    (saves / "slot1.asteria-save.json").write_text('{"a": 1}', encoding="utf-8")
    (saves / "settings.json").write_text('{"music_volume": 0.5}', encoding="utf-8")
    (saves / "notes.txt").write_text("not mirrored", encoding="utf-8")
    assert mirror.sync() == 2
    assert mirror.sync() == 0  # nothing changed: nothing stored again
    assert set(mirror.names()) == {"slot1.asteria-save.json", "settings.json"}
    time.sleep(0.01)
    (saves / "slot1.asteria-save.json").write_text('{"a": 2}', encoding="utf-8")
    assert mirror.sync() == 1
    (saves / "settings.json").unlink()
    assert mirror.sync() == 1
    assert mirror.names() == ["slot1.asteria-save.json"]
    assert storage.getItem("asteria.saves.settings.json") is None
    # a new page: the folder is empty again, restore brings the stored files back
    fresh = tmp_path / "fresh"
    again = FolderMirror(fresh, storage)
    assert again.restore() == 1
    assert json.loads((fresh / "slot1.asteria-save.json").read_text()) == {"a": 2}
    assert again.sync() == 0  # restored files count as stored


def test_folder_mirror_ignores_a_damaged_index_and_odd_names(tmp_path):
    storage = DictStorage({"asteria.saves.index": "not json"})
    mirror = FolderMirror(tmp_path / "s", storage)
    assert mirror.names() == [] and mirror.restore() == 0
    storage.setItem("asteria.saves.index", json.dumps(["../evil.json", "ok.json"]))
    storage.setItem("asteria.saves.ok.json", "{}")
    storage.setItem("asteria.saves.../evil.json", "{}")
    assert mirror.restore() == 1
    assert (tmp_path / "s" / "ok.json").is_file() and not (tmp_path / "evil.json").exists()


# -- the engine guards -----------------------------------------------------------------------


@pytest.fixture
def screen(monkeypatch):
    for key, value in HEADLESS.items():
        monkeypatch.setenv(key, value)
    pygame.display.init()
    yield pygame.display.set_mode((64, 64))
    pygame.display.quit()


def test_the_preloader_decodes_without_threads(screen, tmp_path):
    rels = []
    for i in range(3):
        image = pygame.Surface((24, 16), pygame.SRCALPHA)
        image.fill((40 * i, 80, 160, 255))
        pygame.image.save(image, str(tmp_path / f"p{i}.png"))
        rels.append(f"p{i}.png")
    preloader = ImagePreloader(pygame, lambda rel: tmp_path / rel, threads=False)
    assert preloader.threads is False and preloader._executor is None
    preloader.want(rels + ["missing.png"])
    for _ in range(10):
        preloader.step()
    assert all(preloader.ready(rel) for rel in rels)
    assert preloader._executor is None  # never started a worker
    assert "missing.png" in preloader._failed
    for rel in rels:
        direct = pygame.image.load(tmp_path / rel).convert_alpha()
        assert pygame.image.tobytes(preloader.take(rel), "RGBA") == pygame.image.tobytes(
            direct, "RGBA"
        )
    preloader.close()


def test_the_browser_build_defaults_to_no_threads(monkeypatch):
    monkeypatch.setattr(sys, "platform", "emscripten")
    assert ImagePreloader(pygame, lambda rel: rel).threads is False
    monkeypatch.setattr(sys, "platform", "darwin")
    assert ImagePreloader(pygame, lambda rel: rel).threads is True


def test_a_bundled_cjk_font_wins_over_system_fonts(monkeypatch, tmp_path):
    from asteria.platform.pygame_battle_ui import cjk_font_path

    font = REPO / "asset_library" / "fonts" / "noto_sans_tc" / "NotoSansTC-Regular.otf"
    monkeypatch.setenv("ASTERIA_CJK_FONT", str(font))
    assert cjk_font_path(pygame) == str(font)
    monkeypatch.setenv("ASTERIA_CJK_FONT", str(tmp_path / "missing.otf"))
    assert cjk_font_path(pygame) != str(tmp_path / "missing.otf")  # falls back to the system
    pygame.font.init()
    face = pygame.font.Font(str(font), 20)
    drawn = face.render("勇者", True, (255, 255, 255))
    assert pygame.mask.from_surface(drawn).count() > 40  # ink, not boxes


def test_step_is_the_frame_run_uses(monkeypatch):
    from test_playable_battle_loop import ROOT, _boss_runtime

    for key, value in HEADLESS.items():
        monkeypatch.setenv(key, value)
    runtime = _boss_runtime(ROOT)
    runtime.open()
    try:
        runtime._ui_mode = "field"
        frames = []
        original = runtime._frame
        runtime._frame = lambda events, dt: (
            frames.append((len(events), dt)) or original(events, dt)
        )
        runtime.step(1 / 60)
        runtime.step(1 / 30, events=[])
        assert [dt for _, dt in frames] == [1 / 60, 1 / 30]
        runtime.step = lambda dt: frames.append(("run", dt)) or setattr(runtime, "running", False)
        runtime.run(max_frames=1)
    finally:
        if pygame.get_init():
            runtime.close()
    assert frames[-1][0] == "run"
