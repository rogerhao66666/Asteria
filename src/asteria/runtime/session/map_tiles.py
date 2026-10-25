"""Tiles changed while playing (``SET_TILE``): a door opened, a wall broken, a box moved.

A change lasts until the player leaves the scene (a map's own entering script sets it again,
as the GBA games do), or for good with ``permanent`` (kept in the save, ``world.systems``
under ``tiles.<scene id>``). The field view draws the changed cells and walks by them: a
changed cell of a collision layer opens or closes it."""

from __future__ import annotations

from .support import GameSessionError


class MapTilesMixin:
    TILES_SYSTEM = "tiles."

    def set_tile(self, layer, x, y, tile, *, permanent=False):
        """Put ``tile`` (a tileset tile id, -1 for none) in cell ``(x, y)`` of ``layer`` (its
        name) of the current scene's tile map."""
        layer, x, y, tile = str(layer), int(x), int(y), int(tile)
        if not layer:
            raise GameSessionError("SET_TILE needs a layer")
        key = f"{layer}|{x}|{y}"
        scene_id = self.scene.id
        self._tile_changes.setdefault(scene_id, {})[key] = tile
        if permanent:
            kept = self.world.systems.setdefault(self.TILES_SYSTEM + scene_id, {})
            kept[key] = tile
        self.tile_changes_version += 1
        return tile

    def tile_changes(self, scene_id=None):
        """``{(layer, x, y): tile}`` changed in a scene: the saved ones, then this visit's."""
        scene_id = self.scene.id if scene_id is None else str(scene_id)
        merged = dict(self.world.systems.get(self.TILES_SYSTEM + scene_id, {}))
        merged.update(self._tile_changes.get(scene_id, {}))
        changes = {}
        for key, tile in merged.items():
            layer, x, y = key.rsplit("|", 2)
            changes[(layer, int(x), int(y))] = int(tile)
        return changes

    def _forget_tile_changes(self):
        """A scene loaded: the changes of the scenes left behind are gone (not the saved)."""
        for scene_id in [s for s in self._tile_changes if s != self.scene.id]:
            del self._tile_changes[scene_id]
            self.tile_changes_version += 1


__all__ = ["MapTilesMixin"]
