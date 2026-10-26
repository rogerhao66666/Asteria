"""Mouse control for menus, dialogue and battles (D85).

While a screen draws, it marks the places the pointer can pick: a menu row, a battle command,
a choice, a letter, the message window... (``hotspot(rect, pick)``). On the next frame the
mouse events are turned into what the keyboard would have done there:

- moving over a hotspot runs its ``pick`` (the cursor goes to that row);
- a left click on one runs ``pick`` and presses its key (Return: confirm);
- a right click presses Escape (cancel / back; the field opens the menu);
- the wheel presses Up / Down while a screen has hotspots.

Once the player uses the mouse, a screen with hotspots shows the mouse's words in its corner
(``hint.mouse``; a key press hides them again, an empty text never shows them).

The keys are real pygame key events, sent to the input map (``confirm`` / ``cancel`` held
for one frame, then released) and to the screens that read key events, so every screen
answers the mouse the way it answers its keys. A click that hits no hotspot passes on
untouched (a picture or a figure on the map with a click event). The project's input map
turns it off (``InputActionMap.mouse``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Hotspot:
    rect: tuple[int, int, int, int]
    pick: object = None  # called on hover and before the key (None: nothing to point at)
    key: str = "return"  # the key a left click presses ("": none, the pick is the action)

    def contains(self, x, y):
        left, top, width, height = self.rect
        return left <= x < left + width and top <= y < top + height


class PointerLayer:
    """The hotspots drawn this frame and the mouse events of the next one."""

    def __init__(self, pg):
        self.pg = pg
        self.drawn: list[Hotspot] = []  # registered while this frame draws
        self.live: list[Hotspot] = []  # last frame's: what the pointer is over now
        self._release: list[str] = []  # keys pressed last frame, released this frame
        self._later: list[str] = []  # pressed again while being released: the next frame
        self._over = None
        self.used = False  # the player moved or clicked the mouse since the last real key

    def add(self, rect, pick=None, *, key="return"):
        left, top, width, height = (int(round(v)) for v in rect)
        if width > 0 and height > 0:
            self.drawn.append(Hotspot((left, top, width, height), pick, key))

    def at(self, x, y):
        """The topmost hotspot under ``(x, y)`` (drawn last wins), or None."""
        for spot in reversed(self.live):
            if spot.contains(x, y):
                return spot
        return None

    def _key_event(self, kind, name):
        key = self.pg.key.key_code(name)
        return self.pg.event.Event(kind, key=key, mod=0, unicode="", scancode=0, pointer=True)

    def translate(self, events, *, enabled=True, cancel=True):
        """``events`` with the mouse turned into key presses (see the module); starts the
        next frame's hotspot list. ``cancel`` false: a right click is left alone."""
        pg = self.pg
        self.live, self.drawn = self.drawn, []
        out = [self._key_event(pg.KEYUP, name) for name in self._release]
        releasing, self._release = set(self._release), []
        later, self._later = self._later, []
        for name in dict.fromkeys(later):  # a second click that came while the key went up
            if name in releasing:
                self._later.append(name)  # never up and down in one frame: wait one more
            else:
                out.append(self._key_event(pg.KEYDOWN, name))
                self._release.append(name)
        if not enabled:
            self._over = None
            return out + list(events)
        for event in events:
            pressed = None
            if event.type in (pg.MOUSEMOTION, pg.MOUSEBUTTONDOWN, pg.MOUSEWHEEL):
                self.used = True
            elif event.type == pg.KEYDOWN:
                self.used = False  # back on the keyboard: the mouse hint goes away
            if event.type == pg.MOUSEMOTION:
                spot = self.at(*event.pos)
                if spot is not None and spot.pick is not None and spot.rect != self._over:
                    spot.pick()
                self._over = spot.rect if spot is not None else None
            elif event.type == pg.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
                spot = self.at(*event.pos)
                if spot is not None:
                    if spot.pick is not None:
                        spot.pick()
                    self._over = spot.rect
                    pressed = spot.key or None
                    if pressed is None:
                        continue  # the pick was the whole action
            elif event.type == pg.MOUSEBUTTONDOWN and event.button == 3 and cancel:
                pressed = "escape"
            elif event.type == pg.MOUSEWHEEL and self.live and event.y:
                pressed = "up" if event.y > 0 else "down"
            if pressed is None:
                out.append(event)
            elif pressed in releasing or pressed in self._release:
                if pressed not in self._later:  # up first, else the game sees one long press
                    self._later.append(pressed)
            else:
                out.append(self._key_event(pg.KEYDOWN, pressed))
                self._release.append(pressed)
        return out


def hand_over(runtime, spots, scale, left, top):
    """Hotspots marked on a small screen of its own (a creature screen drawn at 240 x 160 and
    scaled by whole pixels): ``[(rect, pick, key)]`` in its pixels, given to the runtime in the
    window's."""
    hotspot = getattr(runtime, "hotspot", None)
    for (x, y, w, h), pick, key in spots if hotspot is not None else ():
        hotspot((left + x * scale, top + y * scale, w * scale, h * scale), pick, key=key)


__all__ = ["Hotspot", "PointerLayer", "hand_over"]
