from asteria.assets import TextureResource

from .backend import RuntimeBackend, TextureBackend

# System fonts that also cover CJK text (imported projects are often Japanese); the default font is
# the fallback.
DIALOGUE_FONTS = (
    "hiraginosans",
    "hiraginosansgb",
    "arialunicode",
    "applesdgothicneo",
    "notosanscjkjp",
    "notosanscjk",
    "yugothic",
    "msgothic",
)


def dialogue_font(pg, size):
    pg.font.init()
    for name in DIALOGUE_FONTS:
        path = pg.font.match_font(name)
        if path:
            return pg.font.Font(path, size)
    return pg.font.Font(None, size)


class PygameRuntimeBackend(RuntimeBackend, TextureBackend):
    """Low-level runtime window/input/primitive preview adapter.

    Engine/editor/project layers never receive pygame objects.
    """

    def __init__(self, input_map=None):
        try:
            import pygame
        except ImportError as exc:
            raise RuntimeError("Install pygame-ce with: pip install 'asteria[pygame]'") from exc
        from asteria.runtime.input_map import InputActionMap

        self.pg = pygame
        self.screen = None
        self.clock = None
        self._close = False
        self.input_map = input_map or InputActionMap.default()
        self.input_source = None

    def open(self, title, width, height):
        self.pg.init()
        self.screen = self.pg.display.set_mode((int(width), int(height)))
        self.pg.display.set_caption(str(title))
        self.clock = self.pg.time.Clock()
        self._close = False
        from .pygame_input import PygameInputSource

        self.input_source = PygameInputSource(self.pg)

    def tick(self, target_fps=60):
        if self.clock is None:
            raise RuntimeError("Backend is not open")
        ms = self.clock.tick_busy_loop(int(target_fps))
        return min(ms / 1000.0, 0.05)

    def begin_frame(self):
        if self.screen is None:
            raise RuntimeError("Backend is not open")
        for event in self.pg.event.get():
            if self.input_source is not None:
                self.input_source.handle_event(event)
            if (
                event.type == self.pg.QUIT
                or event.type == self.pg.KEYDOWN
                and event.key == self.pg.K_ESCAPE
            ):
                self._close = True
        self.screen.fill((24, 26, 30))

    def draw_grid(self, spacing=32, offset_x=0, offset_y=0):
        if self.screen is None:
            return
        w, h = self.screen.get_size()
        color = (43, 47, 54)
        spacing = max(8, int(spacing))
        x = int(offset_x) % spacing
        while x < w:
            self.pg.draw.line(self.screen, color, (x, 0), (x, h), 1)
            x += spacing
        y = int(offset_y) % spacing
        while y < h:
            self.pg.draw.line(self.screen, color, (0, y), (w, y), 1)
            y += spacing

    def draw_marker(self, x, y, radius=8, selected=False):
        if self.screen is None:
            return
        color = (235, 183, 76) if selected else (137, 151, 180)
        self.pg.draw.circle(self.screen, color, (int(x), int(y)), max(3, int(radius)))

    def poll_actions(self):
        """Current action values from the input map (keyboard and gamepads)."""
        if self.input_source is None:
            return {}
        return dict(self.input_map.evaluate(self.input_source.raw_state()).actions)

    def load_texture(self, asset_id, source_path):
        surface = self.pg.image.load(source_path).convert_alpha()
        return TextureResource(asset_id, surface.get_width(), surface.get_height(), surface)

    def draw_texture(self, texture_resource, draw_command):
        if self.screen is None:
            raise RuntimeError("pygame screen not configured")
        src = self.pg.Rect(*draw_command.source)
        image = texture_resource.backend_handle.subsurface(src)
        target_size = (
            max(1, int(draw_command.width)),
            max(1, int(draw_command.height)),
        )
        if image.get_size() != target_size:
            image = self.pg.transform.scale(image, target_size)
        if draw_command.flip_x:
            image = self.pg.transform.flip(image, True, False)
        if draw_command.opacity < 1.0:
            image = image.copy()
            image.set_alpha(max(0, min(255, int(draw_command.opacity * 255))))
        self.screen.blit(image, (round(draw_command.screen_x), round(draw_command.screen_y)))

    def set_environment(self, environment, time=0.0):
        """Apply the scene environment (pygame fallback: approximate lights, fog, water) at end of
        frame."""
        self.environment, self.environment_time = environment, float(time)

    def draw_rects(self, rects):
        """Flat rectangles ``(x, y, w, h, (r, g, b, a))`` in screen pixels (weather particles)."""
        layer = getattr(self, "_rect_layer", None)
        if layer is None or layer.get_size() != self.screen.get_size():
            layer = self._rect_layer = self.pg.Surface(self.screen.get_size(), self.pg.SRCALPHA)
        layer.fill((0, 0, 0, 0))
        for x, y, w, h, color in rects:
            layer.fill(color, (int(x), int(y), max(1, int(w)), max(1, int(h))))
        self.screen.blit(layer, (0, 0))

    def draw_text_box(self, text, _now=False):
        """A dialogue box along the bottom of the window (event DIALOGUE lines)."""
        env = getattr(self, "environment", None)
        if env is not None and env.active and not _now:
            self._pending_text = text  # UI goes on top of the environment effects
            return
        from .pygame_battle_ui import font_for_text, renderable_text

        width, height = self.screen.get_size()
        box = self.pg.Rect(16, height - 132, width - 32, 116)
        panel = self.pg.Surface(box.size, self.pg.SRCALPHA)
        panel.fill((13, 17, 28, 225))
        self.screen.blit(panel, box.topleft)
        self.pg.draw.rect(self.screen, (124, 145, 190), box, 2, border_radius=6)
        if not hasattr(self, "_font"):
            self._font, self._glyphs, self._cjk_fonts = dialogue_font(self.pg, 26), {}, {}
        for row, line in enumerate(str(text).split("\n")[:4]):
            font = font_for_text(self.pg, self._font, line, self._cjk_fonts, 26)
            image = font.render(
                renderable_text(self.pg, font, line, self._glyphs), True, (240, 242, 248)
            )
            self.screen.blit(image, (box.x + 18, box.y + 12 + row * self._font.get_linesize()))

    def end_frame(self):
        if self.screen is None:
            return
        env = getattr(self, "environment", None)
        if env is not None and env.active:
            from asteria.runtime.environment_fallback import PygameEnvironmentRenderer, unsupported

            if getattr(self, "_l0", None) is None:
                self._l0 = PygameEnvironmentRenderer(self.pg)
            self._l0.time = self.environment_time
            self._l0.apply(self.screen, env)
            self.environment_unsupported = unsupported(env)
            text, self._pending_text = getattr(self, "_pending_text", None), None
            if text is not None:
                self.draw_text_box(text, _now=True)
        self.pg.display.flip()

    def should_close(self):
        return self._close

    def close(self):
        self._close = True
        if self.pg.get_init():
            self.pg.quit()
        self.screen = None
        self.clock = None


class PygameTextureBackend(TextureBackend):
    def __init__(self, screen=None):
        try:
            import pygame
        except ImportError as exc:
            raise RuntimeError("Install pygame-ce with: pip install 'asteria[pygame]'") from exc
        self.pg = pygame
        self.screen = screen

    def load_texture(self, asset_id, source_path):
        surface = self.pg.image.load(source_path).convert_alpha()
        return TextureResource(asset_id, surface.get_width(), surface.get_height(), surface)

    def draw_texture(self, texture_resource, draw_command):
        if self.screen is None:
            raise RuntimeError("pygame screen not configured")
        src = self.pg.Rect(*draw_command.source)
        image = texture_resource.backend_handle.subsurface(src)
        target_size = (
            max(1, int(draw_command.width)),
            max(1, int(draw_command.height)),
        )
        if image.get_size() != target_size:
            image = self.pg.transform.scale(image, target_size)
        if draw_command.flip_x:
            image = self.pg.transform.flip(image, True, False)
        if draw_command.opacity < 1.0:
            image = image.copy()
            image.set_alpha(max(0, min(255, int(draw_command.opacity * 255))))
        self.screen.blit(image, (round(draw_command.screen_x), round(draw_command.screen_y)))
