"""GPU presentation of the playable game (ENG-12, proposal R1).

The playable runtime keeps composing its frame on a pygame Surface (all
existing drawing code is unchanged). With the ModernGL backend that Surface is
an offscreen 32-bit surface; ``GpuPresenter`` uploads it to one texture per
frame and draws it to the window through the post-process chain (R3: bloom,
colour grading, screen shaders, lighting composite). With an empty chain the
window shows exactly the Surface's pixels (tested pixel for pixel).

Upload avoids a Python-side copy when the surface is the usual 32-bit
X/A-R-G-B layout: the raw buffer goes straight to the texture and a texture
swizzle reorders the channels on the GPU.
"""

from __future__ import annotations

import time

QUAD_VERTEX = """
#version 330
in vec2 in_pos;
in vec2 in_uv;
out vec2 v_uv;
void main() {
    gl_Position = vec4(in_pos, 0.0, 1.0);
    v_uv = in_uv;
}
"""

COPY_FRAGMENT = """
#version 330
uniform sampler2D u_texture;
in vec2 v_uv;
out vec4 f_color;
void main() {
    f_color = vec4(texture(u_texture, v_uv).rgb, 1.0);
}
"""


class GpuPresenterError(RuntimeError):
    pass


def _swizzle_for(surface):
    """Texture swizzle that turns the surface's raw 32-bit bytes into RGBA, or None if unsupported."""
    if surface.get_bitsize() != 32 or surface.get_pitch() != surface.get_width() * 4:
        return None
    shifts = surface.get_shifts()[:3]
    # byte index of R, G, B in little-endian memory = shift // 8
    order = {shift // 8: channel for shift, channel in zip(shifts, "RGB", strict=True)}
    if sorted(order) not in ([0, 1, 2], [1, 2, 3]):
        return None
    alpha_byte = ({0, 1, 2, 3} - set(order)).pop()
    order[alpha_byte] = "A"
    by_channel = {channel: index for index, channel in order.items()}
    letters = "RGBA"
    return "".join(letters[by_channel[c]] for c in "RGB") + "1"


class GpuPresenter:
    def __init__(self, ctx, size, *, target=None):
        self.ctx = ctx
        self.size = (int(size[0]), int(size[1]))
        self.target = target  # framebuffer to draw into; None = the window
        import moderngl

        self.texture = ctx.texture(self.size, 4)
        self.texture.filter = (moderngl.NEAREST, moderngl.NEAREST)  # pixel art stays sharp
        self._swizzle = None
        from array import array

        # full-screen triangle strip; the surface's first row is the top of the window
        quad = array("f", [-1, 1, 0, 0, 1, 1, 1, 0, -1, -1, 0, 1, 1, -1, 1, 1])
        self._vbo = ctx.buffer(quad.tobytes())
        self.copy_program = ctx.program(vertex_shader=QUAD_VERTEX, fragment_shader=COPY_FRAGMENT)
        self.copy_program["u_texture"] = 0
        self._copy_vao = ctx.vertex_array(self.copy_program, [(self._vbo, "2f 2f", "in_pos", "in_uv")])
        self.post = None  # set by the post-process stack (R3)
        self.uploads = 0
        self.last_upload_ms = 0.0
        self.last_draw_calls = 0
        self._gpu_query = None
        try:
            self._gpu_query = ctx.query(time=True)
        except Exception:  # noqa: BLE001 - timer queries are optional
            self._gpu_query = None
        self.last_gpu_ms = None

    # -- window ---------------------------------------------------------------------------------
    @classmethod
    def open_window(cls, pg, size, title, *, vsync=False):
        """Open a GL 3.3 core window (pygame owns it, as in ModernglRuntimeBackend) and a presenter for it.

        ``vsync`` is off by default: frames are paced by the runtime clock (as on the pygame path), and on
        macOS SDL's Cocoa swap with vsync can block indefinitely while the window is not being displayed.
        """
        try:
            import moderngl
        except ImportError as exc:
            raise GpuPresenterError("moderngl is not installed (pip install 'asteria[moderngl]')") from exc
        pg.display.gl_set_attribute(pg.GL_CONTEXT_MAJOR_VERSION, 3)
        pg.display.gl_set_attribute(pg.GL_CONTEXT_MINOR_VERSION, 3)
        pg.display.gl_set_attribute(pg.GL_CONTEXT_PROFILE_MASK, pg.GL_CONTEXT_PROFILE_CORE)
        try:
            pg.display.set_mode(tuple(size), pg.OPENGL | pg.DOUBLEBUF, vsync=1 if vsync else 0)
        except pg.error:
            pg.display.set_mode(tuple(size), pg.OPENGL | pg.DOUBLEBUF)  # vsync unsupported here
        pg.display.set_caption(str(title))
        try:
            ctx = moderngl.create_context()
            return cls(ctx, size)
        except Exception as exc:
            raise GpuPresenterError(f"OpenGL context or shaders failed: {exc}") from exc

    @property
    def renderer(self):
        return self.ctx.info.get("GL_RENDERER", "unknown")

    # -- per frame ------------------------------------------------------------------------------
    def upload(self, surface, pg):
        start = time.perf_counter()
        if surface.get_size() != self.size:
            raise GpuPresenterError(f"surface {surface.get_size()} does not match presenter {self.size}")
        swizzle = _swizzle_for(surface)
        if swizzle is not None:
            if swizzle != self._swizzle:
                self.texture.swizzle = swizzle
                self._swizzle = swizzle
            self.texture.write(surface.get_buffer())
        else:
            if self._swizzle != "RGBA":
                self.texture.swizzle = "RGBA"
                self._swizzle = "RGBA"
            self.texture.write(pg.image.tobytes(surface, "RGBA"))
        self.uploads += 1
        self.last_upload_ms = (time.perf_counter() - start) * 1000.0

    def _draw(self):
        target = self.target or self.ctx.screen
        target.use()
        self.ctx.viewport = (0, 0, *target.size)
        if self.post is not None and self.post.active:
            self.last_draw_calls = self.post.render(self.texture, target)
        else:
            self.texture.use(0)
            self._copy_vao.render(mode=self.ctx.TRIANGLE_STRIP)
            self.last_draw_calls = 1

    def present(self, surface, pg):
        """Upload ``surface`` and draw it (through the post chain) into the window or ``target``."""
        self.upload(surface, pg)
        if self._gpu_query is not None:
            with self._gpu_query:
                self._draw()
            self.last_gpu_ms = self._gpu_query.elapsed / 1e6
        else:
            self._draw()

    def read(self, pg):
        """What is on screen now (after post-processing), as a pygame Surface (for screenshots).

        After a buffer swap the window's back buffer is undefined (often an older frame), so the
        current texture is drawn again before reading.
        """
        if self.target is None:
            self._draw()
        target = self.target or self.ctx.screen
        width, height = target.size
        data = target.read(components=3)
        image = pg.image.frombytes(data, (width, height), "RGB")
        return pg.transform.flip(image, False, True)

    def release(self):
        for resource in (self._copy_vao, self._vbo, self.copy_program, self.texture):
            try:
                resource.release()
            except Exception:  # noqa: BLE001 - best effort at shutdown
                pass
        if self.post is not None:
            self.post.release()
