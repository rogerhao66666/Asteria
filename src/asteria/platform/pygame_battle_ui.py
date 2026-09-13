from __future__ import annotations


class PygameBattleUiBackend:
    """Concrete pygame-ce adapter for Asteria BattleUiFrame commands.

    `resolve_icon(asset_id)` may return either a pygame Surface or an object
    whose `backend_handle` is a Surface. Missing icons fall back to a styled
    placeholder so project data errors do not crash presentation.
    """

    def __init__(self, screen, *, resolve_icon=None, font_name=None):
        try:
            import pygame
        except ImportError as exc:
            raise RuntimeError("Install pygame-ce with: pip install 'asteria[pygame]'") from exc
        self.pg = pygame
        self.screen = screen
        self.resolve_icon = resolve_icon
        self.font_name = font_name
        self._fonts = {}

    @staticmethod
    def _rgb(color):
        return tuple(color[:3])

    def _font(self, size):
        size = max(1, int(size))
        if size not in self._fonts:
            if not self.pg.font.get_init():
                self.pg.font.init()
            self._fonts[size] = self.pg.font.Font(self.font_name, size)
        return self._fonts[size]

    def begin_battle_ui(self, scene_id):
        if self.screen is None:
            raise RuntimeError("pygame battle UI screen is not configured")

    def draw_panel(self, panel, *, fill, border, radius, border_width):
        rect = self.pg.Rect(round(panel.x), round(panel.y), max(1, round(panel.width)), max(1, round(panel.height)))
        self.pg.draw.rect(self.screen, self._rgb(fill), rect, border_radius=int(radius))
        if border_width:
            self.pg.draw.rect(self.screen, self._rgb(border), rect, width=int(border_width), border_radius=int(radius))

    def draw_gauge(self, gauge, *, track, fill):
        mode = str(getattr(gauge, "presentation", "bar"))
        normalized = max(0.0, min(1.0, float(gauge.normalized)))
        rect = self.pg.Rect(round(gauge.x), round(gauge.y), max(1, round(gauge.width)), max(1, round(gauge.height)))

        if mode in {"pips", "segmented_bar", "icon_stack"}:
            segments = int(getattr(gauge, "segments", 0))
            if segments <= 0:
                segments = max(1, int(round(float(gauge.maximum)))) if float(gauge.maximum) <= 24 else 5
            gap = 1
            cell_w = max(1, (rect.width - gap * (segments - 1)) // segments)
            filled_count = int(round(normalized * segments))
            icon = None
            if mode == "icon_stack" and self.resolve_icon is not None and getattr(gauge, "icon_asset_id", None):
                value = self.resolve_icon(gauge.icon_asset_id)
                icon = getattr(value, "backend_handle", value)
            for index in range(segments):
                cell = self.pg.Rect(rect.x + index * (cell_w + gap), rect.y, cell_w, rect.height)
                active = index < filled_count
                if icon is not None and active:
                    image = icon if icon.get_size() == cell.size else self.pg.transform.scale(icon, cell.size)
                    self.screen.blit(image, cell.topleft)
                else:
                    self.pg.draw.rect(self.screen, self._rgb(fill if active else track), cell, border_radius=max(1, cell.height // 3))
            return

        if mode == "ring":
            radius = max(3, round(max(rect.width, rect.height) / 2))
            center = (rect.x + rect.width // 2, rect.y + rect.height // 2)
            self.pg.draw.circle(self.screen, self._rgb(track), center, radius, width=max(1, radius // 4))
            if normalized > 0:
                import math
                ring_rect = self.pg.Rect(center[0]-radius, center[1]-radius, radius*2, radius*2)
                start = -math.pi / 2
                self.pg.draw.arc(
                    self.screen, self._rgb(fill), ring_rect, start,
                    start + 2 * math.pi * normalized, width=max(1, radius // 4)
                )
            return

        # bar/action_gauge/timeline/custom roles have a readable bar fallback.
        self.pg.draw.rect(self.screen, self._rgb(track), rect, border_radius=max(1, rect.height // 2))
        width = max(0, min(rect.width, round(rect.width * normalized)))
        if width:
            filled = self.pg.Rect(rect.x, rect.y, width, rect.height)
            self.pg.draw.rect(self.screen, self._rgb(fill), filled, border_radius=max(1, rect.height // 2))

    def draw_icon(self, icon):
        surface = None
        if self.resolve_icon is not None:
            value = self.resolve_icon(icon.asset_id)
            surface = getattr(value, "backend_handle", value)
        target = self.pg.Rect(round(icon.x), round(icon.y), 8, 8)
        if surface is not None:
            image = surface if surface.get_size() == target.size else self.pg.transform.scale(surface, target.size)
            self.screen.blit(image, target.topleft)
        else:
            self.pg.draw.rect(self.screen, (116, 130, 154), target, border_radius=2)
            self.pg.draw.rect(self.screen, (202, 211, 226), target, width=1, border_radius=2)

    def draw_marker(self, marker, *, color):
        cx, cy = round(marker.x), round(marker.y)
        c = self._rgb(color)
        radius = 7 if marker.primary else 5
        self.pg.draw.polygon(self.screen, c, ((cx, cy-radius), (cx-radius, cy), (cx, cy+radius), (cx+radius, cy)), width=2)

    def draw_text(self, text, *, color, size):
        image = self._font(size).render(str(text.text), True, self._rgb(color))
        x, y = round(text.x), round(text.y)
        if text.align == "center":
            x -= image.get_width() // 2
        elif text.align == "right":
            x -= image.get_width()
        self.screen.blit(image, (x, y))

    def draw_vfx(self, effect):
        # Authored VFX remains a separate visual-effect adapter responsibility.
        pass

    def draw_screen_fx(self, effect):
        payload = dict(getattr(effect, "payload", {}) or {})
        effect_name = str(getattr(effect, "effect", ""))
        if effect_name not in {"flash", "hit_flash"}:
            return
        alpha = max(0, min(255, int(payload.get("alpha", 72))))
        overlay = self.pg.Surface(self.screen.get_size(), self.pg.SRCALPHA)
        overlay.fill((255, 255, 255, alpha))
        self.screen.blit(overlay, (0, 0))

    def end_battle_ui(self):
        pass
