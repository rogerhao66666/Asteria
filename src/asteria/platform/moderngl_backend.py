"""moderngl (OpenGL) rendering backend — see /Users/roger/.claude/plans/proud-fluttering-map.md.

Window/context creation is delegated to pygame-ce (Architecture Decision 5 in
the plan): moderngl itself never creates a window, and reusing pygame-ce here
avoids a second windowing/input library alongside `PygameRuntimeBackend` — the
event pump, `poll_actions`, and close-detection conventions all carry over
unchanged, only the drawing internals differ.

All sprite/quad drawing — plain `draw_texture` calls and (from a later phase)
lit `draw_material_sprite` calls — funnels through one `_enqueue_quad`/
`_flush_batch` pair (Decision 2): consecutive draws sharing a texture batch
into a single draw call, and a texture change flushes the batch, which
preserves the caller-given draw order (already sorted upstream by
`build_frame_plan`/`tile_draw`/`reference_runtime`) rather than reordering for
batching — reordering across a texture boundary could change how translucent
sprites blend.
"""
from array import array

from asteria.assets import TextureResource

from .backend import RuntimeBackend, TextureBackend
from .moderngl_shaders import SPRITE_FRAGMENT_SHADER, SPRITE_VERTEX_SHADER

_VERTEX_LAYOUT = "2f 2f 4f"
_VERTEX_ATTRS = ("in_position", "in_uv", "in_tint")
_FLOATS_PER_VERTEX = 8  # x, y, u, v, r, g, b, a

# Half-texel UV inset so adjacent frames packed into the same sprite-sheet
# texture don't bleed into each other at magnified/minified edges.
_TEXEL_INSET = 0.5

_CLEAR_COLOR = (24 / 255, 26 / 255, 30 / 255, 1.0)
_GRID_COLOR = (43 / 255, 47 / 255, 54 / 255)
_MARKER_COLOR = (137 / 255, 151 / 255, 180 / 255)
_MARKER_COLOR_SELECTED = (235 / 255, 183 / 255, 76 / 255)


class ModernglRuntimeBackend(RuntimeBackend, TextureBackend):
    """Sprite-batch runtime backend over a moderngl GL context."""

    def __init__(self):
        try:
            import moderngl
        except ImportError as exc:
            raise RuntimeError(
                "Install moderngl with: pip install 'asteria[moderngl]'"
            ) from exc
        try:
            import pygame
        except ImportError as exc:
            raise RuntimeError(
                "Install pygame-ce with: pip install 'asteria[pygame]'"
            ) from exc
        self._gl = moderngl
        self.pg = pygame
        self.ctx = None
        self.screen_size = (0, 0)
        self._program = None
        self._white_texture = None
        self._batch_texture = None
        self._batch_vertices = []
        self._batch_indices = []
        self.clock = None
        self._close = False

    # ---- RuntimeBackend ----

    def open(self, title, width, height):
        self.pg.init()
        self.pg.display.gl_set_attribute(self.pg.GL_CONTEXT_MAJOR_VERSION, 3)
        self.pg.display.gl_set_attribute(self.pg.GL_CONTEXT_MINOR_VERSION, 3)
        self.pg.display.gl_set_attribute(
            self.pg.GL_CONTEXT_PROFILE_MASK, self.pg.GL_CONTEXT_PROFILE_CORE
        )
        self.pg.display.set_mode(
            (int(width), int(height)),
            self.pg.OPENGL | self.pg.DOUBLEBUF | self.pg.RESIZABLE,
        )
        self.pg.display.set_caption(str(title))
        self.ctx = self._gl.create_context()
        self.ctx.enable(self._gl.BLEND)
        self.ctx.blend_func = self._gl.SRC_ALPHA, self._gl.ONE_MINUS_SRC_ALPHA
        self._program = self.ctx.program(
            vertex_shader=SPRITE_VERTEX_SHADER, fragment_shader=SPRITE_FRAGMENT_SHADER
        )
        self._program["u_texture"] = 0
        self._white_texture = self.ctx.texture((1, 1), 4, bytes((255, 255, 255, 255)))
        self._white_texture.filter = (self._gl.NEAREST, self._gl.NEAREST)
        self.screen_size = (int(width), int(height))
        self.clock = self.pg.time.Clock()
        self._close = False
        self._reset_batch()

    def tick(self, target_fps=60):
        if self.clock is None:
            raise RuntimeError("Backend is not open")
        ms = self.clock.tick_busy_loop(int(target_fps))
        return min(ms / 1000.0, 0.05)

    def begin_frame(self):
        if self.ctx is None:
            raise RuntimeError("Backend is not open")
        for event in self.pg.event.get():
            if event.type == self.pg.QUIT or (
                event.type == self.pg.KEYDOWN and event.key == self.pg.K_ESCAPE
            ):
                self._close = True
            elif event.type == self.pg.VIDEORESIZE:
                self.screen_size = (event.w, event.h)
        self.ctx.viewport = (0, 0, *self.screen_size)
        self.ctx.clear(*_CLEAR_COLOR)
        self._reset_batch()

    def draw_grid(self, spacing=32, offset_x=0, offset_y=0):
        if self.ctx is None:
            return
        width, height = self.screen_size
        spacing = max(8, int(spacing))
        x = int(offset_x) % spacing
        while x < width:
            self._enqueue_solid(x, 0, 1, height, _GRID_COLOR, 1.0)
            x += spacing
        y = int(offset_y) % spacing
        while y < height:
            self._enqueue_solid(0, y, width, 1, _GRID_COLOR, 1.0)
            y += spacing

    def draw_marker(self, x, y, radius=8, selected=False):
        if self.ctx is None:
            return
        color = _MARKER_COLOR_SELECTED if selected else _MARKER_COLOR
        r = max(3, int(radius))
        self._enqueue_solid(x - r, y - r, r * 2, r * 2, color, 1.0)

    def poll_actions(self):
        keys = self.pg.key.get_pressed()
        return {
            "move_left": 1.0 if keys[self.pg.K_LEFT] or keys[self.pg.K_a] else 0.0,
            "move_right": 1.0 if keys[self.pg.K_RIGHT] or keys[self.pg.K_d] else 0.0,
            "move_up": 1.0 if keys[self.pg.K_UP] or keys[self.pg.K_w] else 0.0,
            "move_down": 1.0 if keys[self.pg.K_DOWN] or keys[self.pg.K_s] else 0.0,
        }

    def end_frame(self):
        if self.ctx is None:
            return
        self._flush_batch()
        self.pg.display.flip()

    def should_close(self):
        return self._close

    def close(self):
        self._close = True
        self._program = None
        self._white_texture = None
        self.ctx = None
        if self.pg.get_init():
            self.pg.quit()
        self.clock = None

    # ---- TextureBackend ----

    def load_texture(self, asset_id, source_path):
        from PIL import Image

        image = Image.open(source_path).convert("RGBA")
        # No vertical flip needed: GL samples texture v=0 from the *first*
        # uploaded row, which for a PIL image (decoded top row first) is
        # already the image's top row — matching `v = source_y / tex_height`
        # where source_y is measured from the top, the same convention
        # SpriteFrame/TextureDraw already use. (`fbo.read()`/`ctx.screen.read()`
        # return bytes bottom-row-first, which is a separate, read-side-only
        # convention — don't let it suggest a texture-upload flip is needed;
        # confirmed empirically with `tests/test_moderngl_backend.py`.)
        texture = self.ctx.texture(image.size, 4, image.tobytes())
        texture.filter = (self._gl.NEAREST, self._gl.NEAREST)
        texture.repeat_x = False
        texture.repeat_y = False
        return TextureResource(asset_id, image.width, image.height, texture)

    def draw_texture(self, texture_resource, draw_command):
        if self.ctx is None:
            raise RuntimeError("Backend is not open")
        self._enqueue_quad(
            texture_resource.backend_handle,
            texture_resource.width,
            texture_resource.height,
            draw_command.source,
            draw_command.screen_x,
            draw_command.screen_y,
            draw_command.width,
            draw_command.height,
            draw_command.opacity,
            draw_command.flip_x,
        )

    # ---- shared quad batching ----

    def _reset_batch(self):
        self._batch_texture = None
        self._batch_vertices = []
        self._batch_indices = []

    def _enqueue_solid(self, x, y, width, height, color, opacity):
        self._enqueue_quad(
            self._white_texture, 1, 1, (0, 0, 1, 1), x, y, width, height,
            opacity, False, color,
        )

    def _enqueue_quad(
        self, texture, tex_width, tex_height, source, screen_x, screen_y,
        width, height, opacity, flip_x, color=(1.0, 1.0, 1.0),
    ):
        if texture is not self._batch_texture:
            self._flush_batch()
            self._batch_texture = texture
        sx, sy, sw, sh = source
        u0 = (sx + _TEXEL_INSET) / tex_width
        v0 = (sy + _TEXEL_INSET) / tex_height
        u1 = (sx + sw - _TEXEL_INSET) / tex_width
        v1 = (sy + sh - _TEXEL_INSET) / tex_height
        if flip_x:
            u0, u1 = u1, u0
        x0, y0 = float(screen_x), float(screen_y)
        x1, y1 = x0 + float(width), y0 + float(height)
        r, g, b = color
        a = max(0.0, min(1.0, float(opacity)))
        base = len(self._batch_vertices) // _FLOATS_PER_VERTEX
        self._batch_vertices.extend((
            x0, y0, u0, v0, r, g, b, a,
            x1, y0, u1, v0, r, g, b, a,
            x1, y1, u1, v1, r, g, b, a,
            x0, y1, u0, v1, r, g, b, a,
        ))
        self._batch_indices.extend((base, base + 1, base + 2, base, base + 2, base + 3))

    def _flush_batch(self):
        if self._batch_texture is None or not self._batch_indices:
            self._reset_batch()
            return
        # A fresh buffer per flush is the simplest correct implementation for
        # this phase; reusing a persistent dynamic buffer is a Phase 2+
        # performance follow-up once correctness/parity is proven out.
        vbo = self.ctx.buffer(array("f", self._batch_vertices).tobytes())
        ibo = self.ctx.buffer(array("I", self._batch_indices).tobytes())
        vao = self.ctx.vertex_array(
            self._program, [(vbo, _VERTEX_LAYOUT, *_VERTEX_ATTRS)], ibo
        )
        self._program["u_screen_size"] = tuple(float(v) for v in self.screen_size)
        self._batch_texture.use(0)
        vao.render()
        vao.release()
        vbo.release()
        ibo.release()
        self._reset_batch()
