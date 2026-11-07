"""The scene view's tile painting: the tile, terrain, region and doodad tools, the cell under the
mouse, a stroke painted live and undone, picking tiles, and placing a character by clicking."""

from __future__ import annotations

from math import floor

from asteria.editor.scene.tile_edit import line_cells, world_to_tile
from asteria.graphics import EMPTY_TILE

try:
    from PySide6.QtCore import Qt, Signal
except ImportError:
    Qt = None
    Signal = None


class ViewportTilesMixin:
    """``SceneViewportWidget``'s tile tools, strokes, picking and character placement."""

    def set_tile_mode(self, mode):
        self.tile_tools.set_mode(mode)
        self.update()

    def set_terrain(self, terrain_id):
        self.tile_tools.terrain_id = terrain_id or None

    def set_region(self, region_id, erase=False):
        self.tile_tools.region_id = int(region_id)
        self.tile_tools.region_erase = bool(erase)
        self.update()

    def set_region_layer_name(self, layer_name):
        self.tile_tools.region_layer_name = str(layer_name or "regions")
        self.update()

    def set_doodad(self, definition):
        self.tile_tools.doodad = definition

    def set_selected_tile(self, tile_id):
        self.tile_tools.selected_tile_id = int(tile_id)

    def set_active_tile_layer(self, layer):
        if self.render_source is not None and layer not in self.render_source.tilemap.layers:
            raise ValueError("Layer does not belong to current TileMap")
        self.tile_tools.active_layer = layer
        self.update()

    def _screen_to_tile(self, x, y):
        if self.render_source is None:
            return None
        wx, wy = self.camera.screen_to_world(x, y)
        return world_to_tile(
            self.render_source.tilemap,
            wx,
            wy,
            self.render_source.origin_x,
            self.render_source.origin_y,
        )

    def cell_at_screen(self, x, y):
        """Resolve a clicked scene position into the canonical 48px RPG cell."""
        if self.render_source is not None:
            return self._screen_to_tile(x, y)
        world_x, world_y = self.camera.screen_to_world(x, y)
        return (floor(world_x / 48), floor(world_y / 48))

    def begin_character_placement(self, ghost=None):
        """Wait for a map-cell click; ``ghost`` (a QPixmap of the character) follows the mouse
        so what is about to be placed, and where, is seen before the click."""
        self.character_placement_active = True
        self._placement_ghost = ghost
        self._placement_cell = None
        self.setCursor(Qt.CrossCursor)
        self.update()

    def end_character_placement(self):
        self.character_placement_active = False
        self._placement_ghost = None
        self._placement_cell = None
        self.unsetCursor()
        self.update()

    def _tile_size(self):
        source = self.render_source
        if source is None:
            return (48, 48)
        return (int(source.tilemap.tile_width), int(source.tilemap.tile_height))

    def _append_tile_stroke(self, cell):
        if cell is None:
            return
        if self._last_tile_cell is None:
            new_cells = (cell,)
        else:
            new_cells = line_cells(*self._last_tile_cell, *cell)
        added = []
        for c in new_cells:
            if c not in self._tile_stroke_seen:
                self._tile_stroke_seen.add(c)
                self._tile_stroke_cells.append(c)
                added.append(c)
        self._last_tile_cell = cell
        self._paint_live(added)

    def _paint_live(self, cells):
        """Paint / Erase show on the map while the mouse is still down; the stroke becomes one
        undo step when it is let go (``_undo_live`` first puts the cells back)."""
        tools, source = self.tile_tools, self.render_source
        if not cells or source is None or tools.active_layer is None:
            return
        if tools.mode not in {"paint", "erase"}:
            return
        from asteria.editor.scene.tile_edit import SetTileCommand, tile_at

        try:
            wanted = tools.assignments(cells, origin=self._tile_stroke_cells[0])
        except ValueError:
            return
        live = self.__dict__.setdefault("_live_tiles", {})
        for (x, y), tile_id in wanted.items():
            if x < 0 or y < 0:
                continue
            if (x, y) not in live:
                live[(x, y)] = tile_at(source.tilemap, tools.active_layer, x, y)
            SetTileCommand(source.tilemap, tools.active_layer, x, y, int(tile_id)).redo()

    def _undo_live(self):
        from asteria.editor.scene.tile_edit import SetTileCommand

        live = self.__dict__.pop("_live_tiles", {})
        source, layer = self.render_source, self.tile_tools.active_layer
        if source is None or layer is None:
            return
        for (x, y), old in live.items():
            if layer in source.tilemap.layers:
                SetTileCommand(source.tilemap, layer, x, y, int(old)).redo()

    def _pick_tiles(self, start, end):
        """The eyedropper: the tiles of the active layer (else the topmost one that has a tile)
        between two cells become the brush."""

        from asteria.editor.scene.tile_edit import tile_at

        source = self.render_source
        if source is None or start is None or end is None:
            return None
        layers = list(source.tilemap.ordered_layers())[::-1]
        active = self.tile_tools.active_layer
        x0, x1 = sorted((start[0], end[0]))
        y0, y1 = sorted((start[1], end[1]))

        def pick(x, y):
            if active is not None and tile_at(source.tilemap, active, x, y) != EMPTY_TILE:
                return tile_at(source.tilemap, active, x, y)
            for layer in layers:
                tile = tile_at(source.tilemap, layer, x, y)
                if tile != EMPTY_TILE:
                    return tile
            return EMPTY_TILE

        rows = tuple(tuple(pick(x, y) for x in range(x0, x1 + 1)) for y in range(y0, y1 + 1))
        if all(t == EMPTY_TILE for row in rows for t in row):
            return None
        self.tile_tools.set_stamp(rows)
        if Signal is not None:
            self.tilesPicked.emit(rows)
        return rows

    def _place_doodad(self, x, y):
        from asteria.editor.scene.doodads import build_place_doodads_command

        scene = self.current_scene()
        definition = self.tile_tools.doodad
        if scene is None or definition is None:
            return
        world_x, world_y = self.camera.screen_to_world(x, y)
        try:
            self.document.execute(
                build_place_doodads_command(scene, definition, [(world_x, world_y)])
            )
        except ValueError:
            return
        window = self.window()
        if hasattr(window, "refresh_all"):
            window.refresh_all()
