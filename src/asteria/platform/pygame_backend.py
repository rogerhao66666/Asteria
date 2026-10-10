from asteria.assets import TextureResource

from .backend import RuntimeBackend, TextureBackend


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
            if event.type == self.pg.QUIT or event.type == self.pg.KEYDOWN and event.key == self.pg.K_ESCAPE:
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

    def end_frame(self):
        if self.screen is not None:
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
