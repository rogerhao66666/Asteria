"""Heights on a grid map: who may step where, and who is drawn over the tiles above people.

A tile says what it is with Properties (tags), usually on a hidden layer:

* ``height_<n>``: this cell is at height ``n``. Height 0 lets anybody on and off it (stairs).
  A cell with no such tag is a crossing: anybody may enter it, and whoever does keeps the height
  they had (the ends of a bridge).
* ``block_down`` / ``block_up`` / ``block_left`` / ``block_right``: nobody leaves this cell that
  way, and nobody enters it going the opposite way (a fence along one edge of a cell).

Somebody at height ``h`` (not 0) cannot step onto a cell of another height other than 0. Two
people at different heights do not bump into each other or talk: one walks under the other's
bridge. ``field.height_over`` lists the heights at which people are drawn over the map's layers
above people (on the bridge) instead of under them.
"""

from __future__ import annotations

HEIGHT_TAG = "tag:height_"
BLOCK_TAG = "tag:block_"
OPPOSITE = {"down": "up", "up": "down", "left": "right", "right": "left"}


def compatible(first, second):
    """Whether people at these two heights can meet (height 0 meets everybody)."""
    return not first or not second or first == second


class GridHeights:
    def __init__(self, keys_at, *, size=16.0, over=()):
        self.keys_at = keys_at
        self.size = float(size)
        self.over = frozenset(int(height) for height in over or ())

    def centre(self, cell):
        return ((cell[0] + 0.5) * self.size, (cell[1] + 0.5) * self.size)

    def cell_of(self, x, y):
        return (int(x // self.size), int(y // self.size))

    def height_at(self, cell):
        """The height of a cell, or None on a crossing (no height tag)."""
        for key in self.keys_at(*self.centre(cell)):
            if key.startswith(HEIGHT_TAG):
                try:
                    return int(key[len(HEIGHT_TAG) :])
                except ValueError:
                    continue
        return None

    def _edge(self, cell, way):
        return f"{BLOCK_TAG}{way}" in self.keys_at(*self.centre(cell))

    def stopped(self, start, cell, height):
        """Whether somebody at ``height`` cannot step from cell ``start`` to ``cell``."""
        dx, dy = cell[0] - start[0], cell[1] - start[1]
        if abs(dx) > abs(dy):
            way = "right" if dx > 0 else "left"
        else:
            way = "down" if dy > 0 else "up"
        if self._edge(start, way) or self._edge(cell, OPPOSITE[way]):
            return True
        there = self.height_at(cell)
        return there is not None and not compatible(height, there)

    def stepped(self, start, cell, height, drawn):
        """``(height, drawn)`` after a step: a crossing at either end keeps them; ``drawn`` is
        the last height that was not 0, which decides how the person is drawn."""
        was, there = self.height_at(start), self.height_at(cell)
        if was is None or there is None:
            return height, drawn
        return there, there or drawn

    def placed(self, cell, height=0):
        """``(height, drawn)`` of somebody put on a cell (``height``: what they had before)."""
        there = self.height_at(cell)
        if there is None:
            return height, height
        return there, there


__all__ = ["BLOCK_TAG", "HEIGHT_TAG", "GridHeights", "compatible"]
