"""Tests for the moderngl runtime backend (Phase 1 of the plan at
~/.claude/plans/proud-fluttering-map.md).

These exercise the real batching/shader/texture code in
`ModernglRuntimeBackend` against a `moderngl.create_standalone_context()`
rather than `.open()`'s real pygame window, so the suite never flashes a
window on screen. `.open()`'s window/event-pump plumbing is deliberately
*not* covered here (it mirrors `PygameRuntimeBackend`'s already-tested
window/event conventions almost verbatim) — this file is about the rendering
being correct.

Readback note: `Framebuffer.read()` returns pixel rows bottom-of-image-first
(OpenGL's native convention), the opposite of "row 0 is the top" that
`screen_y`/`source_y` elsewhere in the engine use. `_read_rgba` below takes a
normal top-based `y` (0 = visual top, matching every draw command's
convention) and does the bottom-first conversion internally, so test bodies
never have to think about it. This was confirmed empirically while building
the backend — see `moderngl_backend.py:load_texture`'s comment for the
matching texture-orientation finding (no flip needed on load).
"""

import pytest

moderngl = pytest.importorskip("moderngl")
Image = pytest.importorskip("PIL.Image")

from asteria.assets import TextureResource
from asteria.platform.backend import RuntimeBackend, TextureBackend
from asteria.platform.moderngl_backend import ModernglRuntimeBackend
from asteria.platform.moderngl_shaders import SPRITE_FRAGMENT_SHADER, SPRITE_VERTEX_SHADER


def _standalone_backend(size=(16, 16)):
    """A backend wired to an offscreen context+FBO instead of a real window.

    Skips (rather than fails) when this machine has no usable GL driver, the
    same graceful-degradation the plan calls for.
    """
    try:
        ctx = moderngl.create_standalone_context()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no GL context available: {exc}")
    backend = ModernglRuntimeBackend()
    backend.ctx = ctx
    ctx.enable(moderngl.BLEND)
    ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
    backend._program = ctx.program(
        vertex_shader=SPRITE_VERTEX_SHADER, fragment_shader=SPRITE_FRAGMENT_SHADER
    )
    backend._program["u_texture"] = 0
    backend._white_texture = ctx.texture((1, 1), 4, bytes((255, 255, 255, 255)))
    backend._white_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
    backend.screen_size = size
    backend._reset_batch()
    fbo = ctx.simple_framebuffer(size)
    fbo.use()
    return backend, fbo


def _solid_texture(backend, rgba, size=(1, 1)):
    image = Image.new("RGBA", size, rgba)
    texture = backend.ctx.texture(image.size, 4, image.tobytes())
    texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
    return TextureResource("tex", size[0], size[1], texture)


def _make_draw(source, screen_x, screen_y, width, height, opacity=1.0, flip_x=False):
    return type(
        "Draw",
        (),
        dict(
            source=source,
            screen_x=screen_x,
            screen_y=screen_y,
            width=width,
            height=height,
            opacity=opacity,
            flip_x=flip_x,
        ),
    )()


def _read_rgba(fbo, x, y, screen_height):
    """Read the pixel at top-based screen coordinate (x, y)."""
    data = fbo.read(components=4)
    buffer_row = screen_height - 1 - int(y)
    width = fbo.size[0]
    i = (buffer_row * width + int(x)) * 4
    return tuple(data[i : i + 4])


def test_backend_satisfies_the_runtime_and_texture_contracts():
    assert issubclass(ModernglRuntimeBackend, (RuntimeBackend, TextureBackend))


def test_draw_texture_places_a_solid_color_at_the_requested_screen_rect():
    backend, fbo = _standalone_backend((16, 16))
    resource = _solid_texture(backend, (255, 0, 0, 255))

    backend.ctx.clear(0, 0, 0, 1)
    backend.draw_texture(resource, _make_draw((0, 0, 1, 1), 4, 4, 4, 4))
    backend._flush_batch()

    assert _read_rgba(fbo, 6, 6, 16) == (255, 0, 0, 255)  # inside the quad
    assert _read_rgba(fbo, 12, 12, 16) == (0, 0, 0, 255)  # outside the quad


def test_flip_x_mirrors_the_source_rect():
    backend, fbo = _standalone_backend((8, 4))
    image = Image.new("RGBA", (2, 1))
    image.putpixel((0, 0), (255, 0, 0, 255))  # left = red
    image.putpixel((1, 0), (0, 255, 0, 255))  # right = green
    texture = backend.ctx.texture(image.size, 4, image.tobytes())
    texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
    resource = TextureResource("tex", 2, 1, texture)

    backend.ctx.clear(0, 0, 0, 1)
    backend.draw_texture(resource, _make_draw((0, 0, 2, 1), 0, 0, 8, 4, flip_x=True))
    backend._flush_batch()

    left = _read_rgba(fbo, 1, 2, 4)
    right = _read_rgba(fbo, 6, 2, 4)
    assert left == (0, 255, 0, 255)  # green now on the left: mirrored
    assert right == (255, 0, 0, 255)


def test_opacity_blends_toward_the_cleared_background():
    backend, fbo = _standalone_backend((4, 4))
    resource = _solid_texture(backend, (255, 0, 0, 255))

    backend.ctx.clear(0.0, 0.0, 1.0, 1.0)  # solid blue background
    backend.draw_texture(resource, _make_draw((0, 0, 1, 1), 0, 0, 4, 4, opacity=0.5))
    backend._flush_batch()

    r, g, b, a = _read_rgba(fbo, 2, 2, 4)
    # 50% red over 100% blue, standard alpha blend: ~half red, ~half blue.
    assert 100 < r < 155
    assert b < 155


def test_texture_change_flushes_and_preserves_draw_order():
    backend, fbo = _standalone_backend((8, 4))
    red = _solid_texture(backend, (255, 0, 0, 255))
    green = _solid_texture(backend, (0, 255, 0, 255))

    backend.ctx.clear(0, 0, 0, 1)
    backend.draw_texture(red, _make_draw((0, 0, 1, 1), 0, 0, 4, 4))
    backend.draw_texture(green, _make_draw((0, 0, 1, 1), 4, 0, 4, 4))
    backend._flush_batch()

    assert _read_rgba(fbo, 1, 2, 4) == (255, 0, 0, 255)
    assert _read_rgba(fbo, 5, 2, 4) == (0, 255, 0, 255)


def test_load_texture_round_trips_pixel_orientation(tmp_path):
    backend, fbo = _standalone_backend((4, 4))
    image = Image.new("RGBA", (2, 2))
    image.putpixel((0, 0), (255, 0, 0, 255))  # source top row
    image.putpixel((1, 0), (255, 0, 0, 255))
    image.putpixel((0, 1), (0, 0, 255, 255))  # source bottom row
    image.putpixel((1, 1), (0, 0, 255, 255))
    path = tmp_path / "probe.png"
    image.save(path)

    resource = backend.load_texture("probe", str(path))
    assert (resource.width, resource.height) == (2, 2)

    backend.ctx.clear(0, 0, 0, 1)
    backend.draw_texture(resource, _make_draw((0, 0, 2, 2), 0, 0, 4, 4))
    backend._flush_batch()

    # Screen-space top (small y, top-based) must show the source's top row.
    assert _read_rgba(fbo, 1, 0, 4) == (255, 0, 0, 255)
    assert _read_rgba(fbo, 1, 3, 4) == (0, 0, 255, 255)


def test_draw_grid_and_draw_marker_do_not_raise():
    backend, fbo = _standalone_backend((32, 32))
    backend.ctx.clear(0, 0, 0, 1)
    backend.draw_grid(spacing=8)
    backend.draw_marker(16, 16, radius=4, selected=True)
    backend._flush_batch()


# --- CB9: parity with the pygame backend --------------------------------------


def test_moderngl_and_pygame_render_the_same_draw_commands():
    """Same texture + TextureDraw commands (scaling, flip, opacity) -> same pixels."""
    pygame = pytest.importorskip("pygame")
    from asteria.platform.pygame_backend import PygameTextureBackend

    size = (32, 16)
    gl_backend, fbo = _standalone_backend(size)
    image = Image.new("RGBA", (2, 1))
    image.putpixel((0, 0), (255, 0, 0, 255))
    image.putpixel((1, 0), (0, 0, 255, 255))
    gl_texture = gl_backend.ctx.texture(image.size, 4, image.tobytes())
    gl_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
    draws = (
        _make_draw((0, 0, 2, 1), 0, 0, 8, 8),  # 4x scale
        _make_draw((0, 0, 2, 1), 16, 0, 8, 8, flip_x=True),  # mirrored
        _make_draw((0, 0, 1, 1), 0, 8, 8, 8, opacity=0.5),  # half transparent red
    )
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    for draw in draws:
        gl_backend.draw_texture(TextureResource("tex", 2, 1, gl_texture), draw)
    gl_backend._flush_batch()

    pygame.init()
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill((0, 0, 0, 255))
    py_backend = PygameTextureBackend(surface)
    py_texture = pygame.image.frombytes(image.tobytes(), image.size, "RGBA")
    for draw in draws:
        py_backend.draw_texture(TextureResource("tex", 2, 1, py_texture), draw)

    for x, y in ((1, 1), (6, 6), (17, 2), (22, 5), (3, 11)):
        gl = _read_rgba(fbo, x, y, size[1])[:3]
        py = tuple(surface.get_at((x, y)))[:3]
        assert all(abs(a - b) <= 2 for a, b in zip(gl, py)), (x, y, gl, py)


def test_preview_selects_backend_by_name():
    from asteria.platform.pygame_backend import PygameRuntimeBackend
    from asteria.runtime.preview import build_backend

    assert isinstance(build_backend("pygame"), PygameRuntimeBackend)
    assert isinstance(build_backend("moderngl"), ModernglRuntimeBackend)
    with pytest.raises(ValueError):
        build_backend("vulkan")
