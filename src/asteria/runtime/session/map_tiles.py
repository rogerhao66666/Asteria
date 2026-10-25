"""Tiles changed while playing (``SET_TILE``): a door opened, a wall broken, a box moved; and
the light of a dark place (``SET_LIGHT``): the field is dark but for a circle round the player.

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

    # -- the light of a dark place (SET_LIGHT) ------------------------------------------------
    def set_light(self, radius=None, *, speed=0.0):
        """Darken the field but for ``radius`` world units round the player (``None``: no
        darkness); ``speed`` (units a second, 0 = at once) grows or shrinks the circle there.
        It belongs to the scene it is set in (a map sets its own light as it is entered)."""
        target = None if radius is None else max(0.0, float(radius))
        current = self.light_radius()
        scene = self.scene.id  # a light belongs to its scene: another place is not dark
        if speed and current is not None:
            end = target if target is not None else 400.0  # opens to nothing, then off
            self.light = {"radius": current, "to": end, "speed": float(speed),
                          "off": target is None, "scene": scene}  # fmt: skip
        else:
            self.light = {"radius": target, "scene": scene} if target is not None else {}
        return target

    def light_radius(self):
        """The lit circle's radius now, or None when the field is not dark."""
        if self.light.get("scene") != self.scene.id:
            return None
        return self.light.get("radius")

    def light_moving(self):
        return "to" in self.light and self.light.get("scene") == self.scene.id

    def _light_frame(self, dt):
        light = self.light
        if "to" not in light:
            return
        step = light["speed"] * max(0.0, float(dt))
        radius, end = light["radius"], light["to"]
        radius = min(end, radius + step) if end >= radius else max(end, radius - step)
        if radius == end:
            self.light = {} if light.get("off") else {"radius": end, "scene": light["scene"]}
        else:
            light["radius"] = radius

    def _forget_tile_changes(self):
        """A scene loaded: the changes of the scenes left behind are gone (not the saved)."""
        for scene_id in [s for s in self._tile_changes if s != self.scene.id]:
            del self._tile_changes[scene_id]
            self.tile_changes_version += 1


__all__ = ["MapTilesMixin"]
