"""Menu screens that fit the window (D87).

The engine's menu screens (equipment, enhance, crafting, shops, the quest board, the gacha, the
status pages...) are laid out for a window of at least 1280 x 720. In a smaller window their
right and bottom parts would fall outside it. While such a screen draws, the runtime gives it
a canvas of the screen's size with the window's shape (960 x 540 draws on 1280 x 720, 960 x 640
on 1280 x 853), then shrinks the picture into the window; the places the mouse can pick are
shrunk with it, so a click lands on what it shows. The map or battle behind a menu is drawn
in the window itself, never shrunk.

``render.menu_size`` in the game folder's settings (Game Folder Settings ▸ Rendering) is the
size the menus are made for: ``[1280, 720]`` when not set; ``[0, 0]`` turns the fitting off
(a game whose own layouts are made for its window).
"""

from __future__ import annotations

from contextlib import contextmanager

DESIGN_SIZE = (1280, 720)
# the screens drawn at the menu size; the skill tree reads the mouse itself (drag, zoom) and
# the overlay menus already fit any window
FIT_MODES = frozenset(
    {
        "equipment",
        "enhance",
        "service",
        "crafting",
        "shop",
        "status",
        "quests",
        "achievements",
        "bestiary",
        "bag",
        "extra",
        "pets",
    }
)


def fitted_size(window, design):
    """The canvas a screen made for ``design`` draws on in ``window``: the window's shape, at
    least the design's size; ``window`` itself when it is already big enough."""
    ww, wh = window
    dw, dh = design
    if dw <= 0 or dh <= 0 or ww <= 0 or wh <= 0:
        return (ww, wh)
    scale = max(dw / ww, dh / wh, 1.0)
    return (round(ww * scale), round(wh * scale))


class MenuFitMixin:
    def menu_design_size(self):
        """``render.menu_size`` of the game folder's settings, else 1280 x 720."""
        value = self.manifest.get("render", {}).get("menu_size")
        try:
            width, height = (int(v) for v in value)
        except (TypeError, ValueError):
            return DESIGN_SIZE
        return (width, height)

    @contextmanager
    def menu_fit(self, mode=None):
        """Draw a menu screen inside ``with``: on a canvas of its size when the window is
        smaller, shrunk into the window afterwards (see the module)."""
        if getattr(self, "_fitting", None) is not None or (
            mode is not None and mode not in FIT_MODES
        ):
            yield
            return
        window = (self.width, self.height)
        size = fitted_size(window, self.menu_design_size())
        if size == window or self.screen is None:
            yield
            return
        pg = self.pg
        canvas = self.__dict__.get("_fit_canvas")
        if canvas is None or canvas.get_size() != size:
            canvas = self._fit_canvas = pg.Surface(size, pg.SRCALPHA)
        canvas.fill((0, 0, 0, 0))
        real = self.screen
        pointer = self.__dict__.get("pointer")
        first = len(pointer.drawn) if pointer is not None else 0
        self._fitting = (real, window)
        self.screen, (self.width, self.height) = canvas, size
        try:
            yield
        finally:
            self.screen, (self.width, self.height) = real, window
            self._fitting = None
        real.blit(pg.transform.smoothscale(canvas, window), (0, 0))
        if pointer is not None:
            sx, sy = window[0] / size[0], window[1] / size[1]
            for spot in pointer.drawn[first:]:
                x, y, w, h = spot.rect
                spot.rect = (
                    int(round(x * sx)),
                    int(round(y * sy)),
                    max(1, int(round(w * sx))),
                    max(1, int(round(h * sy))),
                )

    @contextmanager
    def window_drawing(self):
        """Inside a fitted menu: draw on the window itself for a while (the map or battle
        behind the menu keeps its own size)."""
        fitting = getattr(self, "_fitting", None)
        if fitting is None:
            yield
            return
        canvas, size = self.screen, (self.width, self.height)
        self.screen, (self.width, self.height) = fitting
        self._fitting = None
        try:
            yield
        finally:
            self._fitting = fitting
            self.screen, (self.width, self.height) = canvas, size


__all__ = ["DESIGN_SIZE", "FIT_MODES", "MenuFitMixin", "fitted_size"]
