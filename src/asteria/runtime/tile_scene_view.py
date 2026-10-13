"""Tile-map scenes in the playable runtime (D22 A10): canonical TileMap scenes drawn with
pygame.

``TileSceneView`` loads the scene's ``TileMap2D`` binding through the project's asset records
(tile map -> tileset -> sprite sheet -> texture), pre-renders the layers below characters
(order < 100) and above them (order >= 100) once per scene, and each frame shows the camera's part
of them scaled to the screen (nearest-neighbour: pixel art stays crisp). Every entity with a
``SpriteRenderer2D`` is drawn on its feet, sorted by depth; entities with an ``Animator2D`` whose
clip set has ``idle_*`` / ``walk_*`` clips for the four facings animate from their own movement
and facing (a controller's facing when they have one), and play ``attack_<facing>`` while an
action timeline runs on them.

The view also hands the session the map's collision (``collision_enabled`` layers, the map edge
blocks) so controllers, AI and projectiles respect walls. Nothing here is tied to one game or art
style.
"""

from __future__ import annotations

from math import floor

from asteria.core import Transform

from .camera import Camera2D
from .components2d import Animator2DComponent, Camera2DComponent, SpriteRenderer2D
from .tilemap_field import AssetResources, tilemap_binding
from .tilequery import TileMapQuery

DIRECTIONS = ("down", "left", "right", "up")


class MapBlocking:
    """Tile collision plus the map's edge, as a ``collides_world_point`` query."""

    def __init__(self, query, bounds):
        self.query, self.bounds = query, bounds

    def collides_world_point(self, x, y):
        x0, y0, x1, y1 = self.bounds
        if not (x0 <= x < x1 and y0 <= y < y1):
            return True
        return self.query.collides_world_point(x, y)


class _Animated:
    """Directional idle / walk / attack clips of one entity, driven by its movement and facing."""

    def __init__(self, clips):
        self.clips = clips
        self.clip = None
        self.time = 0.0
        self.last = None
        self.facing = "down"

    def update(self, dt, position, facing, attacking):
        moved = self.last is not None and (
            abs(position[0] - self.last[0]) + abs(position[1] - self.last[1]) > 1e-3
        )
        self.last = position
        if facing:
            self.facing = facing
        name = f"walk_{self.facing}" if moved else f"idle_{self.facing}"
        if attacking and f"attack_{self.facing}" in self.clips.clips:
            name = f"attack_{self.facing}"
        if name != self.clip:
            self.clip, self.time = name, 0.0
        else:
            self.time += dt

    def frame(self):
        clip = self.clips.clips.get(self.clip)
        if clip is None or not clip.keyframes:
            return None
        total = sum(k.duration for k in clip.keyframes) or 1.0
        t = self.time % total if clip.loop else min(self.time, total - 1e-6)
        for key in clip.keyframes:
            if t < key.duration:
                return key.frame_index
            t -= key.duration
        return clip.keyframes[-1].frame_index


class TileSceneView:
    def __init__(self, session, root, width, height, pygame):
        self.session = session
        self.pg = pygame
        self.resources = AssetResources(session.project, root)
        self.width, self.height = int(width), int(height)
        self.scene_id = None
        self._textures = {}
        self._frames = {}
        self._animated = {}
        self.load()

    # -- loading ---------------------------------------------------------------------------------
    @staticmethod
    def available(scene):
        return tilemap_binding(scene) is not None

    def _texture(self, asset_id):
        surface = self._textures.get(asset_id)
        if surface is None:
            path = self.resources.path(asset_id, "texture")
            surface = self._textures[asset_id] = self.pg.image.load(str(path)).convert_alpha()
        return surface

    def load(self):
        scene = self.session.scene
        binding = tilemap_binding(scene)
        self.scene_id = scene.id
        self.tilemap = self.resources.get(binding.tilemap_asset_id, "tilemap")
        self.tileset = self.resources.get(self.tilemap.tileset.asset_id, "tileset")
        self.tile_sheet = self.resources.get(self.tileset.sprite_sheet.asset_id, "sprite_sheet")
        tw, th = self.tilemap.tile_width, self.tilemap.tile_height
        cells = [
            (c.chunk_x * self.tilemap.chunk_width + x, c.chunk_y * self.tilemap.chunk_height + y)
            for layer in self.tilemap.layers
            for c in layer.chunks.values()
            for y in range(c.height)
            for x in range(c.width)
            if c.get(x, y) != -1
        ]
        columns = max((x for x, _ in cells), default=0) + 1
        rows = max((y for _, y in cells), default=0) + 1
        self.bounds = (0.0, 0.0, float(columns * tw), float(rows * th))
        self.blocking = MapBlocking(TileMapQuery(self.tilemap), self.bounds)
        self.session.set_tile_blocking(self.blocking)
        texture = self._texture(self.tile_sheet.texture.asset_id)
        self.below = self.pg.Surface((columns * tw, rows * th), self.pg.SRCALPHA)
        self.above = self.pg.Surface((columns * tw, rows * th), self.pg.SRCALPHA)
        for layer in self.tilemap.ordered_layers():
            if not layer.visible:
                continue
            target = self.above if layer.order >= 100 else self.below
            for chunk in layer.chunks.values():
                for y in range(chunk.height):
                    for x in range(chunk.width):
                        tile_id = chunk.get(x, y)
                        if tile_id == -1 or tile_id not in self.tileset.tiles:
                            continue
                        frame = self.tile_sheet.frames[self.tileset.tiles[tile_id].frame_index]
                        area = self.pg.Rect(frame.x, frame.y, frame.width, frame.height)
                        gx = (chunk.chunk_x * self.tilemap.chunk_width + x) * tw
                        gy = (chunk.chunk_y * self.tilemap.chunk_height + y) * th
                        target.blit(texture, (gx, gy), area)
        zoom = 3.0
        for entity in scene.entities():
            spec = entity.try_get(Camera2DComponent)
            if spec is not None and spec.active:
                zoom = spec.zoom
        self.camera = Camera2D(width=self.width, height=self.height, zoom=zoom)
        self._animated = {}
        self.follow(0.0)

    # -- camera ----------------------------------------------------------------------------------
    def follow(self, dt):
        t = self.session.player.get(Transform)
        view_w, view_h = self.width / self.camera.zoom, self.height / self.camera.zoom
        x0, y0, x1, y1 = self.bounds
        want_x, want_y = t.x - view_w / 2, t.y - view_h / 2
        if x1 - x0 > view_w:
            want_x = min(max(want_x, x0), x1 - view_w)
        else:
            want_x = x0 - (view_w - (x1 - x0)) / 2
        if y1 - y0 > view_h:
            want_y = min(max(want_y, y0), y1 - view_h)
        else:
            want_y = y0 - (view_h - (y1 - y0)) / 2
        if dt <= 0:
            self.camera.x, self.camera.y = want_x, want_y
        else:
            k = min(1.0, dt * 10.0)
            self.camera.x += (want_x - self.camera.x) * k
            self.camera.y += (want_y - self.camera.y) * k

    def world_to_screen(self, x, y):
        return self.camera.world_to_screen(x, y)

    # -- frame -----------------------------------------------------------------------------------
    def update(self, dt):
        if self.session.scene.id != self.scene_id and self.available(self.session.scene):
            self.load()
        actions = getattr(self.session, "entity_actions", None)
        running = actions.running if actions is not None else {}
        from .character_control import CharacterController2DComponent

        for entity in self.session.scene.entities():
            animator = entity.try_get(Animator2DComponent)
            if animator is None or not animator.clip_set_id or not entity.has(Transform):
                continue
            state = self._animated.get(entity.id)
            if state is None:
                try:
                    clips = self.resources.get(animator.clip_set_id, "animation")
                except Exception:  # noqa: BLE001 - an entity whose clips do not resolve stays static
                    self._animated[entity.id] = False
                    continue
                needed = [f"{kind}_{d}" for kind in ("idle", "walk") for d in DIRECTIONS]
                ok = all(n in clips.clips for n in needed)
                state = self._animated[entity.id] = _Animated(clips) if ok else False
            if not state:
                continue
            controller = entity.try_get(CharacterController2DComponent)
            facing = controller.facing if controller is not None else None
            if entity is self.session.player and controller is None:
                facing = self.session.facing
            t = entity.get(Transform)
            state.update(dt, (t.x, t.y), facing, entity.id in running)
        self.follow(dt)

    def _sprite(self, sheet_id, frame_index, scale):
        key = (sheet_id, frame_index, scale)
        image = self._frames.get(key)
        if image is None:
            sheet = self.resources.get(sheet_id, "sprite_sheet")
            frame = sheet.frames[frame_index]
            source = self._texture(sheet.texture.asset_id).subsurface(
                (frame.x, frame.y, frame.width, frame.height)
            )
            size = (max(1, round(frame.width * scale)), max(1, round(frame.height * scale)))
            image = self.pg.transform.scale(source, size)
            self._frames[key] = (image, frame.pivot_x, frame.pivot_y)
            image = self._frames[key]
        return image

    def projectile_image(self, definition, vx, vy):
        """A projectile's sprite (its ``sprite`` names a sprite sheet: frame 0) at this zoom,
        turned to its velocity when ``align_to_velocity``; None when it cannot be loaded."""
        from math import atan2, degrees

        try:
            image, _, _ = self._sprite(definition.sprite, 0, self.camera.zoom)
        except Exception:  # noqa: BLE001 - an unknown sprite falls back to the plain marker
            return None
        if not definition.align_to_velocity or not (vx or vy):
            return image
        # sprites are drawn pointing right; screen y grows downwards
        angle = round(-degrees(atan2(vy, vx)) / 15) * 15
        key = ("turned", definition.sprite, angle, self.camera.zoom)
        turned = self._frames.get(key)
        if turned is None:
            turned = self._frames[key] = self.pg.transform.rotate(image, angle)
        return turned

    def _layer(self, screen, surface):
        cam = self.camera
        view_w, view_h = self.width / cam.zoom, self.height / cam.zoom
        x0, y0 = floor(cam.x), floor(cam.y)
        w, h = int(view_w) + 2, int(view_h) + 2
        area = self.pg.Rect(x0, y0, w, h).clip(surface.get_rect())
        if area.width <= 0 or area.height <= 0:
            return
        part = surface.subsurface(area)
        size = (round(area.width * cam.zoom), round(area.height * cam.zoom))
        sx, sy = cam.world_to_screen(area.x, area.y)
        screen.blit(self.pg.transform.scale(part, size), (round(sx), round(sy)))

    def draw(self, screen, flash=()):
        """Layers below characters, the sprites (depth-sorted, on their feet), layers above."""
        settings = getattr(self.session, "combat_scene", None)
        color = getattr(settings, "background_color", "") or "#0c0e14"
        screen.fill(tuple(int(color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)))
        self._layer(screen, self.below)
        sprites = []
        for entity in self.session.scene.entities():
            if not entity.enabled:
                continue
            sprite = entity.try_get(SpriteRenderer2D)
            t = entity.try_get(Transform)
            if (
                sprite is None
                or t is None
                or not sprite.sprite_sheet_asset_id
                or not sprite.visible
            ):
                continue
            state = self._animated.get(entity.id)
            frame = state.frame() if state else None
            if frame is None:
                frame = sprite.frame_index
            sprites.append((t.y, entity, sprite, frame))
        sprites.sort(key=lambda row: row[0])
        for _, entity, sprite, frame in sprites:
            try:
                image, px, py = self._sprite(sprite.sprite_sheet_asset_id, frame, self.camera.zoom)
            except Exception:  # noqa: BLE001 - a missing frame is skipped, the scene keeps drawing
                continue
            t = entity.get(Transform)
            sx, sy = self.camera.world_to_screen(t.x, t.y)
            if sprite.flip_x:
                image = self.pg.transform.flip(image, True, False)
            if entity.id in flash:
                image = image.copy()
                image.fill((120, 120, 120, 0), special_flags=self.pg.BLEND_RGB_ADD)
            screen.blit(
                image, (round(sx - image.get_width() * px), round(sy - image.get_height() * py))
            )
        self._layer(screen, self.above)


__all__ = ["MapBlocking", "TileSceneView"]
