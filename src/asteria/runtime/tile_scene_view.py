"""Tile-map scenes in the playable runtime (D22 A10): canonical TileMap scenes drawn with
pygame.

``TileSceneView`` loads the scene's ``TileMap2D`` binding through the project's asset records
(tile map -> tileset -> sprite sheet -> texture). The layers below characters (order < 100) and
above them (order >= 100) are drawn chunk by chunk: a chunk is rendered the first time it is seen
and kept in a bounded cache, so a map of any size costs only what the camera can see. Each frame
shows the camera's part of them scaled to the screen (nearest-neighbour: pixel art stays
crisp). Every entity with a
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
from .components2d import (
    Animator2DComponent,
    Camera2DComponent,
    ParallaxBackground2DComponent,
    SpriteRenderer2D,
)
from .skeleton_component import SkeletonAnimation2DComponent, SkeletonSceneRuntime
from .tilemap_field import AssetResources, tilemap_binding
from .tilequery import TileMapQuery

DIRECTIONS = ("down", "left", "right", "up")
CHUNK_CACHE = 192  # chunks kept rendered (about 50 MB of 16 x 16 tile chunks of 16 px tiles)


class MapBlocking:
    """Tile collision plus the map's edge, as a ``collides_world_point`` query. The collision
    layers are picked once; a point test is a few dictionary lookups."""

    def __init__(self, query, bounds):
        self.query, self.bounds = query, bounds
        self._layers = [
            layer for layer in query.tilemap.ordered_layers() if layer.collision_enabled
        ]
        tilemap = query.tilemap
        self._tile = (tilemap.tile_width, tilemap.tile_height)
        self._chunk = (tilemap.chunk_width, tilemap.chunk_height)

    def collides_world_point(self, x, y):
        x0, y0, x1, y1 = self.bounds
        if not (x0 <= x < x1 and y0 <= y < y1):
            return True
        tx, ty = floor(x / self._tile[0]), floor(y / self._tile[1])
        cx, cy = tx // self._chunk[0], ty // self._chunk[1]
        index = (ty - cy * self._chunk[1]) * self._chunk[0] + (tx - cx * self._chunk[0])
        for layer in self._layers:
            chunk = layer.chunks.get((cx, cy))
            if chunk is not None and chunk.tiles[index] != -1:
                return True
        return False


class _Animated:
    """Directional idle / walk / attack clips of one entity, driven by its movement and facing."""

    def __init__(self, clips, clip_set_id=""):
        self.clips = clips
        self.clip_set_id = clip_set_id
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
        self._skeleton_runtime = SkeletonSceneRuntime()
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
        cw, ch = self.tilemap.chunk_width, self.tilemap.chunk_height
        # the map's extent: the last tile that holds anything, by chunk (no per-cell scan of a
        # whole big map)
        columns = rows = 0
        for layer in self.tilemap.layers:
            for chunk in layer.chunks.values():
                if all(t == -1 for t in chunk.tiles):
                    continue
                for y in range(chunk.height - 1, -1, -1):
                    row = chunk.tiles[y * chunk.width : (y + 1) * chunk.width]
                    if any(t != -1 for t in row):
                        rows = max(rows, chunk.chunk_y * ch + y + 1)
                        columns = max(
                            columns,
                            chunk.chunk_x * cw + max(x for x, t in enumerate(row) if t != -1) + 1,
                        )
                        break
                for x in range(chunk.width - 1, -1, -1):
                    if any(chunk.tiles[y * chunk.width + x] != -1 for y in range(chunk.height)):
                        columns = max(columns, chunk.chunk_x * cw + x + 1)
                        break
        self.bounds = (0.0, 0.0, float(columns * tw), float(rows * th))
        self.blocking = MapBlocking(TileMapQuery(self.tilemap), self.bounds)
        self.session.set_tile_blocking(self.blocking)
        # the project's map areas (floor damage, regions, stealth...) read this map's tiles
        from .map_rules_field import tile_area_keys

        sets = self.session.project.rpg_database.map_rule_sets
        layer = sets[sorted(sets)[0]].region_layer if sets else "regions"
        self.session.bind_map_rules(tile_area_keys(self.tilemap, self.tileset, layer))
        self._texture_surface = self._texture(self.tile_sheet.texture.asset_id)
        self._frame_rects = {}
        self._chunk_cache = {}  # (group, chunk_x, chunk_y) -> Surface | None, least recent first
        self._canvas = {}
        self._groups = {
            "below": [
                layer
                for layer in self.tilemap.ordered_layers()
                if layer.visible and layer.order < 100
            ],
            "above": [
                layer
                for layer in self.tilemap.ordered_layers()
                if layer.visible and layer.order >= 100
            ],
        }
        zoom = 3.0
        for entity in scene.entities():
            spec = entity.try_get(Camera2DComponent)
            if spec is not None and spec.active:
                zoom = spec.zoom
        self.camera = Camera2D(width=self.width, height=self.height, zoom=zoom)
        self._animated = {}
        self._ahead = (0.0, 0.0)  # the camera's look-ahead offset (CombatScene.camera_look_ahead)
        self.follow(0.0)

    # -- camera ----------------------------------------------------------------------------------
    def follow(self, dt):
        t = self.session.player.get(Transform)
        view_w, view_h = self.width / self.camera.zoom, self.height / self.camera.zoom
        x0, y0, x1, y1 = self.bounds
        want_x = t.x + self._ahead[0] - view_w / 2
        want_y = t.y + self._ahead[1] - view_h / 2
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

        self._apply_class_looks()
        self._look_ahead(dt)
        self._skeleton_runtime.update(self.session.scene, dt)
        for entity in self.session.scene.entities():
            animator = entity.try_get(Animator2DComponent)
            if animator is None or not animator.clip_set_id or not entity.has(Transform):
                continue
            state = self._animated.get(entity.id)
            if state and state.clip_set_id != animator.clip_set_id:
                state = None  # its animation set changed (a new class): load the new one
            if state is None:
                try:
                    clips = self.resources.get(animator.clip_set_id, "animation")
                except Exception:  # noqa: BLE001 - an entity whose clips do not resolve stays static
                    self._animated[entity.id] = False
                    continue
                needed = [f"{kind}_{d}" for kind in ("idle", "walk") for d in DIRECTIONS]
                ok = all(n in clips.clips for n in needed)
                state = self._animated[entity.id] = (
                    _Animated(clips, animator.clip_set_id) if ok else False
                )
            if not state:
                continue
            controller = entity.try_get(CharacterController2DComponent)
            facing = controller.facing if controller is not None else None
            if entity is self.session.player and controller is None:
                facing = self.session.facing
            t = entity.get(Transform)
            state.update(dt, (t.x, t.y), facing, entity.id in running)
        self.follow(dt)

    def _look_ahead(self, dt):
        """Ease the camera toward the way the player faces by ``camera_look_ahead`` world units
        (a CombatScene setting; 0 = centred on the player)."""
        from .character_control import CharacterController2DComponent

        settings = getattr(self.session, "combat_scene", None)
        amount = float(getattr(settings, "camera_look_ahead", 0.0) or 0.0)
        controller = self.session.player.try_get(CharacterController2DComponent)
        direction = {"down": (0, 1), "up": (0, -1), "left": (-1, 0), "right": (1, 0)}.get(
            controller.facing if controller is not None else "", (0, 0)
        )
        if controller is not None and controller.mode == "side":
            direction = (direction[0], 0)  # a platformer looks ahead sideways only
        goal = (direction[0] * amount, direction[1] * amount)
        k = min(1.0, dt * 3.0)
        self._ahead = (
            self._ahead[0] + (goal[0] - self._ahead[0]) * k,
            self._ahead[1] + (goal[1] - self._ahead[1]) * k,
        )

    def _apply_class_looks(self):
        """Entities with ``ClassAppearance`` show the look of their actor's active class."""
        from .actor_link import ClassAppearanceComponent

        session = self.session
        for entity, spec in session.scene.query(ClassAppearanceComponent):
            actor_id = session._actor_of(entity)
            sprite = entity.try_get(SpriteRenderer2D)
            if actor_id is None or sprite is None:
                continue
            looks = spec.parsed()
            classes = session.ensure_actor_progression(actor_id).active_class_ids
            chosen = next((looks[c] for c in reversed(classes) if c in looks), None)
            if chosen is None:
                continue
            sprite.sprite_sheet_asset_id = chosen[0]
            animator = entity.try_get(Animator2DComponent)
            if animator is not None and chosen[1]:
                animator.clip_set_id = chosen[1]

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

    def _parallax(self, screen):
        """Scrolling backdrops (``ParallaxBackground2D``), far to near, below the tile layers."""
        cam = self.camera
        rows = [
            spec
            for _, spec in self.session.scene.query(ParallaxBackground2DComponent)
            if spec.visible and spec.texture_asset_id
        ]
        for spec in sorted(rows, key=lambda r: r.factor_x):
            key = (spec.texture_asset_id, spec.scale, cam.zoom)
            image = self._frames.get(key)
            if image is None:
                try:
                    source = self._texture(spec.texture_asset_id)
                except Exception:  # noqa: BLE001 - a missing backdrop is skipped
                    self._frames[key] = False
                    continue
                size = (
                    max(1, round(source.get_width() * spec.scale * cam.zoom)),
                    max(1, round(source.get_height() * spec.scale * cam.zoom)),
                )
                image = self._frames[key] = self.pg.transform.scale(source, size)
            if image is False:
                continue
            w, h = image.get_size()
            if spec.anchor == "top":
                y = 0
            elif spec.anchor == "center":
                y = (self.height - h) // 2
            else:
                y = self.height - h
            y = round(y + spec.offset_y * cam.zoom - cam.y * spec.factor_y * cam.zoom)
            shift = -cam.x * spec.factor_x * cam.zoom
            if spec.opacity < 1.0:
                image = image.copy()
                image.set_alpha(int(spec.opacity * 255))
            if spec.repeat_x:
                x = shift % w - w
                while x < self.width:
                    screen.blit(image, (round(x), y))
                    x += w
            else:
                screen.blit(image, (round(shift), y))

    def effect_frame_count(self, sheet_id):
        """How many frames an effect sheet has (0 when it cannot be loaded)."""
        try:
            return len(self.resources.get(sheet_id, "sprite_sheet").frames)
        except Exception:  # noqa: BLE001 - an unknown effect plays nothing
            return 0

    def effect_image(self, sheet_id, frame, scale=1.0, angle=0):
        """One frame of an effect sheet at this zoom (times ``scale``), turned by ``angle``
        degrees (steps of 15), or None."""
        try:
            image, _, _ = self._sprite(sheet_id, int(frame), self.camera.zoom * float(scale))
        except Exception:  # noqa: BLE001
            return None
        angle = round(angle / 15) * 15
        if not angle:
            return image
        key = ("effect-turned", sheet_id, int(frame), float(scale), angle, self.camera.zoom)
        turned = self._frames.get(key)
        if turned is None:
            turned = self._frames[key] = self.pg.transform.rotate(image, angle)
        return turned

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

    def _tile_rect(self, tile_id):
        rect = self._frame_rects.get(tile_id)
        if rect is None:
            definition = self.tileset.tiles.get(tile_id)
            if definition is None:
                rect = False
            else:
                frame = self.tile_sheet.frames[definition.frame_index]
                rect = self.pg.Rect(frame.x, frame.y, frame.width, frame.height)
            self._frame_rects[tile_id] = rect
        return rect

    def _chunk_surface(self, group, cx, cy):
        """The pixels of one chunk of a layer group (None when it holds nothing); kept in a
        bounded least-recently-used cache."""
        key = (group, cx, cy)
        cache = self._chunk_cache
        if key in cache:
            surface = cache.pop(key)
            cache[key] = surface  # most recent last
            return surface
        tw, th = self.tilemap.tile_width, self.tilemap.tile_height
        cw, ch = self.tilemap.chunk_width, self.tilemap.chunk_height
        surface = None
        for layer in self._groups[group]:
            chunk = layer.chunks.get((cx, cy))
            if chunk is None:
                continue
            for y in range(chunk.height):
                for x in range(chunk.width):
                    rect = self._tile_rect(chunk.tiles[y * chunk.width + x])
                    if rect:
                        if surface is None:
                            surface = self.pg.Surface((cw * tw, ch * th), self.pg.SRCALPHA)
                        surface.blit(self._texture_surface, (x * tw, y * th), rect)
        cache[key] = surface
        while len(cache) > CHUNK_CACHE:
            cache.pop(next(iter(cache)))
        return surface

    def _layer(self, screen, group):
        cam = self.camera
        tw, th = self.tilemap.tile_width, self.tilemap.tile_height
        cwp, chp = self.tilemap.chunk_width * tw, self.tilemap.chunk_height * th
        view_w, view_h = self.width / cam.zoom, self.height / cam.zoom
        x0, y0 = floor(cam.x), floor(cam.y)
        w, h = int(view_w) + 2, int(view_h) + 2
        canvas = self._canvas.get((w, h))
        if canvas is None:
            canvas = self._canvas[(w, h)] = self.pg.Surface((w, h), self.pg.SRCALPHA)
        canvas.fill((0, 0, 0, 0))
        drawn = False
        for cy in range(floor(y0 / chp), floor((y0 + h) / chp) + 1):
            for cx in range(floor(x0 / cwp), floor((x0 + w) / cwp) + 1):
                chunk = self._chunk_surface(group, cx, cy)
                if chunk is not None:
                    canvas.blit(chunk, (cx * cwp - x0, cy * chp - y0))
                    drawn = True
        if not drawn:
            return
        size = (round(w * cam.zoom), round(h * cam.zoom))
        sx, sy = cam.world_to_screen(x0, y0)
        screen.blit(self.pg.transform.scale(canvas, size), (round(sx), round(sy)))

    def draw(self, screen, flash=()):
        """Layers below characters, the sprites (depth-sorted, on their feet), layers above."""
        settings = getattr(self.session, "combat_scene", None)
        color = getattr(settings, "background_color", "") or "#0c0e14"
        screen.fill(tuple(int(color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)))
        self._parallax(screen)
        self._layer(screen, "below")
        sprites = []
        for entity in self.session.scene.entities():
            if not entity.enabled:
                continue
            sprite = entity.try_get(SpriteRenderer2D)
            skeleton = entity.try_get(SkeletonAnimation2DComponent)
            t = entity.try_get(Transform)
            if t is None:
                continue
            if sprite is not None and sprite.sprite_sheet_asset_id and sprite.visible:
                state = self._animated.get(entity.id)
                frame = state.frame() if state else None
                if frame is None:
                    frame = sprite.frame_index
                sprites.append((t.y, 0, entity, sprite, frame, ()))
            if skeleton is not None and skeleton.visible:
                rig_draws = self._skeleton_runtime.draw_entity(
                    entity,
                    self.camera,
                    lambda asset_id: self.resources.get(asset_id, "sprite_sheet"),
                )
                if rig_draws:
                    sprites.append((t.y, 1, entity, None, None, rig_draws))
        sprites.sort(key=lambda row: (row[0], row[1]))
        for _, _, entity, sprite, frame, rig_draws in sprites:
            if sprite is None:
                for draw in rig_draws:
                    try:
                        self._draw_skeleton_texture(screen, draw)
                    except (KeyError, OSError, RuntimeError, TypeError, ValueError, self.pg.error):
                        continue
                continue
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
        self._layer(screen, "above")

    def _draw_skeleton_texture(self, screen, draw):
        """Draw a skeletal slot with the same pivot and rotation as TextureDraw."""
        image = self._texture(draw.texture_asset_id).subsurface(self.pg.Rect(draw.source))
        size = (max(1, round(draw.width)), max(1, round(draw.height)))
        image = self.pg.transform.scale(image, size)
        if draw.flip_x:
            image = self.pg.transform.flip(image, True, False)
        center = (
            round(draw.screen_x + draw.width / 2),
            round(draw.screen_y + draw.height / 2),
        )
        if draw.rotation_deg:
            image = self.pg.transform.rotate(image, -draw.rotation_deg)
        if draw.opacity < 1:
            image = image.copy()
            image.set_alpha(round(255 * draw.opacity))
        screen.blit(image, image.get_rect(center=center))


__all__ = ["MapBlocking", "TileSceneView"]
