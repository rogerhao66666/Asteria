"""ENG-12 R1: the GPU presenter shows the playable runtime's Surface exactly (identity chain), and
the
playable runtime falls back to pygame when OpenGL is unavailable."""

import pytest

pygame = pytest.importorskip("pygame")
moderngl = pytest.importorskip("moderngl")


@pytest.fixture
def gl():
    try:
        ctx = moderngl.create_standalone_context()
    except Exception as exc:  # noqa: BLE001 - CI without a GL driver
        pytest.skip(f"no OpenGL context: {exc}")
    yield ctx
    ctx.release()


def _pattern(size=(64, 40), *, depth=32):
    surface = pygame.Surface(size, 0, depth)
    surface.fill((12, 34, 56))
    pygame.draw.rect(surface, (255, 0, 0), (0, 0, 8, 8))  # top-left marker
    pygame.draw.rect(surface, (0, 255, 0), (size[0] - 8, size[1] - 8, 8, 8))  # bottom-right marker
    for x in range(size[0]):
        surface.set_at((x, 20), (x * 4 % 256, 255 - x * 4 % 256, 128))
    return surface


@pytest.mark.parametrize("depth", [32, 24])
def test_identity_presentation_is_pixel_exact(gl, depth):
    from asteria.platform.gpu_presenter import GpuPresenter

    surface = _pattern(depth=depth)
    fbo = gl.simple_framebuffer(surface.get_size(), components=4)
    presenter = GpuPresenter(gl, surface.get_size(), target=fbo)
    presenter.present(surface, pygame)
    shown = presenter.read(pygame)
    assert pygame.image.tobytes(shown, "RGB") == pygame.image.tobytes(surface, "RGB")
    assert presenter.last_draw_calls == 1 and presenter.uploads == 1
    presenter.release()


def test_zero_copy_upload_is_used_for_the_runtime_surface_layout(gl):
    from asteria.platform.gpu_presenter import _swizzle_for

    assert _swizzle_for(pygame.Surface((8, 8), 0, 32)) in ("BGR1", "RGB1")
    assert _swizzle_for(pygame.Surface((8, 8), 0, 24)) is None  # falls back to an RGBA copy


def test_playable_runtime_falls_back_to_pygame_when_gl_fails(resource_root, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from test_playable_battle_loop import (
        ROOT,
        _boss_runtime,  # noqa: F401  (fixture helpers)
    )

    from asteria.editor import EditorDocument
    from asteria.platform import gpu_presenter
    from asteria.project import Project
    from asteria.runtime.game_save import GameRuntimeSave
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    def broken(*args, **kwargs):
        raise gpu_presenter.GpuPresenterError("no OpenGL in this environment")

    monkeypatch.setattr(
        gpu_presenter.GpuPresenter, "open_window", classmethod(lambda cls, *a, **k: broken())
    )
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    save = GameRuntimeSave.load_json(ROOT / "saves" / "boss_stress.asteria-save.json", project)
    runtime = PlayableTestRuntime(project, save, ROOT, backend="moderngl")
    runtime.open()
    try:
        assert runtime.gpu is None and "no OpenGL" in runtime.gpu_fallback_reason
        runtime._ui_mode = "field"
        runtime._frame([], 0.016)
        runtime.present()  # pygame path keeps working
        assert runtime.capture().get_size() == (runtime.width, runtime.height)
    finally:
        runtime.close()
